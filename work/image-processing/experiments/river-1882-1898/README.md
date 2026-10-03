# 1882 and 1898 river EDA

**2026-10-01.** Both images come from `iiif.maparchive.vn`, using its fixed
tile URLs. `eda.py` caches the *original JPEG response bytes* in
`/private/tmp/vma-river-iiif-raw-cache`; the shared `fetch_crop_level0` helper
currently re-encodes tiles in its cache, which changed some pixel values between
the first fetch and a later read. A repeat of this EDA from the raw-byte cache
produced the same `eda.json` SHA-256:
`411af292d430c290c52708834bb1564e6bcc1bac046758e035c93e0dd5273401`.
`windows.json` pins the source-pixel boxes; `eda.json` records each crop's RGB
hash, tile count and statistics. `contact.jpg` shows the native crops and
`dark-rb-histograms.png` plots the dark-ink distributions. Reproduce with:

```sh
work/ocr/.venv/bin/python -u work/image-processing/experiments/river-1882-1898/eda.py
```

The two `water_core` windows are visually all water. The `dry_blue` windows are
blue-grey urban land. The quay and creek windows mix classes and are visual
failure probes, not accuracy controls. This is a small purposive sample, not a
whole-sheet estimate. Each statistic below uses **native source pixels** unless
its tile level is named.

## What the pixels say

| Measure | 1882 water | 1882 blue land | 1898 water | 1898 blue land |
| --- | ---: | ---: | ---: | ---: |
| Median RGB | 225, 212, 193 | 216, 206, 188 | 239, 237, 221 | 208, 212, 210 |
| Dark-pixel share, max RGB < 0.8 | 11.96% | 38.41% | 13.36% | 40.95% |
| Median dark-pixel `(R−B)/255` | +0.055 | +0.067 | −0.024 | −0.043 |
| Dark pixels passing `(R−B)/255 < 0.07` | 81.91% | 64.24% | 99.87% | 92.04% |
| Global gradient directionality | 0.882 | 0.445 | 0.834 | 0.578 |

The colour cut accepts much of the blue land on both sheets. The water-to-land
order of the dark `(R−B)/255` median even reverses between sheets. A single
absolute threshold cannot be the river definition. Both water cores have
strong directional ruling, but the 1898 creek window scores **0.815** because
its *salmon land hatch* is also directional. Direction alone is not water.
1898's water is much brighter than its blue land, while 1882's water and blue
land are closer in brightness. A colour likelihood can help, but its samples
must come from each sheet and include confusable land.

VMA's pyramid level changes the colour seen by the detector. The median dark
`(R−B)/255` in the **same water-core boxes** is:

| VMA tile scale | 1882 | 1898 |
| --- | ---: | ---: |
| Native (factor 1) | +0.055 | −0.024 |
| Factor 2 | +0.078 | +0.012 |
| Factor 4 | +0.106 | +0.031 |

The nearby blue-land medians move far less (1882 +0.067 → +0.067 → +0.067;
1898 −0.043 → −0.035 → −0.039). Downsampled river ink blends with paper
more than dense land hatch does. This explains why the earlier 1882 half-size
colour pass could nearly erase an all-water river core even though its native
ink is mostly below the 0.07 cut. The table compares VMA's actual fixed tile
levels; a Lanczos resize of the native crop is **not equivalent** to those
levels, as `eda.json` records. River measurements and proposed masks should
therefore use one pinned native tile level and source-pixel coordinates.

## Shared method, separate calibration

Work on 1882 and 1898 together for the *method and review gates*. Their river
drawings both have ruled water and explicit banks, so the same feature logic is
worth testing. They differ in pigment, paper, rotation and river/land contrast;
reuse of one sheet's RGB thresholds would overfit. The 1898 sheet is north-up
while 1882 is rotated about 90° on paper, so texture features should use
orientation strength and local continuity rather than a fixed horizontal or
vertical direction.

1. **Read native tiles with an overlap halo.** Keep the source grid, tile-byte
   hashes and output resolution pinned. Do not borrow the 6051-pixel block
   render for the river pass. Cache raw IIIF bytes rather than recompressed
   tiles before comparing small colour changes.
2. **Calibrate appearance per sheet.** Sample a few confirmed water interiors,
   dry blue parcels, roads, hatched land, and paper near each bank. Use local
   paper-relative colour and ruling density as *probabilities*, not a single
   hue cut. Preserve a low-confidence class where water and land overlap.
3. **Constrain the proposal with bank and connection evidence.** Trace paired
   shorelines where visible, seed the named main river and tributaries, and
   propagate through small gaps only when the bank geometry supports it. A
   bridge or river label may interrupt ink without ending the water body.
   Dry streets at the Arsenal and blue-grey 1898 blocks need explicit negative
   evidence. The current hard `land_mask` can also erase enclosed basins, so
   review those separately.
4. **Review feature types separately.** Main river, narrow creek, basin, quay,
   bridge and text occlusion fail differently. Do not choose one morphology
   radius to cover all of them. Mark a proposed shoreline's uncertainty where
   the printed bank is ambiguous.
5. **Gate on both sheets.** Trace water and adjacent land in several disjoint
   native-pixel windows per sheet. Include open river, an Arsenal/quay reach,
   a narrow channel, blue-grey urban land, and a fold or lettering gap.
   Calibrate on some windows and hold others out, including at least one
   1898 window. Compare water IoU, false-water area on land, and bank distance
   by case. A threshold that improves the 1882 core but floods 1898 land or
   Arsenal streets fails. The existing two 1882 volunteer waterway traces and
   these four binary cores/controls cannot establish whole-sheet precision.

This paired EDA makes the next implementation choice clear: build one
source-resolution, bank-aware river workflow with per-sheet colour estimates.
Do not promote the 1882 `0.09` diagnostic mask or apply it to 1898 as a final
river layer.

A concrete first algorithm trial is a **seeded region graph** over overlapping
native tiles. Each small image region gets a sheet-calibrated water likelihood
from paper-relative colour and local line texture. A detected bank adds a high
cost to crossing into the neighbouring region; confirmed dry land adds a
negative seed. OCR hydrology labels and a few checked interior points provide
positive seeds. The graph can bridge an isolated text or bridge gap without a
large morphological close that leaks down an Arsenal street. Treat narrow
channels and enclosed basins as separate seed cases, then join only where the
printed banks permit it. The graph's low-margin regions become the human review
queue. Keep the existing colour mask as one input and a baseline comparator,
not the target to imitate.
