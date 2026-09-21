# River masks for georeferencing: first local comparison

2026-09-20. This is a read-only feasibility check of the existing colour probe,
not a river accuracy or georeferencing improvement claim. Inputs are the four
source-resolution 1024 px crops and the exact coordinates recorded in
`docs/journals/260920-colour-transfer.md`. Reproduce the overlays with:

```sh
work/ocr/.venv/bin/python work/analysis/district4/river_probe.py \
  --input-dir /private/tmp --out-dir /private/tmp
```

| Sheet | Cleaned mask pixels / 1,048,576 | Overlay inspection |
|---|---:|---|
| 1923 | 94,330 (9.0%) | Follows the hatched river in the lower right; only a short bank reach is in the crop. |
| 1942 | 102,580 (9.8%) | Water-color cluster, dark bank ink and local color occupancy follow the main river and southern channel. The first color-only mask (390,102 px) flooded onto land; an intermediate cleaned mask still painted stippled shore. |
| 1959 | 334,192 (31.9%) | Follows the broad cyan river; some narrow tributaries and bank details remain unselected. |
| 1968 | 195,370 (18.6%) | Follows the broad river and several branching reaches; printed text and the bridge interrupt the fill locally. |

All four overlays are plausible candidates for *annotation*, not validated
correspondences. The first 1942 result remains a useful negative control:
the pale water and adjacent land share colour, and color-only closing connected
unrelated land. A later 7-pixel closing also painted stippled foreshore; the
source-resolution correction uses local color occupancy to reject it. The
revised 1942 path still needs bank ink and two manually selected seeds. A pixel
count is area, not precision. The before/after and exact cleanup
changes are in `docs/journals/260920-colour-transfer.md` §Residue cleanup.

## What can be compared now

The 1882 `colour_blocks.py` water region is designed to reject parcel polygons
inside river water. It uses blue-grey *ruling*, directional coherence, hydrology
OCR seeds and a land barrier. `river_probe.py` instead selects a sheet-specific
colour component from manually chosen seeds and, on 1942, bank ink. They have
different outputs and neither has an exhaustive river reference mask. The masks above cannot be
ranked against the 1882 water region by IoU or boundary error.

MapSAM2 cannot run locally as a comparator: `work/MapSAM2/` has inference code,
but no local SAM2 environment or fine-tuned checkpoint. The existing LoRA was
trained on cadastral feature traces, not labelled river masks. Applying it to
water without new examples would not be a fair learned-water comparison.

## Gate before changing a georeference

1. Hand-trace water and both banks in fixed, disjoint windows of the *same*
   source scan for each method. Include one easy broad reach, one creek or
   basin, and one confusing land area. Keep one set of windows unseen during
   threshold selection or fine-tuning.
2. Score foreground IoU, false-positive area on land, and bank distance in
   source pixels on those held-out windows. Record source scan dimensions.
3. If a learned comparator is wanted, fine-tune or prompt MapSAM2 with *river*
   annotations from separate windows. Its published building, vineyard and
   railway scores are not river results.
4. Match each accepted mask to the same reference hydrography, fit the same
   transform family, and score independent GCPs withheld from fitting. Report
   their error alongside the existing Allmaps fit. A lower residual on points
   used to fit a transform is insufficient.

The reference hydrography must be dated or checked at stable reaches: riverbank
changes and reclamation can produce a neat image match to the wrong shoreline.
The 1942 live crop is 7479×6314 while its saved GCP annotation is about twice
that size; reconcile the scan before comparing its pixels to annotation GCPs.

**Decision from this run:** do not replace the current method or update any
georeference. All four masks justify a controlled annotation test; the visually
cleaned banks do not yet have a measured error. The 1942 color-only path remains
rejected.
