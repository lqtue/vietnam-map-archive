#!/usr/bin/env python3
"""City blocks read off a polychrome sheet's own ink, in its own pixel grid.

    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --census
    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --out work/ocr/outputs/<uuid>/colour
    python work/ocr/scripts/colour_blocks.py --self-check          # no network, no data

Why this exists: `modern_prior.py` builds the block prior from 2023 geodata —
2.1M HCMC buildings dissolved, or TASCO road surfaces complemented — and warps
it into the sheet through the georeference. Both paths inherit 11.3 m RMSE and
141 years of drift, which is why EVAL-BASELINE describes SAM2's job against
that prior as snapping drifted modern geometry onto 1882 ink. A block found by
colour starts *on* the ink, and it works on sheets the modern layer cannot help
at all — District 4, where the archive holds no footprints and the 1882
peninsula is not the 2023 one.

Design: plan and gates in `docs/journals/260918-colour-blocks.md` (P1).

The method, in the order the code runs it:

  1. One fetch of the whole sheet at `--render`. Blocks are coarse — the 1882
     median is ~2,700 m² — so there is no tiling here and therefore no
     tile-boundary stitching, which is the part that would have been hard.
  2. `r - g` separates the legend's warm classes. On the 1882 Plan Cadastral it
     is bimodal: cream at ~+0.045, salmon at ~+0.14, a trough at +0.065 holding
     3.4%. `find_split` locates that trough, and **refuses a unimodal sheet**
     rather than returning noise — which is how a monochrome scan declines.
  3. Blocks are the connected components of the **pigmented** classes —
     salmon, green, blue-grey — closed by `--close` first. What separates one
     block from the next is the *street*, which is cream and tens of pixels
     wide. What divides a block internally is the printed building line, which
     is 1-2 px. A closing kernel between those two widths rejoins a block
     without ever bridging a street.
  4. Each component becomes a polygon via a concave hull over its boundary
     pixels, scaled back to full-image source pixels.

Three classes are emitted, found on two axes and claimed in a fixed order —
salmon on `r - g`, then blue-grey on `r - b`, then the hatched administrative
green on `r - g` again, below the cream peak. The order is not cosmetic: blue
and green both sit low on `r - g`, so claiming green first swallows the
military parcels whole (65 blocks to 1, measured).

**Cream is still not a block.** Street surface and unassigned *non affectées*
land are the same tone and are separated by name, not palette — the
`street_name` extractions `to_sam2_seeds.py` discards. Adding cream to the mask
does not work and was measured: the street network welds every cream parcel to
every other, giving one component of 11.91 km², 100% of the mask, 0 blocks in
the area band.

Two designs were measured and rejected before this one, both on the 1882 tile
`4142_4032`, and both are recorded so they are not re-attempted:

  - **Components of not-ink.** Fails at every scale. At 1:1 the building lines
    and the hatching are barriers too, so the sheet breaks into 2,927
    fragments and 3 survive the area band; by 6x downscale the outlines have
    greyed past the ink threshold and everything floods into one component.
    There is no scale at which block outlines are barriers and building lines
    are not, because they are the same ink.
  - **Opening the ink by thickness**, on the theory that a block outline is
    heavier than a building line. It is not: a 2x2 opening takes ink from
    10.2% to 3.0% and a 3x3 takes it to 0.3%, so the two line weights are
    indistinguishable on this sheet.

Outputs, both the same polygons in the two shapes the rest of the pipeline
already reads:

  blocks.geojson    `crs: source-pixels-y-down`, the contract
                    `to_sam2_seeds.load_seeds_from_prior` checks and refuses on.
                    Drops straight into `inference_tiles_as_video.py --prior`.
  blocks.run.json   `{"polygons": [{"coords": [[x, y], ...]}]}` — what
                    `seg_eval.py` scores, so P1 can be graded the day it runs.

Two knobs that decide whether a run means anything, both reported:

  --render    the working resolution. The wash has to survive it and so do the
              streets. Measured on the 1882 tile, the block count is flat from
              1:1 to about 4x and the pigment is intact; past 6x the classes
              start bleeding into each other.
  --close     morphological closing before componenting, in render px. It
              rejoins a wash across the printed lines drawn on top of it; the
              street is far too wide to bridge. Swept against the 24 land_plot
              traces: k=0 scores 0.273 / cover 0.90, k=3 0.253 / 0.94, k=5
              0.247 / 0.98, k=9 0.125 / 0.97. **Read that spread as noise, not
              as a ranking** — 0.027 across k=0..5 at n=24 is the same
              magnitude as the repeat-pass variation this file's Gemini section
              records, and the two ends trade against each other anyway (k=0
              fragments the blue class into 188 components where k=5 gives 44,
              and building cover falls 0.97 to 0.66). Default 5, which holds
              coverage; do not tune it on 24 polygons.

The merge guard is the area band, not a line-width heuristic: a kernel that
did bridge a street would show up as the largest component running past
`--max-m2`, and the run prints what it dropped for that reason.

ponytail: the concave hull is a hull, not a trace. A block with a genuine
notch comes back filled. The upgrade is marching squares on the component
mask, and the signal to do it is `seg_eval` cover running high while IoU stays
flat — that is over-coverage, which is what a hull does.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from scipy import ndimage

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# The CRS token `to_sam2_seeds.load_seeds_from_prior` refuses on. Not a
# formality: GeoJSON means lng/lat unless told otherwise, and a Saigon lng/lat
# read as a pixel is the top-left corner of every sheet in the corpus, so every
# prompt would land in the title block and nothing downstream would fail.
PRIOR_CRS = "source-pixels-y-down"

# Below this, `V` is line work rather than a wash — outline, hatching, or
# lettering. Measured on the 1882 sheet, where ink comes to 10.2% of the paper.
INK_V = 0.55

# The classes a block can be made of. Cream is not among them: it is the
# street surface and the unassigned domain land at once, and separating those
# needs the OCR street names rather than the palette (P2).
PIGMENT_CLASSES = ("salmon", "green", "blue")

# Closing kernel, render px. Load-bearing — see the module docstring for the
# plateau this sits in the middle of.
CLOSE_PX = 5

# A valley only counts as one if it is this much below the shallower of the two
# peaks it sits between. 1882: peaks 25.6% and 8.4%, valley 3.4% — 0.40 of the
# shallower, comfortably inside.
VALLEY_RATIO = 0.60

# Looser on the r - b axis, and the asymmetry is structural rather than a fudge:
# cream is most of the paper while the blue-grey military wash is a handful of
# parcels, so the smaller peak is low and the valley between them is shallow
# *relative to it* by construction. Measured on the 1882 tile the valley is 4.4%
# against a 6.8% cool peak — a ratio of 0.65, real but inside 0.60. A monochrome
# sheet still refuses at this value because it has no second peak at all, which
# --self-check pins.
COOL_VALLEY_RATIO = 0.80

# Area band, m². Same intent as modern_prior's BLOCK_MIN/MAX_AREA_M2: below is
# one tube house, above is open country the outline never closed around.
MIN_AREA_M2 = 200.0
MAX_AREA_M2 = 120_000.0

# Applied only when the sheet's scale is unknown (no annotation, no --mpp).
MIN_AREA_PX = 400

# The sheet is split into this many crops per axis for the split vote. 8 puts
# roughly 750 px a side on a 6051 px render of the 1882 sheet — a few blocks,
# enough for a mode, small enough that a paddy crop abstains instead of
# dragging the median.
VOTE_GRID = 8

RG_BINS = 24
RG_RANGE = (-0.10, 0.26)

# The green/cream pair needs finer bins over a narrower window than the
# cream/salmon pair: those two modes are 0.032 apart, which is two bins at
# RG_BINS and invisible.
RG_FINE_BINS = 48
RG_FINE_RANGE = (-0.05, 0.19)
HULL_RATIO = 0.4
MAX_HULL_POINTS = 600


# ── colour ───────────────────────────────────────────────────────────────────

def rg_histogram(rgb: np.ndarray, bins: int = RG_BINS,
                 rng: tuple[float, float] = RG_RANGE) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of `r - g` over every pixel. The whole polychromy test."""
    a = rgb.astype(np.float32) / 255.0
    return np.histogram(a[..., 0] - a[..., 1], bins=bins, range=rng)


