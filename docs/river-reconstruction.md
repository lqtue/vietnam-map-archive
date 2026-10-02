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

**v2 and a third batch (seed 3, 2026-10-01).** On the calibrate windows the visible outward
fault was landing stages filled as water; v2 (`27fd4197`) cuts solid dark structures out. Scored
once on 102 fresh points (90 within 30 px of the v2 edge): **92.9% [86–97], identical to v1 on
the same points, error for error.** The pier fix touched no labelled point. Missed water is again
0/32. Of 7 false-water points, 6 are quay points in seen held-out windows; the unseen held-out
windows score 98.7% [93–100] (1 error). Across the three batches the false water collects at the
quay windows of the seen set, which in practice means the Arsenal quay, the leak case from the
first 0.09 sweep. The calibrate quay (`quay_primauguet`) does not show it, so it cannot be fixed
there.

**v3 (`1006337f`, 2026-10-01): the Arsenal fault was not a quay fault.** `arsenal_quay` is now a
`calibrate` window (it was `seen` from the first sweep and held nearly all the remaining false
water; `chinois_quay` stays the clean quay test). Looking at it, the false water is not along the
bank at all. It is the military buildings and the ground beside them, filled by the pixel stage
(`refine`), not by the cell stage or the core:

- **Buildings are machine-ruled too, at a finer pitch.** Land hatch is 4.48 px; the blue fill of
  the buildings is 3.55 px, same 144 degrees (measured by FFT on the H-shaped block and on the bars).
  The per-pixel Gabor is tuned to 4.48, so the buildings read as unruled blue lines, were closed
  into solid water, and the thin ring of hatch around each one was swept in with them.
- **Walls blank the ruling response beside them.** A dark outline swamps the Gabor's local
  normaliser, so a 25-30 px strip of ordinary hatch next to every wall reads 33 (fully ruled land
  reads 88; ripples read under 0.5) and falls just under `RULE_PX` 45.
- **Hole fill then finished the job.** A ring of such pixels enclosed the building, and the
  hole-fill (up to `HOLE_MAX` 40 000 px) refilled it.

The change, all in `refine`/`gabor_rule`, no cell logic touched: a second Gabor period
(`RULE_PERIODS` 4.48 and 3.55, per-pixel maximum); the Gabor input floored at `GABOR_FLOOR` 0.7 so a
dark outline cannot dominate the normaliser; a pixel with share at least `RULE_SOFT` 15 within
`RULE_REACH` 10 px of a fully ruled area is ruled too, where "area" means a connected ruled region
of at least `RULE_BLOB` 4 000 px; and an enclosed patch more than `HOLE_RULED` 0.5 ruled is not
refilled. The area condition matters: without it the soft rule also ate real creek ripples beside
bridge decks (the deck is ruled), turning labelled-water points to land. Self-check has two new
cases (a 3.55 building, and one ringed by ripple lines); each fails with the old constants.

Regression against `27fd4197` (water kept as `river/water-27fd4197.png`, v3 as
`river/water-1006337f.png`; the pass is deterministic):

| | v2 | v3 |
|---|---|---|
| sheet `water_px` | 11 038 228 | 10 784 780 (-253 448, -2.3%) |
| pixels added / removed | | 34 / 253 482 |
| `arsenal_quay` water | 240 361 | 79 971 (the river) |
| `quay_primauguet` | 346 032 | 345 096 (-936) |
| `abattoir_creeks` | 46 205 | 46 101 (-104) |
| `open_bank`, `river_label`, `western_creek`, `garden_pond`, `dry_blue_parcels` | | unchanged |
| `bridge_basin` (seen) | 253 598 | 248 232 (-5 366) |
| unseen heldout boxes (counts only) | | +34 / -17 212 |

Every removed edge pixel I looked at outside the unseen boxes is a clean improvement: the water
edge moves from a few pixels outside the last ripple line onto it, and ruled land slivers and
buildings drop out. On the 536 owner-labelled water/land/road points of batches 1-3, **529 are now
right (514 before)**: 15 predictions changed, all from water to a correctly labelled land point (14
in `arsenal_quay`, which goes from 36/50 to 50/50, and one in an unseen heldout window, counted
not inspected). **No labelled-water point turned to land and none turned to water.** The 7
remaining errors (3 missed water, 4 false) are all outside `arsenal_quay`: one `blue_domain` miss
and six in unseen heldout windows (the one flip there is the correct one counted above). These
batches are spent on v2 and are only a regression check; v3's score comes from batch 4.

One slip to disclose: while tuning I printed the per-point flips for batches 1-3 once with the
unseen heldout points included, and one point in `arsenal_basin` showed (a flip to correct). After
that the script printed counts only for those windows, and every pixel I viewed was outside the
unseen boxes. An intermediate setting (a softer rule without the area condition) had turned two
labelled-water points to land in unseen windows; I rejected it on that count alone, and fixed the
bridge-deck loss on windows I am allowed to see.

**Batch 4 (seed 4).** 77 points from `label.py points 1882 --seed 4
--unseen --per 3 --edge water-1006337f.png --edge-per 8 --band 30`: heldout windows with `seen: false`
only, 11 each in `chinois_quay`, `creek_nw`, `arsenal_basin`, `charner_canal`, `avalanche_head` and
the road windows `quay_rondpoint`, `outskirts_rail` (3 uniform + 8 within 30 px of the v3 edge).
Owner-labelled 2026-10-01; 3 unsure dropped.

| v3 (`1006337f`) on batch 4 | accuracy | missed water | false water |
|---|---|---|---|
| all | **100.0% [95-100] (74/74)** | 0/32 | 0/42 |
| edge stratum | 100.0% [93-100] (53/53) | 0/25 | 0/28 |
| `quay` (`chinois_quay`) | 100.0% [72-100] (10/10) | 0/6 | 0/4 |

