#!/usr/bin/env python3
"""Modern geodata warped into a historical sheet's own pixel grid.

    python work/ocr/scripts/modern_prior.py --map-id <uuid> --blocks --roads
    python work/ocr/scripts/modern_prior.py --map-id <uuid> --built-fraction 16
    python work/ocr/scripts/modern_prior.py --self-check          # no network

Why this exists: the corpus has 2023 ground truth sitting next to it — a
cadastral-grade building layer for HCMC (2.1M polygons) and an OSM extract —
and the pipeline could not see either, because everything on the Python side
speaks source pixels and both of those speak lng/lat. `scale.py` already reads
the ground control points out of a sheet's georeference annotation to answer
"how many metres is one pixel"; the same points answer "where on this scan is
this coordinate", which is the whole bridge.

**Read the epoch gap before trusting any of this.** Inside the 1882 Plan
Cadastral's extent the modern layer holds 51,382 buildings on 38% of the
ground; the sheet itself draws a colonial town in paddy. Overlaying the two
directly produces roughly 1,100 false seeds per real building, so the modern
buildings are NOT a positive prompt source as they stand. What survives 1882 →
2023 is the *block structure*, not the individual building, which is why the
useful outputs here are blocks, road centrelines and built fraction rather
than footprints:

  --blocks           buildings buffer-dissolved into blocks. The street network
                     falls out as the gaps, and blocks are what persist.
  --blocks-from-roads the same blocks built the other way up — the complement of
                     the TASCO road-surface polygons, so a block edge is the
                     kerb line the survey drew rather than a buffer distance
                     somebody chose. On the 1882 sheet: 1,184 blocks against the
                     8 m buffer's 666, land_plot IoU 0.262 vs 0.197 and cover
                     0.87 vs 0.60. Both write blocks.geojson; pass --out to keep
                     two. Prefer this one — see EVAL-BASELINE.
  --roads            OSM through-street centrelines plus their junctions.
                     Junctions are the alignment primitive; footways are
                     dropped (885 of them in the 1882 extent, 5 named).
  --built-fraction N an N x N grid of 2023 built fraction. Use it as a
                     *de-prioritiser*: 2023-empty implies 1882-empty (river,
                     port, marsh) and holds. The converse does not.
  --survivors        the one honest positive set: large footprint, low rise.
                     406 candidates in the 1882 extent against 51,382 raw.

Water is deliberately not offered as a negative mask. OSM carries 8 river
segments in the 1882 extent because the Charner and Bonard canals were filled;
masking on it would erase exactly the water the old sheets are most useful for.

Everything is written in **source-pixel coordinates, y-down** — the same grid
`ocr_labels.global_x/global_y` and the MapSAM2 polygons already share, so
the output drops straight into `to_sam2_seeds.py` or the review UI.

Pure geometry plus two file reads and one annotation fetch. Self-check at the
bottom runs with no network and no data files.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import shapely

from scale import MIN_GCP_CONDITION, gcps_from_annotation, metres_per_pixel

# The two local sources. Both are Saigon-only: the buildings run
# 106.408,10.412 → 107.034,11.135 and the OSM extract 106.625,10.349 →
# 107.067,10.880, so the 21 Huế and Hanoi sheets in the corpus get nothing
# from either and need their own extracts before this is worth running on them.
BUILDINGS_GPKG = Path("/Users/airm1/Desktop/tasco/hcmc/hcmc_buildings_3d.gpkg")
OSM_GPKG = Path("/Users/airm1/Desktop/tasco/hcmc/saigon_osm.gpkg")

# The TASCO topographic vector product, same ground as the buildings file
# (106.408,10.376 → 107.034,11.135). It carries what neither of the two above
# does: the road *surface* as polygons, 74,566 of them, plus river and lake
# polygons. That makes a block derivable as the negative space of the street
# network rather than as buildings grown until they touch, which is what
# `blocks()` does and what BLOCK_BUFFER_M is apologising for.
TASCO_GPKG = Path("/Users/airm1/Desktop/tasco/hcmc/vector_out/hcmc_vector.gpkg")

# Road surface and water, the two things a block is not. `region_duongbos` is
# the carriageway including the hẻm fabric; `region_duongbokhacs` is the other
# paved ground beside it. Bridges (`region_caugiaothongs`) and tunnels
# (`region_hamgiaothongs`) are deliberately out: a bridge deck over a river
# would carve the water into two blocks that no sheet has ever drawn.
ROAD_SURFACE_LAYERS = ("region_duongbos", "region_duongbokhacs")
WATER_SURFACE_LAYERS = ("region_river", "region_lake")

# What survives the complement as a block. Unlike BLOCK_BUFFER_M these two do
# NOT move any block edge — every edge is fixed by the road network before the
# filter runs. They only decide which of the resulting parts is a city block:
# below the floor are noding slivers where two carriageway polygons fail to
# quite meet, above the ceiling is paddy, marsh and the open ground between
# villages, which is one polygon the size of a district and useless as a prompt.
BLOCK_MIN_AREA_M2 = 500.0
BLOCK_MAX_AREA_M2 = 200_000.0

# Which OSM highway values count as a street. `service` is the hẻm fabric —
# 1,344 ways in the 1882 extent and genuinely named 583 times — so it is in,
# but footway/steps/path are out: 885 footways there carry 5 names between
# them, and they postdate every sheet in the corpus.
STREET_CLASSES = (
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "living_street",
    "service",
)

# A block is buildings grown until neighbours touch, then shrunk back. The gap
# is the widest thing that should still count as *inside* a block rather than a
# street between two.
#
# 4 m was the first guess — the gap between two tube houses on one block — and
# it under-merges badly: on the 1959 sheet it returns 19,783 "blocks" of which
# 3,225 are a single house. 8 m spans the narrow hẻm as well and returns 8,609,
# halving both the total and the singletons, at the cost of 22 blocks too large
# to fit a 1024 px tile (1 at 4 m). Since each block becomes one SAM2 box prompt,
# that halving is GPU money.
#
# Beyond 8 m the merge starts eating streets: 12 m gives 59 oversized and 30 m
# gives 1,453 blocks with a median width of 27 m, which is no longer a block —
# it is whatever survived being swallowed.
#
# ponytail: one constant for the whole corpus. It is a per-sheet quantity really
# (alley width varies by district and by era), so pass `buffer_m` explicitly if a
# sheet comes back visibly over- or under-merged.
BLOCK_BUFFER_M = 8.0

# The survivor filter. A colonial-era structure that kept its plot is large and
# low; the tube-house fabric that replaced everything else averages 103 m².
SURVIVOR_MIN_AREA_M2 = 800.0
SURVIVOR_MAX_HEIGHT_M = 25.0

# Below this the affine is not describing the sheet, it is describing noise.
# Nothing downstream should be built on a fit this loose — see `SheetFit.ok`.
MAX_RMS_PX = 60.0

# An affine has three coefficients per axis, so three control points fit it
# exactly and report zero residual whatever the points say. That zero is not a
# good georeference, it is no measurement at all — `SheetFit.informative` is
# what separates the two, and the sweep prints "—" rather than "0.0" for them.
MIN_INFORMATIVE_GCPS = 4

# Dropping a point costs a degree of freedom. Below this a leave-one-out fit
# lands on or near the exact-fit floor and reports a spectacular improvement
# for every point, which says nothing about any of them.
MIN_OUTLIER_GCPS = 6

METRES_PER_DEG_LAT = 111_132.95
METRES_PER_DEG_LON_EQUATOR = 111_320.0


@dataclass(frozen=True)
class SheetFit:
    """A sheet's georeference as two affines, plus how well they actually fit.

    `scale.py` fits pixels → metres to get one scalar out. This keeps both
    directions and, more to the point, keeps the residuals: the per-GCP miss in
    pixels is the only georeference quality number the corpus has that costs
    nothing to compute, and every other output in this file is worthless on a
    sheet where it is large.

    Longitude and latitude are centred on the sheet before fitting. Degrees are
    ~1e2 with the signal in the 1e-2, and an uncentred design matrix throws that
    away to floating point for no reason.
    """

    origin: np.ndarray  # lng/lat the fit is centred on
    to_px: np.ndarray  # 3x2: [dlng, dlat, 1] -> [x, y]
    to_deg: np.ndarray  # 3x2: [x, y, 1] -> [dlng, dlat]
    n_gcps: int
    rms_px: float
    max_px: float
    metres_per_px: float

    @property
    def informative(self) -> bool:
        """False when the fit is exactly determined and the residual is a zero
        by construction rather than by agreement."""
        return self.n_gcps >= MIN_INFORMATIVE_GCPS

    @property
    def ok(self) -> bool:
        """An uninformative fit is never `ok` — it is unmeasured, not good."""
        return self.informative and self.rms_px <= MAX_RMS_PX

    @property
    def rms_m(self) -> float:
        return self.rms_px * self.metres_per_px

    def px(self, lonlat: np.ndarray) -> np.ndarray:
        """(N,2) lng/lat -> (N,2) source pixels, y-down."""
        d = np.asarray(lonlat, float).reshape(-1, 2) - self.origin
        return np.column_stack([d, np.ones(len(d))]) @ self.to_px

    def lonlat(self, px: np.ndarray) -> np.ndarray:
        """(N,2) source pixels -> (N,2) lng/lat."""
        p = np.asarray(px, float).reshape(-1, 2)
        return np.column_stack([p, np.ones(len(p))]) @ self.to_deg + self.origin

    def bbox_lonlat(self, width: int, height: int) -> tuple[float, float, float, float]:
        """The scan's four corners in lng/lat, as a clip box for the data reads.

        The corners, not the pixel bbox transformed twice: this scan's x-axis
        runs north, so an axis-aligned box in pixels is a rotated diamond on the
        ground and its bounding box is what the sources have to be asked for.
        """
        corners = np.array(
            [[0, 0], [width, 0], [width, height], [0, height]], float
        )
        ll = self.lonlat(corners)
        return (
            float(ll[:, 0].min()),
            float(ll[:, 1].min()),
            float(ll[:, 0].max()),
            float(ll[:, 1].max()),
        )

    def __str__(self) -> str:
        if not self.informative:
            return (
                f"{self.n_gcps} gcps  residual undefined — an affine fits three "
                f"points exactly, so this sheet has never been checked"
            )
        flag = "" if self.ok else "  ** RMS OVER LIMIT **"
        return (
            f"{self.n_gcps} gcps  rms {self.rms_px:.1f} px "
            f"({self.rms_m:.1f} m)  worst {self.max_px:.1f} px  "
            f"{self.metres_per_px:.3f} m/px{flag}"
        )


def fit_sheet(ann: dict[str, Any]) -> SheetFit | None:
    """Least-squares affine both ways over a georeference annotation's GCPs.

    None when there are fewer than three points, which is the same floor
    `scale.py` refuses at: two points fit a line and the cross-axis term they
    imply is invented.
    """
    px, lonlat, _ = gcps_from_annotation(ann)
    if len(px) < 3:
        return None

    # Control points strung along a line fit a line, not a plane: lstsq still
    # returns something, and it is a transform that collapses one axis. The
    # same floor `scale.py` refuses at, for the same reason.
    centred = px - px.mean(axis=0)
    singular = np.linalg.svd(centred, compute_uv=False)
    if singular[0] <= 0 or singular[-1] / singular[0] < MIN_GCP_CONDITION:
        return None

    origin = lonlat.mean(axis=0)
    d = lonlat - origin
    fwd_design = np.column_stack([d, np.ones(len(d))])
    to_px, *_ = np.linalg.lstsq(fwd_design, px, rcond=None)

    inv_design = np.column_stack([px, np.ones(len(px))])
    to_deg, *_ = np.linalg.lstsq(inv_design, d, rcond=None)

    miss = np.linalg.norm(fwd_design @ to_px - px, axis=1)
    fit = metres_per_pixel(ann)

    return SheetFit(
        origin=origin,
        to_px=to_px,
        to_deg=to_deg,
        n_gcps=len(px),
        rms_px=float(np.sqrt((miss**2).mean())),
        max_px=float(miss.max()),
        metres_per_px=fit.mean if fit else float("nan"),
    )


def gcp_report(ann: dict[str, Any]) -> list[tuple[int, float, float, float]]:
    """Per-control-point miss, and the sheet RMS with that point dropped.

    An RMS is a verdict with no defendant. Leave-one-out names the point: on
    the 1968 Sài Gòn sheet the whole-sheet RMS is 142 px, dropping any one
    point leaves it at ~147 — except one, which takes it to 7. That is one bad
    control point, not a bad scan, and Allmaps smears it over the sheet because
    a helmert fit has no way to reject an outlier.

    Returns (index, miss_px, rms_without_px, gain_px), worst gain first.
    """
    fit = fit_sheet(ann)
    if fit is None or fit.n_gcps < MIN_OUTLIER_GCPS:
        return []
    px, lonlat, _ = gcps_from_annotation(ann)
    d = lonlat - fit.origin
    miss = np.linalg.norm(np.column_stack([d, np.ones(len(d))]) @ fit.to_px - px, axis=1)

    features = (ann.get("items", [{}])[0].get("body", {}) or ann).get("features") or []
    out = []
    for i in range(len(px)):
        kept = [f for j, f in enumerate(features) if j != i]
        without = fit_sheet({"items": [{"body": {"features": kept}}]})
        rms_without = without.rms_px if without else float("nan")
        out.append((i, float(miss[i]), rms_without, fit.rms_px - rms_without))
    out.sort(key=lambda r: -r[3])
    return out


def _read(path: Path, layer: str, columns: list[str], bbox, where: str | None = None):
    """(geometries, {column: array}) out of a GPKG, clipped by bbox.

    `pyogrio.raw` rather than `read_dataframe` on purpose — geopandas would drag
    pandas and pyproj into a venv whose whole point is that it holds only what
    the pipeline imports.
    """
    import pyogrio
    import pyogrio.raw as raw

    # A clip box larger than the source is silently answered with "everything
    # I have", which reads exactly like a complete answer. It is how the 1959
    # and 1968 sheets both came back with the same 2,676 streets: the Saigon
    # OSM extract stops at 106.625 and both sheets run west of it.
    have = pyogrio.read_info(str(path), layer=layer).get("total_bounds")
    if have is not None:
        short = [
            side
            for side, outside in (
                ("west", bbox[0] < have[0]),
                ("south", bbox[1] < have[1]),
                ("east", bbox[2] > have[2]),
                ("north", bbox[3] > have[3]),
            )
            if outside
        ]
        if short:
            print(
                f"  ! {path.name}:{layer} stops short of the sheet on the "
                f"{', '.join(short)} — counts below are a floor, not a total",
                file=sys.stderr,
            )

    meta, _, wkb, fields = raw.read(
        str(path), layer=layer, columns=columns, bbox=tuple(bbox), where=where
    )
    geoms = shapely.from_wkb(wkb)
    named = {str(name): arr for name, arr in zip(meta["fields"], fields)}
    return geoms, named


def load_buildings(
    bbox,
    path: Path = BUILDINGS_GPKG,
    min_area_m2: float | None = None,
    max_height_m: float | None = None,
):
    """Modern building polygons in the box, optionally filtered to survivors."""
    clauses = []
    if min_area_m2 is not None:
        clauses.append(f"area_m2 >= {min_area_m2}")
    if max_height_m is not None:
        clauses.append(f"height <= {max_height_m}")
    where = " AND ".join(clauses) if clauses else None
    return _read(path, "buildings", ["area_m2", "height"], bbox, where)


def load_streets(bbox, path: Path = OSM_GPKG, classes: Iterable[str] = STREET_CLASSES):
    """OSM street centrelines in the box, footways and steps excluded."""
    quoted = ",".join(f"'{c}'" for c in classes)
    return _read(path, "lines", ["name", "highway"], bbox, f"highway IN ({quoted})")


def warp(geoms, fit: SheetFit):
    """Every vertex through `fit.px`, geometry types untouched."""
    return shapely.transform(geoms, fit.px, include_z=False)


def blocks(building_px, metres_per_px: float, buffer_m: float = BLOCK_BUFFER_M):
    """Buffer-dissolve buildings into blocks, in pixel space.

    Grow by half the gap, union, shrink back by the same. The shrink is what
    keeps the block edge on the building line instead of half a lane out into
    the street, and it is why this is not just `unary_union(buffer)`.
    """
    grow = buffer_m / metres_per_px / 2.0
    # Mitred joins, not the default round ones: buildings are rectilinear, and
    # a round grow followed by a round shrink shaves every corner — a lone
    # square comes back 0.0035% short, and a block of forty comes back with
    # forty rounded corners it never had.
    merged = shapely.union_all(shapely.buffer(building_px, grow, join_style="mitre"))
    return shapely.buffer(merged, -grow, join_style="mitre")


def load_road_surface(bbox, path: Path = TASCO_GPKG):
    """Road-surface and water polygons in the box, as one geometry array each.

    Returned separately rather than pre-unioned because the caller reports the
    two counts apart — a sheet that comes back with no water read a box the
    river does not enter, which is worth seeing, and a sheet with no roads at
    all means the extent check above it fired and nobody looked.
    """
    roads = [g for layer in ROAD_SURFACE_LAYERS
             for g in _read(path, layer, ["madoituong"], bbox)[0]]
    water = [g for layer in WATER_SURFACE_LAYERS
             for g in _read(path, layer, ["madoituong"], bbox)[0]]
    return np.array(roads, object), np.array(water, object)


def blocks_from_roads(
    road_px,
    water_px,
    page,
    metres_per_px: float,
    min_area_m2: float = BLOCK_MIN_AREA_M2,
    max_area_m2: float = BLOCK_MAX_AREA_M2,
):
    """City blocks as the negative space of the street network, in pixel space.

    Returns (blocks, {reason: count}) so the caller can print what it dropped.
    A block here has no buffer in it: its edges are the kerb lines the survey
    drew, so the 4 m-versus-8 m question that makes `blocks()` unpinnable does
    not arise. What does arise is that the complement of a road network is
    everything that is not road — including the river, which is why water goes
    into the same union, and including open country, which is what max_area_m2
    is for.

    ponytail: `difference` against the whole page in one call. Fine at one
    sheet (1.3 s over a 3.3 km window, 1,783 road polygons); if a sheet ever
    covers the full 74k it may want a grid. Measure before splitting it.
    """
    m2_per_px2 = metres_per_px**2
    obstacles = [g for g in list(road_px) + list(water_px) if g is not None and not g.is_empty]
    if not obstacles:
        return [], {"no road surface in box": 1}

    parts = shapely.get_parts(shapely.difference(page, shapely.union_all(obstacles)))
    dropped: Counter[str] = Counter()
    kept = []
    for g in parts:
        if g.is_empty:
            continue
        area_m2 = float(g.area) * m2_per_px2
        if area_m2 < min_area_m2:
            dropped["sliver"] += 1
        elif area_m2 > max_area_m2:
            dropped["open ground"] += 1
        else:
            kept.append(g)
    return kept, dict(dropped)


def junctions(street_px, tolerance_px: float = 1.0):
    """Points where three or more street ends meet, in pixel space.

    OSM ways share an exact node at a junction, so counting repeated vertices
    finds them without any geometric intersection test. Snapping to
    `tolerance_px` absorbs the float drift the warp introduces.

    ponytail: vertex counting, not true noding — it finds junctions where ways
    are split (which OSM does at every intersection) and misses a crossing where
    one way passes over another unsplit. Swap in `shapely.node` if bridges and
    flyovers start mattering.
    """
    seen: Counter[tuple[int, int]] = Counter()
    for geom in street_px:
        if geom is None or geom.is_empty:
            continue
        for x, y in shapely.get_coordinates(geom):
            seen[(round(x / tolerance_px), round(y / tolerance_px))] += 1
    return np.array(
        [[k[0] * tolerance_px, k[1] * tolerance_px] for k, n in seen.items() if n >= 3],
        float,
    ).reshape(-1, 2)


def built_fraction(centroids_px, areas_m2, width: int, height: int, n: int, metres_per_px: float):
    """An n x n grid of 2023 built ground fraction over the scan.

    ponytail: buildings are binned by centroid and counted whole, rather than
    clipped to the cell. A building is ~10 m across and a cell here is hundreds,
    so the error is edge-only. Clip properly if the grid ever gets fine enough
    that a cell and a building are the same size.
    """
    grid = np.zeros((n, n), float)
    if len(centroids_px) == 0:
        return grid

    cw, ch = width / n, height / n
    col = np.clip((centroids_px[:, 0] / cw).astype(int), 0, n - 1)
    row = np.clip((centroids_px[:, 1] / ch).astype(int), 0, n - 1)
    np.add.at(grid, (row, col), np.nan_to_num(np.asarray(areas_m2, float)))

    cell_ground_m2 = (cw * metres_per_px) * (ch * metres_per_px)
    return grid / cell_ground_m2


def _feature(geom, props: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": json.loads(shapely.to_geojson(geom)),
        "properties": props,
    }


def _write(path: Path, features: list[dict], extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "type": "FeatureCollection",
        # Loudly not lng/lat. Anything that reads this and assumes WGS84 lands
        # in the Gulf of Guinea, which at least fails visibly.
        "crs": "source-pixels-y-down",
        "features": features,
    }
    if extra:
        doc.update(extra)
    path.write_text(json.dumps(doc), encoding="utf-8")
    print(f"  → {path}  ({len(features)} features)")


def _annotation_source(row: dict[str, Any]) -> str | None:
    return row.get("annotation_url") or (
        f"https://annotations.allmaps.org/maps/{row['allmaps_id']}"
        if row.get("allmaps_id")
        else None
    )


def _paginate(url: str, key: str, table: str, select: str, page: int = 1000):
    """Every row of one column set, one table, no filter — pipeline_status,
    ocr_labels and footprints are all small enough (hundreds to
    low thousands of rows) that paging through them beats writing a group-by
    view for a report that runs by hand."""
    import requests

    from supabase_client import _headers

    rows, start = [], 0
    while True:
        resp = requests.get(
            f"{url}/rest/v1/{table}",
            params={"select": select},
            headers={**_headers(key), "Range": f"{start}-{start + page - 1}"},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < page:
            return rows
        start += page


def sweep(limit_rms: float = MAX_RMS_PX) -> int:
    """Fit every georeferenced sheet in the corpus and rank them by residual,
    alongside where each one sits in the OCR/segmentation pipeline — the one
    table for "is this map done, and what's the next thing to do to it".

    Needs no local data at all — a georeference annotation is the whole input —
    so unlike everything else in this file it covers the Huế and Hanoi sheets
    too. One Supabase query for the corpus, then the annotations in parallel,
    because they are ~50 independent HTTP fetches and nothing else here is slow.
    """
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor

    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()
    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={
            "select": "id,name,year,status,location,allmaps_id,annotation_url",
            "order": "year.asc.nullsfirst",
        },
        headers=_headers(key),
        timeout=30,
    )
    resp.raise_for_status()
    rows = [r for r in resp.json() if _annotation_source(r)]
    print(f"{len(rows)} georeferenced sheets\n")

    pipeline = {
        p["map_id"]: p
        for p in _paginate(url, key, "map_pipeline_status", "map_id,stage")
    }
    ocr_n = Counter(e["map_id"] for e in _paginate(url, key, "ocr_labels", "map_id"))
    fp_n = Counter(f["map_id"] for f in _paginate(url, key, "footprints", "map_id"))

    def status_cols(map_id: str) -> str:
        stage = pipeline.get(map_id, {}).get("stage", "idle")
        return f"{stage:<12} ocr={ocr_n.get(map_id, 0):<5} fp={fp_n.get(map_id, 0):<4}"

    def one(row: dict[str, Any]):
        try:
            ann = requests.get(_annotation_source(row), timeout=30)
            if not ann.ok:
                return row, None, f"HTTP {ann.status_code} from the annotation store"
            doc = ann.json()
            fit = fit_sheet(doc)
            if fit is None:
                return row, None, "fewer than 3 usable control points"
            return row, fit, gcp_report(doc)
        except Exception as exc:  # a sheet that will not load is a result too
            return row, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, rows))

    ok = [(r, f, g) for r, f, g in results if f is not None]
    bad = [(r, g) for r, f, g in results if f is None]
    ok.sort(key=lambda t: -t[1].rms_px)

    head = (
        f"{'rms px':>7} {'rms m':>7} {'worst':>7} {'gcps':>4}  {'year':<5} {'status':<8} "
        f"{'pipeline':<12} {'ocr':<9} {'fp':<8} {'sheet':<40} outlier"
    )
    print(head)
    print("-" * len(head))
    flagged, blind = [], []
    for row, fit, report in ok:
        year = str(row.get("year") or "????")
        name = (row.get("name") or "")[:40]
        cols = status_cols(row["id"])
        if not fit.informative:
            blind.append(row)
            print(f"{'—':>7} {'—':>7} {'—':>7} {fit.n_gcps:4d}? {year:<5} "
                  f"{row['status']:<8} {cols} {name:<40} exact fit, nothing measured")
            continue

        drop = ""
        if report and report[0][3] > fit.rms_px / 2:
            i, _miss, without, _gain = report[0]
            drop = f"gcp {i} → {without:.1f} px"
            flagged.append((row, fit, report[0]))
        rms_m = "     ?" if math.isnan(fit.rms_m) else f"{fit.rms_m:7.1f}"
        mark = "!" if not fit.ok else " "
        print(
            f"{fit.rms_px:7.1f} {rms_m} {fit.max_px:7.1f} {fit.n_gcps:4d}{mark} "
            f"{year:<5} {row['status']:<8} {cols} {name:<40} {drop}"
        )

    for row, err in bad:
        print(f"{'—':>7} {'—':>7} {'—':>7} {'—':>4}  "
              f"{str(row.get('year') or '????'):<5} {row['status']:<8} "
              f"{status_cols(row['id']):<31} "
              f"{(row.get('name') or '')[:40]:<40} {err}")

    measured = [t for t in ok if t[1].informative]
    over = [t for t in measured if not t[1].ok]
    print(f"\n{len(measured)} of {len(rows)} sheets carry enough control points to "
          f"be checked at all; {len(over)} of those are over the {limit_rms:.0f} px limit.")

    if blind:
        print(f"\n{len(blind)} sheets sit on exactly 3 control points, so their "
              f"georeference has never been tested. Add a fourth to any of them "
              f"and the residual becomes a real number:")
        for row in blind:
            print(f"  {row['id']}  {row['status']:<8} {(row.get('name') or '')[:50]}")

    if flagged:
        print(f"\n{len(flagged)} sheets are fixable by dropping one control point:")
        for row, fit, (i, miss, without, _gain) in flagged:
            print(f"  {row['id']}  {(row.get('name') or '')[:44]:<44} "
                  f"gcp {i} misses {miss:.0f} px → drop it for {without:.1f} px "
                  f"(sheet is {fit.rms_px:.0f} px now)")

    if bad:
        gone = [r for r, err in bad if "HTTP" in err]
        unusable = [(r, err) for r, err in bad if "HTTP" not in err]
        if gone:
            print(f"\n{len(gone)} sheets carry an allmaps_id or annotation_url that "
                  f"resolves to nothing — listed as georeferenced, and are not.")
        for row, err in unusable:
            print(f"\n{row['id']}  {row['status']:<8} {(row.get('name') or '')[:50]}"
                  f"\n  has an annotation but {err} — the warp is unconstrained.")
    return 0


def legend_status() -> int:
    """Per map: is a numbered legend (legend_entry) joined against the numbered
    markers scattered across the sheet (legend_ref), and how much of it landed?
    Also: how many separate OCR runs fed this map, since a sheet assembled from
    several partial passes is exactly the shape that hides a coverage gap (the
    1968 body run stopping short of the south band and never being caught is
    what this flag exists to catch next time, not just that once).

    `legend_entry.notes` carries `n=<N>; grid=<letter>` (written by the join
    step, see work/ocr/scripts/*legend* callers); `legend_ref.text` is the bare
    number read off the map body. A ref "matches" when its number is one a
    legend_entry actually claims -- matching them tells you what fraction of
    the legend a person could actually click through to on the map, not just
    that both lists are non-empty.
    """
    import re

    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()

    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={"select": "id,name,year,status", "order": "year.asc.nullsfirst"},
        headers=_headers(key),
        timeout=30,
    )
    resp.raise_for_status()
    names = {m["id"]: m for m in resp.json()}

    rows = _paginate(url, key, "ocr_labels", "map_id,category,review_status,run_id,notes,text")
    by_map: dict[str, list[dict]] = {}
    for r in rows:
        by_map.setdefault(r["map_id"], []).append(r)

    print(f"{len(by_map)} maps carry OCR extractions\n")
    head = f"{'runs':>4}  {'legend':>15}  {'institution':>11}  sheet"
    print(head)
    print("-" * len(head))

    flagged_missing = []
    for map_id, ext in sorted(by_map.items(), key=lambda kv: names.get(kv[0], {}).get("year") or 0):
        row = names.get(map_id, {})
        active = [e for e in ext if e["review_status"] != "rejected"]
        n_runs = len({e["run_id"] for e in ext if e["run_id"]})
        n_institution = sum(1 for e in active if e["category"] == "institution")

        entries = {}
        for e in active:
            if e["category"] != "legend_entry":
                continue
            m = re.search(r"n=(\d+)", e.get("notes") or "")
            if m:
                entries[int(m.group(1))] = e["text"]
        refs = [e["text"].strip() for e in active if e["category"] == "legend_ref"]
        ref_nums = [int(t) for t in refs if t.isdigit()]
        matched = {n for n in ref_nums if n in entries}

        if entries:
            legend_col = f"{len(matched)}/{len(entries)} matched"
        elif n_institution >= 20:
            legend_col = "none — candidate"
            flagged_missing.append((row, n_institution))
        else:
            legend_col = "—"

        runs_mark = "!" if n_runs > 1 else " "
        name = (row.get("name") or map_id)[:40]
        print(f"{n_runs:4d}{runs_mark} {legend_col:>15}  {n_institution:11d}  "
              f"{str(row.get('year') or '????'):<5} {row.get('status', '?'):<8} {name}")

    print(f"\n`!` on runs = assembled from more than one OCR pass — worth checking "
          f"the passes' tile/global_bbox extents actually union to the full sheet "
          f"(the way 1968's body run alone stopped at 73% of the image height).")
    if flagged_missing:
        print(f"\n{len(flagged_missing)} sheets carry 20+ institution labels but no "
              f"legend_entry at all — likely candidates for a legend/numerals pass:")
        for row, n in sorted(flagged_missing, key=lambda t: -t[1]):
            print(f"  {row.get('id', '?')}  {n:4d} institutions  {(row.get('name') or '')[:50]}")
    return 0


def run(args: argparse.Namespace) -> int:
    from iiif_tiles import get_iiif_base_from_supabase, get_image_info
    from scale import annotation_for_map

    ann = annotation_for_map(args.map_id)
    if not ann:
        print(f"no georeference annotation for {args.map_id}", file=sys.stderr)
        return 1

    fit = fit_sheet(ann)
    if not fit:
        print("too few ground control points to fit", file=sys.stderr)
        return 1

    base = get_iiif_base_from_supabase(args.map_id)
    if not base:
        print(f"no IIIF source for {args.map_id}", file=sys.stderr)
        return 1
    info = get_image_info(base)
    width, height = int(info["width"]), int(info["height"])

    bbox = fit.bbox_lonlat(width, height)
    print(f"sheet   {width} x {height} px")
    print(f"georef  {fit}")
    print("bbox    %.6f,%.6f → %.6f,%.6f" % bbox)
    if args.gcps:
        print("\n  #   miss px   rms without   gain")
        for i, miss, without, gain in gcp_report(ann):
            flag = "   <-- drop this one" if gain > fit.rms_px / 2 else ""
            print(f"  {i:<3} {miss:8.1f} {without:13.1f} {gain:6.1f}{flag}")

    if not fit.ok:
        print(
            "\nRMS is over the limit — the georeference does not describe this "
            "scan well enough for anything below to mean much. Fix the control "
            "points first.\n",
            file=sys.stderr,
        )

    if args.blocks and args.blocks_from_roads:
        print("--blocks and --blocks-from-roads both write blocks.geojson; "
              "pick one, or give the second run its own --out", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "outputs" / "prior" / args.map_id

    if args.blocks or args.built_fraction or args.survivors:
        geoms, cols = load_buildings(bbox)
        px = warp(geoms, fit)
        print(f"\nbuildings  {len(geoms)} in box")

        if args.blocks:
            merged = blocks(px, fit.metres_per_px)
            polys = [g for g in shapely.get_parts(merged) if not g.is_empty]
            # The clip box is the bounding box of a *rotated* sheet, so its
            # corners take in ground the scan does not cover — on the 1882
            # cadastral, whose x-axis runs north, that is 59 blocks landing off
            # the image entirely. Drop them here rather than leave every
            # consumer to discover them: a seed outside every tile is a warning
            # worth reading, and this would make it fire on every run.
            page = shapely.box(0, 0, width, height)
            inside = shapely.intersects(shapely.centroid(np.array(polys)), page)
            dropped = int((~inside).sum())
            polys = [g for g, keep in zip(polys, inside) if keep]
            if dropped:
                print(f"blocks     {dropped} outside the scan itself, dropped")
            print(f"blocks     {len(polys)} from {len(geoms)} buildings")
            _write(
                out / "blocks.geojson",
                [_feature(g, {"area_px": round(float(g.area), 1)}) for g in polys],
            )

        if args.built_fraction:
            cent = shapely.get_coordinates(shapely.centroid(px))
            grid = built_fraction(cent, cols["area_m2"], width, height, args.built_fraction, fit.metres_per_px)
            path = out / "built_fraction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "n": args.built_fraction,
                        "width": width,
                        "height": height,
                        "note": "2023 built ground fraction per cell; low means "
                        "was-empty-then too, high means nothing about 1882",
                        "grid": np.round(grid, 4).tolist(),
                    }
                ),
                encoding="utf-8",
            )
            empty = int((grid < 0.02).sum())
            print(f"  → {path}  ({empty}/{grid.size} cells under 2% built)")

        if args.survivors:
            sg, sc = load_buildings(
                bbox, min_area_m2=SURVIVOR_MIN_AREA_M2, max_height_m=SURVIVOR_MAX_HEIGHT_M
            )
            spx = warp(sg, fit)
            feats = [
                _feature(g, {"area_m2": float(a), "height": float(h)})
                for g, a, h in zip(spx, sc["area_m2"], sc["height"])
            ]
            print(f"survivors  {len(feats)} of {len(geoms)} "
                  f"(area ≥ {SURVIVOR_MIN_AREA_M2:.0f} m², height ≤ {SURVIVOR_MAX_HEIGHT_M:.0f} m)")
            _write(out / "survivors.geojson", feats)

    if args.blocks_from_roads:
        lo, hi = (float(v) for v in args.block_area_m2.split(","))
        roads, water = load_road_surface(bbox)
        road_px, water_px = warp(roads, fit), warp(water, fit)
        page = shapely.box(0, 0, width, height)
        polys, dropped = blocks_from_roads(road_px, water_px, page, fit.metres_per_px, lo, hi)
        print(f"\nroad surface {len(road_px)} polygons, water {len(water_px)}")
        for reason, n in sorted(dropped.items()):
            print(f"blocks     {n} dropped as {reason}")
        print(f"blocks     {len(polys)} between {lo:.0f} and {hi:.0f} m\u00b2")
        _write(
            out / "blocks.geojson",
            [_feature(g, {"area_px": round(float(g.area), 1),
                          "area_m2": round(float(g.area) * fit.metres_per_px**2, 1)})
             for g in polys],
            {"source": "road-surface complement", "block_area_m2": [lo, hi]},
        )

    if args.roads:
        geoms, cols = load_streets(bbox)
        px = warp(geoms, fit)
        feats = [
            _feature(g, {"name": (n or None), "highway": h})
            for g, n, h in zip(px, cols["name"], cols["highway"])
        ]
        jx = junctions(px)

        # Two name counts, because they answer different questions. The hẻm
        # (`service`) are named and real, but no sheet in this corpus prints
        # them — the 1959 sheet's own index lists 375 *streets*. Compare a body
        # pass against `through`, not against everything.
        named = {n for n in cols["name"] if n}
        through = {
            n for n, h in zip(cols["name"], cols["highway"]) if n and h != "service"
        }
        print(
            f"\nstreets    {len(feats)} ways, {len(named)} distinct names "
            f"({len(through)} excluding hẻm), {len(jx)} junctions"
        )
        _write(
            out / "streets.geojson",
            feats,
            {"distinct_names": len(named), "distinct_names_through": len(through)},
        )
        _write(
            out / "junctions.geojson",
            [_feature(shapely.Point(x, y), {}) for x, y in jx],
        )

    return 0


def _self_check() -> None:
    """No network, no data files — the geometry only."""
    # A synthetic sheet: 1000x800 px, quarter-turn so image-x runs north, at a
    # scale of roughly one metre per pixel. Built as an exact affine so the fit
    # has to recover it to floating point.
    origin = np.array([106.70, 10.78])
    m_per_deg_lon = METRES_PER_DEG_LON_EQUATOR * math.cos(math.radians(10.78))
    # A 4x3 grid of control points, not the four corners: with only four, any
    # one of them can be moved a long way and the remaining three still admit
    # an exact affine, so leave-one-out cannot tell a bad point from a good one.
    gx, gy = np.meshgrid(np.linspace(0, 1000, 4), np.linspace(0, 800, 3))
    px_gcp = np.column_stack([gx.ravel(), gy.ravel()])
    # image x -> north, image y -> east
    lon = origin[0] + px_gcp[:, 1] / m_per_deg_lon
    lat = origin[1] - px_gcp[:, 0] / METRES_PER_DEG_LAT
    ann = {
        "items": [
            {
                "body": {
                    "transformation": {"type": "helmert"},
                    "features": [
                        {
                            "properties": {"resourceCoords": [float(x), float(y)]},
                            "geometry": {"coordinates": [float(a), float(b)]},
                        }
                        for (x, y), a, b in zip(px_gcp, lon, lat)
                    ],
                }
            }
        ]
    }

    fit = fit_sheet(ann)
    assert fit is not None
    assert fit.n_gcps == 12, fit.n_gcps
    assert fit.rms_px < 1e-6, f"exact affine must fit exactly, got {fit.rms_px}"
    assert fit.ok

    # Both directions, and the round trip.
    got = fit.px(np.column_stack([lon, lat]))
    assert np.allclose(got, px_gcp, atol=1e-6), got
    assert np.allclose(fit.lonlat(px_gcp), np.column_stack([lon, lat]), atol=1e-12)

    # The corner bbox must be the rotated diamond's box, not the pixel box: a
    # sheet whose x-axis runs north is taller in longitude than in latitude.
    minlon, minlat, maxlon, maxlat = fit.bbox_lonlat(1000, 800)
    # Pixel (0,0) is this sheet's north-west corner, so it is the box's min
    # longitude and its max latitude, not an interior point.
    assert abs(minlon - origin[0]) < 1e-9 and abs(maxlat - origin[1]) < 1e-9
    span_lon_m = (maxlon - minlon) * m_per_deg_lon
    span_lat_m = (maxlat - minlat) * METRES_PER_DEG_LAT
    assert abs(span_lon_m - 800) < 1.0, span_lon_m
    assert abs(span_lat_m - 1000) < 1.0, span_lat_m

    # Fewer than three points is a refusal, not a guess.
    feats = ann["items"][0]["body"]["features"]
    two = {"items": [{"body": {"features": feats[:2]}}]}
    assert fit_sheet(two) is None

    # Exactly three fits perfectly and means nothing. The zero must not be
    # allowed to read as a good result anywhere: not through `ok`, and not by
    # handing the caller an outlier to chase.
    corners = [feats[0], feats[3], feats[8]]  # not the first three: those are one row
    three = fit_sheet({"items": [{"body": {"features": corners}}]})
    assert three is not None and three.rms_px < 1e-9, three
    assert not three.informative and not three.ok
    assert "nothing measured" not in str(three) and "never been checked" in str(three)
    assert gcp_report({"items": [{"body": {"features": corners}}]}) == []

    # ...and a collinear set is refused outright rather than fitted flat.
    assert fit_sheet({"items": [{"body": {"features": feats[:3]}}]}) is None

    # Same for five: dropping one leaves four, one degree of freedom off the
    # exact-fit floor, so every point looks like the culprit.
    assert gcp_report({"items": [{"body": {"features": feats[:5]}}]}) == []
    assert len(gcp_report({"items": [{"body": {"features": feats[:6]}}]})) == 6

    # A bad control point has to show up in the residual rather than be absorbed.
    bent = json.loads(json.dumps(ann))
    bent["items"][0]["body"]["features"][5]["properties"]["resourceCoords"] = [1000, 1400]
    bad = fit_sheet(bent)
    assert bad is not None and bad.max_px > 100, bad
    assert not bad.ok, "a 600 px control point miss must fail the gate"

    # ...and leave-one-out has to name it, not just report that something is
    # wrong. Dropping the bent point returns an exact fit; dropping any other
    # leaves the bend in.
    report = gcp_report(bent)
    worst, miss, without, gain = report[0]
    assert worst == 5, report
    assert without < 1e-6 < gain, (without, gain)
    assert all(r[2] > bad.rms_px / 2 for r in report[1:]), report

    # Blocks: at a 4 m gap two squares 3 m apart merge and two 30 m apart do not.
    # The buffer is named rather than defaulted, so this keeps testing the
    # distances it describes even when BLOCK_BUFFER_M moves.
    near = shapely.box(0, 0, 10, 10), shapely.box(13, 0, 23, 10)
    far = shapely.box(0, 0, 10, 10), shapely.box(40, 0, 50, 10)
    assert shapely.get_num_geometries(blocks(np.array(near), 1.0, buffer_m=4)) == 1
    assert shapely.get_num_geometries(blocks(np.array(far), 1.0, buffer_m=4)) == 2

    # The gap is what the buffer spans, so widening it merges the far pair too.
    assert shapely.get_num_geometries(blocks(np.array(far), 1.0, buffer_m=40)) == 1

    # ...and the shrink puts the edge back on the building line, not out in the
    # street: one square in, one square out, same size.
    solo = blocks(np.array([shapely.box(0, 0, 10, 10)]), 1.0, buffer_m=4)
    assert abs(solo.area - 100.0) < 1e-6, solo.area

    # Junctions: a plus sign built as four ways sharing the centre node.
    plus = np.array(
        [
            shapely.LineString([(0, 0), (5, 0)]),
            shapely.LineString([(5, 0), (10, 0)]),
            shapely.LineString([(5, -5), (5, 0)]),
            shapely.LineString([(5, 0), (5, 5)]),
        ]
    )
    jx = junctions(plus)
    assert len(jx) == 1 and np.allclose(jx[0], [5, 0]), jx
    # A single unsplit way through a T has only two ends at the node, so the
    # T is found and a bare crossing is not — the documented ceiling.
    assert len(junctions(np.array([shapely.LineString([(0, 0), (10, 0)])]))) == 0

    # Built fraction: one 100 m² building alone in a 10x10 px cell at 1 m/px
    # is 1% of it, and the whole grid sums to what went in.
    grid = built_fraction(np.array([[5.0, 5.0]]), np.array([10.0]), 20, 20, 2, 1.0)
    assert grid.shape == (2, 2)
    assert abs(grid[0, 0] - 10.0 / 100.0) < 1e-9, grid
    assert abs(grid.sum() - 0.1) < 1e-9, grid
    assert built_fraction(np.empty((0, 2)), [], 20, 20, 2, 1.0).sum() == 0.0

    # Blocks as the road complement. A 100x100 page, one 4 px cross of road
    # surface: four quadrants, each 48x48 px. At 1 m/px that is 2,304 m² a
    # block, so the default 500 m² floor keeps all four.
    page = shapely.box(0, 0, 100, 100)
    cross = np.array([shapely.box(48, 0, 52, 100), shapely.box(0, 48, 100, 52)], object)
    quads, dropped = blocks_from_roads(cross, np.array([], object), page, 1.0)
    assert len(quads) == 4 and not dropped, (len(quads), dropped)
    assert all(abs(g.area - 48 * 48) < 1e-6 for g in quads)

    # The floor and the ceiling select, and never reshape: the same four parts
    # come back whole or not at all.
    _, only_slivers = blocks_from_roads(cross, np.array([], object), page, 1.0, min_area_m2=1e6)
    assert only_slivers == {"sliver": 4}, only_slivers
    _, only_open = blocks_from_roads(cross, np.array([], object), page, 1.0, max_area_m2=10.0)
    assert only_open == {"open ground": 4}, only_open

    # Water is an obstacle like a road: flooding one quadrant leaves three.
    with_water = blocks_from_roads(
        cross, np.array([shapely.box(0, 0, 48, 48)], object), page, 1.0
    )[0]
    assert len(with_water) == 3, len(with_water)

    # metres_per_px scales the filter, not the geometry. At 0.1 m/px each
    # quadrant is 23 m², under the floor, and every one of them is a sliver.
    assert blocks_from_roads(cross, np.array([], object), page, 0.1)[1] == {"sliver": 4}

    # No road surface in the box is not "one block the size of the page".
    assert blocks_from_roads(np.array([], object), np.array([], object), page, 1.0) == (
        [],
        {"no road surface in box": 1},
    )

    print("modern_prior self-check OK")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map-id", help="maps.id UUID")
    p.add_argument("--blocks", action="store_true", help="buffer-dissolved building blocks")
    p.add_argument("--blocks-from-roads", action="store_true",
                   help="blocks as the complement of the road surface (no buffer)")
    p.add_argument("--block-area-m2", metavar="MIN,MAX",
                   default=f"{BLOCK_MIN_AREA_M2:.0f},{BLOCK_MAX_AREA_M2:.0f}",
                   help="which complement parts count as a block (selects, never reshapes)")
    p.add_argument("--roads", action="store_true", help="OSM street centrelines + junctions")
    p.add_argument("--survivors", action="store_true", help="large, low-rise buildings only")
    p.add_argument("--built-fraction", type=int, metavar="N", help="N x N built-fraction grid")
    p.add_argument("--gcps", action="store_true", help="per-control-point residual + leave-one-out")
    p.add_argument("--out", help="output directory (default work/ocr/outputs/prior/<map-id>)")
    p.add_argument("--sweep", action="store_true",
                   help="fit every georeferenced sheet in the corpus, worst residual first")
    p.add_argument("--legend", action="store_true",
                   help="per map: OCR run count, legend_entry/legend_ref join completeness")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()

    if args.self_check:
        _self_check()
        return 0
    if args.sweep:
        return sweep()
    if args.legend:
        return legend_status()
    if not args.map_id:
        p.error("--map-id is required unless --self-check")
    if not (args.blocks or args.blocks_from_roads or args.roads or args.survivors
            or args.built_fraction or args.gcps):
        p.error("nothing to do — pass at least one of --blocks --blocks-from-roads "
                "--roads --survivors --built-fraction")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