def find_split(counts: np.ndarray, edges: np.ndarray,
               valley_ratio: float = VALLEY_RATIO) -> float | None:
    """The `r - g` trough between the cream mode and the salmon mode.

    None when the sheet is unimodal — a monochrome scan, or a wash so faint
    there is nothing to separate. Returning None is the useful answer: it is
    how this pass declines a sheet it cannot read, in the same spirit as C2's
    colour triage scoring ~0 on a monochrome scan and changing nothing.

    The peak is taken as the global maximum and the second mode is searched
    only to its *right*, because the classes this separates are ordered: cream
    paper sits nearer r == g than any pigment laid on top of it.
    """
    counts = np.asarray(counts, dtype=float)
    if counts.sum() <= 0:
        return None

    p1 = int(np.argmax(counts))
    best = None
    for p2 in range(p1 + 2, len(counts)):
        valley = counts[p1 + 1:p2]
        if valley.size == 0:
            continue
        floor = valley.min()
        # A real valley, not a slope: it has to sit well under the shallower of
        # the two peaks, or every point on a long tail reads as a second mode.
        if floor < valley_ratio * min(counts[p1], counts[p2]) and counts[p2] > 0:
            score = counts[p2] - floor
            if best is None or score > best[0]:
                best = (score, p1 + 1 + int(np.argmin(valley)))
    if best is None:
        return None
    i = best[1]
    return float((edges[i] + edges[i + 1]) / 2.0)