**What this does and does not show.** v2 also scores 74/74 on batch 4: the fix's region
(`arsenal_quay`, now calibrate) is not in it, so batch 4 does not measure the fix. It shows v3 did
not break the unseen windows, edge points included. The Arsenal gain (36/50 to 50/50) rests on
spent points in a window v3 was tuned on, and v3 was partly selected on unseen-box flip counts
(above). Small batches: the lower bound at 74 points is 95%. Not done here: the 1898 transfer (next section). No layer
is approved. This task is tracked under `river-reconstruction` in [ROADMAP.md](ROADMAP.md).

## River pass, 1898 (2026-10-02)

The 1882 pass, code unchanged in its logic, run on the 16267 x 14859 Bertaux sheet
(`20ec4f9a`). Native raster pinned in `native.json` (`rgb_sha256` `0538ff83...`, 3776 tiles;
all nine 1898 window crops hash identically when cut from it, `export.py --verify 1898`). Sheet
spec in `windows.json` `sheets.1898`: legend swatches (read off the native legend), neatline
(`[700, 790, 14928, 13380]`: the four-line frame is tilted and keystoned, so the box lies inside
the innermost line at all four sides), furniture (title, scale bar with credit, legend). Features
by `sheet_features.py --sheet 1898` (2.5 GB, 95 s); the pass takes 160 s and 2.5 GB. Nothing
needed tiling. **Discipline:** the five `seen: false` heldout windows (`quay_canal`,
`creek_north`, `bridge_label`, `dry_salmon`, `hatched_bank`) were never cropped or viewed. Every
whole-sheet image I opened had them painted black, and to keep that true after I was gone the
previews that `sheet_features.py` and `river_pass.py` write now blank them as well
([`view.py`](../work/analysis/river_ref/view.py)); no count taken inside one gated a decision.

### How 1898 draws, against 1882

| | 1882 | 1898 |
|---|---|---|
| Machine ruling | land hatch 4.48 px, buildings 3.55 px, salmon 5.09 px, all at 144 deg | **5.9-6.0 px at 45 deg**, the same for salmon, blue, green and grey hatch (225 of 245 strongly ruled 64 px cells in a 1200 x 1000 land crop sit at 6.0 px / 45 deg); building fills are flat wash, 2.95 px is only the second harmonic |
| Ripples | hand engraved, 6-28 px, follow the bank, ink same blue as the military ruling | engraved contours, **graded**: 4-6 px at the bank, 12-19 px mid-river (water_core 11.5-19, median 16), lines run across the whole width of the open river; in a creek they are concentric and end in a blank centre |
| Bank | no ink line, ripples stop | **a dense blue band** (line pitch about 4 px for 25-60 px, growing smoothly), so the outermost line is a printed bank. Water is `blue` in the wash labels (89-96% of marked pixels on open_bank and water_core) |
| Structure ink | same blue as the water | landing stages and buildings are hatched in **neutral black** (OD blue/red about 1.0, at 45 and 135 deg); water lines run 0.2-0.6 at the bank |
| Paper, pigments | paper 226, 213, 190; ink brownish | paper 247, 240, 219; ink neutral; legend has the same five swatches (blue, grey, blank, green, salmon) and unmixing picks the right wash on the calibrate windows |

Things that look like ripples: the 6 px ruling itself when a creek bank runs at 45 degrees (the
Gabor reads some interior creek lines as ruled and leaves five blank ovals, 20-30 px across, in
`creek_west`); the pier hatching at 135 degrees (first run: pier arms filled as water blobs);
tramway and rail lines (parallel pairs, review only); letter-spaced lettering; and the military
building hatch in `dry_blue`.

### What became per sheet

`sheets.<id>.ruling` in `windows.json`; `river_pass.sheet_ruling` supplies 1882's values when a
key is absent, so 1882 needs none (they are written out for 1882 too, as they stood).

| key | 1882 | 1898 |
|---|---|---|
| `spacing` (FFT band of the cell test) | 4.0-5.6 | 5.2-6.8 |
| `periods` (per-pixel Gabor) | 4.48, 3.55 | 5.95, 2.95 |
| `angle`, `tol` | 144, 8 | 45, 8 |
| `structure` | none | `rel` 0.6, `odr` 0.8, `close` 4, `open` 6 |

`structure` is the one addition: dark (grey/paper < 0.6), neutral (OD blue >= 0.8 red) pixels,
closed (r 4) and opened (r 6), dilated by `SOLID_PAD`, join the solid-structure cut-out. Absent
for 1882, which hatches structures in the water's own blue. Every other constant is unchanged,
including `GABOR_SIGMA` 4, `SEED_SPACING` 6.5 and the cell thresholds. **1882 is bit-identical**:
`water.png` rerun after the change `cmp`s equal to `water-1006337f.png`. Self-check has two new
cases (6 px at 45 deg ruled and 11 px ripples not; a black-hatched pier cut out only when
`structure` is set) and passes for both sheets' settings.

### Calibrate-window results (viewed, not scored)

`water-b7ff0618.png`: 16.20 M water px, 18 285 review px (7 bodies). One tuning step only: the
first run (no `structure`) left the piers of `open_bank` half-filled with water blobs; with it
they are cut out cleanly, and nothing else in the four windows moved.

- **`water_core`** 100% water. **`open_bank`** 85.5% water: the whole river across 1000 px, both
  banks followed to the outermost bank-band line, the five T-shaped landing stages and the
  `RIVIERE DE` lettering cut out as holes (bold lettering is cut out as in 1882). A few water
  blobs stick onto the lettering `ATELIERS ... VIALES` ashore.
