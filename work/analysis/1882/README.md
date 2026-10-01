# 1882 river pilot — source-pixel windows

The five windows in `river-windows.json` were selected by looking at the 1882
cadastral scan at native resolution on 2026-10-01. Their canonical image service is
**VMA's IIIF mirror** at `https://iiif.maparchive.vn/iiif/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`.
`river-windows.jpg` is assembled from its fixed tiles. These are a compact diagnostic set for
the colour pass's river result: three places where water should be found or separated
from land, and two places where blue wash or dense linework must **not** be called water.
Coordinates refer to the **12102 × 8982 source scan**, not a 6051-pixel render or
the georeferenced map. The manifest pins one fixed tile's SHA-256 as an image-identity
check; it is not a checksum of the whole scan. A changed georeference does not move
these source-pixel boxes, but a rescan may. Rebuild the contact sheet with
`python work/analysis/1882/build_contact.py` after a scan change, then recheck the boxes.

The visual descriptions identify what to trace, **not ground-truth masks**. Three
`binary_controls` have been hand-checked on VMA's tiles: a 200 × 200 source-pixel
box entirely inside the open river, and the two all-dry urban windows. They support
only local water coverage and dry leakage measurements. The bank, creek and quay
still need separate hand-traced water, land, bridge and dock masks. Edge-crossing
features need an explicit clipped-window rule. Until those annotations exist, the
window shares below are not proposal precision or whole-sheet recall.

## River trial, 2026-10-01

The working image was composed from **VMA IIIF fixed tiles** at 6051 × 4491 pixels,
half the 12102 × 8982 source scan. The first colour run treated that render as the
source; its OCR seeds and area thresholds were therefore mis-scaled. It is invalid.
Rebuild that image and the five-window contact sheet with
`python work/analysis/1882/build_contact.py --render-out /private/tmp/vma-1882-iiif-6051.png`.
`colour_blocks.py --source-width 12102` now keeps the source grid explicit for a
pre-downsampled local image; `--export-water-mask` saves the exact mask used by
water filtering at render resolution. The corrected baseline saved 842,489 water
pixels. Its mask covered **0.08%** of the all-water core and **0%** of both dry
controls. The overlay is `river-baseline-007.jpg`.

The VMA render's dark ripple ink mostly has red-minus-blue above the existing
`WATER_LINE_RB = 0.07` cut. A diagnostic sweep using the same pre-water polygons,
image bytes and 16 VMA OCR hydrology points yielded:

| Ink cut | All-water core | Dry blue parcels | Dry city blocks | Visual result |
| --- | ---: | ---: | ---: | --- |
| 0.07 | 0.08% | 0% | 0% | Most open river missed |
| 0.09 | 60.70% | 0% | 0% | Open river and creek improve; holes remain |
| 0.11 | 100% | 0% | 0% | False water spreads through Arsenal streets |

`river-proposal-009.png` is the **0.09 diagnostic mask**, 6051 × 4491 render pixels,
with 255 for proposed water and 0 elsewhere. It is not an approved river footprint.
`river-proposal-009.jpg` shows the same mask over the five review windows. In the
quay window, 0.09 still catches only part of the visible water and slightly leaks
along the Arsenal edge. The two city controls alone would miss this false positive;
the quay must be traced before a threshold change is promoted into the default
pipeline. At 0.11 the large dry-land leak is obvious despite perfect scores on
the three binary controls. The creek remains incomplete at both cuts.

For repeatable sweeps, `hydrology-points.json` freezes the 16 source-pixel seed
positions from the 499 OCR rows pooled across three VMA runs, and `sweep_water.py`
checks the working image hash against the pre-water polygon run. Run
`review_water.py --image <VMA render> --mask <mask> --out <overlay>` to reproduce
the local control shares and contact sheet. The VMA render used here has RGB-byte
SHA-256 `ef24dd44038eda5998305556461edb1cfbffc7c01e3651b38bf815b0f579a3ff`.

Next, trace water and adjacent land in the bank, creek and quay windows and record
missed-water area, false-water area and shoreline error separately. The existing
`waterway` mean IoU of 0.582 uses only two volunteer traces; it was measured on a
locally cached copy. It does not settle the Arsenal and creek failures.
Keep MapSAM2 proposals separate:
there is no evaluated water run on the colour prior, and the LoRA trained on this
sheet's 46 volunteer traces.

The river comes first. The Arsenal window also exposes street gaps and parcels for
the subsequent road and block reviews; the dry city window overlaps the scoped
block/building study area in `docs/ROADMAP.md` (`shape-precision`). Do not count
either window as exhaustive for those feature types until they are traced as such.

The evidence behind this set is `docs/journals/260919-seg-audit.md` (river and
road defects), `docs/journals/260918-colour-blocks.md` (water trade-offs), and
`docs/image-processing-record.md` (feature-level comparison).
