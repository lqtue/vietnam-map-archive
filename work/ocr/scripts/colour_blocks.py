#!/usr/bin/env python3
"""City blocks read off a polychrome sheet's own ink, in its own pixel grid.

    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --census
    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --out work/ocr/outputs/<uuid>/colour
    python work/ocr/scripts/colour_blocks.py --map-id <uuid> --cream --drop-furniture --out <dir>
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

def water_points(map_id: str) -> list[tuple[float, float]]:
    """Centres of the sheet's `hydrology` labels, in source pixels.

    Sixteen of them on the 1882 sheet — far too sparse to outline the water, and
    an earlier attempt to use them that way found only 4 of 840 cream parcels.
    They are exactly enough for the oversized-component test, though, because
    there the region is already one connected blob and the label only has to
    land inside it.
    """
    from supabase_client import fetch_ocr_extractions

    return [(r["global_x"] + (r["global_w"] or 0) / 2.0,
             r["global_y"] + (r["global_h"] or 0) / 2.0)
            for r in fetch_ocr_extractions(map_id)
            if r.get("category") == "hydrology" and r.get("global_x") is not None]


def furniture_mask(map_id: str, pad: float = 200.0):
    """The title cartouche and the legend box, from the sheet's own OCR labels.

    Both are printed rectangles full of text, which is the one thing the OCR
    pass is reliably good at, so they need no geometry of their own. The union
    of the padded `title` and `legend` label boxes drops 11 of the 1882 sheet's
    253 blocks — the same furniture counted by hand in the journal.

    A *hull* of those boxes is wrong and was tried: `legend` also tags the
    boundary annotations strung along the neatline, so their convex hull is
    very nearly the whole sheet. Per-label boxes, unioned.
    """
    from supabase_client import fetch_ocr_extractions

    rows = [r for r in fetch_ocr_extractions(map_id)
            if r.get("category") in ("title", "legend") and r.get("global_x") is not None]
    if not rows:
        return None
    boxes = [shapely.box(r["global_x"], r["global_y"],
                         r["global_x"] + (r["global_w"] or 1.0),
                         r["global_y"] + (r["global_h"] or 1.0)).buffer(pad)
             for r in rows]
    return shapely.union_all(boxes)


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
    p.add_argument("--recut", action="store_true",
                   help="rescue components over --max-m2 by re-cutting them at a higher "
                        "ink threshold instead of dropping them. Recovers the naval quarter "
                        "(blue 41 -> 216 blocks) and costs ~60 s and river false positives")
    p.add_argument("--cream", action="store_true",
                   help="also emit the cream parcels — the unassigned domain land the "
                        "block pass leaves blank. Its own ink threshold, no closing")
    p.add_argument("--cream-ink", type=float,
                   help="override the swept cream ink threshold")
    p.add_argument("--drop-furniture", action="store_true",
                   help="drop polygons inside the title or legend box, located from the "
                        "sheet's OCR labels (needs --map-id and Supabase credentials)")
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

    wet: list[tuple[float, float]] = []
    if args.map_id:
        try:
            wet = water_points(args.map_id)
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

    if args.drop_furniture:
        if not args.map_id:
            print("  --drop-furniture needs --map-id; skipped", file=sys.stderr)
        else:
            try:
                furn = furniture_mask(args.map_id)
            except Exception as exc:                              # noqa: BLE001
                furn = None
                print(f"  (no furniture mask: {exc})")
            if furn is None or furn.is_empty:
                print("  no title/legend labels on this sheet — nothing dropped")
            else:
                before = len(feats)
                feats = [f for f in feats if not shapely.centroid(f["geom"]).within(furn)]
                print(f"  dropped {before - len(feats)} inside the title or legend box")

    kinds: dict[str, int] = {}
    for f in feats:
        kinds[f["feature_type"]] = kinds.get(f["feature_type"], 0) + 1
    label = "blocks + parcels" if args.cream else "blocks"
    print(f"{len(feats)} {label}: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    if args.out:
        write_outputs(Path(args.out), feats, {
            "source": "colour-blocks",
            "rg_split": round(split, 4),
            "cool_split": round(cool, 4) if cool is not None else None,
            "green_split": round(green, 4) if green is not None else None,
            "render": int(rgb.shape[1]),
            "ink_fraction": round(ink_fraction, 4),
            "cream_ink": round(cream_ink_v, 3) if cream_ink_v is not None else None,
            "block_area_m2": [args.min_m2, args.max_m2] if mpp else None,
        })
    else:
        print("(no --out, nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