- **`creek_west`** 15.8% water: the branching creek with its side channels, the thin southern
  reach under `Binh`, the two bank spikes, all with outlines on the bank band; the salmon-hatched
  land at right untouched. Weak: the five blank ovals inside the creek (ruled-confusion, above)
  and a few pixels of straight edge at two junctions.
- **`dry_blue`** 0% water; the blue parcels' diagonal hatching is ruled and ignored. One review
  body, the long hatched hospital block at the window's bottom left.
- **Outside the windows**, whole-sheet overlay with the heldout boxes black: the Saigon River,
  the Arroyo de l'Avalanche, the northwest creek system and the Arroyo Chinois mouth are found;
  the river's east-bank shoals are blobbed. **Missed:** the narrowest creek heads (one to three
  lines wide, in the northwest and at the west edge) and the hatched "Canal de ceinture" strip,
  the same limit as 1882's thin creeks. These are my reading of overlays, not a score.

### Review bodies awaiting the owner

Seven, in `river/review.jpg` (`work/ocr/outputs/20ec4f9a-16bd-4895-a593-40c6ed9c9555/river/`, built
by `review_sheet.py`; raw crop beside the outlined one). None touches a heldout window, so all
are drawn. By eye: #1 and #2 military building complexes inside the blue-wash hospital land (#2
is the `dry_blue` block above); #3, #4 and #5 the tramway and rail tracks (pairs of parallel
lines) with no water pixels; #6 and #7 the letter-spaced lettering `Khanh Hoi`. I expect all seven
to be dry, but they are the owner's to call: a confirmed answer is a point in `confirmed.json`.

### Batch 1

80 points, seed 1, `label.py points 1898 --seed 1 --per 8 --edge water-b7ff0618.png --edge-per 10
--band 30`: 8 uniform in each of the five heldout windows and 10 within 30 px of the proposal's
edge in each that has one (`quay_canal`, `creek_north`, `bridge_label`, `hatched_bank`: 18 each;
`dry_salmon` has no edge, 8). Owner-labelled 2026-10-02; 2 unsure dropped. The pass is v3 with the 1898 ruling and `structure`
settings, `water-b7ff0618.png`, scored once; nothing in 1898 was tuned on these points.

| 1898 batch 1 | accuracy | missed water | false water |
|---|---|---|---|
| all (heldout) | **97.4% [91-99] (76/78)** | 0/28 | 2/50 (4.0%) |
| edge stratum | 94.7% [83-99] (36/38) | 0/18 | 2/20 |
| uniform | 100% [91-100] (40/40) | 0/10 | 0/30 |
| `quay` | 97.1% (33/34) | 0/13 | 1/21 |
| `creek` | 94.4% (17/18) | 0/5 | 1/13 |
| `bridge_gap`, `dry_land` | 100% (18/18, 8/8) | | |

Both errors are false water 4 and 9 px outward of the proposal's edge: edge placement, not a missed
or invented body. 1898 reaches the 1882 level (96.5% on its first batch) with only the ruling
period and angle changed plus the black-hatch `structure` step. The 7 review bodies were
answered dry by the owner on 2026-10-02 (`confirmed.json`, 7 dry, 0 stale); the water mask is unchanged
and the review layer is empty.
Not done: the narrow creek heads, the hatched "Canal de ceinture", a fresh 1898 batch after any
edge fix. No layer is approved.

## Road pass, 1882 (2026-10-02)

[`work/ocr/scripts/road_pass.py`](../work/ocr/scripts/road_pass.py), commit `4ecf05fc`, on `paper.npy`, the
water mask `water.png` and the cell layers `cells.npz`, `texture.npz`. Writes `river/road.png` (255 = road),
`road-preview.jpg` (unseen heldout boxes black) and `road-run.json`. Deterministic (two runs `cmp` equal),
229 s, 3.0 GB resident (3.95 GB peak footprint). `--self-check` builds one synthetic sheet (street with a pavement strip and kerb line, a closed blank block, a ruled
block, a letter, a tramway, a creek with a deck, a garden patch) and makes eight checks; the pavement and tramway ones
fail with `R_CORE` or `RED_OD` changed.

### The representation, and why

A street is the unfilled space between block outlines, so the pass finds that space and keeps what is
street-shaped; it does not look for road texture, because there is none. Blocks are ruled (their hatch is ink
every 4-5 px) or blank (paper closed by an outline), and the outline is the evidence that matters:

1. **Ink** = grey / local paper below `INK_GREY` 0.92, grown 1 px. That is outlines, kerb lines, hatch of every
   pigment, lettering and the red tramway. Ink components under `GLYPH` 60 px across (letters, numbers, the
   city-limit crosses) are not walls.
2. **Free space** = not ink, not water (`water.png` == 255, grown 2 px), inside the road neatline, outside the
   furniture. Bridges are not water in that mask (the pass cut the decks out), so they are free or ink.
3. **Core** = free space deeper than `R_CORE` 9 px from any wall, and not in a machine-ruled cell or a garden.
   Hatch fills no core (lines every 4-5 px). **This is the pavement rule:** a pavement is a strip a few px
   inside the block outline, bounded by a thin kerb line (measured 8-16 px wide, carriageway 20-30 px), so
   it is narrower than `2 * R_CORE`, is not core, and the carriageway is what remains. The kerb line is read
   from the scan as ordinary ink: nothing recognises it as a kerb. Where no kerb is drawn the strip and the
   street are one wide space and all of it is road, which is the owner's "block's outer line" case.
4. **Grow back**: the core is dilated `R_CORE + 2` steps through free space only (4-connected), so the road
   returns to its lines and never crosses a kerb into the pavement beyond it.
