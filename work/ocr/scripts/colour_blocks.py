#!/usr/bin/env python3
"""City blocks read off a polychrome sheet's own ink, in its own pixel grid.

    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --census
    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --out work/ocr/outputs/<uuid>/colour
    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --no-cream --no-drop-water --out <dir>
    python work/ocr/scripts/colour_blocks.py --self-check          # no network, no data

The second line is the full pass — cream parcels, the legend key, the furniture,
water and sliver drops and the oversize re-cut are all **on by default**, because
that is the run every number in `work/ocr/EVAL-BASELINE.md` was measured on. Each
has a `--no-...` escape that restores the run it names, and each escape's help
text carries what turning it off costs.

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

**Cream is a parcel, not a block, and needs `--cream` and its own threshold.**
Street surface and unassigned *non affectées* land are the same tone, so cream
cannot be componented the way a block is. The recorded reason it "does not
work" — one component of 11.91 km², 100% of the mask, 0 blocks in the band —
was measured at `INK_V = 0.55`, and that turned out to be the whole of the
problem: at 0.55 a 2 px cadastral divider is grey rather than ink, so every
parcel leaks into the street. Swept up to the sheet's own paper tone
(`cream_ink`) the mask falls apart into parcels instead, with the street left
as the one oversized component the area band already drops. On the 1882 sheet
that is 850 parcels at V < 0.80, and it takes land_plot IoU from 0.247 to
0.346 against a 0.262 target. The pass runs at the same render as the block
pass and adds about 4 s.

The two passes are not the same measurement and must not share knobs: at 0.80
the salmon class shatters into 10,078 components (20 in band) and the hatched
green vanishes entirely, because hatching *is* ink at that threshold.

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
  --cream-ink the cream pass's own ink threshold, swept by default rather than
              fixed — see `cream_ink`, and CREAM_INK_RANGE for why a constant
              carried between sheets is the failure mode this pass was hiding.
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
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from PIL import Image, ImageDraw
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

# The classes a block can be made of. Cream is not among them: a block is a
# component *of* the pigment, and cream is street surface and unassigned domain
# land at once. The cream pass below finds those separately, and at a threshold
# of its own — see CREAM_INK_RANGE.
PIGMENT_CLASSES = ("salmon", "green", "blue")

# The cream pass sweeps its ink threshold over this range and keeps the value
# that puts the most *area* in the band. Sweeping rather than fixing is the
# lesson of the pass itself: INK_V = 0.55 was carried over from another sheet
# and is exactly what made cream look unsplittable. At 0.55 the 1882 sheet
# returns one component holding 98% of the mask; at 0.75-0.85 it returns 660-820
# parcels, and above the paper's own V peak (0.90 here) the paper becomes ink
# and the band empties. The upper bound is therefore read off the sheet, not
# written down.
CREAM_INK_RANGE = (0.55, 0.05)      # (start, step); the stop is the paper peak
CREAM_INK_MARGIN = 0.03             # keep clear of the peak itself

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
    # Replacing this precedence with nearest-legend-swatch classification, the
    # way NYPL's map vectorizer does it, was tried on 2026-09-18 and scored
    # worse — land_plot 0.346 -> 0.307 with *more* predictions. A swatch is
    # solid ink and a wash is that ink diluted, and even with the dilution
    # fitted (alpha 0.60, 91% agreement with these troughs) a fifth class
    # interleaved with the fourth fragments the blocks. Journal: § Nearest-
    # legend-swatch. Do not re-attempt without a different mechanism.
    #
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
                   sl: tuple | None = None,
                   classes: tuple[str, ...] = PIGMENT_CLASSES) -> str:
    """The pigment covering most of one component.

    Only the pigmented classes are candidates: a block is a component *of* the
    pigment union, so cream is not an answer here even where a closing has
    swallowed some paper inside the block.

    `sl` is the component's bounding slice, so the masks are cropped to it
    rather than a full-frame array being allocated per component — at a few
    thousand components on a 4096 px sheet that difference is the run.
    """
    best, share = classes[0], -1.0
    for name in classes:
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
                       green: float | None = None,
                       classes: tuple[str, ...] = PIGMENT_CLASSES,
                       recut: bool = False,
                       water: list[tuple[float, float]] | None = None,
                       ) -> tuple[list[dict], dict[str, int]]:
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
    for name in classes:
        pigment |= masks[name]
    if close > 0:
        pigment = ndimage.binary_closing(pigment, np.ones((close, close), bool))

    labels, n = ndimage.label(pigment)
    vmax = rgb.astype(np.float32).max(axis=2) / 255.0
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
                # Never on cream. An oversized cream component is the street
                # network — one connected surface by construction — and its
                # being over the cap is the guard that drops it, not a merge
                # failure to be rescued. Re-cutting it returns 240 street
                # fragments and costs 100 s.
                # Water is the other honest oversize, and unlike a merge it can
                # be named: the sheet labels its own river. An oversized
                # component holding a `hydrology` label is the Rivière de Saigon
                # or an arroyo, and the cap was right about it — re-cutting it
                # returns the water tint as dozens of blue "blocks". This is the
                # one place a sparse label fences a region instead of merely
                # locating it: the component *is* the fence.
                parts = (recut_oversized(sub, vmax[sl], px_area_m2, min_area_m2, max_area_m2)
                         if recut else [])
                if not parts:
                    dropped["too large"] += 1
                    continue
                for part in parts:
                    # The water test goes on the *parts*, not the parent. On this
                    # sheet the naval quarter's blue-grey is the same tint as the
                    # river and touches it along the quay, so parent and river are
                    # one 397,560 m² component: testing the parent drops the
                    # arsenal with the water (blue 218 -> 41, measured). After the
                    # re-cut they are separate pieces and the label lands in one.
                    if water and _holds_point(part, sl, scale, water):
                        dropped["water"] = dropped.get("water", 0) + 1
                        continue
                    geom = component_polygon(part, sl[1].start, sl[0].start, scale)
                    if geom is None:
                        dropped["no ring"] += 1
                        continue
                    out.append({
                        "geom": geom,
                        "feature_type": dominant_class(masks, part, sl, classes),
                        "area_px": round(float(geom.area), 1),
                    })
                dropped["recut"] = dropped.get("recut", 0) + 1
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
            "feature_type": dominant_class(masks, sub, sl, classes),
            "area_px": round(float(geom.area), 1),
        })
    return out, dropped



def _holds_point(mask: np.ndarray, sl: tuple, scale: float,
                 pts: list[tuple[float, float]]) -> bool:
    """Does this component mask contain any of `pts`, given in source pixels?"""
    for x, y in pts:
        r, c = int(y / scale) - sl[0].start, int(x / scale) - sl[1].start
        if 0 <= r < mask.shape[0] and 0 <= c < mask.shape[1] and mask[r, c]:
            return True
    return False


def _kept_as(labels: np.ndarray, sl, idx: int, scale: float, feats: list[dict],
             tree) -> tuple[float, int | None]:
    """(overlap share, index in `feats`) for the polygon this component became.

    Half of `explain_at`'s job is not accusing a filter of eating a block that
    is sitting in the output. The share is over the component's own polygon, so
    a block `subtract_blocks` cut back reads as a partial rather than as a miss.
    """
    if sl is None or tree is None:
        return 0.0, None
    g = component_polygon(labels[sl] == idx, sl[1].start, sl[0].start, scale)
    if g is None or g.area <= 0:
        return 0.0, None
    share, best = max(((feats[i]["geom"].intersection(g).area / g.area, int(i))
                       for i in tree.query(g)), default=(0.0, None))
    return (share, best) if share >= 0.5 else (share, None)


def explain_at(rgb: np.ndarray, split: float, scale: float, pt: tuple[float, float],
               feats: list[dict], *, mpp: float | None, close: int = CLOSE_PX,
               min_area_m2: float = MIN_AREA_M2, max_area_m2: float = MAX_AREA_M2,
               ink_v: float = INK_V, cool: float | None = None,
               green: float | None = None, probe: float = 120.0,
               classes: tuple[str, ...] = PIGMENT_CLASSES) -> list[str]:
    """Why is there (or isn't there) a polygon around this source pixel?

    Three sessions in a row have opened with "X has no polygon" — the Arsenal's
    dockyard apron, `Prisons`, `Nouveau Palais de Justice` — and each time the
    answer was reached by hand: classify the pixel, find its component, measure
    it, read it against the band. That is mechanical, so it is a flag.

    It reports a *neighbourhood*, `probe` source px a side, not a pixel, and
    both halves of that are load-bearing:

    - A label's centre usually lands on the label's own lettering, which is
      ink and belongs to no component at all. `Prisons` reads exactly that way.
    - A single containing polygon is not coverage. The `ARSENAL DE LA MARINE`
      label sits on the *edge* of the block above the boulevard, so a
      point-in-polygon test calls it covered while the yard it names is empty.
      The covered share of the probe box is what tells those two apart.

    The covered share is answered from `feats`, the run's real output, so it
    can never disagree with the run. Only the verdicts on the components
    re-derive anything, and they re-derive it from the same `classify`,
    closing and labelling the pass uses.

    An in-band component is matched back to the polygon it became before any
    filter is named, because usually it became one. `Prisons` reads as a
    3,385 px component "dropped later", and it is not dropped at all: it is the
    5,739 m2 block beside the label, which simply does not contain the label's
    own pixel. Naming four filters there is a false accusation, and it stood in
    the queue for a session. A filter added to `blocks_from_colour` and not
    named here still shows up honestly, as a component that is in band and
    matches nothing in the output.
    """
    x, y = pt
    out = [f"at source px ({x:.0f}, {y:.0f}), probing {probe:.0f} px around it:"]
    r, c = int(y / scale), int(x / scale)
    if not (0 <= r < rgb.shape[0] and 0 <= c < rgb.shape[1]):
        return out + ["  off the sheet"]

    # Covered share of the probe box: an 11x11 grid of source-px samples.
    half = probe / 2.0
    grid = [(x + half * i / 5.0, y + half * j / 5.0)
            for i in range(-5, 6) for j in range(-5, 6)]
    tree = shapely.STRtree([f["geom"] for f in feats]) if feats else None
    covered, owners = 0, {}
    for gx, gy in grid:
        p = shapely.Point(gx, gy)
        for i in (tree.query(p) if tree is not None else []):
            if shapely.contains_xy(feats[i]["geom"], gx, gy):
                covered += 1
                owners[i] = owners.get(i, 0) + 1
                break
    share = covered / len(grid)
    out.append(f"  {share:.0%} of that box is covered by {len(owners)} polygon(s)")
    for i, n in sorted(owners.items(), key=lambda kv: -kv[1])[:3]:
        g = feats[i]["geom"]
        a = f"{g.area * mpp ** 2:,.0f} m²" if mpp else f"{g.area:,.0f} px²"
        out.append(f"    {n * 100 // len(grid):3d}%  {feats[i]['feature_type']}, {a}, "
                   f"outline circularity {outline_circularity(g):.3f}")
    if share > 0.95:
        return out

    masks = classify(rgb, split, ink_v, cool, green)
    here = [n for n in masks if masks[n][r, c]]
    out.append(f"  the centre pixel is {', '.join(here) or 'nothing'}"
               + ("" if set(here) & set(classes)
                  else f" — not one of {classes}, so the block pass never sees it"))
    pigment = np.zeros(rgb.shape[:2], bool)
    for name in classes:
        pigment |= masks[name]
    if close > 0:
        pigment = ndimage.binary_closing(pigment, np.ones((close, close), bool))
    labels, _ = ndimage.label(pigment)
    win = labels[max(0, int((y - half) / scale)):int((y + half) / scale) + 1,
                 max(0, int((x - half) / scale)):int((x + half) / scale) + 1]
    ids = [i for i in np.unique(win) if i]
    if not ids:
        return out + ["  no pigment component anywhere in the box, even after the closing"]
    sizes = np.bincount(labels.ravel())
    objs = None
    out.append(f"  {len(ids)} pigment component(s) in the box:")
    for idx in sorted(ids, key=lambda i: -sizes[i])[:4]:
        n_px = int(sizes[idx])
        if mpp is None:
            verdict = ("DROPPED too small" if n_px < MIN_AREA_PX else "in band")
            out.append(f"    {idx}: {n_px:,} px  {verdict} (no sheet scale)")
            continue
        area = n_px * (mpp * scale) ** 2
        if area < min_area_m2:
            verdict = f"DROPPED too small, < {min_area_m2:,.0f} m²"
        elif area > max_area_m2:
            verdict = f"DROPPED too large, > {max_area_m2:,.0f} m² — --recut re-cuts it"
        else:
            if objs is None:
                objs = ndimage.find_objects(labels)
            share, i = _kept_as(labels, objs[idx - 1], idx, scale, feats, tree)
            verdict = (f"KEPT as a {feats[i]['geom'].area * mpp ** 2:,.0f} m² "
                       f"{feats[i]['feature_type']} polygon ({share:.0%} of the "
                       f"component) — the probe centre falls outside it"
                       if i is not None else
                       "in band and in no polygon — no ring, the furniture box, "
                       "the water test or the sliver filter")
        out.append(f"    {idx}: {n_px:,} px = {area:,.0f} m²  {verdict}")
    return out


def labels_matching(map_id: str, needle: str,
                    run_id: str | None = None) -> list[tuple[str, str, float, float]]:
    """(text, category, x, y) for every OCR label whose text contains `needle`.

    Every match, deliberately. Several labels on the 1882 sheet have duplicate
    `ocr_labels` rows at different positions, and which one you take
    changes the verdict — a check built on "the first row" is not reproducible
    and the journal has a 6/10-against-7/10 to prove it.
    """
    low = needle.lower()
    return [(r["text"], r.get("category") or "?",
             r["global_x"] + (r["global_w"] or 0) / 2.0,
             r["global_y"] + (r["global_h"] or 0) / 2.0)
            for r in ocr_rows(map_id, run_id)
            if r.get("global_x") is not None and low in (r.get("text") or "").lower()]


def recut_oversized(sub: np.ndarray, v: np.ndarray, px_area_m2: float | None,
                    min_area_m2: float, max_area_m2: float,
                    probe_range: tuple[float, float] = CREAM_INK_RANGE):
    """A component over the area cap, re-cut at a higher ink threshold.

    The cap exists to catch a merge failure — an outline the closing bridged, or
    a wash that never closed. But a *legitimate* single-tint domain also trips
    it: the naval quarter on the 1882 sheet is one continuous blue-grey wash
    across many blocks and the streets between them, 397,560 m² against a
    120,000 cap, and until now the run dropped it whole. What the reader then
    sees is the cream pass claiming the leftovers, so the quarter comes back
    outlined in the wrong class with ragged edges.

    Dropping it is throwing away the sheet's own answer. The lines inside it are
    printed, they are simply lighter than the block outlines the low threshold
    is tuned for, so the same sweep that splits cream splits this: on that
    quarter, V ≥ 0.65 gives 37 banded components holding 295,678 m² of the
    397,560 — three quarters of it recovered, with the largest now under the cap.

    Returns a list of masks, empty when no threshold rescues it (then the caller
    drops it as before, and that is still the honest answer for a real merge).

    The cost this used to carry — "river false positives" — was paid off by the
    pixel water test: the parts that land on the river are dropped by
    `--drop-water`, and the parts that land on the Arsenal are kept because a
    part *is* a compact polygon and `land_mask` bounds the region at it. That
    is what finally covers the dockyard apron, which had no polygon at all and
    so was claimed as water at 1.00. What the re-cut still costs is one green
    block over the Abattoir's grounds catching a `waterway` trace inside them
    (cover 0.64 -> 0.99) and land_plot mean 0.350 -> 0.331.
    """
    if px_area_m2 is None:
        return []
    best, best_area = None, 0.0
    start, step = probe_range
    stop = float(v[sub].max()) - CREAM_INK_MARGIN if sub.any() else start
    t = start
    while t < stop:
        lab, n = ndimage.label(sub & (v >= t))
        if n:
            sizes = np.bincount(lab.ravel())
            sizes[0] = 0
            areas = sizes * px_area_m2
            sel = (areas >= min_area_m2) & (areas <= max_area_m2)
            area = float(areas[sel].sum())
            if area > best_area:
                best, best_area = (lab, np.where(sel)[0]), area
        t += step
    if best is None:
        return []
    lab, keep = best
    return [lab == i for i in keep]


# ── cream ────────────────────────────────────────────────────────────────────

def paper_peak(rgb: np.ndarray) -> float:
    """The sheet's own paper tone, as the mode of V. The ceiling on the ink sweep.

    An ink threshold at or above this calls the paper ink: on the 1882 sheet
    V=0.90 takes the ink fraction from 26% to 81% and the band empties. Reading
    it off the sheet is what makes the sweep survive a darker scan, browner
    paper or a different JPEG — which is most of what "another era" means at
    the pixel level.
    """
    hist, edges = np.histogram(rgb.max(axis=2) / 255.0, bins=100, range=(0.0, 1.0))
    return float(edges[int(hist.argmax())])


def cream_ink(rgb: np.ndarray, split: float, *, cool: float | None, green: float | None,
              px_area_m2: float | None, min_area_m2: float, max_area_m2: float,
              probe: int = 4) -> tuple[float, list[tuple[float, int]]]:
    """The ink threshold that splits cream into the most banded parcel area.

    The invariant the sheet supplies, and the whole reason this can be measured
    without ground truth: a street network is *one* component and parcels are
    many. Too low a threshold and the dividers are grey, so every parcel welds
    to the street; too high and the paper joins the ink and there is nothing
    left. In between is a plateau, and its argmax is the answer.

    Swept on a `probe`-times downscaled copy — a dozen `classify` calls on a
    quarter-scale sheet, well under a second. Returns (threshold, curve).
    """
    small = rgb[::probe, ::probe]
    cell = (px_area_m2 * probe * probe) if px_area_m2 else None
    stop = paper_peak(small) - CREAM_INK_MARGIN
    start, step = CREAM_INK_RANGE
    best, best_area, curve = start, -1.0, []
    v = start
    while v < stop:
        masks = classify(small, split, v, cool, green)
        labels, n = ndimage.label(masks["cream"])
        if n:
            sizes = np.bincount(labels.ravel())
            sizes[0] = 0
            areas = sizes * cell if cell else sizes * (probe * probe)
            lo = min_area_m2 if cell else MIN_AREA_PX
            hi = max_area_m2 if cell else float("inf")
            sel = (areas >= lo) & (areas <= hi)
            area = float(areas[sel].sum())
            curve.append((round(v, 2), int(sel.sum())))
            if area > best_area:
                best, best_area = v, area
        else:
            curve.append((round(v, 2), 0))
        v += step
    return best, curve



def subtract_blocks(feats: list[dict], min_keep: float = 0.15) -> tuple[list[dict], int, int]:
    """Cut the pigmented blocks out of the cream hulls that closed over them.

    A cream component is often the paper *around* a block — a street corner, a
    margin, an L. `component_polygon` returns a concave hull, and the hull of a
    ring is a disc, so that component comes back as a polygon lying on top of
    the block it surrounds. Measured on the 1882 sheet: 188 of 840 cream
    polygons were more than a quarter pigment inside their own outline, and it
    is the first thing a reader notices in an overlay.

    The blocks are already in hand from the first pass, so the fix needs no new
    geometry: subtract their union. A cream polygon reduced to almost nothing
    was a block with a rim, not a parcel, and is dropped. Scored: land_plot
    0.346 → 0.350 with 38 fewer predictions, which under a best-match metric is
    an improvement twice over.

    ponytail: this leans on the block hulls being roughly right, because it
    subtracts hull from hull. A true raster trace of both would not need it —
    that is `rasterio.features.shapes`, and it is a GDAL dependency this script
    does not have.
    """
    blocks = [f["geom"] for f in feats if f["feature_type"] != "cream"]
    if not blocks:
        return feats, 0, 0
    union = shapely.union_all([shapely.make_valid(g) for g in blocks])
    out, cut, dropped = [], 0, 0
    for f in feats:
        g = f["geom"]
        if f["feature_type"] != "cream" or not shapely.intersects(g, union):
            out.append(f)
            continue
        d = shapely.difference(shapely.make_valid(g), union)
        if d.is_empty or d.area < min_keep * g.area:
            dropped += 1
            continue
        if d.geom_type == "MultiPolygon":
            d = max(d.geoms, key=lambda q: q.area)      # a ring cut into arms
        if d.geom_type != "Polygon":
            out.append(f)
            continue
        if d.area < 0.98 * g.area:
            cut += 1
        out.append({**f, "geom": d, "area_px": round(float(d.area), 1)})
    return out, cut, dropped


# ── map furniture ────────────────────────────────────────────────────────────

_OCR_CACHE: dict[tuple[str, str | None], list] = {}


def ocr_rows(map_id: str, run_id: str | None = None) -> list:
    """Every OCR extraction on a sheet, read once and pinned to a run if asked.

    **A table a pipeline writes into is not a fixed input**, and this function
    is where that bites. The water seeds, the furniture mask, the legend panel
    and `--explain` all read `ocr_labels`, and with no run filter they read
    whatever runs happen to be in it. The 1882 sheet's 499 placed labels are
    three runs pooled — `post0910` 287, `v1b` 177 and `2026-09-04T0527` 35 —
    so the same object is seeded up to three times and re-OCR'ing the sheet
    changes this pass's geometry with nothing in the output recording why.

    Pooling stays the default so no existing run moves, but it is now printed
    rather than silent: pass `--ocr-run-id` to pin it, and `blocks.run.json`
    records what was used.
    """
    key = (map_id, run_id)
    if key not in _OCR_CACHE:
        from supabase_client import fetch_ocr_extractions

        rows = fetch_ocr_extractions(map_id, run_id)
        runs: dict[str, int] = {}
        for r in rows:
            runs[r.get("run_id") or "(none)"] = runs.get(r.get("run_id") or "(none)", 0) + 1
        where = ", ".join(f"{k} {v}" for k, v in sorted(runs.items(), key=lambda kv: -kv[1]))
        print(f"  {len(rows)} OCR rows from "
              + (f"run {run_id}" if run_id else f"{len(runs)} pooled run(s): {where}"))
        _OCR_CACHE[key] = rows
    return _OCR_CACHE[key]


def water_points(map_id: str, run_id: str | None = None) -> list[tuple[float, float]]:
    """Centres of the sheet's `hydrology` labels, in source pixels.

    Sixteen of them on the 1882 sheet — far too sparse to outline the water, and
    an earlier attempt to use them that way found only 4 of 840 cream parcels.
    They are exactly enough for the oversized-component test, though, because
    there the region is already one connected blob and the label only has to
    land inside it.
    """
    return [(r["global_x"] + (r["global_w"] or 0) / 2.0,
             r["global_y"] + (r["global_h"] or 0) / 2.0)
            for r in ocr_rows(map_id, run_id)
            if r.get("category") == "hydrology" and r.get("global_x") is not None]


def furniture_rows(map_id: str, run_id: str | None = None):
    """One OCR read shared by the furniture mask and the unpadded legend crop."""
    return [r for r in ocr_rows(map_id, run_id)
            if r.get("category") in ("title", "legend") and r.get("global_x") is not None]


def main_map_frame(map_id: str):
    """The printed border as a box, or None when the sheet has no `main_map`."""
    from supabase_client import fetch_triage_regions
    crop = (fetch_triage_regions(map_id, ["main_map"]) or [None])[0]
    if crop is None:
        return None
    x, y, w, h = crop
    return shapely.box(x, y, x + w, y + h)


def furniture_mask(map_id: str, pad: float = 200.0, *, rows=None, run_id: str | None = None):
    """The title cartouche and the legend box, from the sheet's own OCR labels.

    Both are printed rectangles full of text, which is the one thing the OCR
    pass is reliably good at, so they need no geometry of their own. The union
    of the padded `title` and `legend` label boxes drops 11 of the 1882 sheet's
    253 blocks — the same furniture counted by hand in the journal.

    A *hull* of those boxes is wrong and was tried: `legend` also tags the
    boundary annotations strung along the neatline, so their convex hull is
    very nearly the whole sheet. Per-label boxes, unioned.
    """
    if rows is None:
        rows = furniture_rows(map_id, run_id)
    if not rows:
        return None
    boxes = [shapely.box(r["global_x"], r["global_y"],
                         r["global_x"] + (r["global_w"] or 1.0),
                         r["global_y"] + (r["global_h"] or 1.0)).buffer(pad)
             for r in rows]
    return shapely.union_all(boxes)


# ── output ───────────────────────────────────────────────────────────────────

# The sheet's own colour key: median (r - g, r - b) inside each legend swatch on
# the 1882 Plan Cadastral, sampled from the `legend` triage region at
# [9681, 6961, 1754, 988]. Five classes, where `classify` knows four — the one
# it has never had is *service local*, which the sheet draws as a black diagonal
# hatch rather than a tint (59.6% ink in its swatch against 21.6% for the next
# densest), so no trough on either axis has ever found it.
#
# --legend-swatches auto now reads the largest OCR legend box at the run's
# render scale, with the detector checked at native scale to within 0.008.
# Fixed remains the default and the fallback: a 0.04 disagreement on either
# axis rejects the entire measured key. Ceiling: the five rectangles must still
# be in the 1882 order, on the right of the panel, and near its colours. This
# measures render-scale colour; it does not yet read class names or admit a
# different palette. Ink density is scale-dependent and is not a third axis.
LEGEND_SWATCHES = {
    "blue": (0.000, 0.008),      # domaniales affectees aux services militaire et marine
    "admin": (0.039, 0.067),     # domaniales affectees au service local  (a hatch)
    "cream": (0.059, 0.149),     # domaniales non affectees  — this is bare paper
    "green": (0.016, 0.122),     # proprietes communales
    "salmon": (0.165, 0.263),    # proprietes particulieres
}


def groups(values):
    """Inclusive runs of consecutive sorted integer values."""
    cuts = np.flatnonzero(np.diff(values) > 1) + 1
    return [(a[0], a[-1]) for a in np.split(values, cuts) if len(a)]


def longest_run(mask):
    ends = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return max((b - a for a, b in zip(ends[::2], ends[1::2])), default=0)


def find_swatches(rgb):
    """The five outlined rectangles in a legend-panel crop, top to bottom.

    The rightmost third is relative to the panel, not the whole sheet. These
    are the probe's measured outline tests, unchanged.

    **It only survives 1:1, so `--legend-swatches auto` is inert at every
    render this pass actually uses.** Measured on the cached 1882 panel
    (1754 x 988 source px), resampled to what each `--render` would hand it:

        --render 12102  scale 1.00  1754 px   OK, max delta 0.008 -> accepted
        --render  6051  scale 2.00   877 px   found 5 of 10 borders -> fallback
        --render  4096  scale 2.95   594 px   found 5 of 10 borders -> fallback
        --render  3000  scale 4.03   435 px   found 3 of 10 borders -> fallback

    The cause is the row test, not the colour: a swatch outline is a thin rule,
    and once shrunk the bottom border of one box and the top of the next merge
    into a single dark run, so five stacked boxes stop yielding ten separate
    ones. Counting `2 * len(LEGEND_SWATCHES)` is what then rejects the panel —
    correctly, since a mis-paired run would mis-order the classes.

    Not loosened, deliberately: the gate is the only thing standing between a
    wrong crop and a repainted sheet, and a detector that guesses at which runs
    are shared would trade a safe fallback for a silent mis-assignment. The
    honest upgrade is a border finder that does not assume separated rules
    (match five boxes between six lines, shared edges allowed) — worth building
    with the second polychrome sheet, since until then 1:1 already answers it.
    """
    h, w = rgb.shape[:2]
    x0 = 2 * w // 3                             # the key is a column on the right
    dark = rgb.max(axis=2) <= int(0.45 * 255)
    rows = np.array([longest_run(dark[y, x0:]) >= 0.045 * w for y in range(h)])
    lines = groups(np.flatnonzero(rows))
    if len(lines) != 2 * len(LEGEND_SWATCHES):
        raise RuntimeError(f"expected {2 * len(LEGEND_SWATCHES)} horizontal swatch borders, "
                           f"found {len(lines)}")
    boxes = []
    for top, bottom in zip(lines[::2], lines[1::2]):
        t, b = top[0], bottom[1]
        cols = np.array([longest_run(dark[t:b + 1, x]) >= 0.5 * (b - t)
                         for x in range(x0, w)])
        sides = [(a + x0, z + x0) for a, z in groups(np.flatnonzero(cols))]
        border = np.r_[np.arange(top[0], top[1] + 1), np.arange(bottom[0], bottom[1] + 1)]
        # Of every candidate left/right pair wide enough to be a swatch, take the
        # one whose top and bottom edges are actually drawn between them.
        choices = [(dark[border, left:right + 1].mean(), left, right)
                   for i, (left, _) in enumerate(sides)
                   for _, right in sides[i + 1:]
                   if right - left >= 2 * (b - t)]
        if not choices:
            raise RuntimeError("could not match vertical sides to a horizontal outline")
        _, left, right = max(choices)
        boxes.append((t, b, left, right))
    return boxes


def legend_swatches(rgb: np.ndarray, scale: float, rows):
    """Read the panel at the same scale as the polygons that will use its key.

    `legend` also labels neatline annotations; their union was nearly the whole
    sheet in the furniture experiment above. Take the single largest-area box,
    without furniture padding, and never hunt for a more convenient candidate
    if it fails. `scale` is source pixels per render pixel, hence division here.
    Floor/ceil keep the box's edge pixels; clipping prevents negative indices
    from wrapping into the far margin.

    The probe's four-pixel inset and median RGB differences are kept literally,
    now in render pixels. A shrunken outline can disappear or leave no interior.
    Reject that, non-finite medians, and any axis over 0.04 from the fixed key;
    accepting only part of a key would mix two different paper references in
    the dilution fit. The gate makes a wrong crop safe, but cannot establish
    new class meanings or validate a palette unlike the 1882 sheet's.
    """
    try:
        panels = [r for r in rows if r.get("category") == "legend"]
        if not panels:
            raise ValueError("no legend OCR box")
        panel = max(panels, key=lambda r: (r.get("global_w") or 0) * (r.get("global_h") or 0))
        x, y, w, h = (panel[k] for k in ("global_x", "global_y", "global_w", "global_h"))
        if w <= 0 or h <= 0:
            raise ValueError("largest legend OCR box has no area")
        height, width = rgb.shape[:2]
        x0, y0 = max(0, math.floor(x / scale)), max(0, math.floor(y / scale))
        x1, y1 = min(width, math.ceil((x + w) / scale)), min(height, math.ceil((y + h) / scale))
        print(f"  legend panel source box: {[x, y, w, h]}")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("legend OCR box is outside the render")
        crop = rgb[y0:y1, x0:x1]
        measured = {}
        for name, (t, b, left, right) in zip(LEGEND_SWATCHES, find_swatches(crop)):
            sw = crop[t + 4:b + 1 - 4, left + 4:right + 1 - 4]
            if not sw.size:
                raise ValueError(f"{name} has no interior after the 4 px inset")
            med = np.median(sw.reshape(-1, 3) / 255, axis=0)
            measured[name] = (float(med[0] - med[1]), float(med[0] - med[2]))
        for name, value in measured.items():
            print(f"  legend measured {name}: r-g {value[0]:.3f}, r-b {value[1]:.3f}")
        for name, value in measured.items():
            delta = np.abs(np.array(value) - LEGEND_SWATCHES[name])
            if not np.isfinite(delta).all() or (delta > 0.04).any():
                raise ValueError(f"{name} disagreed: delta r-g {delta[0]:.3f}, r-b {delta[1]:.3f}")
    except Exception as exc:                                  # noqa: BLE001
        print(f"  legend swatches source: fallback ({exc})")
        return LEGEND_SWATCHES
    print("  legend swatches source: measured")
    return measured


PAPER_CLASS = "cream"
# The two classes the legend draws as ink rather than as a tint: *service local*
# is a black hatch at 59.6% ink and the military class a blue ruling at 21.6%,
# against 10.6% for the densest of the three tints. A block whose ink turns out
# not to be a ruling cannot be either of them, whatever colour that ink is.
HATCH_CLASS = "admin"
INK_CLASSES = (HATCH_CLASS, "blue")


def fit_dilution(points: list[tuple[float, float]],
                 swatches: dict[str, tuple[float, float]] = LEGEND_SWATCHES,
                 lo: float = 0.15, hi: float = 1.0, steps: int = 35) -> tuple[float, float]:
    """One scalar: how dilute the printed wash is against the legend's full ink.

    A legend swatch is the tint at full strength; the same tint laid over a block
    is thinner, so the swatches sit further out than any wash on the sheet and
    matching a block straight against them drops everything to the nearest pale
    class. Measured here: a salmon block's wash is r - g 0.086 where its swatch
    is 0.165, which is why an unfitted match collapsed salmon from 95 blocks to 8.

    The model is one global alpha along each swatch's own direction away from
    bare paper, `paper + alpha * (swatch - paper)`. Alpha is chosen to minimise
    the total distance from each block's wash to its nearest prototype — the
    sheet's own components vote for it, nothing is scored against ground truth,
    and the paper class is a fixed point at any alpha.
    """
    P = swatches[PAPER_CLASS]
    best_a, best_cost = 1.0, float("inf")
    for a in np.linspace(lo, hi, steps):
        protos = [(P[0] + a * (v[0] - P[0]), P[1] + a * (v[1] - P[1])) for v in swatches.values()]
        cost = 0.0
        for px, py in points:
            cost += min((px - qx) ** 2 + (py - qy) ** 2 for qx, qy in protos)
        if cost < best_cost:
            best_a, best_cost = float(a), cost
    return best_a, best_cost


# Water is the one thing on this sheet that is drawn rather than washed, and it
# is a *region* rather than a property a polygon carries. Three measurements say
# so. The open river is bare paper — (r - g, r - b) of +0.059, +0.141
# mid-channel against +0.047, +0.133 over dry land, the same tone to three
# decimals. Its ink is the engraved ripple, which is pale blue in places
# (r - b +0.031) and neutral in others, so no ink colour holds across the whole
# river. And most of the polygons the cream pass traces there sit *between* the
# ripple lines and contain no ink at all — 0 to 17 pixels of it — so a
# per-polygon test has nothing to read in exactly the places it is needed.
## The water is drawn, and what is drawn is a blue line. Not blue in the sense of
# b > r — nothing on this sheet is — but *less red than black ink is*: over the
# dark pixels, the ripple ruling reads `r - b` +0.031 to +0.051 where the black
# ink of a building reads +0.086 and lettering +0.169. Threshold that, close the
# gaps between the lines, and the result is the water's own shape, to the pixel:
# the quay edge, the jetties, the mouth of a creek a cell grid cannot see.
#
# This replaced a 64 px grid of cells tested for coherence, wash and ink
# density. That version measured the wash over *all* of a cell's pixels, so the
# ripple ink dragged the cell under its own threshold — the more the cell looked
# like river, the more certainly it was discarded — and its square edge left a
# staircase along every bank. The whole diagnosis, and five measured dead ends,
# are at the foot of docs/journals/260918-colour-blocks.md.
#
# Two things bound it, and both are needed:
#
#  - LAND, taken from the pass's own output: any polygon compact enough to be a
#    parcel. A ripple ribbon is not compact, so the river cannot vouch for
#    itself. Without this the region has no barrier at all — what kept the grid
#    version off the city was only that the city's cells happened not to
#    *connect* to the river's, and every loosening flooded the sheet.
#  - The `hydrology` labels, which say which of the remaining regions to
#    believe. The same signature also describes the ruled neatline margin,
#    which is furniture and fine to lose.
#
# The labels do a second job on the land side, and it is the one that makes the
# two bounds safe together: a polygon that *holds* a hydrology label is water,
# and never land. Compactness is a guess and the sheet's lettering is not, so
# without this an arroyo reach that came out compact — which `--recut` produces,
# at 0.315 circularity — is admitted to `land_mask` and shields itself.
#
# ponytail: seven constants, one sheet, and `WATER_LINE_RB` is the load-bearing
# one — it is the gap between this sheet's blue and this sheet's black. Ceiling:
# a sheet that draws its water in black, or one whose ink has aged to the same
# hue. Upgrade: fit the cut from the sheet's own dark-pixel histogram, the way
# `cream_ink` sweeps its threshold, rather than pinning it at 0.07.
WATER_LINE_V = 0.80         # dark enough to be a drawn line
WATER_LINE_RB = 0.07        # ...and less red than this sheet's black ink
WATER_LINE_W = 2            # ...and thin enough to be a line rather than a wash
WATER_WASH_MIN_PX = 200     # ...and a wash is a *region*, not an erosion crumb
WATER_RIPPLE_COH = 0.30     # ...and a ripple is ruled, where tree stipple runs no way
WATER_COH_CELL = 16         # render px; narrower than the creeks it has to resolve
WATER_COH_BLOB = 8          # ...and stipple is a bed of cells, not one stray cell
WATER_CLOSE = 8             # render px; bridges the gap between two ruled lines
WATER_OPEN = 2              # ...then takes back the stray specks it joined
WATER_MIN_PX = 5_000        # a body smaller than this is not a river
WATER_HOLE_PX = 20_000      # a hole this small in the water is lettering, not land
WATER_SHARE = 0.35          # a polygon this far into the region is water
WATER_RIPPLE_CIRC = 0.25    # a stringy polygon touching the region is ripple


def outline_circularity(geom) -> float:
    """`4*pi*A / P^2` of the polygon's OUTLINE, ignoring any holes in it.

    A block with a courtyard is still a block. Taken on the polygon itself,
    `area` loses the courtyard while `length` gains its ring, so a perfectly
    ordinary city block scores below a ribbon does — which is how a 0.14 km²
    piece of the Jardin Botanique came to be called ripple.
    """
    ring = shapely.Polygon(geom.exterior)
    return 4 * math.pi * ring.area / (ring.length ** 2) if ring.length else 0.0


def land_mask(feats: list[dict], shape: tuple[int, int], scale: float,
              min_circ: float = WATER_RIPPLE_CIRC,
              named: list[bool] | None = None) -> np.ndarray:
    """Every polygon compact enough to be a parcel, burnt into a mask.

    This is the water test's only barrier, and it has to come from geometry
    rather than from colour: the river's own paper is the same tone as dry
    land (measured +0.149 against +0.141), so no threshold separates them.
    Compactness does, because the cream pass fragments water into ribbons and
    nothing else on the sheet is a ribbon.

    `named` marks the polygons that hold a `hydrology` label. Compactness is a
    guess and the sheet's own lettering is not, so a named polygon is never
    land — otherwise an arroyo that came out compact vouches for itself and
    the region stops at its own bank.
    """
    out = np.zeros(shape, bool)
    for i, f in enumerate(feats):
        g = f["geom"]
        if named and named[i]:
            continue
        if outline_circularity(g) < min_circ:
            continue
        win = _poly_window(g, shape, scale)
        if win is not None:
            sel, x0, y0, x1, y1 = win
            out[y0:y1, x0:x1] |= sel
    return out


SPLIT_RG = 0.035            # a building's wash is this much redder than its plot's
SPLIT_MIN_M2 = 40.0        # ...over an area a building could have
SPLIT_MAX_SHARE = 0.80     # ...and covering less of the parcel than the parcel


def split_buildings(feats: list[dict], rgb: np.ndarray, scale: float,
                    mpp: float | None, rg: float = SPLIT_RG,
                    ink_v: float = INK_V, min_m2: float = SPLIT_MIN_M2,
                    max_share: float = SPLIT_MAX_SHARE) -> list[dict]:
    """The redder wash inside a finished parcel, as building polygons.

    This is P3 — the within-block split — and it is the one thing the block
    prior has never been able to do: `building` sits at 0.122 against
    `land_plot` 0.331 because a parcel legitimately holds several buildings,
    so the ink is found and the subdivision is not.

    **Two corrections to the plan this came from, both measured here.**

    P3 was written as *split the salmon block*, on the reading that a building
    stands on a *propriétés particulières* plot. On this sheet it does not:
    of the 17 volunteer `building` traces, **15 fall inside a cream polygon and
    2 inside a green one, and none inside a salmon one**. A rule scoped to
    salmon could not have reached any of them, so this runs over every class.

    And what separates a building from its plot is not a sheet-wide threshold.
    P3's retracted null looked for two reds *in the sheet's histogram*; the
    delta that exists is **local** — a trace's wash against the wash of the
    parcel it stands in, median +0.035 with 10 of 17 positive. So the baseline
    is each polygon's own median, re-derived per polygon, and the sheet's
    global trough is not used at all.

    The four traces that go the *other* way are the sheet's second building
    convention: a dense black fill, ink 0.21-0.44 against an open parcel's
    0.05-0.09, whose wash median is dragged *below* its plot's by its own ink.
    They are not recoverable on colour and are not attempted here — an ink
    axis was measured and is a separate null (see the 2026-09-19 audit).

    Scored against the 17 traces at `rg` 0.035: **mean 0.278, @.5 5** against
    the block prior's 0.122 / @.5 1 on 888 polygons and SAM2-on-the-modern-
    prior's 0.160. Fewer predictions and five times the hits, which is the one
    direction a best-match-per-trace metric cannot manufacture.

    ponytail: there is still no precision figure for this, because nothing in
    this repo could produce one until `seg_eval --window` landed beside it and
    no window has been exhaustively traced yet. `--no-split-buildings` restores
    the run without it. The upgrade is to trace one dense window and score it.
    """
    px_m2 = (mpp * scale) ** 2 if mpp else None
    min_px = max(4, int(min_m2 / px_m2)) if px_m2 else MIN_AREA_PX
    a = rgb.astype(np.float32) / 255.0
    rgd = a[..., 0] - a[..., 1]
    ink = a.max(axis=2) < ink_v

    out: list[dict] = []
    for f in feats:
        win = _poly_window(f["geom"], rgb.shape[:2], scale)
        if win is None:
            continue
        sel, x0, y0, x1, y1 = win
        area = int(sel.sum())
        if area < min_px * 2:
            continue
        sub_ink = ink[y0:y1, x0:x1]
        wash = sel & ~sub_ink
        if wash.sum() < 20:
            continue
        # The parcel's own wash, ink excluded. A parcel with buildings on it is
        # still mostly open ground, so its median is the open ground's colour.
        base = float(np.median(rgd[y0:y1, x0:x1][wash]))
        cand = wash & (rgd[y0:y1, x0:x1] > base + rg)
        # A building's outline is ink and splits its own wash in two; close
        # across it, then clip back so nothing escapes the parcel.
        cand = ndimage.binary_closing(cand, np.ones((3, 3), bool)) & sel
        lab, n = ndimage.label(cand)
        if not n:
            continue
        sizes = ndimage.sum(cand, lab, range(1, n + 1))
        for idx, size in enumerate(sizes, start=1):
            # Too small is noise in the wash; too large is the parcel itself
            # coming back under a different name.
            if size < min_px or size > max_share * area:
                continue
            geom = component_polygon(lab == idx, x0, y0, scale)
            if geom is None:
                continue
            out.append({"geom": geom, "feature_type": "building",
                        "area_px": round(float(geom.area), 1)})
    return out


def ruling_mask(rgb: np.ndarray, cell: int = WATER_COH_CELL,
                min_coh: float = WATER_RIPPLE_COH, min_blob: int = WATER_COH_BLOB,
                min_grad: float = 0.02, min_ink: int = 24) -> np.ndarray:
    """Cells whose line work runs one way. P2d's measure, read on a grid.

    The wash test cannot tell a packed ripple from tree stipple: both are dark,
    and both survive an erosion. Dropping the erosion crumbs to rescue the
    creeks therefore let the Jardin Botanique's stipple into the region the
    moment `--recut` took away the land polygon that had been covering it —
    and no crumb size separates the two, because the stipple floods at 20 px
    while the creek does not come back until 100.

    Direction does separate them, which is exactly what P2d found for the
    hatch: on a 16 px cell the creek's ruling scores p10 **0.304** and the open
    river's **0.755**, against the garden's p50 **0.182**. Measured on the
    gradient rather than on thresholded ink, for the reason in
    `ink_coherence` — a one-pixel line comes back broken and a broken line has
    no direction left.

    This only ever *removes* from the blue mask, so it cannot reopen a window
    the water was already staying out of.

    ponytail: the threshold is one number on one sheet. Ceiling: a sheet whose
    water is stippled rather than ruled, where this would erase the river.
    Upgrade: read it off the distribution inside the hydrology labels' own
    cells, which are water by assertion, instead of pinning it at 0.30.
    """
    grey = rgb.astype(np.float32).mean(axis=2) / 255.0
    gy, gx = np.gradient(grey)
    h, w = grey.shape
    rows, cols = h // cell, w // cell
    if not (rows and cols):
        return np.ones((h, w), bool)
    H, W = rows * cell, cols * cell
    u, v = gx[:H, :W], gy[:H, :W]
    use = np.hypot(u, v) > min_grad

    def blocks(a: np.ndarray) -> np.ndarray:
        return a.reshape(rows, cell, cols, cell).sum(axis=(1, 3))

    jxx, jyy, jxy = blocks(u * u * use), blocks(v * v * use), blocks(u * v * use)
    tr = jxx + jyy
    coh = np.where(tr > 0, np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / np.maximum(tr, 1e-12), 0.0)
    # A cell with almost no ink has no direction to measure and no ripple in it
    # either; leave it in and let the rest of the chain decide.
    bad = (coh < min_coh) & (blocks(use.astype(np.float32)) >= min_ink)
    # Only a *bed* of unruled cells is stipple. Gating cell by cell cut the
    # creek at the 10% of its cells that fail and left fragments under
    # WATER_MIN_PX, which killed the very thing this pass had just rescued —
    # the same mistake as dilating every erosion crumb, one level up. The
    # plateau is flat from 8 cells to 64, so this is a shape, not a tuning.
    lab, n = ndimage.label(bad)
    if n:
        sizes = ndimage.sum(bad, lab, range(1, n + 1))
        bad = np.isin(lab, [i for i in range(1, n + 1) if sizes[i - 1] >= min_blob])
    out = np.ones((h, w), bool)
    out[:H, :W] = ~np.repeat(np.repeat(bad, cell, axis=0), cell, axis=1)
    return out


def water_region(feats: list[dict], rgb: np.ndarray, scale: float,
                 water: list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray, list[bool]]:
    """(the water as a pixel mask, the land mask bounding it, per-polygon named).

    Split out of `water_mask` so the review renderer can tint exactly what the
    pass tested. It had its own copy of this chain, and a second copy of a
    twelve-step morphology is a copy that drifts — the pictures are the only
    check the water work has, so they have to be of the real mask.
    """
    a = rgb.astype(np.float32) / 255.0
    v = a.max(axis=2)
    rb = a[..., 0] - a[..., 2]
    h, w = v.shape

    def disk(r: int) -> np.ndarray:
        y, x = np.ogrid[-r:r + 1, -r:r + 1]
        return x * x + y * y <= r * r

    blue = (v < WATER_LINE_V) & (rb < WATER_LINE_RB)
    # Hue alone is not enough: the military class's wash is blue-grey too, and
    # it flowed down the streets of the Arsenal quarter and joined the river,
    # taking the Jardin Botanique and 0.14 km² of the Magasins with it. The
    # water is a *line*. Erode by a line's own width and a wash survives while
    # a ruling disappears, so what survives is exactly what to throw away.
    #
    # ...but only what survives as a *region*. A wide river is ruled sparsely
    # and erodes to nothing; a narrow creek is the same ruling packed into a
    # ribbon, and where two lines touch it survives as a crumb. The Rach Cầu
    # Chông reach threw 305 crumbs, none over 140 px, and dilating each by
    # `WATER_LINE_W + 2` blanketed the creek: 79% of its blue went, against 9%
    # of the open river's. Componenting the survivors and keeping the ones big
    # enough to be an area fill separates the two — the creek's largest crumb
    # is 140 px and the Arsenal quarter's wash is 1,140.
    wash = ndimage.binary_erosion(blue, structure=disk(WATER_LINE_W))
    wlab, wn = ndimage.label(wash)
    if wn:
        wsz = ndimage.sum(wash, wlab, range(1, wn + 1))
        wash = np.isin(wlab, [i for i in range(1, wn + 1) if wsz[i - 1] >= WATER_WASH_MIN_PX])
    blue &= ~ndimage.binary_dilation(wash, structure=disk(WATER_LINE_W + 2))
    blue &= ruling_mask(rgb)
    solid = ndimage.binary_closing(blue, structure=disk(WATER_CLOSE))
    solid = ndimage.binary_opening(solid, structure=disk(WATER_OPEN))
    # The sheet names its own water, so read the name before guessing at shape.
    named = [any(shapely.contains_xy(f["geom"], x, y) for x, y in water) for f in feats]
    land = land_mask(feats, (h, w), scale, named=named)
    solid &= ~land
    lab, n = ndimage.label(solid)
    if not n:
        return np.zeros((h, w), bool), land, named
    sizes = ndimage.sum(solid, lab, range(1, n + 1))
    seeded = {lab[int(y / scale), int(x / scale)] for x, y in water
              if 0 <= int(y / scale) < h and 0 <= int(x / scale) < w}
    seeded.discard(0)
    full = np.isin(lab, [i for i in seeded if sizes[i - 1] >= WATER_MIN_PX])
    if not full.any():
        return full, land, named
    # The sheet letters its own river. Black ink is not a blue line, so
    # "RIVIÈRE DE SAIGON" punches a hole straight through the water it names.
    holes = ndimage.binary_fill_holes(full) & ~full
    hlab, hn = ndimage.label(holes)
    if hn:
        hs = ndimage.sum(holes, hlab, range(1, hn + 1))
        full = full | np.isin(hlab, [i + 1 for i, s in enumerate(hs) if s <= WATER_HOLE_PX])
    return full, land, named


def water_mask(feats: list[dict], rgb: np.ndarray, scale: float, water: list[tuple[float, float]],
               ink_v: float = INK_V, share: float = WATER_SHARE) -> list[bool]:
    """True for each polygon lying in the sheet's water.

    `water` is the hydrology labels, in source px. `ink_v` is unused and kept
    for the call signature; the water's line work is found on hue, not on the
    ink threshold, because at `INK_V` the ripple is only half there.

    Three ways to be water. Holding a `hydrology` label is the first and the
    only one that is evidence rather than inference — the same evidence the
    oversize path already fences a component with. Mostly inside the region is
    the second. Touching it at all while being too stringy to be a parcel is
    the third, and it is what catches a ribbon lying along the bank — measured
    safe rather than assumed: no hand trace on this sheet overlaps the region
    except one `waterway`, at 0.60, which is water finding water.
    """
    if not water:
        return [False] * len(feats)
    h, w = rgb.shape[:2]
    full, _land, named = water_region(feats, rgb, scale, water)
    if not full.any():
        return named
    out: list[bool] = []
    for f, is_named in zip(feats, named):
        if is_named:
            out.append(True)
            continue
        win = _poly_window(f["geom"], (h, w), scale)
        if win is None:
            out.append(False)
            continue
        sel, x0, y0, x1, y1 = win
        if sel.sum() < 10:
            out.append(False)
            continue
        inside = (sel & full[y0:y1, x0:x1]).sum() / sel.sum()
        circ = outline_circularity(f["geom"])
        out.append(bool(inside > share or (inside > 0 and circ < WATER_RIPPLE_CIRC)))
    return out


# A parcel is compact and a ripple is not. `4*pi*A / P^2` is 1 for a circle and
# falls as a polygon gets stringy; a cadastral parcel on this sheet sits well
# above 0.2 and the shapes the cream pass traces between the river's ripple
# lines sit under 0.1. It is not a water detector — it removes a sliver wherever
# one is, including the rims `subtract_blocks` leaves behind — but on this sheet
# the slivers are overwhelmingly the river.
#
# Swept against the traces: at 0.10 it drops 110 polygons (0.48 km²) and
# land_plot holds at 0.350 with building at 0.122, both to the digit. At 0.15 it
# drops 142 and land_plot falls to 0.326, so it has started eating real parcels.
#
# ponytail: one constant with its ceiling measured two steps away. Upgrade: none
# needed on this sheet; on a sheet with genuinely long thin parcels — a canal
# frontage, a rice-field strip — lower it or turn the flag off, because the
# shape prior is simply false there.
MIN_CIRCULARITY = 0.10


def sliver_mask(feats: list[dict], min_circ: float = MIN_CIRCULARITY) -> list[bool]:
    """True for each polygon too stringy to be a parcel."""
    out = []
    for f in feats:
        g = f["geom"]
        out.append(bool(g.length and 4 * math.pi * g.area / (g.length ** 2) < min_circ))
    return out


def _poly_window(geom, shape: tuple[int, int], scale: float, inset: int = 0):
    """The polygon's bounding window in render px, and its mask inside it.

    Returns `(sel, x0, y0, x1, y1)` or None if the window is degenerate. `inset`
    blanks that many pixels of the mask's own border, for a measure that would
    otherwise read the polygon's outline as if it were content.
    """
    ring = [(x / scale, y / scale) for x, y in geom.exterior.coords]
    xs = [q[0] for q in ring]
    ys = [q[1] for q in ring]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(shape[1], int(max(xs)) + 1), min(shape[0], int(max(ys)) + 1)
    if x1 - x0 < max(2, 2 * inset + 2) or y1 - y0 < max(2, 2 * inset + 2):
        return None
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).polygon([(q[0] - x0, q[1] - y0) for q in ring], fill=255)
    sel = np.asarray(m) > 0
    if inset:
        sel = sel.copy()
        sel[:inset] = sel[-inset:] = False
        sel[:, :inset] = sel[:, -inset:] = False
    return sel, x0, y0, x1, y1


def wash_points(feats: list[dict], rgb: np.ndarray, scale: float,
                ink_v: float = INK_V) -> list[tuple[float, float, float, float]]:
    """Per polygon: median (r - g, r - b) over every pixel, and again over paper.

    Two measures because the sheet's two kinds of evidence are measured on
    different pixels and are not interchangeable. The legend swatches are
    all-pixel medians, ink included, because two of the five classes *are* ink —
    measure only the paper between a hatch and you throw away what defines it.
    `green_split`, by contrast, is a trough in the paper-only histogram
    (`live = max >= ink_v`), so arbitrating with it means comparing paper to
    paper. Mixing the two silently is how a diluted swatch ends up overruling a
    boundary the sheet itself voted for.

    The paper-only pair is also what names a block once the hatch test has said
    its ink is *not* the class: a garden's stipple is dark and neutral, so its
    all-pixel median sits on the blue prototype whatever wash is underneath, and
    the Jardin Botanique came back blue. For a block whose ink is line work over
    a tint, the tint is the evidence and it is between the lines.
    """
    a = rgb.astype(np.float32) / 255.0
    rg, rb = a[..., 0] - a[..., 1], a[..., 0] - a[..., 2]
    paper = a.max(axis=2) >= ink_v
    out: list[tuple[float, float, float, float]] = []
    for f in feats:
        win = _poly_window(f["geom"], rgb.shape[:2], scale)
        if win is None:
            out.append((float("nan"),) * 4)
            continue
        sel, x0, y0, x1, y1 = win
        if sel.sum() < 25:
            out.append((float("nan"),) * 4)
            continue
        pap = sel & paper[y0:y1, x0:x1]
        if pap.sum() < 25:
            pap = sel                       # all ink: the paper measure is the same one
        out.append((float(np.median(rg[y0:y1, x0:x1][sel])),
                    float(np.median(rb[y0:y1, x0:x1][sel])),
                    float(np.median(rg[y0:y1, x0:x1][pap])),
                    float(np.median(rb[y0:y1, x0:x1][pap]))))
    return out


# A hatch runs one way and tree stipple runs none. Measured at --render 6051 on
# the 1882 sheet: the two hatched administrative blocks score 0.74 and 0.59,
# while the Jardin Botanique's stipple scores 0.036 and the Cimetiere's 0.029 —
# two clusters an order of magnitude apart, with the Champ de Manoeuvres' much
# finer blue ruling between them at 0.118.
#
# ponytail: one constant, not a voted trough. Ceiling: the number scales with
# --render, because a hatch aliases away as the sheet is shrunk (the same two
# blocks score 0.81 and 0.75 at full source resolution). Re-measure, or sweep it
# the way `cream_ink` sweeps its threshold, before trusting it at another render.
HATCH_COHERENCE = 0.30


def ink_coherence(geom, grad: tuple[np.ndarray, np.ndarray], scale: float,
                  min_grad: float = 0.02) -> float:
    """How much of a polygon's line work runs at one angle, 0 (none) to 1 (all).

    The structure tensor of the greyscale gradient, summed over the polygon:
    `sqrt((Jxx - Jyy)^2 + 4 Jxy^2) / (Jxx + Jyy)`. One number, no angle needed,
    and the doubled-angle algebra makes it blind to a line's sign, so a ruling
    reads the same whichever way it is drawn.

    It is measured on the *gradient*, not on the ink mask, and that is the whole
    difference from the two density nulls recorded in the journal. Thresholding
    first throws away the hatch on this sheet — its lines are one source pixel
    of grey, so at `INK_V` they come back broken, and a broken line has no
    direction left to measure: the same two blocks score 0.215 and 0.064 that
    way, which is no separation at all.

    Being a ratio of the tensor's eigenvalue gap to its trace, it is also blind
    to how *much* ink there is, which is what ink density could never get past —
    a densely built block carries as much ink as a hatched one, but its ink runs
    two ways at once and cancels, while a garden's runs every way.
    """
    gy, gx = grad
    # The polygon's own edge is a line, and a strong one. Three pixels in.
    win = _poly_window(geom, gx.shape[:2], scale, inset=3)
    if win is None or min(win[3] - win[1], win[4] - win[2]) < 8:
        return float("nan")
    sel, x0, y0, x1, y1 = win
    a, b = gx[y0:y1, x0:x1], gy[y0:y1, x0:x1]
    use = sel & (np.hypot(a, b) > min_grad)     # paper is flat; skip it
    if use.sum() < 200:
        return float("nan")
    u, v = a[use], b[use]
    jxx, jyy, jxy = float((u * u).sum()), float((v * v).sum()), float((u * v).sum())
    tr = jxx + jyy
    if tr <= 0:
        return float("nan")
    return float(((jxx - jyy) ** 2 + 4 * jxy ** 2) ** 0.5 / tr)


def relabel_by_swatch(feats: list[dict], rgb: np.ndarray, scale: float,
                      alpha: float | None = None, green: float | None = None,
                      ink_v: float = INK_V,
                      hatch: float | None = None,
                      swatches: dict[str, tuple[float, float]] = LEGEND_SWATCHES) -> tuple[list[dict], int, float, int]:
    """Name each finished polygon by the wash it holds, against the fitted key.

    Runs after the geometry is fixed, which is the whole difference from the
    per-pixel nearest-swatch pass rejected on 2026-09-18: that one interleaved
    two classes inside one block and fragmented it (land_plot 0.346 -> 0.307).
    This cannot move a boundary, only the name on it.

    It exists because `dominant_class` structurally cannot answer *cream*: it
    votes over PIGMENT_CLASSES, of which cream is not one, so a *non affectee*
    plot with red buildings drawn on it has no cream pixels among the candidates
    and comes back salmon every time.

    `green`, when given, is the sheet's own voted `r - g` trough and **overrules
    the key on the cream/green boundary alone**. Each source of evidence is used
    where it is the stronger one: the swatches order classes the troughs cannot
    (communales and service local swap between the axes, so no cascade of 1-D
    cuts separates them), while cream and green sit 0.043 apart on `r - g` and
    the diluted prototypes land closer still — matched against them alone, green
    claimed 470 polygons on a sheet with nothing like 470 communal parcels. The
    trough is fitted from this sheet's own pixels and is simply better for that
    one cut.

    `hatch`, when given, is the coherence a block's line work must reach to be
    called *service local*, which the legend draws as a hatch. The key cannot
    hold that one either, for the reason the colour axes never could: the class
    has no hue, only ink, so anything densely inked lands near its prototype —
    and the densest ink on this sheet is tree stipple, which took both gardens
    and bled into the Champ de Manoeuvres. A hatch is directional and stipple is
    not, so the block that fails the test falls back to its nearest prototype
    among the three classes that *are* a tint, matched on its paper. Colour
    names a tint; only geometry can name a ruling.
    """
    pts = wash_points(feats, rgb, scale, ink_v=ink_v)
    if alpha is None:
        # Fit on the pigmented blocks only. A cream parcel is bare paper by
        # definition, so it carries no tint and cannot say how strongly a tint
        # prints; including the ~800 of them drags the fit toward the paper
        # prototype and every class collapses inward (alpha 0.38 against 0.52,
        # and the named-block check falls from 6/8 to 5/8).
        tinted = [(q[0], q[1]) for f, q in zip(feats, pts)
                  if q[0] == q[0] and f["feature_type"] != PAPER_CLASS]
        alpha, _ = fit_dilution(tinted or [(q[0], q[1]) for q in pts if q[0] == q[0]], swatches)
    P = swatches[PAPER_CLASS]
    protos = {k: (P[0] + alpha * (v[0] - P[0]), P[1] + alpha * (v[1] - P[1]))
              for k, v in swatches.items()}
    grad = None
    if hatch is not None:
        v = rgb.astype(np.float32).max(axis=2) / 255.0
        grad = np.gradient(v)
    changed = demoted = 0
    for f, q in zip(feats, pts):
        if q[0] != q[0]:
            continue
        near = min(protos, key=lambda k: (protos[k][0] - q[0]) ** 2 + (protos[k][1] - q[1]) ** 2)
        if near == HATCH_CLASS and grad is not None:
            coh = ink_coherence(f["geom"], grad, scale)
            if coh == coh and coh < hatch:
                # Paper, not ink, and the two ink classes are not on the ballot
                # — see `wash_points` and INK_CLASSES. The stipple that just
                # failed the test is the thing being ignored.
                tints = [k for k in protos if k not in INK_CLASSES]
                near = min(tints, key=lambda k: (protos[k][0] - q[2]) ** 2 + (protos[k][1] - q[3]) ** 2)
                demoted += 1
        if green is not None and near in ("green", PAPER_CLASS):
            # Paper measure against a paper-measured trough — see `wash_points`.
            near = "green" if q[2] <= green else PAPER_CLASS
        if near != f["feature_type"]:
            f["feature_type"] = near
            changed += 1
    return feats, changed, alpha, demoted


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
        # Exterior ring only. `subtract_blocks` can leave a cream polygon with a
        # hole in it — a rim around a block — and this contract is one ring:
        # seg_eval does `Polygon(coords)`. Flattening exterior *and* interior into
        # a single list builds a self-crossing polygon, which scored worse than
        # either honest reading (land_plot 0.350 -> 0.337 on 36 of 1044). The
        # GeoJSON beside this keeps the true geometry, holes and all.
        "polygons": [
            {
                "coords": [[round(x, 1), round(y, 1)]
                           for x, y in f["geom"].exterior.coords],
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

    # The cream pass finds what the block pass is built to leave out. In the
    # fixture the streets and the cream parcel are the same tone, so with the
    # ink lines read as boundaries the surrounding street is one component and
    # the quarters of each parcel are their own — which is the mechanism, and
    # what fails first if the class set stops being honoured.
    cfeats, _ = blocks_from_colour(img, split, scale=1.0, mpp=None, close=0,
                                   ink_v=0.75, cool=cool, green=gsplit,
                                   classes=("cream",))
    assert cfeats, "the cream pass must find the cream the block pass drops"
    assert all(f["feature_type"] == "cream" for f in cfeats), \
        f"cream pass must not label a parcel with a pigment class: {cfeats[0]}"

    # The sweep must refuse to climb into the paper: every candidate it returns
    # is below the sheet's own V mode, or the whole sheet reads as ink.
    peak = paper_peak(img)
    chosen, curve = cream_ink(img, split, cool=cool, green=gsplit, px_area_m2=None,
                              min_area_m2=MIN_AREA_M2, max_area_m2=MAX_AREA_M2, probe=1)
    assert chosen < peak, f"cream ink {chosen} must stay under the paper peak {peak}"
    assert curve, "the sweep must report its curve"

    # A ruling reads as one direction and stipple as none. Two patches of the
    # same ink density, so the thing being measured is direction and nothing
    # else — which is exactly what the two density nulls could not do.
    rule = np.full((160, 160, 3), 235, np.uint8)
    rule[:, ::4] = 60                                   # a ruling, every 4 px
    dots = np.full((160, 160, 3), 235, np.uint8)
    rs = np.random.default_rng(7)
    dots[rs.random((160, 160)) < 0.25] = 60             # the same ink, scattered
    square = shapely.box(8, 8, 152, 152)
    grad_r = np.gradient(rule.astype(np.float32).max(axis=2) / 255.0)
    grad_d = np.gradient(dots.astype(np.float32).max(axis=2) / 255.0)
    c_rule = ink_coherence(square, grad_r, 1.0)
    c_dots = ink_coherence(square, grad_d, 1.0)
    assert c_rule > HATCH_COHERENCE > c_dots, \
        f"the hatch test must split a ruling from stipple: {c_rule:.3f} vs {c_dots:.3f}"

    # The sliver filter keeps a block and drops a ribbon of the same area.
    block = {"geom": shapely.box(0, 0, 100, 100)}
    ribbon = {"geom": shapely.box(0, 0, 1000, 10)}
    assert sliver_mask([block, ribbon]) == [False, True], "sliver filter must split 1:1 from 100:1"

    # The water test, on the thing it actually keys on: a blue line. The top
    # half is ruled in blue-grey over paper, the bottom half is blank paper,
    # and a patch of the water is lettered over in black ink the way the sheet
    # letters its own river.
    wat = np.full((320, 640, 3), (232, 222, 202), np.uint8)
    wat[:160][:, ::5] = (120, 130, 150)                 # the ripple, every 5 px
    wat[64:128, 256:320] = (232, 222, 202)              # clear a patch...
    rs2 = np.random.default_rng(3)
    blot = wat[64:128, 256:320]
    blot[rs2.random(blot.shape[:2]) < 0.25] = (60, 40, 30)   # ...and letter it
    edge = {"geom": shapely.box(0, 158, 400, 168)}      # a ribbon mostly past the bank
    holed = {"geom": shapely.box(264, 94, 312, 100)}    # a ripple under the lettering
    island = {"geom": shapely.box(380, 8, 560, 159)}    # a *parcel* out on the water
    far = {"geom": shapely.box(40, 240, 140, 319)}      # a block well onto the land
    wm = water_mask([edge, holed, island, far], wat, 1.0, [(100.0, 40.0)])
    assert wm == [True, True, False, False], \
        f"water: the ribbon and the lettered patch are water, the parcels are not: {wm}"
    # Each half of that carries its own weight. The ribbon keeps most of its
    # area outside the water, so only the stringiness test reaches it; the
    # lettered patch is water only because the hole is filled; and the island
    # survives sitting on ruled water paper only because land bounds the region
    # — which is the barrier the whole test rests on.
    assert not water_mask([island], wat, 1.0, [(100.0, 40.0)])[0], \
        "a compact parcel is land however watery the paper it sits on"
    # ...and with no hydrology label there is no region and nothing is dropped.
    assert water_mask([edge, holed, island, far], wat, 1.0, []) == [False] * 4, \
        "no label must mean no water region at all"
    # The sheet's own lettering outranks the shape guess. Drop a hydrology
    # label inside that same compact island and it is the water it names —
    # and it stops shielding the region, which is the half that matters: an
    # arroyo that came out compact would otherwise vouch for itself.
    lbl = water_mask([island, far], wat, 1.0, [(100.0, 40.0), (400.0, 40.0)])
    assert lbl == [True, False], f"a named polygon is water however compact: {lbl}"

    # Areas are filtered in m² when the sheet's scale is known.
    f3, d3 = blocks_from_colour(img, split, scale=1.0, mpp=1.0, min_area_m2=100_000, cool=cool, green=gsplit)
    assert len(f3) == 0 and d3["too small"] == 4, f"m² band not applied: {d3}"

    # ...and --explain must name the filter that did it, on the same fixture.
    why = "\n".join(explain_at(img, split, 1.0, (50.0, 50.0), [], mpp=1.0,
                                min_area_m2=100_000, cool=cool, green=gsplit, probe=20.0))
    assert "0% of that box" in why and "too small" in why, f"--explain must name the band: {why}"
    # A polygon over the probe box is the other answer, and it comes from the
    # run's own output rather than from a re-derivation.
    covered = explain_at(img, split, 1.0, (50.0, 50.0),
                         [{"geom": shapely.box(0, 0, 100, 100), "feature_type": "salmon"}],
                         mpp=1.0, cool=cool, green=gsplit, probe=20.0)
    assert "100% of that box" in covered[1], f"--explain must read the run first: {covered}"
    # An in-band component that the run KEPT must be named as kept. Probing the
    # street beside a parcel is the `Prisons` shape: the box is barely covered,
    # the component beside it is in band, and blaming a filter for it is wrong.
    f4, _ = blocks_from_colour(img, split, scale=1.0, mpp=1.0, cool=cool, green=gsplit)
    beside = "\n".join(explain_at(img, split, 1.0, (100.0, 50.0), f4, mpp=1.0,
                                  cool=cool, green=gsplit, probe=20.0))
    assert "KEPT as" in beside and "dropped later" not in beside, \
        f"--explain must match an in-band component to the polygon it became: {beside}"

    # component_polygon is a concave hull, and both neighbours it sits between
    # are silent failures: a convex hull scores fine and swallows the notch, a
    # per-pixel trace scores fine and carries a thousand vertices. An 89-line
    # swap to the trace once rode into `main` inside a docs commit because
    # nothing here could tell the three apart. These two shapes can.
    ell = np.ones((200, 200), bool)
    ell[100:, 100:] = False
    g = component_polygon(ell, 0, 0, 1.0)
    notch = g.area / shapely.box(*g.bounds).area
    assert notch < 0.80, f"the notch of an L was swallowed — convex hull? ({notch:.3f})"

    ragged = np.ones((200, 200), bool)
    ragged[::2, 190:] = False
    verts = len(component_polygon(ragged, 0, 0, 1.0).exterior.coords)
    assert verts <= 20, f"a ragged edge returned {verts} vertices — per-pixel trace?"

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
    p.add_argument("--no-recut", dest="recut", action="store_false",
                   help="drop components over --max-m2 instead of re-cutting them at a higher "
                        "ink threshold. Re-cutting is the default because it is the only thing "
                        "that puts a block over the Arsenal de la Marine's dockyard apron "
                        "(81,764 m²) — on the 1882 sheet exactly one component trips the cap, "
                        "1.77 km² of naval quarter welded to the river's ripple band, and with "
                        "no block there the water region runs straight over the quay. It costs "
                        "888 polygons against 798, land_plot mean 0.331 against 0.350, and "
                        "~55 s. --no-recut restores the smaller, faster, blunter run")
    # Every flag below defaults ON, which is the run every number in
    # EVAL-BASELINE.md and docs/journals/260918-colour-blocks.md was measured on.
    # They were opt-in while each was being proved; leaving them that way meant a
    # bare `--map-id` run returned the 253-block pass at land_plot 0.247 instead of
    # the 888-polygon one at 0.331, i.e. the script withheld its own best result
    # from anyone who had not read the journal. `--recut` set the precedent for
    # the `--no-...` escape and the others now follow it.
    p.set_defaults(recut=True, cream=True, drop_furniture=True, drop_water=True,
                   drop_slivers=True, swatch_labels=True, split_buildings=True,
                   clip_main_map=True)
    p.add_argument("--no-clip-main-map", dest="clip_main_map", action="store_false",
                   help="keep the polygons outside the printed border. The paper "
                        "margin, the mount and the scanner surround are tinted and "
                        "componented like anything else, and their concave hulls run "
                        "diagonally across the sheet; the 1898 sheet showed both. The "
                        "rectangle is the sheet's own `main_map` triage region, so "
                        "this needs --map-id and is a no-op on a sheet not yet triaged")
    p.add_argument("--no-swatch-labels", dest="swatch_labels", action="store_false",
                   help="name each polygon by a pixel vote over the pigment classes "
                        "instead of against the legend's own five swatches. The "
                        "swatch key is the default because it is the only thing that "
                        "gives the sheet its fifth class, *service local*, which is a "
                        "hatch rather than a tint and which no trough can find; it "
                        "also lets a block be cream, which a vote over the pigment "
                        "union cannot. Changes no geometry either way")
    p.add_argument("--legend-swatches", choices=("fixed", "auto"), default="fixed",
                   help="fixed 1882 key (default), or measure the largest OCR legend "
                        "box at render scale; requires --map-id, falls back on "
                        "disagreement. Detection needs 1:1 — see find_swatches, it "
                        "falls back at every --render below source width")
    p.add_argument("--hatch-coherence", type=float, default=HATCH_COHERENCE,
                   help="with --swatch-labels, the share of a block's line work that "
                        "must run at one angle for it to be called the hatched "
                        "administrative class. Tree stipple runs every way and fails "
                        f"it (default {HATCH_COHERENCE}); 0 disables the test")
    p.add_argument("--dilution", type=float,
                   help="override the fitted wash strength (0-1) for --swatch-labels")
    p.add_argument("--no-cream", dest="cream", action="store_false",
                   help="emit blocks only, leaving the cream parcels — the unassigned "
                        "domain land — blank. The cream pass is the default because "
                        "those parcels are two thirds of the 1882 sheet's hand-traced "
                        "land plots: without it land_plot mean is 0.247 on 253 "
                        "polygons, with it 0.331 on 888. Its own swept ink threshold, "
                        "no closing")
    p.add_argument("--cream-ink", type=float,
                   help="override the swept cream ink threshold")
    p.add_argument("--no-drop-furniture", dest="drop_furniture", action="store_false",
                   help="keep the polygons inside the title cartouche and the legend "
                        "box. They are printed rectangles full of text and are not "
                        "parcels; dropping them is the default and moves no score, "
                        "which is the point — it removes 19-21 things that were never "
                        "scoreable. Located from the sheet's own OCR labels, so it "
                        "needs --map-id and Supabase credentials and declines without "
                        "them")
    p.add_argument("--no-drop-water", dest="drop_water", action="store_false",
                   help="keep the polygons that are river surface: bare paper drawn "
                        "over with sparse blue ripple, which the cream pass traces "
                        "into long thin parcels across the whole river. Dropping them "
                        "is the default and takes ~200 polygons off the 1882 sheet "
                        "without moving land_plot or building a digit, because every "
                        "one of them was a false positive. This removes geometry")
    p.add_argument("--no-drop-slivers", dest="drop_slivers", action="store_false",
                   help="keep polygons too stringy to be a parcel (outline circularity "
                        f"below {MIN_CIRCULARITY}). On the 1882 sheet these are the shapes "
                        "the cream pass traces between the river's ripple lines. "
                        "Dropping them is the default: swept, and the traces do not "
                        "notice — though the ceiling is two steps away, at 0.15 "
                        "land_plot falls to 0.326. Removes geometry")
    p.add_argument("--explain", metavar="X,Y|TEXT",
                   help="after the run, say what happened at a point — either source "
                        "pixels as X,Y or a substring of an OCR label ('Prisons'), in "
                        "which case every matching row is explained, because duplicate "
                        "rows at different positions are what makes a named check "
                        "irreproducible. Answers KEPT from the run's own output and "
                        "re-derives the component only when nothing covers the point")
    p.add_argument("--no-split-buildings", dest="split_buildings", action="store_false",
                   help="stop after the parcels, without the within-block split. The "
                        "split is on by default because it is the only thing that has "
                        "moved `building` off the block prior's ceiling — 0.122 to "
                        "0.278 mean and 1 to 5 traces over IoU 0.5, on fewer polygons. "
                        "It has no precision figure yet, so turn it off if a consumer "
                        "needs the block prior alone")
    p.add_argument("--split-rg", type=float, default=SPLIT_RG,
                   help="how much redder than its own parcel's wash a building is "
                        f"(default {SPLIT_RG}, the measured median over the 17 traces)")
    p.add_argument("--ocr-run-id",
                   help="pin the OCR rows this pass reads — the water seeds, the "
                        "furniture mask, the legend panel and --explain — to one run. "
                        "Without it every run on the sheet is pooled, which is the "
                        "default only so nothing existing moves: the 1882 sheet's 499 "
                        "labels are three runs, so an object can seed the pass three "
                        "times and re-OCR'ing a sheet silently changes its geometry")
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

    rows = None
    swatches = LEGEND_SWATCHES
    if args.legend_swatches == "auto":
        try:
            if not args.map_id:
                raise ValueError("--legend-swatches auto needs --map-id")
            rows = furniture_rows(args.map_id, args.ocr_run_id)
        except Exception as exc:                              # noqa: BLE001
            # None, not [] — `furniture_mask` reads this same fetch below and
            # treats an empty list as "the sheet has no title or legend labels",
            # so a blip here would silently turn --drop-furniture into a no-op
            # and report it as a property of the sheet.
            rows = None
            print(f"  legend swatches source: fallback ({exc})")
        else:
            swatches = legend_swatches(rgb, scale, rows)

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

    wet: list[tuple[float, float]] = []
    if args.map_id:
        try:
            wet = water_points(args.map_id, args.ocr_run_id)
            print(f"{len(wet)} hydrology labels — oversized components holding one stay dropped")
        except Exception as exc:                                  # noqa: BLE001
            print(f"  (no hydrology labels: {exc})")

    feats, dropped = blocks_from_colour(
        rgb, split, scale, mpp=mpp, close=args.close,
        min_area_m2=args.min_m2, max_area_m2=args.max_m2, ink_v=args.ink, cool=cool,
        green=green, water=wet, recut=args.recut,
    )
    for reason, n in sorted(dropped.items()):
        if n:
            print(f"  dropped {n} as {reason}")
    cream_ink_v = None
    if args.cream:
        px_area_m2 = (mpp * scale) ** 2 if mpp else None
        if args.cream_ink is not None:
            cream_ink_v = args.cream_ink
        else:
            cream_ink_v, curve = cream_ink(
                rgb, split, cool=cool, green=green, px_area_m2=px_area_m2,
                min_area_m2=args.min_m2, max_area_m2=args.max_m2)
            print(f"cream ink swept to V < {cream_ink_v:.2f} "
                  f"(paper peak {paper_peak(rgb):.2f}); in-band by threshold: {curve}")
        # No closing: the closing is what rejoins a *block* across the lines drawn
        # on it, and here those same lines are the parcel boundaries being read.
        cfeats, cdropped = blocks_from_colour(
            rgb, split, scale, mpp=mpp, close=0,
            min_area_m2=args.min_m2, max_area_m2=args.max_m2, ink_v=cream_ink_v,
            cool=cool, green=green, classes=("cream",), recut=False)
        print(f"  cream pass: {len(cfeats)} parcels, dropped "
              + ", ".join(f"{n} {r}" for r, n in sorted(cdropped.items()) if n))
        feats = feats + cfeats
        feats, cut, mostly_block = subtract_blocks(feats)
        if cut or mostly_block:
            print(f"  cut {cut} cream hulls back off the blocks they closed over, "
                  f"dropped {mostly_block} that were a block with a rim")

    if args.clip_main_map and args.map_id:
        # The neatline is not a colour boundary, so nothing upstream of here can
        # see it: the margin, the mount and the scanner surround carry tone and
        # component exactly like a block. Their hulls are worse than the
        # polygons — a stringy margin strip hulls into a diagonal across the
        # sheet. The rectangle is already in the database (`main_map`, the same
        # crop `to_sam2_seeds.load_seeds_from_prior` clips against); this pass
        # was the only consumer that never read it.
        try:
            frame = main_map_frame(args.map_id)
        except Exception as exc:                                  # noqa: BLE001
            frame = None
            print(f"  (no main_map crop: {exc})")
        if frame is None:
            print("  no main_map region on this sheet — nothing clipped")
        else:
            x, y, x1, y1 = (int(v) for v in frame.bounds)
            before = len(feats)
            feats = [f for f in feats if shapely.centroid(f["geom"]).within(frame)]
            print(f"  dropped {before - len(feats)} outside the printed border "
                  f"[{x} {y} {x1 - x} {y1 - y}]")

    if args.drop_furniture:
        if not args.map_id:
            print("  --drop-furniture needs --map-id; skipped", file=sys.stderr)
        else:
            try:
                furn = furniture_mask(args.map_id, rows=rows, run_id=args.ocr_run_id)
            except Exception as exc:                              # noqa: BLE001
                furn = None
                print(f"  (no furniture mask: {exc})")
            if furn is None or furn.is_empty:
                print("  no title/legend labels on this sheet — nothing dropped")
            else:
                before = len(feats)
                feats = [f for f in feats if not shapely.centroid(f["geom"]).within(furn)]
                print(f"  dropped {before - len(feats)} inside the title or legend box")

    if args.drop_water:
        wet_mask = water_mask(feats, rgb, scale, wet, ink_v=args.ink)
        kept = [f for f, w in zip(feats, wet_mask) if not w]
        km2 = sum(f["geom"].area for f, w in zip(feats, wet_mask) if w) * ((mpp or 0) ** 2) / 1e6
        print(f"  dropped {len(feats) - len(kept)} as river surface"
              + (f" ({km2:.2f} km²)" if mpp else ""))
        feats = kept

    if args.drop_slivers:
        thin = sliver_mask(feats)
        km2 = sum(f["geom"].area for f, w in zip(feats, thin) if w) * ((mpp or 0) ** 2) / 1e6
        feats = [f for f, w in zip(feats, thin) if not w]
        print(f"  dropped {sum(thin)} as slivers, too stringy to be a parcel"
              + (f" ({km2:.2f} km²)" if mpp else ""))

    if args.swatch_labels:
        feats, changed, alpha, demoted = relabel_by_swatch(
            feats, rgb, scale, alpha=args.dilution, green=green, ink_v=args.ink,
            hatch=args.hatch_coherence or None, swatches=swatches)
        print(f"  legend key fitted at alpha {alpha:.2f} of full ink; "
              f"re-labelled {changed} of {len(feats)} polygons")
        if demoted:
            print(f"  {demoted} of them held ink that runs no one way — stipple, "
                  f"not a hatch — and took the nearest tint instead")

    if args.split_buildings:
        built = split_buildings(feats, rgb, scale, mpp, rg=args.split_rg, ink_v=args.ink)
        print(f"  within-parcel split: {len(built)} buildings off "
              f"{len(feats)} parcels")
        feats = feats + built

    kinds: dict[str, int] = {}
    for f in feats:
        kinds[f["feature_type"]] = kinds.get(f["feature_type"], 0) + 1
    label = "blocks + parcels" if args.cream else "blocks"
    print(f"{len(feats)} {label}: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    if args.explain:
        try:
            x, y = (float(v) for v in args.explain.split(","))
            targets = [(args.explain, "point", x, y)]
        except ValueError:
            if not args.map_id:
                print("  --explain by label needs --map-id", file=sys.stderr)
                targets = []
            else:
                targets = labels_matching(args.map_id, args.explain, args.ocr_run_id)
                if not targets:
                    print(f"  no OCR label contains {args.explain!r}")
        for text, cat, x, y in targets:
            print(f"\n{text}  [{cat}]")
            for line in explain_at(rgb, split, scale, (x, y), feats, mpp=mpp,
                                   close=args.close, min_area_m2=args.min_m2,
                                   max_area_m2=args.max_m2, ink_v=args.ink,
                                   cool=cool, green=green):
                print(line)
        print()

    if args.out:
        write_outputs(Path(args.out), feats, {
            "source": "colour-blocks",
            "rg_split": round(split, 4),
            "cool_split": round(cool, 4) if cool is not None else None,
            "green_split": round(green, 4) if green is not None else None,
            "render": int(rgb.shape[1]),
            # The working image itself, not the request that produced it. Two
            # fetches of `--map-id X --render 6144` are not the same pixels:
            # `fetch_crop` can answer from the region URL, from a composed tile
            # pyramid or from a full download, and each resamples differently.
            # Measured on 20ec4f9a: two runs at this render split the green axis
            # at +0.0125 and +0.0075, and the class mix inside the same frame
            # went salmon 284 -> 671, green 106 -> 11 on 3,185 vs 3,177 polygons.
            # The geometry was stable and the labels were not. Every threshold
            # below is derived from these bytes, so without this the manifest
            # cannot tell a real change from a different JPEG.
            "image_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "ink_fraction": round(ink_fraction, 4),
            "cream_ink": round(cream_ink_v, 3) if cream_ink_v is not None else None,
            "block_area_m2": [args.min_m2, args.max_m2] if mpp else None,
            # Which OCR rows seeded the water, the furniture mask and the legend
            # panel. null means every run on the sheet was pooled, which is a
            # property of the run and not of the sheet — see `ocr_rows`.
            "ocr_run_id": args.ocr_run_id,
        })
    else:
        print("(no --out, nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