def cool_split(rgb: np.ndarray, split: float, ink_v: float = INK_V) -> float | None:
    """The `r - b` trough separating the blue-grey wash from cream paper.

    A second axis is needed because the pale washes on this sheet are not blue
    or green in any naive sense — the paper's own warmth dominates them.
    Measured on the 1882 tile: the *Parc du Génie* blue-grey reads
    rgb(0.737, 0.713, 0.685), so `b > r` is never true and a channel-order test
    finds nothing. What it does have is a much smaller `r - b` than the street
    beside it — 0.052 against 0.123 — because the blue lifts the B channel.

    Same `find_split`, same refusal: None means this sheet carries no separable
    cool wash, and the class is then simply absent rather than guessed at.
    """
    a = rgb.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    warm = (~(a.max(axis=2) < ink_v)) & ((r - g) <= split)
    if not warm.any():
        return None
    # Negated so the cream mode is the global peak and the cool mode sits to
    # its right, which is the ordering `find_split` searches in.
    counts, edges = np.histogram(-(r - b)[warm], bins=RG_BINS, range=(-0.26, 0.10))
    trough = find_split(counts, edges, valley_ratio=COOL_VALLEY_RATIO)
    return None if trough is None else -trough


def green_split(rgb: np.ndarray, ink_v: float = INK_V) -> float | None:
    """The `r - g` trough on the *left* of the cream peak: the hatched class.

    The 1882 sheet's administrative parcels — *Direction des Travaux Publics*,
    *Hôtel du Procureur Général*, *Conseil de Guerre* — are a pale grey-green
    under fine diagonal hatching, and they are **16 of the 24 `land_plot`
    traces**, so nothing that misses them can score. They were missed at first
    for two compounding reasons:

      - they sit *below* cream on `r - g` (0.027 against 0.059, measured
        against the traces themselves), and `find_split` only ever searches to
        the right of the global peak, which is where salmon is;
      - at `RG_BINS` the two modes are two bins apart and invisible. At
        `RG_FINE_BINS` over the narrower `RG_FINE_RANGE` the structure is
        plain: a green peak at +0.025 (13.4%), a valley at +0.030 (5.0%), the
        cream peak at +0.045 (15.5%).

    Of six candidate axes scored against the traced pixels — `r-g`, `r-b`,
    `g-b`, V, S and local ink density — `r - g` separates best, with 17% of
    hatched pixels inside cream's 10-90 range against 42% for ink density. So
    this is the same axis and the same primitive as everything else here, just
    mirrored: negate, and the left mode becomes a right one for `find_split`.
    """
    a = rgb.astype(np.float32) / 255.0
    live = a.max(axis=2) >= ink_v
    if not live.any():
        return None
    rg = (a[..., 0] - a[..., 1])[live]
    lo, hi = RG_FINE_RANGE
    counts, edges = np.histogram(-rg, bins=RG_FINE_BINS, range=(-hi, -lo))
    trough = find_split(counts, edges)
    return None if trough is None else -trough