5. **Open fields** (free space deeper than `FAT` 70 px: the blank land outside the city limit, a bigger
   plaza) are cut out with a margin; a street that flares into one stops there. Without this, the blank paper
   outside the red limit line was the largest "road" on the sheet.
6. **Tramway**: road on both sides of a red line (od(R) < 0.65 od(G)) is joined across it by a closing of
   12 px, restricted to the tramway's own pixels.
7. **Components**: a blank block is a paper face closed by its outline, so it is free space too. It is
   separated from the street by its outline and is compact; the street network is long and thin. A component is
   kept if area / (inscribed radius)^2 >= `SHAPE_MIN` 20, or it is as large as a network (`NET_AREA`
   200 000 px), or it is thin and a little shorter (radius <= `LANE_R` 24 and ratio >= 12: a street cut by a
   tramway or lettering).
8. **Gardens** (owner: park paths and garden interiors are block): lawns and tree masses are unruled,
   incoherent texture (`texture.npz` coherence < 0.3) in big dense patches; a patch is where 45% of a 7 x 7
   cell window is stipple, at least 60 cells, closed over its paths. The paths are cut from the road
   outright. This finds the Jardin de la Ville, the tree masses beside it and the Jardin Botanique.
9. **Bridges** (after selection, so a deck cannot join a street to the blank lots beside it): a dark
   hatched blob within 14 px of water (opened by 3 px, 150-8000 px) that touches the selected road on two
   separate sides is added.

Two sheet facts went into `windows.json` `sheets.1882.road`: the frame. The water pass's neatline is the
outermost frame line; the map starts inside the inner thin line, 100 px further in at left and top. Measured
from row and column dark profiles: inner line at x 597, y 555 and y 8298; the bottom is cut at y 7950, the top
of the scale bar. The hand-drawn furniture boxes were tight, so they are padded by 100 px. Before this, slivers
between the frame and those boxes were the longest "streets" on the sheet.

Constants: `INK_GREY` 0.92, `INK_PAD` 1, `GLYPH` 60, `R_CORE` 9, `FAT` 70, `RED_OD` 0.65, `BRIDGE_REACH` 14,
`BRIDGE_INK` 0.8, `BRIDGE_MIN`/`MAX` 150/8000, `SHAPE_MIN` 20, `NET_AREA` 200 000, `LANE_R` 24, `LANE_RATIO` 12,
`GARDEN_COH` 0.3, `GARDEN_WIN` 7, `GARDEN_FRAC` 0.45, `GARDEN_MIN` 60 (all in `road-run.json`).

### Tuning, and calibrate-window results (viewed, not scored)

Tuned on `ne_cream`, `dense_grid`, `creek_crossing` and whole-sheet views with the unseen boxes blacked out.
**No labelled point was used while tuning**, spent or not; no reviewed traces exist for any road window
(`traces/1882-*.geojson` are empty, `reviewed: false`), so `score.py <dir> --layer road` has nothing to score.
Road share of window: `ne_cream` 17.5%, `dense_grid` 9.1%, `creek_crossing` 7.4%; whole sheet 4.7%.

- **`ne_cream`**: one street network, every blank block and the little plots inside the dense plot patch
  dropped. Misses: one elongated blank plot kept, a narrow lane between plots lost.
- **`dense_grid`**: the kerbed carriageways, not their pavement strips (the strips are separate pieces
  and drop). Lettering "Bonnard" is road. The wide strip lettered "Bonnard" is a closed polygon
  drawn with the block shadow-line convention; it is kept (long, thin) and may be a plot or canal, the owner's
  call. Junction squares where kerb returns cut them off from the streets are lost.
- **`creek_crossing`**: the street along the limit kept and the one bridge with road on both sides added; the outside blank paper
  is cut; the tramway no longer splits the street at its crossing. Streets are still broken at "Rue" (a letter
  touches the kerb line) and at the tramway where the pieces fail the shape test.

### The first honest score (frozen `4ecf05fc`, run once, 2026-10-02)

`score.py --points 1882 road.png --layer road`, all 635 labels (21 unsure dropped), bridge = road. **Accuracy
does not beat the trivial answer**: 94.5% of the labelled points are not road (the points were drawn for the
water layer: quays, creeks, plots), and "nothing is road" scores 94.5% [92-96].

| | accuracy [95% CI] | missed road | false road |
|---|---|---|---|
| all batches | **85.7% [83-88] (526/614)** | **17/34 (50% [34-66])** | 71/580 (12.2% [10-15]) |
| batches 2, 3, 4 (pavement rule) | **82.8% [78-86] (269/325)** | 9/16 (56% [33-77]) | 47/309 (15.2% [12-20]) |
| batch 1 alone (predates the pavement rule) | 88.9% [85-92] (257/289) | 8/18 | 24/271 (8.9%) |
| unseen heldout windows | 83.9% [80-87] (355/423) | 9/23 | 59/400 (14.8%) |
| seen heldout / calibrate windows | 90.0% [84-94] / 88.2% [77-94] | 6/7, 2/4 | 8/133, 4/47 |
| uniform / edge stratum | 89.7% [86-92] / 79.6% [74-84] | 10/22, 7/12 | 28/347, 43/233 |

By window case, all batches: quay 81.6% [73-88] (3/7 missed, 18/107 false), `quay_plaza` (`quay_rondpoint`) 70.2%
[57-80] (16/55 false), canal 82.3%, bridge_gap 84.6% (bridges: 1 of 4 road/bridge-labelled points found),
outskirts (`outskirts_rail`) 84.5%, creek 88.5%, dry_land 93.1%, moat 96.7%, basin 96.7%. Only 34 points are road
(5.5%), so every road-recall figure rests on single digits.

