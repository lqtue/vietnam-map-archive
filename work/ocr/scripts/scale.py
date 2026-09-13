"""Sheet scale from a map's own georeference — metres per source pixel.

Why this exists: tile size is a *ground-distance* decision (`docs/pipelines.md`
§ Getting more out of OCR, step 3 — "ground per call is still the biggest single
lever"), and until now nothing on the Python side could see the ground. Every
tile size in the corpus was chosen by hand, per sheet, from a number someone
worked out once and wrote in a commit message.

The input was already on disk. `iiif_tiles.get_iiif_base_from_allmaps` fetches
the Allmaps annotation and reads exactly one field out of it
(`target.source.id`), discarding the 10-15 ground control points sitting beside
it. Those are the scale:

    items[0].body.features[].properties.resourceCoords   # source pixels
    items[0].body.features[].geometry.coordinates        # lng, lat
    items[0].body.transformation.type                    # helmert | polynomial | …

`helmert` is a similarity transform — uniform scale, one rotation — so a single
metres-per-pixel figure is exact for the whole sheet by construction. A
`polynomial` or `thinPlateSpline` fit varies across the sheet; measured on this
corpus it barely does (1959 is polynomial and comes out 0.2% anisotropic), so
one number is still the right answer here. `ScaleFit.anisotropy` is what says
whether to trust it, and `metres_per_pixel` refuses rather than guesses when
there are too few points to fit.

Verified against the three sheets whose tile size was picked by hand:

    1882 cadastral   10 gcps  helmert     0.343 m/px   1.0% anisotropic
    1959 Sài Gòn     10 gcps  polynomial  0.999 m/px   0.2%
    1968 Sài Gòn     15 gcps  helmert     1.273 m/px   0.0%

Pure functions plus one `requests.get`; no Supabase, no model calls. Self-check
at the bottom: `python work/ocr/scripts/scale.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

# WGS84 local approximations. Accuracy needed here is ~1% — the number feeds a
# tile size that is then snapped to a whole grid, so a metre either way is
# invisible. Do not reach for pyproj on this account.
METRES_PER_DEG_LAT = 111_132.95
METRES_PER_DEG_LON_EQUATOR = 111_320.0

# Ground per call, in metres. 1400 is measured, not chosen: at the old 2400 px
# default the 1959 sheet was 5.7 km per call and returned ~1 usable label in the
# study area, and 1400 m returned 627 rows from the same crop.
DEFAULT_TILE_METRES = 1400.0

# Render width is NOT a resolution knob, and this constant is a cost cap rather
# than a quality target. Measured on the 1882 gate sheet (2026-09-10): a 2400 px
# frame and a 1024 px frame of the same tile cost the same ~1032 input tokens,
# because the API normalises an image to its own patch budget before the model
# sees it — 1032 tokens is four 768 px patches, so the effective ceiling is
# around 1536 px (that last step is inferred from the token count, not measured
# directly). Above it the extra bytes buy nothing: same tokens, same score
# (matched 71 -> 73, text_recall 0.906 -> 0.878, a wash), 13% more wall clock.
#
# The consequence is the useful part. If the frame is normalised to a fixed
# budget whatever its pixel size, then the only thing that sets how much detail
# reaches the model is how much *ground* is inside the frame — which is exactly
# `DEFAULT_TILE_METRES` above, and why tile size is the lever the docs say it
# is. It also means no flag can rescue a coarse scan: the 1968 sheet holds
# 1.273 m of ground in every source pixel, so at any tile size its glyphs
# arrive softer than the 1959 sheet's. That one needs a rescan, not a run.
MAX_RENDER_SIZE = 1536

# A label lying across a tile boundary has to be whole in *one* frame or the
# join has to rescue it, and the join is measured not to (EVAL-BASELINE.md, "the
# fragment join is not a lever"). Both scored runs sat at 0.20-0.25.
DEFAULT_OVERLAP_RATIO = 0.25

# Three points determine an affine exactly, and thirteen sheets in this corpus
# carry exactly three — a whole cohort, mostly the Huế and Cochinchine plans.
# Requiring four excluded all of them for nothing. What three points cannot
# survive is being nearly collinear, so that is guarded separately below rather
# than by demanding more points than the sheet has.
MIN_GCPS = 3

# Smallest-to-largest singular value of the centred pixel coordinates. Below
# this the control points lie close to a line, the second axis of the fit is
# noise, and the scale it reports is whatever the residuals happened to say.
MIN_GCP_CONDITION = 0.05

# Floor on a tile, in pixels. Not a resolution limit — a value-per-call one: the
# API normalises a frame to roughly 1536 px of patches (see MAX_RENDER_SIZE), so
# a 300 px tile pays for a whole call and fills a fifth of the budget it bought.
# The regional sheets are what this is for: the 1930 Giadinh survey is 8.5 m in
# every pixel, and 1400 m of ground there is a 167 px tile — 8,175 calls to read
# a road map whose labels are towns. A sheet that hits the floor wants a larger
# --tile-metres, and `TileFit.holds_target` is how the caller knows.
MIN_TILE_PX = 640

# Anisotropy over this and the sheet is not uniformly scaled — a strongly
# warped polynomial fit, or GCPs concentrated in one corner. The caller should
# fall back to an explicit --tile-size and say so.
ANISOTROPY_LIMIT = 0.05

# Above this many metres in every source pixel, no flag rescues the sheet. The
# frame is normalised to a fixed patch budget (see MAX_RENDER_SIZE), so the ink
# per metre in the *scan* is the ceiling, and 1.1 is where the corpus turns:
# 1959 at 0.999 m/px reads 0.712 of its printed names in one pass, 1968 at
# 1.273 reads 0.327. Two points, so treat it as a flag to raise at triage —
# "this needs a better scan" — not as a refusal.
#
# **Both of those points are large-scale city plans (1:4,000–1:12,500), and the
# threshold does not transfer to a small-scale sheet.** What sets recall is
# ground per printed *name*, not ground per pixel, and those move in opposite
# directions with scale: a street name on a city plan spans tens of metres, a
# village name on a 1:25,000 topographic sheet spans hundreds, so the same m/px
# leaves the second one several times taller in pixels. Measured 2026-09-13 on
# An Thi (Indochine 1:25,000, 5089×3615, 4.26 m/px — nearly 4× this line):
# **272 unique extractions in a single pass**, 222 of them places, 216 carrying
# correct Vietnamese diacritics. That is between the 1882 cadastral's 499 over
# two passes and the 1968 sheet's 392. The flag fires on 95 of 109 georeferenced
# sheets, so it separates almost nothing on its own; read it next to the map's
# scale, and prefer `TileFit.metres_per_tile` against a ground target, which is
# the number the tiling experiment actually moved recall with.
COARSE_SCAN_METRES_PER_PX = 1.1


@dataclass(frozen=True)
class ScaleFit:
    """Metres per source pixel, along each image axis."""

    mx: float
    my: float
    n_gcps: int
    transformation: str | None

    @property
    def mean(self) -> float:
        return (self.mx + self.my) / 2

    @property
    def anisotropy(self) -> float:
        """How far the two axes disagree, as a fraction of the mean."""
        return abs(self.mx - self.my) / self.mean

    @property
    def trustworthy(self) -> bool:
        return self.anisotropy <= ANISOTROPY_LIMIT

    def __str__(self) -> str:
        return (
            f"{self.mean:.3f} m/px ({self.mx:.4f} x, {self.my:.4f} y; "
            f"{self.anisotropy * 100:.1f}% anisotropic, {self.n_gcps} gcps, "
            f"{self.transformation or 'transformation unstated'})"
        )


@dataclass(frozen=True)
class TileFit:
    """A tile size that holds a ground target and lands on a whole grid."""

    tile: int
    render: int
    cols: int
    rows: int
    metres_per_tile: float
    metres_per_rendered_px: float
    smallest_edge_fraction: float
    target_metres: float

    @property
    def n_tiles(self) -> int:
        return self.cols * self.rows

    @property
    def holds_target(self) -> bool:
        """Whether the grid actually delivers the ground target it was asked for.

        False when a bound bound first: the tile floor on a coarse sheet (which
        overshoots — 640 px of an 8.5 m/px survey is 5.4 km per call), or the
        sheet's own edge on a small scan (which undershoots). Either way the
        target was not what got applied, and a caller printing the plan should
        say so rather than let the number look chosen.
        """
        return abs(self.metres_per_tile - self.target_metres) <= self.target_metres * 0.2

    def __str__(self) -> str:
        return (
            f"tile {self.tile} render {self.render} -> "
            f"{self.metres_per_tile:.0f} m/call, "
            f"{self.metres_per_rendered_px:.2f} m per rendered px, "
            f"grid {self.cols}x{self.rows} = {self.n_tiles} tiles, "
            f"smallest edge tile {self.smallest_edge_fraction * 100:.0f}%"
            + ("" if self.holds_target else
               f" [not {self.target_metres:.0f} m: "
               + ("the " + str(MIN_TILE_PX) + "px tile floor bound, so this sheet wants a "
                  "larger --tile-metres" if self.metres_per_tile > self.target_metres
                  else "the sheet is smaller than one tile at that target")
               + "]")
        )


def gcps_from_annotation(ann: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, str | None]:
    """Pull (source pixels, lng/lat, transformation type) out of a georef annotation.

    Tolerates a bare FeatureCollection as well as the full Web Annotation, since
    `annotation_url` on an R2-mirrored map points at a rewritten document.
    """
    body = ann
    items = ann.get("items")
    if isinstance(items, list) and items:
        body = items[0].get("body", {})
    features = body.get("features") or []
    transformation = (body.get("transformation") or {}).get("type")

    px: list[list[float]] = []
    lonlat: list[list[float]] = []
    for f in features:
        rc = (f.get("properties") or {}).get("resourceCoords")
        coords = (f.get("geometry") or {}).get("coordinates")
        if not rc or not coords or len(rc) < 2 or len(coords) < 2:
            continue
        px.append([float(rc[0]), float(rc[1])])
        lonlat.append([float(coords[0]), float(coords[1])])

    return np.array(px, float), np.array(lonlat, float), transformation


def metres_per_pixel(ann: dict[str, Any]) -> ScaleFit | None:
    """Least-squares affine over the GCPs → metres per source pixel per axis.

    None when there are too few points to fit. A caller that gets None must fall
    back to an explicit tile size; there is no sensible default scale for a sheet
    whose scan resolution is unknown.
    """
    px, lonlat, transformation = gcps_from_annotation(ann)
    if len(px) < MIN_GCPS:
        return None

    # Collinear control points fit a line, not a plane; the cross-axis scale
    # they imply is noise. Refuse rather than report it.
    centred = px - px.mean(axis=0)
    singular = np.linalg.svd(centred, compute_uv=False)
    if singular[0] <= 0 or singular[-1] / singular[0] < MIN_GCP_CONDITION:
        return None

    # Degrees to metres in a local tangent plane at the sheet's own latitude.
    lat = math.radians(float(lonlat[:, 1].mean()))
    metres = lonlat * np.array(
        [METRES_PER_DEG_LON_EQUATOR * math.cos(lat), METRES_PER_DEG_LAT]
    )

    # Fit [x, y, 1] -> [easting, northing]; the two columns of A are where one
    # pixel of image-x and image-y land on the ground, so their magnitudes are
    # the per-axis scale and the rotation drops out.
    design = np.column_stack([px, np.ones(len(px))])
    affine, *_ = np.linalg.lstsq(design, metres, rcond=None)
    mx = float(np.hypot(affine[0, 0], affine[0, 1]))
    my = float(np.hypot(affine[1, 0], affine[1, 1]))

    return ScaleFit(mx=mx, my=my, n_gcps=len(px), transformation=transformation)


def annotation_for_map(map_id: str) -> dict[str, Any] | None:
    """The map's georeference annotation — mirrored copy first, Allmaps second.

    The one impure function here, and the reason it is here rather than in
    `iiif_tiles`: everything that reads GCPs should read them the same way.
    """
    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()
    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={"id": f"eq.{map_id}", "select": "allmaps_id,annotation_url"},
        headers=_headers(key),
        timeout=20,
    )
    if not resp.ok:
        return None
    rows = resp.json()
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    source = row.get("annotation_url") or (
        f"https://annotations.allmaps.org/maps/{row['allmaps_id']}"
        if row.get("allmaps_id")
        else None
    )
    if not source:
        return None
    ann = requests.get(source, timeout=20)
    return ann.json() if ann.ok else None


def _grid(region_w: int, region_h: int, tile: int, overlap: int) -> tuple[int, int]:
    step = max(tile - overlap, 1)
    cols = math.ceil(max(region_w - overlap, 1) / step)
    rows = math.ceil(max(region_h - overlap, 1) / step)
    return cols, rows


def tile_size_for(
    m_per_px: float,
    region_w: int,
    region_h: int,
    target_metres: float = DEFAULT_TILE_METRES,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    tolerance: float = 0.15,
    max_render: int = MAX_RENDER_SIZE,
) -> TileFit:
    """Pick a tile size holding `target_metres` of ground, on a grid with no sliver.

    The freedom inside `tolerance` is spent on the grid, not on the ground: the
    ideal size for the 1968 sheet is 1103 px, which leaves a 13th column 103 px
    wide — twelve extra calls on nothing. 1120 px is 1.5% off the target and
    lands 12 columns exactly. Ground per call comes first, then fewest calls,
    then the fattest remaining edge tile.
    """
    ideal = target_metres / m_per_px
    # Never below the floor, never larger than the region itself (a tile that
    # covers the whole sheet is one call, which is a legitimate answer for a
    # small scan and a silly one to search past).
    ceiling = max(region_w, region_h)
    lo = min(max(int(ideal * (1 - tolerance)), MIN_TILE_PX), ceiling)
    hi = max(min(max(int(ideal * (1 + tolerance)), lo + 1), ceiling), lo)

    best: tuple | None = None
    for tile in range(lo, hi + 1):
        overlap = int(tile * overlap_ratio)
        cols, rows = _grid(region_w, region_h, tile, overlap)
        step = max(tile - overlap, 1)
        edge = min(
            (region_w - (cols - 1) * step) / tile,
            (region_h - (rows - 1) * step) / tile,
        )
        # Ground per call is the lever, so it is the primary key — but bucketed
        # to 5% of the target, because a metre of ground is not worth a wasted
        # call. On the 1968 crop the arithmetic size (1103 px, 1404 m) needs 13
        # columns and 1120 px (1426 m, 1.9% off) needs 12: same bucket, 12 fewer
        # calls out of 48. A tighter bucket buys the metre and pays a quarter of
        # the run for it.
        band = max(target_metres * 0.05, 1.0)
        key = (
            round(abs(tile * m_per_px - target_metres) / band),
            cols * rows,
            -round(edge, 2),
            abs(tile - ideal),
        )
        if best is None or key < best[0]:
            best = (key, tile, cols, rows, edge)

    assert best is not None  # the range always holds at least one candidate
    _, tile, cols, rows, edge = best

    render = render_size_for(tile, max_render)
    return TileFit(
        tile=tile,
        render=render,
        cols=cols,
        rows=rows,
        metres_per_tile=tile * m_per_px,
        metres_per_rendered_px=tile * m_per_px / render,
        smallest_edge_fraction=edge,
        target_metres=target_metres,
    )


def render_size_for(tile: int, max_render: int = MAX_RENDER_SIZE) -> int:
    """Render the tile 1:1, but never above the API's own patch ceiling.

    Deliberately not a quality knob — see MAX_RENDER_SIZE. Sending a 4048 px
    tile costs the same tokens as sending 1536 px of it and takes longer, so
    this is the one place the corpus stops paying for pixels the model will
    throw away. It never upsamples: more pixels than the scan holds is more
    bytes carrying the same ink.
    """
    return max(1, min(tile, max_render))


def _self_check() -> None:
    # A synthetic sheet at exactly 2 m/px, rotated 30°, so the fit has to
    # recover scale through a rotation rather than reading it off a diagonal.
    theta = math.radians(30.0)
    lat0, lon0 = 10.776, 106.701
    m_per_deg_lon = METRES_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat0))
    features = []
    for x, y in [(0, 0), (4000, 0), (0, 3000), (4000, 3000), (2000, 1500), (1000, 2500)]:
        east = 2.0 * (x * math.cos(theta) - y * math.sin(theta))
        north = 2.0 * (x * math.sin(theta) + y * math.cos(theta))
        features.append(
            {
                "properties": {"resourceCoords": [x, y]},
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon0 + east / m_per_deg_lon, lat0 + north / METRES_PER_DEG_LAT],
                },
            }
        )
    ann = {
        "items": [
            {"body": {"type": "FeatureCollection", "features": features,
                      "transformation": {"type": "helmert"}}}
        ]
    }

    fit = metres_per_pixel(ann)
    assert fit is not None, "six GCPs must fit"
    assert abs(fit.mean - 2.0) / 2.0 < 0.005, f"scale off: {fit.mean}"
    assert fit.anisotropy < 0.01 and fit.trustworthy, f"should read isotropic: {fit}"
    assert fit.n_gcps == 6 and fit.transformation == "helmert"

    # A bare FeatureCollection is accepted too (mirrored annotations are rewritten).
    assert metres_per_pixel(ann["items"][0]["body"]) is not None

    # Three points are enough — thirteen sheets in the corpus have exactly three.
    three = {"items": [{"body": {"features": features[:3]}}]}
    assert metres_per_pixel(three) is not None, "three points determine an affine"

    # Too few refuses rather than guessing.
    thin = {"items": [{"body": {"features": features[:MIN_GCPS - 1]}}]}
    assert metres_per_pixel(thin) is None, "must refuse under MIN_GCPS"

    # Collinear points refuse too: they fit a line, and the cross-axis scale
    # they imply is noise rather than a measurement.
    line = []
    for x in (0, 1000, 2000, 3000, 4000):
        east, north = 2.0 * x * math.cos(theta), 2.0 * x * math.sin(theta)
        line.append({"properties": {"resourceCoords": [x, int(x * 0.5)]},
                     "geometry": {"coordinates": [lon0 + east / m_per_deg_lon,
                                                  lat0 + north / METRES_PER_DEG_LAT]}})
    assert metres_per_pixel({"items": [{"body": {"features": line}}]}) is None, \
        "collinear GCPs must refuse"

    # A malformed feature is skipped, not fatal.
    dirty = {"items": [{"body": {"features": features + [{"properties": {}, "geometry": {}}]}}]}
    assert metres_per_pixel(dirty).n_gcps == 6

    # Sizing holds the ground target and never leaves a sliver edge tile.
    for m_per_px, w, h in [(0.343, 12102, 8982), (0.999, 14000, 10773), (1.273, 10816, 13523)]:
        t = tile_size_for(m_per_px, w, h)
        assert abs(t.metres_per_tile - DEFAULT_TILE_METRES) / DEFAULT_TILE_METRES < 0.16, str(t)
        assert t.smallest_edge_fraction > 0.25, f"sliver column: {t}"
        assert t.cols >= 1 and t.rows >= 1 and t.n_tiles == t.cols * t.rows
        assert 1 <= t.render <= MAX_RENDER_SIZE

    # A coarse regional sheet hits the tile floor rather than asking for 8,175
    # calls: the 1930 Giadinh survey is 8.5 m/px, where 1400 m is a 167 px tile.
    giadinh = tile_size_for(8.506, 9406, 13685)
    assert giadinh.tile >= MIN_TILE_PX, f"floor must bind: {giadinh}"
    assert not giadinh.holds_target, "and the caller must be told the target did not apply"
    # 167 px would have been 8,175 calls; the floor is 580. Still too many for a
    # road map, which is why `holds_target` is False and the caller prints the
    # target that would hold instead of quietly running this one.
    assert giadinh.n_tiles < 1000, f"floor did not bite: {giadinh}"
    assert giadinh.metres_per_tile > 1400 * 1.2, "floor overshoots the target, by definition"

    # A sheet smaller than one tile is one call, not a search past its own edge.
    tiny = tile_size_for(3.215, 4386, 3492, target_metres=20_000)
    assert tiny.n_tiles >= 1 and tiny.tile <= max(4386, 3492), str(tiny)

    # The 1968 sheet is the case the tolerance exists for. Sized over its own
    # main_map crop (the region a run actually tiles, not the whole scan), the
    # arithmetic answer of 1103 px needs 13 columns where 1120 needs 12 — and
    # the hand-picked run used 1120 for exactly that reason.
    t68 = tile_size_for(1.273, 10015, 9533)
    assert t68.cols <= 12, f"snap should avoid the 13th column: {t68}"
    assert t68.n_tiles <= 144, f"should not exceed the hand-picked grid: {t68}"

    # Render side: 1:1 under the ceiling, clamped above it, never upsampled.
    assert render_size_for(1120) == 1120, "under the ceiling, render the tile 1:1"
    assert render_size_for(4048) == MAX_RENDER_SIZE, "above it, stop paying for pixels"
    assert render_size_for(9000, max_render=2048) == 2048, "the cap is a parameter"
    assert all(render_size_for(t) <= t for t in (100, 1000, 1536, 4048)), "never upsample"

    print("scale.py self-check ok")


if __name__ == "__main__":
    _self_check()
