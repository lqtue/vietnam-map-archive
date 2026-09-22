# Colour-pass transfer check — four Saigon plans

**2026-09-20.** Test whether the 1882 `colour_blocks.py` method transfers to the
1923, 1942, 1959, and 1968 District 4 sheets before using its shapes as
automatic georeferencing evidence. This is an exploratory visual check, not a
segmentation accuracy score: there are no exhaustive hand traces on these four
sheets.

**Correction, same day:** the overview run below cannot assess the river. Its
2048-pixel render loses printed texture, and `water_mask` needs OCR hydrology
labels that the `--iiif-base` runs did not supply. Each run's `dropped 0 as river
surface` is therefore an abstention, not a negative detection result. Full
resolution IIIF river crops and the revised interpretation are below.

## Method

The live public IIIF image for each map was fetched. The script's `--census`
ran at its default 4096-pixel render. A full 4096-pixel 1923 run was killed
with exit 137 in this environment. All four geometry runs therefore used
`--render 2048 --no-recut --no-split-buildings`, with the live scan's estimated
metres per source pixel supplied through `--mpp`. The 1882-specific swatch
labelling and the default cream-parcel step remained enabled. Without
`--map-id`, OCR-based furniture removal and map-frame clipping were unavailable;
these results test the image-only detector, including its known tendency to
trace furniture and margins. Outputs are local under
`/private/tmp/vma-colour-transfer-{year}/`; overview overlays are
`/private/tmp/vma-colour-transfer-{year}-overlay.png` and the four-panel sheet is
`/private/tmp/vma-colour-transfer-contact.png`.

| year | map id | live image px | m/px used | 4096 census votes | 2048 geometry votes | output polygons | image SHA-256 |
|---|---|---:|---:|---:|---:|---:|---|
| 1923 | `1bce28f0-aa82-48eb-8e33-8f0b07182c2f` | 16064×14027 | 0.8452 | 22/64 | 15/64 | 6,268 | `5bfd93bf5ebb57fec5f37eebf92520b36ceb15f2fbdd04df583a3055ff2ca30f` |
| 1942 | `eca788e5-6780-4dca-bf23-7651a1c48aba` | 7479×6314 | 1.69 | 17/64 | 10/64 | 7,717 | `11f7aeba2b6e758bc5d908f6b75830943a561ee4d8c2415465b38292fc063784` |
| 1959 | `34d4edb2-f7df-4c47-a65a-f6b471400396` | 14000×10773 | 0.9974 | 19/64 | 32/64 | 10,782 | `72fc959bd4620ea7c9750da59ea39949739b33848e35951950eb364e44468f25` |
| 1968 | `3a446d85-25a8-4e81-9cfc-8de357c3a5df` | 10816×13523 | 1.2729 | 18/64 | 18/64 | 15,180 | `1ad73644293f0a656f2ef596f2a8205b8aa9044300eab801e5cfc6f98bc9123c` |

The 1942 live image is the 7479×6314 scan. Its saved GCP annotation uses a
roughly 2× larger scan (14915×12602); this check does not validate or transfer
those coordinates. See `work/analysis/district4/georef_error.md`.

## Visual observations

- **1923:** many outlines land on real parcels and blocks, including outside the
  dense centre. The detector also draws over the legend and along the map frame.
  Some large blue outlines surround grey land rather than water. This is the
  best candidate of the four for geometry-only matching after masking furniture
  and validating a small set of features by hand.
- **1942:** real block geometry is visible among 7,717 polygons, but the legend
  columns and map margins also become polygons. The ink fraction is only 0.56%
  at this render, and the red/green split got 10/64 crop votes. The color names
  cannot be used as cross-sheet classes without recalibration.
- **1959:** dense blue outlines cover ordinary land parcels across much of the
  sheet; the cool-color split got only 6/64 crop votes at 2048. Red outlines
  cluster in the printed built-up centre, but the proposed class labels do not
  consistently describe the map's own legend. Geometry may still be useful
  after selecting stable landmarks by hand.
- **1968:** the dense city core fragments into many small candidates while
  large blue outlines occupy rural land. The cool-color split got 9/64 crop
  votes. The default 1882 palette is not a reliable semantic classifier here.

The raw count rises by year but is **not** a quality ranking: map area, source
resolution, paper style and printed detail all differ. The overlay inspection
establishes some boundary-following and obvious false positives; it does not
establish recall, precision, or usable correspondences between sheets.

## Full-resolution river check

Each 1024×1024 crop below was assembled at source resolution from the public
IIIF tile pyramid with `iiif_tiles.fetch_crop`, without downsampling. The
four-panel contact sheet is `/private/tmp/vma-river-fullres-contact.png`; source
crops are `/private/tmp/vma-river-fullres-{year}.png`. Coordinates are source
pixels, top-left of each crop.

| year | crop x,y | what the source actually draws |
|---|---:|---|
| 1923 | 11000,4500 | Narrow Saigon river with dense blue hatching; the water is a pattern, not a uniform blue fill. |
| 1942 | 3400,2750 | Pale green-grey water enclosed by dark banks; its fill is close to adjacent land colors. |
| 1959 | 11500,4300 | Broad, saturated cyan river with crisp banks and a magenta navigation line. |
| 1968 | 7700,1850 | Broad blue river, dark shoreline, and printed text over the water. |

This reverses any inference that the four rivers are equally invisible to a
color method. The 1959 and 1968 water fills should be straightforward to
segment with **sheet-specific** color samples. The 1923 hatch needed a
source-resolution test, and the 1942 low-contrast fill needed its bank geometry
tested; both tests are recorded below. None of these claims is a measured river IoU. The existing
1882
`water_region` detector is seeded by hydrology OCR and calibrated to ruled
water, so the four image-only whole-sheet runs did not test it.

## Decision for auto-georeferencing

Do not match polygons by the emitted 1882 color class across these years. For
auto-georeferencing, first test the river as an independent, full-resolution
signal: sample each sheet's water style; extract water or shoreline in overlapping
source-resolution tiles; merge at tile seams; and evaluate against hand-drawn
river windows before using it for registration. 1959 and 1968 are the clearest
color candidates. Require spatially distributed matches and independent check
points before accepting any transform. The 1942 scan mismatch must be resolved
before comparing source pixels to its GCP annotation.

## River mask probe, 2026-09-20

`work/analysis/district4/river_probe.py` applies explicit RGB-difference
thresholds to the 1923, 1959 and 1968 source-resolution crops. Each has a
manually chosen river seed, a small closing operation, and a connected
component selection. On 1942, this color-only version flooded onto land. The
revised 1942 path clusters ten colors, selects the pale river cluster, blocks
crossing dark bank ink, then keeps the two seeded channel components. The
seeds, water color prototype, and thresholds were chosen by looking at these
four crops; this is **not** a general model or an independent validation. Run:

```bash
work/ocr/.venv/bin/python work/analysis/district4/river_probe.py
```

The selected masks and overlays are in `/private/tmp/vma-river-mask-{year}.png`
and `/private/tmp/vma-river-detected-{year}.png`; the contact image is
`/private/tmp/vma-river-detection-contact.png`.

| year | selected px in 1024² | visual verdict |
|---|---:|---|
| 1923 | 94,370 | Main hatched river follows the banks in this window; lettering and some small shore gaps remain. |
| 1942 | 117,157 | Revised color-cluster + dark-bank mask follows the main river and southern channel in this window, with small gaps. The first color-only mask (390,102 px) and a gradient watershed both flooded onto land. |
| 1959 | 334,223 | Broad cyan river follows its banks, with the nearby blue channels also selected. |
| 1968 | 195,492 | Broad blue river and connected channels follow their banks; some very pale water is missed. |

Thus a seeded, sheet-specific mask follows water visually in **all four selected
windows**, but 1942 needs a bank barrier and its result is more brittle. No
precision/recall or full-sheet result follows from this. Before georeferencing,
a detector needs multiple windows per sheet, overlapping native-resolution
tiles, seam handling, and held-out river outlines. The 1942 color-only failure
must remain visible beside the corrected result: a connected component can
look complete while crossing the bank into roads and buildings.

## Residue cleanup after visual review

The first cleanup was wrong: it treated pale unselected pockets along the 1942
canal as missing water and closed with a 7-pixel radius. A source-resolution
inspection shows the mask was actually painting the **stippled foreshore** pink,
outside the printed blue-gray banks. Wider closings made that error worse.

The revised cleanup measures, in a 21×21 source-pixel window, how much of the
area belongs to the pale-water color cluster. Solid channel fill scores high;
stippled shore scores low. It keeps pixels above 0.35 occupancy within the
bank-fenced component, closes only 3 pixels, then uses a 3×3 median, fills
enclosed holes, and drops connected residues under 100 pixels on all four.
The 1942 threshold was chosen on this crop, so it still needs a held-out check.
The probe saves `vma-river-uncleaned-{year}.png` beside the updated
`vma-river-detected-{year}.png` for direct review. The 1942 pair is
`/private/tmp/vma-river-1942-before-after.png`.

| year | selected px before cleaning | cleaned px | changed px | remaining components |
|---|---:|---:|---:|---:|
| 1923 | 94,370 | 94,330 | 104 | 1 |
| 1942 | 117,157 | 102,580 | 22,643 | 2 channels |
| 1959 | 334,223 | 334,192 | 101 | 1 |
| 1968 | 195,492 | 195,370 | 276 | 1 |

On 1942 the revised pass removes 18,610 pixels of mostly stippled shore and
adds 4,033 pixels inside the selected channels; the area falls about 12%.
Visual alignment to the printed banks improves on this crop, but no crop has
a hand-drawn reference yet. The other three masks changed by at most 276
pixels; larger smoothing there could erase real narrow water. Do not use any
of these boundaries as GCPs until held-out bank distance and false-positive
area are measured.

## Full-sheet transfer, 2026-09-21

`river_full_map.py` now runs each sheet end to end at 1:1 — every native 256 px
level0 tile fetched once, 1024 px cores with a 32 px halo, a disk-backed
`candidate.uint8` the size of the scan, and a preview. Three fixes went in
first, all of them things that made the earlier run untrustworthy rather than
wrong:

- The 1942 k-means palette was refitted on every run from
  `/private/tmp/vma-river-fullres-1942.png`, a file that is not in the repo.
  The ten centroids are now frozen in `river_palette_1942.json` and read back,
  so a run after a cleared `/private/tmp` gives the same mask instead of
  crashing or, worse, a different palette.
- The tile fetch retried three times with no backoff. A single
  `ConnectionResetError` at 24 workers killed a 3,465-tile sheet outright. Now
  five attempts with an exponential sleep, and the default is 8 workers.
- `--self-check` (the convention `metrics.py` and `georef_error.py` already
  follow): the frozen palette, the halo against the widest neighbourhood any
  path reads, exact-once tiling coverage, and `preview()`'s uint8 `add.reduceat`
  against the factor that would wrap it.

**The thresholds were deliberately not retuned.** This run answers one
question: does a crop-tuned colour rule transfer to the whole sheet?

| year | candidate px | of scan | verdict |
|---|---:|---:|---|
| 1942 | 1,849,563 | 3.9% | **transfers.** The river network traces across both panels with little visible land bleed. |
| 1923 | 61,629,808 | 27.4% | **floods.** River plus both fold creases, the margins, the neat-line and a diffuse wash over most of the sheet. |

1923 is the predicted failure, and it is worth stating exactly what failed.
The crop thresholds (`b-r > -0.080`, `b-g > -0.090`, `r-g < 0.040`) accept
almost anything that is not strongly red. On the 1024 px crop that did not
matter, because a **seeded connected component** then kept only the river.
`river_full_map.py` has no such selection step, so what it writes is a colour
candidate, not a river — which is what its `run.json` `status` says, and why
the number above is not a detection result.

**The fold creases are the incidental finding.** On 1923 they are detected as
strong continuous lines across the full sheet. That sheet already has only 3
GCPs and an unmeasurable residual (`georef_error.md`); physical folds are a
second reason its geometry cannot be assumed rigid.

Next for the detector, in order: carry the seeded component selection into the
full-sheet path; mask the margins and the neat-line; then per-sheet thresholds
chosen on one window and tested on a different one.

## The tighten pass, 2026-09-21

All four sheets ran end to end, and the earlier two-sheet picture was wrong in
the direction that matters: **three of four transfer, not one of two.** The
crop-tuned colour rule holds wherever the sheet prints water as a saturated
fill. 1923 is the only failure, and it prints water as blue *hatching*.

| year | candidate px | of scan | tightened px | of scan | components kept |
|---|---:|---:|---:|---:|---:|
| 1942 | 1,849,563 | 3.9% | 1,419,060 | **3.01%** | 62 / 374 |
| 1959 | 8,809,219 | 5.8% | 5,066,683 | **3.36%** | 94 / 1,295 |
| 1968 | 9,706,486 | 6.6% | 5,484,968 | **3.75%** | 215 / 2,415 |
| 1923 | 61,629,808 | 27.4% | 19,263,276 | **8.55%** | 523 / 24,066 |

Every count above reproduced exactly on an independent re-run, which is what
the frozen `river_palette_1942.json` was added to guarantee.

`tighten()` turns the colour candidate into a selection with four rejections,
all specified in **ground units** so one setting covers four scans at four
resolutions (0.85–1.69 m/px):

- **local occupancy** (18 m window, ≥ 0.80) drops the dithered colour wash.
  Measured first: on 1923 the wash sits at 64 px-block density 0.2–0.75 while
  real water reaches 1.0, and only 3.6% of blocks exceed 0.9.
- **erosion to seeds** (8 m radius) drops everything thinner than a river —
  fold creases, the neat-line, title lettering, most roads.
- **reconstruction** from those seeds puts the full width back, so a river is
  not thinned by the step that found it.
- **an area floor** (2,000 m²) drops the remaining specks.

The neat-line is masked on the **seeds**, not the mask: the margin band then has
no seed and dies at reconstruction, while a river running off the sheet is still
seeded inside and rebuilt outwards rather than cut at the frame. The box comes
from the darkest rule near each edge of the 1600 px overview, and is **rejected**
when it covers under 60% of the sheet. That rejection fired on 1968, where the
profile picks up an interior rule and the box would have cut half the map;
1968 therefore ran with no frame mask and the other three were cropped.

What each sheet gained:

- **1923** loses the whole-sheet wash, the margin band and the title lettering.
  27.4% → 8.55%, and 24,066 components → 523.
- **1959** loses 42% of its pixels and 93% of its components with no visible
  change to the river network. That was almost all residue.
- **1942** and **1968** clean up comparably, but 1942 also loses narrow
  south-eastern branches: 8 m is 5 px at 1.69 m/px, so isolated channels under
  about 17 m wide do not survive. **The cost of the pass is scale-dependent,
  not uniform** — the coarsest scan pays the most.

### What is still wrong on 1923, measured

Two fold creases and the wide Cholon boulevards survive, which is why 1923 sits
at 8.55% against roughly 3% for the others. In a 256 px window each:

| | in mask | blue ink (b−r > 0.02) | hatch occupancy p90 |
|---|---:|---:|---:|
| river | 54.5% | 8.9% | 0.406 |
| road, Cholon | 23.4% | 6.3% | 0.286 |
| fold, horizontal | 24.1% | 3.0% | 0.129 |
| fold, vertical | 8.3% | 0.2% | 0.000 |

Blue ink separates the vertical fold outright but **not** the boulevard.
Hatch occupancy orders all four correctly, so a 1923 rule built on hatch
density rather than "not strongly red" is the right next move — but the numbers
above come from the same four windows the thresholds would be chosen on, so
picking a cut from them would be fitting to the sample. That retune needs a
held-out window, per `river-comparison.md` §Gate.

**None of this is a detection result.** No sheet has a hand-drawn reference, so
there is still no IoU, no false-positive area and no bank distance; `run.json`
carries `"selection only; no hand-drawn reference, no IoU or bank error"` on
every sheet. Reproduce without refetching tiles:

```bash
python work/analysis/district4/river_full_map.py --self-check
python work/analysis/district4/river_full_map.py --year all --tighten-only
```