def split_by_vote(rgb: np.ndarray, grid: int = VOTE_GRID,
                  axis: str = "rg", ink_v: float = INK_V,
                  rg_split: float | None = None) -> tuple[float | None, int, int]:
    """Find the split on a grid of crops and take the median of the votes.

    Pooling the whole sheet does not work, and the reason is worth keeping:
    a sheet is not homogeneous. On the 1882 Plan Cadastral the *tile* 4142_4032
    is 41% salmon and cleanly bimodal, but over the whole scan — margins,
    neatline, and a colonial town drawn in paddy — salmon is a few percent and
    decays monotonically off the cream peak. `find_split` correctly refuses it.
    The bimodality is a property of the built-up area, not of the paper.

    So each crop votes and the ones with no pigment in them abstain, which
    needs no prior idea of where the built-up area is. Returns
    (split, voted, total); split is None only when *no* crop was bimodal,
    which is still how a monochrome sheet declines.
    """
    h, w = rgb.shape[:2]
    ch, cw = max(h // grid, 1), max(w // grid, 1)
    votes: list[float] = []
    total = 0
    for gy in range(grid):
        for gx in range(grid):
            crop = rgb[gy * ch:(gy + 1) * ch, gx * cw:(gx + 1) * cw]
            if crop.size == 0:
                continue
            total += 1
            if axis == "rg":
                v = find_split(*rg_histogram(crop))
            elif axis == "green":
                v = green_split(crop, ink_v)
            else:
                v = cool_split(crop, rg_split if rg_split is not None else 0.0, ink_v)
            if v is not None:
                votes.append(v)
    if not votes:
        return None, 0, total
    return float(np.median(votes)), len(votes), total


def classify(rgb: np.ndarray, split: float, ink_v: float = INK_V,
             cool: float | None = None, green: float | None = None) -> dict[str, np.ndarray]:
    """Per-pixel class masks. `ink` is taken out first and is not a wash."""
    a = rgb.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rg, rb = r - g, r - b
    ink = a.max(axis=2) < ink_v
    live = ~ink
    salmon = live & (rg > split)
    # Precedence matters and is not arbitrary: the blue-grey military wash and
    # the hatched administrative wash *both* sit low on `r - g` (0.024 and
    # 0.027), so a green-first order swallows the military parcels whole — it
    # took blue from 65 blocks to 1 on this sheet. Blue is claimed first
    # because it is identified on the other axis, `r - b`, where it is distinct
    # (0.052 against cream's 0.123) and green is not.
    rest = live & ~salmon
    blue = rest & (rb < cool) if cool is not None else np.zeros_like(salmon)
    greenm = rest & ~blue & (rg <= green) if green is not None else np.zeros_like(salmon)
    warm = rest & ~blue & ~greenm
    return {
        "ink": ink,
        # Warm and pigmented: the salmon *particulières* wash. The darker
        # red-brown building fills sit inside this class and stay there —
        # measured against the 89 building traces, no colour axis separates a
        # building from the plot it stands on (best is r - g at 0.64 overlap,
        # against 0.17 for the green/cream pair). Buildings on this sheet are
        # outlines, not fills: the only thing that moves is ink density, 0.182
        # inside a building trace against 0.067 on open plot. Splitting them is
        # SAM2's job, not a threshold's.
        "salmon": salmon,
        "blue": blue,
        # The hatched administrative parcels, found on the left of the cream
        # peak — see `green_split`. Absent, not guessed, when no trough is
        # measured on a sheet.
        "green": greenm,
        # Everything else warm: street surface and unassigned domain land at
        # once, separated by name in P2 rather than by palette here.
        "cream": warm,
    }


def dominant_class(masks: dict[str, np.ndarray], sel: np.ndarray,
                   sl: tuple | None = None) -> str:
    """The pigment covering most of one component.

    Only the pigmented classes are candidates: a block is a component *of* the
    pigment union, so cream is not an answer here even where a closing has
    swallowed some paper inside the block.

    `sl` is the component's bounding slice, so the masks are cropped to it
    rather than a full-frame array being allocated per component — at a few
    thousand components on a 4096 px sheet that difference is the run.
    """
    best, share = "salmon", -1.0
    for name in PIGMENT_CLASSES:
        m = masks[name][sl] if sl is not None else masks[name]
        n = float((m & sel).sum())
        if n > share:
            best, share = name, n
    return best


# ── geometry ─────────────────────────────────────────────────────────────────

def component_polygon(sub: np.ndarray, ox: int, oy: int, scale: float,
                      ratio: float = HULL_RATIO):
    """One component mask → a shapely polygon in full-image source pixels.

    The ring comes from a concave hull over the component's boundary pixels,
    decimated to `MAX_HULL_POINTS`. A block is a trapezoid or an L; a convex
    hull swallows the notch of the L and a per-pixel trace carries a thousand
    vertices SAM2 will never look at, since `blocks_to_seeds` reads the bounds
    and throws the ring away. The hull is the middle that costs one call.
    """
    inner = ndimage.binary_erosion(sub, np.ones((3, 3), bool))
    ys, xs = np.nonzero(sub & ~inner)
    if len(xs) < 4:
        return None
    if len(xs) > MAX_HULL_POINTS:
        step = len(xs) // MAX_HULL_POINTS + 1
        xs, ys = xs[::step], ys[::step]

    pts = np.column_stack([(xs + ox) * scale, (ys + oy) * scale]).astype(float)
    try:
        geom = shapely.concave_hull(shapely.MultiPoint(pts), ratio=ratio)
    except Exception:
        geom = None
    if geom is None or geom.is_empty or geom.geom_type != "Polygon":
        # Collinear or degenerate: a box still prompts, and is still scoreable.
        x0, y0, x1, y1 = pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()
        if x1 <= x0 or y1 <= y0:
            return None
        geom = shapely.box(x0, y0, x1, y1)
    geom = geom.simplify(max(scale, 1.0))
    return geom if geom.geom_type == "Polygon" and not geom.is_empty else None


def blocks_from_colour(rgb: np.ndarray, split: float, scale: float,
                       *, mpp: float | None, close: int = CLOSE_PX,
                       min_area_m2: float = MIN_AREA_M2,
                       max_area_m2: float = MAX_AREA_M2,
                       ink_v: float = INK_V,
                       cool: float | None = None,
                       green: float | None = None) -> tuple[list[dict], dict[str, int]]:
    """Pigment → close → connected components → polygons, classified and banded.

    Returns (features, dropped) where a feature is {geom, feature_type,
    area_px}. The union of the pigmented classes is what gets componented: the
    street between two blocks is cream and wide, the line between two buildings
    inside one block is ink and thin, so a closing in between rejoins the block
    and leaves the street alone. Cream parcels are deliberately absent — see
    the module docstring, and P2.
    """
    masks = classify(rgb, split, ink_v, cool, green)
    pigment = np.zeros(rgb.shape[:2], bool)
    for name in PIGMENT_CLASSES:
        pigment |= masks[name]
    if close > 0:
        pigment = ndimage.binary_closing(pigment, np.ones((close, close), bool))

    labels, n = ndimage.label(pigment)
    dropped: dict[str, int] = {"too small": 0, "too large": 0, "no ring": 0}
    out: list[dict] = []
    if n == 0:
        return out, dropped

    px_area_m2 = (mpp * scale) ** 2 if mpp else None
    for sl, idx in zip(ndimage.find_objects(labels), range(1, n + 1)):
        if sl is None:
            continue
        sub = labels[sl] == idx
        n_px = int(sub.sum())
        # Cheap reject before any geometry: source px² if the scale is known,
        # render px² if it is not.
        if px_area_m2 is not None:
            area_m2 = n_px * px_area_m2
            if area_m2 < min_area_m2:
                dropped["too small"] += 1
                continue
            if area_m2 > max_area_m2:
                dropped["too large"] += 1
                continue
        elif n_px < MIN_AREA_PX:
            dropped["too small"] += 1
            continue

        geom = component_polygon(sub, sl[1].start, sl[0].start, scale)
        if geom is None:
            dropped["no ring"] += 1
            continue
        out.append({
            "geom": geom,
            "feature_type": dominant_class(masks, sub, sl),
            "area_px": round(float(geom.area), 1),
        })
    return out, dropped


# ── output ───────────────────────────────────────────────────────────────────

def write_outputs(out_dir: Path, feats: list[dict], extra: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = {
        "type": "FeatureCollection",
        "crs": PRIOR_CRS,
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(shapely.to_geojson(f["geom"])),
                "properties": {"area_px": f["area_px"], "feature_type": f["feature_type"]},
            }
            for f in feats
        ],
        **extra,
    }
    (out_dir / "blocks.geojson").write_text(json.dumps(doc), encoding="utf-8")

    # The same polygons in seg_eval.py's shape, so a run is scoreable the day
    # it is produced rather than after somebody writes a converter.
    run = {
        "source": "colour-blocks",
        **extra,
        "polygons": [
            {
                "coords": [[round(x, 1), round(y, 1)]
                           for x, y in shapely.get_coordinates(f["geom"]).tolist()],
                "feature_type": f["feature_type"],
            }
            for f in feats
        ],
    }
    (out_dir / "blocks.run.json").write_text(json.dumps(run), encoding="utf-8")
    print(f"  → {out_dir / 'blocks.geojson'}  ({len(feats)} features)")
    print(f"  → {out_dir / 'blocks.run.json'}  (seg_eval input)")