**Wrong points** (88, all batches): 45 within 8 px of the proposal's edge, 78 within 24 px, ten farther: 34, 40,
43, 79, 79, 84, 101 and three at 150 or more. All 71 false-road points are labelled `land` (none water), spread over
the windows with the most edge points: `quay_rondpoint` 16, `chinois_quay` 14, `creek_nw` 8, `outskirts_rail` 7,
`charner_canal` 7, `bridge_basin` 6, the other five windows 2-5 each. They sit within 24 px of an edge: strips beside
quays, canals and creeks that the owner calls land (pavement, plot) and that the pass cannot tell from a quay
road, because a quay pavement has no kerb line to stop on. The ten far errors are bodies, not edges: whole
plots read as street or a street missed.

I did not look at pixels in any unseen window to find out why; the diagnosis above is from counts by label and
window only. The pass is **not good enough to promote**: half of road points are missed and a tenth of land
points are called road. No layer is approved.

### Weak spots (what the pass cannot do)

- **Pavement and kerb line**: it can only honour a kerb that is drawn and wider than 8-16 px of carriageway
  away from the block line; a pavement wider than 17 px, or a kerb the scan lost, is road; a street with no
  kerb is road to its outlines. Nothing reads "kerb": a quay pavement against water is road if it is wide.
- **Blank block vs street**: only shape tells them apart. A blank block that leaks through a gap in its outline,
  an elongated blank plot (long thin plots read as lane), and a street drawn as a closed polygon with lettering
  inside it (read as a plot) are wrong. Shadow-line thickness (thick lower-right side) was measured and is too
  faint to separate them at this scale.
- **Narrow lanes** under about 20 px between outlines (R_CORE 9), and single-line streets where no space is drawn.
- **Lettering** that touches a kerb line or outline cuts the street there; removing such letters by stroke width
  opened outline gaps and merged lots into streets, so it is not in the pass.
- **Junction squares and small plazas** cut off by kerb returns, and compact open spaces generally; the
  70 px open-field cut also clips plaza edges.
- **Outskirts**: sparse plots, the blank land outside the limit and the west bank are the least reliable.
- **Gardens**: the garden mask follows 32 px cells, so a garden edge is rough and some path may remain.

### Batch 5 (seed 5): pending owner labels

Three new road windows, placed after the pass was frozen and by eye on the 1/8 whole-sheet view (unseen
boxes black), `seen: false`, clear of every unseen water box: `west_dense` (dense old quarter, [2700, 3600,
1000, 1000]), `msg_quay` (Messageries Maritimes quay, [1700, 5800, 1000, 1000]) and `ne_boulevard` (a wide street
NE of the Jardin de la Ville, [6300, 1600, 1000, 1000]; the case name is a guess). One slip: I had already
viewed the 1/8 whole-sheet road preview (not the places at higher scale), so the windows were not placed before
any proposal at all. 90 points, 30 per window (10 uniform, 20 within 30 px of the `road-4ecf05fc.png` edge):
`label.py points 1882 --seed 5 --unseen --only west_dense,msg_quay,ne_boulevard --per 10 --edge road-4ecf05fc.png
--edge-per 20 --band 30`. `--only` is new; without it, `--unseen` also takes in the seven unseen water windows
and this command gives 300 points. **Batch 5 pending owner labels**; it was not viewed or scored.

## Road pass v2, 1882 (2026-10-02)

[`work/ocr/scripts/road_pass.py`](../work/ocr/scripts/road_pass.py), commit `a772ecd1`, frozen mask
`river/road-a772ecd1.png` (gitignored with the other outputs; sha256 `5ce76c69...59c20a`). Same inputs as v1. Deterministic (two full runs
`cmp` equal), 748-1007 s, 2.0-2.6 GB resident, 3.7-4.3 GB peak footprint. `--self-check` now has seven synthetic
sheets and seventeen asserts (street with pavement and kerb, boulevard of two promenades and a lettered carriageway,
block with its pavement, lane against plot, quay strip against yard, pier against shed, garden); each new constant
fails at least one (`FAT_Q`, `PIER_WATER`, `NARROW_AREA`, `R_FACE`, `PAVE_RATIO`, `INNER_MIN`, `KERB_MAX`, `HATCH_RATIO`,
`HATCH_BLOCK` were each changed and caught). **v2 is frozen and was not scored by the owner's labels when written.**

### Diagnosis (viewed windows only, see discipline)

Viewed natively and v1 side by side on `arsenal_quay`, `quay_primauguet`, `ne_cream`, `dense_grid`,
`creek_crossing`, `bridge_basin`, `blue_domain`, `garden_pond`, `western_creek`. **The quay-pavement hypothesis did
not hold as stated.** On `arsenal_quay` and `quay_primauguet` v1 puts no road on a water-side pavement at all: the
river quay there is either a street between two lines (road, fragmented by lettering and cross hatching) or a plain
blank strip that v1 did not take. The four false points in `arsenal_quay` were: a leak through a gap in a building's
outline into the paper between the building and its block line (two points), the wide promenade beside a boulevard
(one), and the pavement beside "No. 15" (one). What v1 got wrong, by area on the nine calibrate / seen windows (v1-only
and v2-only pixels, approximate, windows overlap a little):

| cause | evidence | area |
|---|---|---|
| blank yards, plazas and open ground beside water called road (`FAT` cut too shallow, no cut at all beside water) | v1-only pixels in blobs 16 px or deeper | 156 k px lost |
| quay-side and creek-side strips and blobs | v1-only pixels within 40 px of water (`open_bank` 45 k, `western_creek` 88 k, `quay_primauguet` 41 k) | 95 k lost |
| pavement strips: a kerb and a block line, or a block line and a thin line (a promenade beside a boulevard) | v1-only strips under 16 px deep | 36 k lost |
| narrow carriageways dropped: v1 needed a 19 px core, a street between kerbs is 12-20 px | v2-only pixels in strips under 9 px deep (lane-like) | 150 k gained |
| mid-width carriageways dropped the same way | v2-only, 9-16 px | 123 k gained |
| bridge decks, piers and landing stages | `bridge_basin`, `quay_primauguet` | not counted |

