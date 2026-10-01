# River reconstruction on the 1882 and 1898 Saigon plans

**Record date: 2026-10-01. Status: exploratory; no river layer approved.**

The 1882 cadastral sheet is the first in-depth reconstruction. River is the first
feature, before roads, blocks and buildings. The 1898 Bertaux cadastral plan is
the paired transfer check. Both are polychrome and draw water with repeated
lines and visible banks. Their pigment, paper, rotation and water-to-land colour
relationships differ. **Develop and evaluate one river method on both sheets;
calibrate its appearance model on each sheet separately.** This shares the
expensive tracing and evaluation design while making an 1882-only threshold
failure visible before it becomes a general rule.

## Sources and coordinate rule

| Sheet | VMA map ID | Source scan | River sample |
| --- | --- | ---: | --- |
| 1882 Plan Cadastral | `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b` | 12102 × 8982 px | [1882 river pilot](../work/analysis/1882/README.md) |
| 1898 Bertaux | `20ec4f9a-16bd-4895-a593-40c6ed9c9555` | 16267 × 14859 px | [paired EDA](../work/analysis/river_pair/README.md) |

Use **VMA's `iiif.maparchive.vn` fixed tiles**, in source image pixels. Do not
mix a source-pixel trace with a reduced render without recording the scale. A
georeference change does not alter source-pixel coordinates, but a rescan can.
The paired EDA pins each crop's RGB hash in `eda.json`; its script caches the
original VMA JPEG tile bytes. The shared `fetch_crop_level0` cache currently
re-encodes fetched JPEGs at quality 90, which changed some pixel values on a
repeat read. That is material when a colour cut lies close to the ink colour.
Fix or bypass that cache before using small pixel differences as an acceptance
test. The raw-byte EDA repeated with the same JSON SHA-256.

The review artefacts are separate from approved archive features:

| Artefact | What it shows |
| --- | --- |
| [1882 window manifest](../work/analysis/1882/river-windows.json) and [contact sheet](../work/analysis/1882/river-windows.jpg) | Source-pixel river, quay, creek and dry-control sites. |
| [1882 default overlay](../work/analysis/1882/river-baseline-007.jpg) | The missed open river at the current 0.07 ink cut. |
| [1882 0.09 mask](../work/analysis/1882/river-proposal-009.png) and [overlay](../work/analysis/1882/river-proposal-009.jpg) | A diagnostic result at 6051 × 4491 render pixels. |
| [Paired native crops](../work/analysis/river_pair/contact.jpg), [dark-ink histograms](../work/analysis/river_pair/dark-rb-histograms.png), [statistics](../work/analysis/river_pair/eda.json) | Cross-sheet pixels and VMA pyramid measurements. |

## What has been measured

The 1882 colour pipeline uses a water mask mainly to remove false parcel
proposals. Its first VMA IIIF run on a 6051 × 4491 render wrongly treated that
render as the 12102-pixel source; OCR hydrology seeds and area thresholds were
mis-scaled. **Discard that run.** `colour_blocks.py --source-width 12102` now
keeps the source grid explicit, and `--export-water-mask` saves the actual mask
used for filtering. The corrected default mask covers only **0.08%** of a
hand-checked 200 × 200 source-pixel box entirely inside the open river and **0%**
of two all-dry city controls. This is a local coverage check, not whole-sheet
recall or precision.

A fixed-geometry diagnostic sweep on that half-size 1882 render gave:

| Dark-ink `(R−B)/255` cut | Open-river core selected | Dry city controls selected | Visual finding |
| --- | ---: | ---: | --- |
| < 0.07, current | 0.08% | 0% | Most open water absent |
| < 0.09, proposal | 60.70% | 0% | Main river and creek improve; holes and quay errors remain |
| < 0.11 | 100% | 0% | False water visibly runs into Arsenal streets |

These are **mask shares**, not raw colour shares. The dry controls cannot detect
the Arsenal leak. The 0.09 mask is a saved diagnostic proposal, not an accepted
shoreline and not a setting to apply to 1898. The earlier best-match waterway
IoU of **0.582** uses only **two** 1882 volunteer traces, not an exhaustive or
independent river test. MapSAM2 has no evaluated water-specific run on the
colour prior; its LoRA trained on the sheet's 46 volunteer traces.

The [paired native-pixel EDA](../work/analysis/river_pair/README.md) uses one
visually all-water box and one blue-grey dry-land box on each sheet, plus mixed
quay and creek probes. Its key figures are:

| Native-pixel measure | 1882 water | 1882 blue land | 1898 water | 1898 blue land |
| --- | ---: | ---: | ---: | ---: |
| Median RGB | 225, 212, 193 | 216, 206, 188 | 239, 237, 221 | 208, 212, 210 |
| Median dark-ink `(R−B)/255` | +0.055 | +0.067 | −0.024 | −0.043 |
| Dark ink passing `< 0.07` | 81.91% | 64.24% | 99.87% | 92.04% |

Dark ink here means `max(R,G,B)/255 < 0.8`. Water and blue-grey land overlap
on both sheets; the ordering of their median dark ink reverses. A fixed colour
cut is therefore neither a water definition nor a transferable setting.
Directional ruling helps, but hatch on dry land can also be directional: the
1898 mixed creek window's global directionality is **0.815** largely because of
salmon land hatch.

The VMA tile level changes the colour seen by the detector in the *same water
boxes*:

| VMA fixed-tile factor | 1882 median dark `(R−B)/255` | 1898 median dark `(R−B)/255` |
| --- | ---: | ---: |
| 1, native | +0.055 | −0.024 |
| 2 | +0.078 | +0.012 |
| 4 | +0.106 | +0.031 |

The blue-grey land median shifts much less. Sparse river lines blend with
paper as the pyramid level changes; the EDA does not establish whether JPEG
encoding, resampling or another processing step accounts for the exact shift.
The practical rule is to **detect and score river water at one pinned native
tile level**, in overlapping tiles, and keep the output in source pixels. The
block pipeline's half-size render remains a separate baseline.

## Hard cases and proposed response

| Case | Observed failure | Response to test |
| --- | --- | --- |
| Open river | 1882 half-size hue cut drops almost all of a confirmed water core. | Use native tiles and a sheet-calibrated appearance likelihood; check the entire interior, not just ripple ink. |
| Narrow creek | The current mask finds fragments but misses banks and reaches. | Follow paired bank evidence and connection from a confirmed creek seed; do not require the open river's minimum component area. |
| Arsenal quay and dry streets | A wider colour cut recovers water but leaks across the quay into streets. | Treat the printed bank as a costly boundary crossing and nearby streets as negative evidence; trace quay water and land for a false-water score. |
| Enclosed basin or lake | Hard land exclusion can remove real water. A prior size/containment rule also flooded dry city blocks. | Give enclosed water its own confirmed seed and bank test; do not infer it from enclosure alone. |
| Bridge, label or fold | Black print and paper gaps interrupt the water texture. | Permit short connections supported by banks on both sides, then flag the gap for human review. |
| Blue-grey urban hatch | Many dry-land dark pixels pass the water hue cut on both sheets. | Calibrate with hard negative land samples and keep a land/road barrier; do not call every directional blue mark water. |

The first algorithm trial should be a **seeded region graph** on overlapping
native tiles. For each small region, estimate water likelihood from local
paper-relative colour, line density and line direction; fit appearance
separately for each sheet. Put a high cost on crossing a detected bank, use OCR
hydrology names and checked interior points as positive seeds, and checked dry
streets or parcels as negative seeds. Review regions where the evidence is
close. Keep main river, narrow channels and enclosed basins as distinct cases.
This is a design proposal, not a tested improvement.

## Evaluation gate and work order

1. **Make a paired reference set.** Hand-trace water and adjacent land in
   disjoint native-pixel windows on both sheets: open river, quay, narrow
   channel, enclosed water if present, blue-grey urban land, and one text,
   bridge or fold gap. Record how a boundary crossing the window is clipped.
   Keep some windows out of all colour calibration and method tuning.
2. **Run comparable proposals.** Save the existing 1882 mask, the 0.09 trial,
   the proposed bank-aware method, and the corresponding 1898 outputs with
   source IDs, tile level, crop hashes, code settings and OCR seed run pinned.
   Do not silently pool new OCR runs into an old comparison.
3. **Measure by case and sheet.** Report water IoU, false-water area on land,
   missed-water area and bank distance in source pixels. Report main river,
   creek, quay and basin separately. A good core score with an Arsenal or
   1898 land leak fails the gate. Selected-window scores are not whole-sheet
   precision; say how the windows were chosen.
4. **Review before promotion.** Have a person check low-confidence shoreline
   reaches and record corrections with their source pixels. Accept a river
   layer only after the held-out windows and visual whole-sheet review pass.
   Then move to road surfaces, followed by blocks and buildings.

**Change to step 1 (owner, 2026-10-01): blind point labels replace polygon tracing.** Tracing
cost hours per window; 300 random points in the held-out windows, each labelled water / road /
land / unsure on a page that never shows a proposal, the window or its case
([`label.py`](../work/analysis/river_ref/label.py)), are one keystroke each and give accuracy
with a ±2–3 point interval. What they do not give is a shoreline distance in pixels: the
scorer reports, for each wrong point, its distance to the proposal's edge instead. Few points
land on narrow water, so creek and basin numbers rest on single digits; an edge-stratified batch
is the fix. Traces remain supported by `score.py` if a window ever needs one.