def print_census(counts: np.ndarray, edges: np.ndarray, split: float | None) -> None:
    total = counts.sum() or 1
    peak = counts.max() or 1
    print("\nr - g histogram:")
    for i, c in enumerate(counts):
        bar = "#" * int(60 * c / peak)
        mark = "  <- split" if split is not None and edges[i] <= split < edges[i + 1] else ""
        print(f"  {edges[i]:+.3f} {bar:<60} {100 * c / total:5.1f}%{mark}")
    if split is None:
        print("\nunimodal — no second mode above the global peak.")
        print("This sheet is not polychrome enough for a colour block pass.")
    else:
        print(f"\nsplit at r - g = {split:+.3f}")


# ── self-check ───────────────────────────────────────────────────────────────

# Read off the 1882 tile rather than invented, so the fixture exercises the
# real separations: cream street, salmon wash, and the blue-grey that a naive
# `b > r` test cannot see.
CREAM = (208, 196, 177)      # r-g +0.047  r-b +0.122
SALMON = (195, 169, 149)     # r-g +0.102  r-b +0.180
BLUEGREY = (188, 182, 175)   # r-g +0.024  r-b +0.051
HATCHED = (198, 191, 170)    # r-g +0.027  r-b +0.110 — the administrative wash
INK = (50, 46, 42)