So the main failure was the opposite of the one in the brief: v1 was missing road (any carriageway under 19 px between
kerbs) and calling open ground road; pavement was the smaller share.

### Changes (each general, each with a self-check case)

1. **Faces at 7 px** (`R_FACE` 3, was a 19 px core): a face is free space that survives a 3 px opening, grown back to
   its walls through free space. This is what recovers carriageways between kerbs (12-20 px), lanes and junction
   squares. Cost: it admits more narrow blank strips, so the next two steps follow.
2. **Narrow-only components need 15 000 px** (`NARROW_AREA`): a component with no 19 px core is a plot or a pavement
   ring unless it is as large as a network. Specks under 500 px left by the pavement cut are dropped (`SPECK`).
3. **Open ground** (`fat_region`): an exact union of inscribed disks around every pixel deeper than `FAT` 70 px (not
   a band along the walls), plus **a yard beside water** deeper than `FAT_Q` 36 px whose nearest wall is water within
   20 px (a quay road is 15-35 px, a blank yard behind it is deeper), grown by `YARD_EDGE` 10 px, and the rim of both
   followed `RIM` 30 px along narrow ground (`RIM_R` 10), because a union of disks leaves a rim at the field's walls.
4. **Kerbs by chords** (`pavement`): the strip-shaped faces (`strip_faces`: area 200, ratio 6, not open ground)
   are cut by chords along four axes (`run_layers`, exact, run-length based). A pixel's chord is the shortest through it;
   across a wall of at most `KERB_MAX` 8 px lies a neighbouring strip of 7-60 px. Strips beyond on **both** sides: the
   carriageway (`inner`, kept; an `inner` stretch under `INNER_MIN` 600 px is a tramway or junction blip and not one).
   On **one** side only: **pavement** if the strip beyond is `PAVE_RATIO` 1.5 times wider and it is under `W_NARROW` 19,
   or if a hatched block lies against its outer wall and it is no wider than `HATCH_RATIO` 1.25 times the strip
   beyond (hatch = ink that closes over 3 px and holds a 6 px disk), or if it lies beside an inner strip (within its
   own width plus a wall, and not along the same strip, `SAME_STRIP` 40). That last test is the boulevard's two
   wide promenades. Pavement pieces under `PAVE_LEN` 40 px are kept as road. No kerb on either side: a plain street, kept
   (the owner's "no kerb, the block's outer line" case).
5. **Quay**: a street line and water make a strip with no kerb beyond it; it is road if it passes the yard test
   (step 3). A quay pavement against water cannot be told from the quay road by any drawn line, so it stays road
   when there is no inner strip beside it. This is the quay rule as far as the drawing supports.
6. **Piers and landing stages** (`PIER_WATER` 0.4): a hatched deck with water on at least 40% of its 4 px rim is road,
   not only a deck with road on two sides (the owner labels piers bridges).
7. `--window` now refuses a window that touches a blind box and walls the blind boxes off, so a preview computes on
   nothing it may not show. `score.py --points ... --spent` keeps only points in calibrate / seen:true windows.

Constants not listed above are unchanged (`INK_GREY`, `INK_PAD`, `GLYPH`, `R_CORE` is now only the narrow-component
test, `RED_OD`, `BRIDGE_*`, `SHAPE_MIN`, `NET_AREA`, `LANE_*`, `GARDEN_*`); all are in `road-run.json`.

### Spent evidence only

191 labelled points (unsure dropped) in windows that are calibrate or `seen: true`: `arsenal_quay` 51, `bridge_basin` 52,
`citadel_moat` 30, `blue_domain` 29, `dry_city_blocks` 29 (no point in `ne_cream`, `dense_grid`, `creek_crossing`,
`quay_primauguet`). Of those 11 are road (8 road, 3 bridge), 156 land, 24 water; water counts as not road.
The trivial all-land answer is 180/191 = 94.2%.

| | accuracy | missed road | false road |
|---|---|---|---|
| v1 `4ecf05fc` | 171/191 = 89.5% | 8/11 | 12/180 |
| v2 `a772ecd1` | 179/191 = 93.7% | 6/11 | 6/180 |
| v1 / v2 without `bridge_basin` (139 points) | 133/139 and 133/139 | 6/9 and 6/9 | 6/130 and 6/130 |

**The gain is all in `bridge_basin`** (v1 6 false + 2 missed bridge points, v2 none), which is the window I viewed to
write the pier rule and the yard rule. Elsewhere v1 and v2 tie: 6 missed and 6 false each, with different points.
So there is no evidence here that the kerb logic works on a quay, and no evidence it does not; the spent windows hold
too few road points (11) and almost no pavement points. v2 is still **below the all-land baseline** on these points.

Points that flipped from right to wrong (three):
`1882-0003` (`arsenal_quay`, road to land: the wide strip beside the kerb pair of the boulevard, which v1 left in
and the new promenade rule cuts; the owner called it road, so the rule is wrong for this strip, or the label reads
the promenade as carriageway), `1882-0222` (`citadel_moat`, land to road: a 20 px strip in an acute block corner
with a thin line on its far side that is the outline, read as a plain street), `1882-0010` (`arsenal_quay`, land to
road: the strip beside the lettered "No. 15" strip, a pavement with a broken kerb).
Eleven flipped from wrong to right: `0116 0357 0358 0359 0362 0366` (`bridge_basin` land), `0363 0494` (`bridge_basin`
bridges), `0286` (`blue_domain`), `0025` (`dry_city_blocks`), `0461` (`arsenal_quay`).
Still wrong: missed `0003 0276 0048 0203 0303 0462`; false `0001 0292 0222 0010 0307 0465`. Bridge-labelled points in
spent windows: v1 found 0 of 3, v2 2 of 3 (`0462` in `arsenal_quay` is still missed). `0001` sits in a wide
paper-coloured street and I cannot see why the owner called it land.

**Area, whole sheet (7390 x 10800 px road frame):** v1 5.12 M px (6.4%), v2 6.09 M px (7.6%); 4.11 M in both, 1.01 M
only v1, 1.98 M only v2. Inside the spent windows the biggest drops are `open_bank` (7.6% to 0.6%, open river
called road by v1), `western_creek` (16.5% to 10.5%), `quay_primauguet` (8.2% to 5.3%); the biggest gains `creek_crossing`
(7.4% to 15.0%), `dense_grid` (9.1% to 13.7%), `dry_city_blocks` (14.3% to 18.2%), `garden_pond` (2.0% to 6.6%).
Counts only in unseen heldout boxes (road share v1 to v2, not looked at, not a tuning gate): `chinois_quay` 14.9 to 9.8%,
`creek_nw` 16.3 to 17.7, `arsenal_basin` 3.8 to 6.8, `charner_canal` 7.7 to 13.1, `avalanche_head` 12.9 to 11.7,
`quay_rondpoint` 11.4 to 14.7, `outskirts_rail` 27.5 to 28.1, `west_dense` 16.6 to 18.2, `msg_quay` 16.7 to 6.4,
`ne_boulevard` 10.6 to 16.3. `msg_quay` losing 60% of its road and `charner_canal` gaining 70% are the two changes to
watch when the labels come in.

### Weak spots (v2)

- Lanes and narrow faces now come in, and so do narrow blank plots: `creek_crossing` doubled (7.4% to 15.0%), and
  `western_creek` shows a blank plot with a building (a few thousand px) read as road. The 15 000 px rule only stops isolated ones.
- **Gardens**: `garden_pond` gained 30 k px, paths along the pond that the 32 px garden cells do not cover. Not fixed.
- A leak through a gap in a building outline still lets road into the paper around the building (`arsenal_quay`, two points).
- A promenade wider than a carriageway beside a boulevard is land by rule; one spent point says the owner called it road.
- A kerb with a gap, or lettering that touches it, breaks the chord test locally (`VOTE` 9 and `SAME_STRIP` 40 smooth it).
- Junction squares inside a kerb return are recovered only where a 7 px face survives.
- Quay pavement beside water with no drawn kerb is road. The pass cannot do better from the drawing.

### Discipline

Viewed and tuned on: the three calibrate road windows, `arsenal_quay`, `quay_primauguet`, `blue_domain`, `bridge_basin`,
`citadel_moat`, `dry_city_blocks`, `garden_pond`, `western_creek`, and the whole-sheet 1/8 preview with every unseen box
black. Labelled points used as tuning and regression evidence: the 191 above. Not viewed, not scored, not used: any
`seen: false` heldout box, the labelled points in them, batch 5. The whole-sheet area counts for unseen boxes above
are counts of a finished mask, and were computed after the freeze decision. **No blind box was seen; no `seen`
flag was changed.** Windows seen on 2026-10-02 for the diagnosis were already `calibrate` or `seen: true`. One caveat on
the numbers: the three false-road fixes in `bridge_basin` were tuned while looking at that window, so its eight flips
are not independent.

### Batch 5 stays unlabelled; batch 6 scored

Batch 5 (seed 5, 90 points in `west_dense`, `msg_quay`, `ne_boulevard`) was drawn within 30 px of **v1's** edge. v2's
edge lies elsewhere (`msg_quay` lost most of its road), so the 60 edge points no longer test v2's edges; the 30 uniform
points still would, but scoring v2 on part of a batch drawn around v1 is not clean. It stays in `points-1882.json`,
unlabelled, as a record. **Batch 6 (seed 6), 90 points, pending owner labels:** `west_dense` 30, `msg_quay` 30,
`ne_boulevard` 30 (10 uniform + 20 within 30 px of the `road-a772ecd1.png` edge each):
`label.py points 1882 --seed 6 --only west_dense,msg_quay,ne_boulevard --per 10 --edge road-a772ecd1.png --edge-per 20
--band 30` (no `--unseen`: it would add the seven unseen water windows). Not viewed, served or scored. Score with
`score.py --points 1882 river/road-a772ecd1.png --layer road --seed 6`.

**Batch 6 result (owner-labelled 2026-10-02; 7 unsure dropped; v2 scored once, not tuned afterwards).**
v1 (`road-4ecf05fc.png`) is rescored on the same points for comparison; the batch was drawn around v2's
edges, so that comparison favours v2 slightly.

| batch 6 | v2 | v1 |
|---|---|---|
| all (83 points, 17 road) | **84.3% [75-91] (70/83)** | 88.0% [79-93] (73/83) |
| road missed | 1/17 | 0/17 |
| land called road | 12/66 (18%) | 10/66 (15%) |
| uniform stratum (28) | **100% [88-100]** | 89.3% (25/28) |
| edge stratum (55) | 76.4% [64-86] | 87.3% [76-94] |
| `quay` | 82.1% (false 4/21) | 71.4% (false 8/21) |
| `boulevard` | 77.8% (false 6/26) | 96.3% (false 1/26) |
| `dense_old_quarter` | 92.9% (false 2/19) | 96.4% (false 1/19) |

Calling nothing a road scores 79.5% (66/83) on this edge-weighted batch, so v2 is above it here (the
94.5% figure was on the mostly-uniform batches 1-4). What v2 does differently: away from edges it is
right on all 28 uniform points (v1 missed three land points far from any edge, at 4, 13 and 31 px),
and it halves the quay false road. **What it gets wrong is edge placement:** 12 of the 13 wrong points
lie within 6 px of v2's edge (eleven at 1-3 px), and 6 of the 12 false-road points are in `boulevard`
at 1-3 px. A 1-3 px error is the thickness of a kerb stroke, so it is where the label itself is least
certain (a point on the stroke is `unsure`, and the owner dropped 7). A road edge pulled in by
about the stroke width is a testable fix; it was **not** applied, because batch 6 is now spent for the
road layer and the shift has to be set on calibrate windows and scored on a new batch. Road
recall rests on 17 points. No road layer is approved.

## Road pass v2: where the edge sits against the stroke (2026-10-02, diagnosis only)

The batch 6 result above left a testable idea: 12 of 13 wrong points lie within 6 px of v2's edge, so pull the
edge in by about a stroke width. Before changing the pass I measured where v2's edge sits against the ink stroke it
follows, with [`edge_profile.py`](../work/analysis/river_ref/edge_profile.py) on windows I may view. **The idea does
not survive the measurement, and v2 is unchanged (no v3, no batch 7).**

**Measurement.** For each straight stretch of the edge of `road-a772ecd1.png` (the smoothed mask normal agrees at
4 and 10 px) the ink density `1 - grey / local paper` is sampled along the normal, `t = 0` at the edge, `t > 0` into
the road. The stroke is the ink run just outside (`t` in -8..+1); its centre is the ink-weighted mean of the run
above half its peak. Road windows that are calibrate or `seen: true` (`ne_cream`, `dense_grid`, `blue_domain`;
`creek_crossing` is skipped because its 40 px margin touches `creek_nw`): 31 290 straight edge pixels, 97.5% with a
stroke. A block's lower-right sides are drawn thick and its upper-left sides thin, so the road is split by whether it
lies lower-right of its wall (the thick side) or upper-left of it:

| side of the wall the road lies on | n | stroke width (FWHM, 0.5 px steps) | stroke centre vs v2 edge | stroke's road-side half-max face vs v2 edge |
|---|---|---|---|---|
| lower-right (thick sides) | 6 858 | 3.0 px | **-3.20 px** [IQR -3.83 to -2.56] | -1.75 px |
| upper-left (thin shadow line) | 6 905 | 2.0 px | **-2.67 px** [-3.45 to -2.20] | -1.75 px |
| other orientations | 16 749 | 2.0 px | -2.66 px [-3.23 to -2.20] | -1.75 px |

Negative is outside the road, in the wall. The same run on all 14 calibrate or seen windows of both layers (94 k
pixels) gives -2.99, -2.69 and -2.71. The difference between the sides is 0.5 px, in line with the README's "under
1 px". 88-96% of edge pixels lie 1-2 px from the nearest raw ink pixel (`grey < INK_GREY`): the edge is the ink
threshold plus `INK_PAD`, and a synthetic boulevard shows the road ending one ink-pad pixel plus the threshold
pixel from the kerb line.

**What this says.** v2's edge does not sit outside the stroke. It sits **2.7-3.2 px on the road side of the stroke
centre** (1.75 px clear of the stroke's visible face). "The edge is the centre of the line" (README) therefore
means widening the road by about 3 px per side, not pulling it in. As a probe, `road | (ink & dilate(road, 3))`
adds +11.8% (`ne_cream`), +16.7% (`dense_grid`) and +18.6% (`blue_domain`) road area. It flips none of the 191 spent
labelled points (no spent point is near an edge) and, from the geometry, cannot remove false road: it moves the
edge away from the road. I did not apply it. A pull-in in the direction the batch 6 errors suggest would go the
other way from the owner's rule, and every face v2 keeps is at least 7 px wide (`R_FACE` 3), so 3 px per side
would shrink the 12-20 px carriageways between kerbs to 6-14 px and the narrow lanes to 1-3 px.

**So the 1-3 px false road is not edge placement.** A point inside a strip narrower than about 8 px is within 4 px
of the strip's edge whatever the edge does, so a pavement strip or plot sliver that v2 keeps as road produces
exactly this pattern (and 6 of 12 sit in `boulevard`, the case with the most kerb pairs). This is consistent with
the counts but not shown: I looked at no pixel of an unseen window. What the viewable windows do show is room for
it. Road at chord width under 10 px is 4.8% (`ne_cream`), 7.3% (`dense_grid`) and 11.9% (`blue_domain`) of road;
`ne_cream` has long 8-12 px strips between parallel lines kept as road. In a replica of the kerb stage on
`dense_grid`, one-sided strips of at most 24 px kept as road include 14 777 px (10% of its road) whose width is
1.1-1.5 times the strip across the kerb, just under `PAVE_RATIO` 1.5. Whether they are pavement or street is the
owner's call; no label in a viewable window says.

**Next, for whoever owns the decision.** The 12 batch 6 false-road points are spent for the road layer, so they may
be looked at to see which of these they are (strip of a pavement, a plot sliver, a boulevard promenade). If they
are narrow strips, the fix is in `pavement` / `PAVE_RATIO` / `NARROW_AREA`, not in the edge, and it needs a fresh
batch drawn on the new mask.

**Discipline.** Viewed and measured: `ne_cream`, `dense_grid`, `blue_domain` and the other calibrate or seen
windows only (the 1882 whole-sheet mask was read only inside them). No unseen heldout box was viewed or measured, no
labelled point in an unseen window was used or scored, batch 6 was not touched, no `seen` flag changed. The probe
growth was scored on the 191 spent points only (`score.py --spent` rule).