## River pass v1, 1882 (2026-10-01)

[`work/ocr/scripts/river_pass.py`](../work/ocr/scripts/river_pass.py), commit `27ee4023`, on the
sheet-wide layers of `sheet_features.py`. What the sheet showed first:

- **Colour cannot do it.** Ripples and the military ruling are the same blue ink (measured optical
  density directions agree within noise). The earlier hue cuts failed for this reason.
- **Geometry can.** The military ruling and the salmon hatch are machine-ruled: 4.48 and 5.09 px,
  always at 144°, with a sharp spectral peak. Ripples are hand engraved, 6–28 px apart, following
  the bank. A per-cell FFT measures the share of power at the ruling (≈0.9 ruled, <0.06 ripples).
- **The south bank has no ink line**; the ripples stop. The proposal's edge is therefore the
  outermost ripple line, not a detected bank.
- **The citadel's rampart hachures look exactly like ripples** (owner: they draw height, not a
  ditch). Texture cannot separate them, so only water joined to the river network is accepted;
  isolated water-like bodies (the citadel, garden ponds, creek pieces cut off by bridges) go to a
  review list and are not water until a person confirms them. This is the "enclosed water needs its
  own confirmed seed" rule above.

Thresholds were set on the calibrate windows and on whole-sheet cell maps; one tuning overlay also
showed `citadel_moat`, `blue_domain` and part of `bridge_basin`, which are marked `seen`. Score,
run once on 300 owner labels (11 unsure), review bodies counted as not water:

| Group | Accuracy [95% CI] | Missed water | False water |
|---|---|---|---|
| all | 96.5% [94–98] (279/289) | 4/52 | 6/237 |
| held-out, unseen | 97.6% [94–99] (163/167) | 3/40 | 1/127 |
| held-out, seen | 95.1% [90–98] (116/122) | 1/12 | 5/110 |
| quay | 89.8% [78–96] | 0/17 | **5/32** |
| creek | 95.8% [86–99] | 2/9 | 0/39 |
| dry land, moat (dry), outskirts, canal, bridge | 100% | — | 0 |

The failure that matters is **false water on quays**: all five false points sit 17–60 px past
the bank, the leak this document predicted. Three of the four misses are more than 150 px from any
proposed water, i.e. whole bodies not found: narrow creeks too thin for 32 px cells. Calibration
views show the same limit on the garden streams. The 1882 dry and moat windows have no false water.
**Owner review of the isolated bodies (2026-10-01).** Of 12, five are water (three creek reaches
cut off by bridges or the tramway, the Gouverneur garden pond, the Jardin Botanique pond) and
seven are not (citadel rampart ×3, street lettering ×2, cathedral hatching, a block edge). The
answers are points in [`confirmed.json`](../work/analysis/river_ref/confirmed.json); the pass
promotes a confirmed body and reports a point that no longer lands in a body as stale. Rescored on
the same labels (fair: the change came from the review, not from the labels): **97.2% [95–99]**,
missed water 2/52, false water unchanged at 6/237; unseen held-out 98.8% [96–100]. Both creek
misses were in confirmed reaches. Left: the five quay points, one basin miss and one basin false
point, and one water point in `blue_domain` more than 150 px from any proposed water.

**Fresh batch, edge-stratified (seed 2, 2026-10-01).** 156 new points in the held-out windows:
108 within 30 px of the `15995ce3` water edge, 48 uniform; committed before labelling, labelled
by the owner (7 unsure, bridges dropped). The same version, scored once:

| Group | Accuracy [95% CI] | Missed water | False water |
|---|---|---|---|
| all (edge-weighted, so harder than the sheet) | 95.3% [91–98] (141/148) | **0/43** | 7/105 |
| edge stratum, within 30 px | 94.1% [88–97] | 0/38 | **6/63** |
| uniform stratum | 97.9% [89–100] | 0/5 | 1/42 |

Every error is false water, every one within 61 px of the proposal's edge and five of seven
within 22 px: **the edge sits outside the bank, never inside it.** The bias is one-sided, so it is
a placement fault (closing radius, core cells, hole filling), not a detection fault. Quays, the
canal and creeks all show it. Both batches are now spent on this version.

Not done: the edge fix (tune on calibrate windows, score on a third batch), the 1898 transfer.
No layer is approved. This task is tracked under `river-reconstruction` in
[ROADMAP.md](ROADMAP.md).