def _synthetic() -> np.ndarray:
    """Cream streets, four washed parcels, ink building lines inside them.

    Built to the shape the real sheet has, so the fixture pins the mechanism
    rather than a happy case:

      - the gap between parcels is 20 px of cream — the street;
      - each parcel is cut into four by 2 px ink lines — the building lines,
        which `--close` has to bridge and a street-width gap must survive;
      - one parcel is cream, the same tone as the street, and must therefore
        *not* appear in the output (P2's job, not P1's).
    """
    img = np.full((200, 200, 3), CREAM, np.uint8)                 # street
    for x0, x1, y0, y1, col in [
        (10, 90, 10, 90, SALMON),
        (110, 190, 10, 90, SALMON),
        (10, 90, 110, 190, HATCHED),    # administrative parcel
        (110, 190, 110, 190, BLUEGREY),
    ]:
        img[y0:y1, x0:x1] = col
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        img[y0:y1, mx:mx + 2] = INK            # building lines, 2 px
        img[my:my + 2, x0:x1] = INK
    return img


def _self_check() -> None:
    img = _synthetic()
    counts, edges = rg_histogram(img)
    split = find_split(counts, edges)
    assert split is not None, "synthetic sheet is bimodal and must produce a split"
    assert 0.02 < split < 0.14, f"split {split} outside the cream/salmon gap"

    # The cool wash is invisible on channel order and must be found on r - b.
    cool = cool_split(img, split)
    assert cool is not None, "blue-grey vs cream is separable on r - b and was not found"
    assert 0.05 < cool < 0.12, f"cool split {cool} outside the blue-grey/cream gap"

    gsplit = green_split(img)
    assert gsplit is not None, "the hatched wash sits left of cream and was not found"

    feats, dropped = blocks_from_colour(img, split, scale=1.0, mpp=None, cool=cool, green=gsplit)
    kinds = sorted(f["feature_type"] for f in feats)
    # Four parcels, each whole. The street is never a block.
    assert len(feats) == 4, f"expected 4 parcels, got {len(feats)}: {kinds} {dropped}"
    assert kinds.count("salmon") == 2, f"expected 2 salmon, got {kinds}"
    assert kinds.count("blue") == 1, f"blue-grey not recovered on r - b: {kinds}"
    assert kinds.count("green") == 1, f"hatched parcel not recovered on r - g: {kinds}"
    assert "cream" not in kinds, f"cream is not a block: {kinds}"

    # Precedence, pinned: blue-grey and the hatched wash both sit low on r - g,
    # so a green-first order eats the military parcel. On the real sheet that
    # took blue from 65 blocks to 1.
    m = classify(img, split, cool=cool, green=gsplit)
    assert not (m["green"] & m["blue"]).any(), "green and blue must not overlap"
    assert m["blue"].sum() > 0, "green claimed the blue-grey parcel"

    # Without the cool split there is no blue class at all — the documented
    # decline, not a silent reclassification of the wash as cream.
    nocool, _ = blocks_from_colour(img, split, scale=1.0, mpp=None, cool=None)
    assert len(nocool) == 2, f"no cool split must mean no blue block, got {len(nocool)}"

    # The mechanism, pinned from the other side: without the closing, the ink
    # lines cut each parcel into four. If this ever stops failing, --close has
    # stopped being what rejoins a block and the default is measuring nothing.
    frag, _ = blocks_from_colour(img, split, scale=1.0, mpp=None, close=0, cool=cool, green=gsplit)
    assert len(frag) == 16, f"expected 4 quarters x 4 parcels without closing, got {len(frag)}"

    # ...and the street survives a closing far wider than the building lines.
    wide, _ = blocks_from_colour(img, split, scale=1.0, mpp=None, close=15, cool=cool, green=gsplit)
    assert len(wide) == 4, f"close=15 bridged a 20 px street: {len(wide)} blocks"

    # A monochrome scan must decline, not return noise.
    grey = np.full((200, 200, 3), 210, np.uint8)
    grey[40:160, 40:160] = 120
    assert find_split(*rg_histogram(grey)) is None, "monochrome sheet must refuse"
    # ...on the cool axis too, at its looser ratio.
    assert cool_split(grey, 0.072) is None, "monochrome sheet must refuse the cool split"
    assert green_split(grey) is None, "monochrome sheet must refuse the green split"

    # The ceiling of the whole method, pinned rather than left to be
    # rediscovered: two parcels separated by an alley *narrower* than the
    # closing kernel merge into one block, and nothing about the output says
    # so. This is why --close must stay well under the sheet's street width,
    # and why the area band is the guard that catches it when it does not.
    alley = np.full((200, 200, 3), (232, 222, 202), np.uint8)
    alley[10:190, 10:98] = (236, 196, 186)
    alley[10:190, 102:190] = (236, 196, 186)      # 4 px of cream between them
    merged, _ = blocks_from_colour(alley, 0.08, scale=1.0, mpp=None, close=9)
    assert len(merged) == 1, f"a 4 px alley should not survive close=9; got {len(merged)}"
    apart, _ = blocks_from_colour(alley, 0.08, scale=1.0, mpp=None, close=3)
    assert len(apart) == 2, f"a 4 px alley should survive close=3; got {len(apart)}"

    # Areas are filtered in m² when the sheet's scale is known.
    f3, d3 = blocks_from_colour(img, split, scale=1.0, mpp=1.0, min_area_m2=100_000, cool=cool, green=gsplit)
    assert len(f3) == 0 and d3["too small"] == 4, f"m² band not applied: {d3}"

    # The GeoJSON must carry the token to_sam2_seeds refuses on.
    assert PRIOR_CRS == "source-pixels-y-down"
    print("colour_blocks self-check OK")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map-id", help="maps.id UUID; the IIIF base and scale are read from it")
    p.add_argument("--iiif-base", help="IIIF image base URL (overrides --map-id lookup)")
    p.add_argument("--local-image", help="read this file instead of fetching (no network)")
    p.add_argument("--render", type=int, default=4096,
                   help="longest edge of the working image. Ink lines are 2-3 source px: "
                        "too small and the outlines dissolve and blocks merge (default 4096)")
    p.add_argument("--rg-split", type=float, help="override the auto-detected r-g trough")
    p.add_argument("--cool-split", type=float,
                   help="override the auto-detected r-b trough (blue-grey vs cream)")
    p.add_argument("--ink", type=float, default=INK_V, help=f"V below this is line work (default {INK_V})")
    p.add_argument("--close", type=int, default=CLOSE_PX,
                   help="morphological closing, render px. Rejoins a block across its "
                        f"printed building lines; the street is far too wide to bridge "
                        f"(default {CLOSE_PX})")
    p.add_argument("--min-m2", type=float, default=MIN_AREA_M2)
    p.add_argument("--max-m2", type=float, default=MAX_AREA_M2)
    p.add_argument("--mpp", type=float, help="metres per source pixel; read from the annotation if omitted")
    p.add_argument("--census", action="store_true", help="print the histogram and stop")
    p.add_argument("--out", help="output directory for blocks.geojson + blocks.run.json")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()

    if args.self_check:
        _self_check()
        return 0
    if not (args.local_image or args.iiif_base or args.map_id):
        p.error("one of --map-id, --iiif-base or --local-image is required")

    from PIL import Image

    if args.local_image:
        Image.MAX_IMAGE_PIXELS = None
        pil = Image.open(args.local_image).convert("RGB")
        source_w = pil.width
        if pil.width > args.render:
            pil = pil.resize((args.render, round(pil.height * args.render / pil.width)))
    else:
        from iiif_tiles import fetch_crop, get_image_info, get_iiif_base_from_supabase

        base = args.iiif_base or get_iiif_base_from_supabase(args.map_id)
        if not base:
            print(f"no IIIF base for {args.map_id}", file=sys.stderr)
            return 1
        info = get_image_info(base)
        source_w, source_h = int(info["width"]), int(info["height"])
        print(f"sheet {source_w} x {source_h}, rendering to {args.render}")
        pil = fetch_crop(base, 0, 0, source_w, source_h, size=args.render, fit=True)

    rgb = np.asarray(pil, dtype=np.uint8)[..., :3]
    scale = source_w / rgb.shape[1]
    print(f"working image {rgb.shape[1]} x {rgb.shape[0]}, scale {scale:.2f} source px per render px")

    counts, edges = rg_histogram(rgb)
    if args.rg_split is not None:
        split, voted, total = args.rg_split, 0, 0
    else:
        split, voted, total = split_by_vote(rgb)
        if total:
            print(f"r - g split by vote: {voted}/{total} crops bimodal")
    if args.census or split is None:
        print_census(counts, edges, split)
        if split is not None:
            print("(the histogram above is the whole sheet, pooled; the split is "
                  "the median of the crops that voted)")
        return 0 if args.census else 2

    ink_fraction = float((rgb.astype(np.float32).max(axis=2) / 255.0 < args.ink).mean())
    print(f"ink {100 * ink_fraction:.1f}% of the paper")
    green, gvoted, gtotal = split_by_vote(rgb, axis="green", ink_v=args.ink)
    if gtotal:
        print(f"green split by vote: {gvoted}/{gtotal} crops trimodal")
    print(f"green split r - g = {green:+.3f}" if green is not None
          else "no separable hatched/green wash on this sheet")

    if args.cool_split is not None:
        cool = args.cool_split
    else:
        cool, cvoted, ctotal = split_by_vote(rgb, axis="cool", ink_v=args.ink, rg_split=split)
        if ctotal:
            print(f"r - b split by vote: {cvoted}/{ctotal} crops bimodal")
    print(f"cool split r - b = {cool:+.3f}" if cool is not None
          else "no separable cool wash on this sheet")

    mpp = args.mpp
    if mpp is None and args.map_id:
        try:
            import scale as scale_mod
            ann = scale_mod.annotation_for_map(args.map_id)
            fit = scale_mod.metres_per_pixel(ann) if ann else None
            if fit:
                mpp = (fit.mx + fit.my) / 2.0
                print(f"scale {mpp:.4f} m per source px from {fit.n_gcps} control points")
        except Exception as exc:                                  # noqa: BLE001
            print(f"  (no scale from the annotation: {exc})")
    if mpp is None:
        print(f"  no sheet scale — filtering at {MIN_AREA_PX} render px² instead of m²")

    feats, dropped = blocks_from_colour(
        rgb, split, scale, mpp=mpp, close=args.close,
        min_area_m2=args.min_m2, max_area_m2=args.max_m2, ink_v=args.ink, cool=cool,
        green=green,
    )
    for reason, n in sorted(dropped.items()):
        if n:
            print(f"  dropped {n} as {reason}")
    kinds: dict[str, int] = {}
    for f in feats:
        kinds[f["feature_type"]] = kinds.get(f["feature_type"], 0) + 1
    print(f"{len(feats)} blocks: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    if args.out:
        write_outputs(Path(args.out), feats, {
            "source": "colour-blocks",
            "rg_split": round(split, 4),
            "cool_split": round(cool, 4) if cool is not None else None,
            "green_split": round(green, 4) if green is not None else None,
            "render": int(rgb.shape[1]),
            "ink_fraction": round(ink_fraction, 4),
            "block_area_m2": [args.min_m2, args.max_m2] if mpp else None,
        })
    else:
        print("(no --out, nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
