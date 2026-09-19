# District 4 — urban evolution

The morphology series behind "the urban evolution of District 4": for each
historical sheet that covers the peninsula between the Bến Nghé and Tẻ canals,
how much of it was built, how coarse the blocks were, how dense the streets,
how much water was still open. Two years compared is the change.

## A green run in five minutes, with no data

```bash
source work/ocr/.venv/bin/activate
python work/analysis/district4/metrics.py --self-check   # the measurements are right
python work/analysis/district4/series.py --demo          # the pipeline runs end to end
```

The demo prints a three-year table from synthetic geometry. The numbers are
invented; the code path is the real one. From here every change is incremental
and immediately testable.

## The real run

```bash
python work/analysis/district4/series.py \
  --maps $(cat work/analysis/district4/maps.txt) \
  --out district4.csv
```

The AOI now defaults to `district4.geojson` — the peninsula itself. Do not pass
a bbox; see "the AOI is a polygon" below.

`maps.txt` is generated, not curated by hand:

```bash
node --env-file=.env scripts/collection_aoi.mjs --aoi district4
```

That ranks every georeferenced sheet by how well it *resolves* the district,
and it is the list to trust over any typed from memory. Measured 2026-09-04.

**A m/px figure is only checkable if the scan it was measured on is written
next to it** — pixel dimensions, not just a name. This table went without that
for months and it cost nothing until two different scans of the 1959 sheet
produced two different, individually-correct numbers that looked like a
contradiction. See the 2026-09-10 correction below the next table. The `Scan
(px)` column here is added for the same reason; "not established" means this
revision could not pin the figure down from anything on disk, not that no such
scan exists.

| Year | Ground resolution over D4 | Covers | Sheet | Scan (px) |
|------|--------------------------|--------|-------|-----------|
| 1882 | 0.34 m/px | 21% | Plan Cadastral de la ville de Saigon | 12102×8982 |
| 1923 | 0.85 m/px | 56% | Saigon - Cholon | 16064×14027 |
| 1968 | 1.27 m/px | 66% | Sài Gòn — Việt Nam City Maps 1:12,500 | 10816×13523 |
| 1895 | 1.68 m/px | 100% | Plan des environs de Saïgon | 13654×8964 |
| 1942 | 1.69 m/px | 95% | Plan de Saigon - Cho Lon | 7479×6314 — **superseded, see the 2026-09-19 note below** |
| 1959 | 2.80 m/px | 97% | Đô thành Sài Gòn | 5000×3790, Virtual Saigon/IRD — **superseded, see below** |

**The 1942 row above has the same fault, found 2026-09-19.** Its `Scan (px)` was recorded as
7479×6314 and marked *confirmed* because the sheet's own layout job reported that `source_size` on
2026-09-05. The sheet's **Allmaps annotation puts its control points on 14915×12602** — and
14915/7479 = 1.994, 12602/6314 = 1.996, so this is one scan at twice the other, exactly the 1959
situation. Both figures are correct about their own scan. The one that matters for any ground claim
is the one the GCPs live on, which is the annotation's.

This is the second time this table has been wrong in this precise way, so state it as a rule rather
than a correction: **a `source_size` from a layout job describes the scan that job fetched, which is
not necessarily the scan the georeference was built on.** Only the annotation settles it.

Measured georeference error for all six sheets, added 2026-09-19:
`work/analysis/district4/georef_error.md`. Four of six now carry a stated limit — 1968 at 9.0 m,
1882 at 12.7 m, 1959 at 12.8 m, and **1942 at 72.3 m RMSE with a worst point of 193.7 m**. 1895 and
1923 cannot be measured from their own control points, for reasons given there.

**The 1959 row above is stale as of 2026-09-10.** It is what `collection_aoi.mjs`
measured on 2026-09-04, against the 5,000×3790 scan. The scan the OCR pipeline
reads today is 14,000×10,773 — nearly three times the pixel width, the same
city at 0.999 m/px rather than 2.80 (`docs/pipelines.md`'s 2026-09-10 note;
`scale.py`'s self-check fits `(0.999, 14000, 10773)` for this sheet, and
`tests/mpp-parity.spec.ts` pins that GCP-fit estimator against
`collection_aoi.mjs`'s own to 0.24% agreement). Nobody has re-run
`collection_aoi.mjs` against the new scan, so the 97%-covers / 2.80-m/px pairing
above is left as measured rather than guessed at — read it as "true of the
5,000×3790 scan, measured 2026-09-04," not as this sheet's current standing.
The full story, and what it changes below, is in the next section.

Six sheets, 1882→1968. **1878 and 1898 are not in it**, though earlier notes
listed both: their georeferences put them entirely north of the Bến Nghé canal,
so they are plans of the colonial centre (today's District 1), not of this
peninsula. 1878 clips 8% of the district along the canal and 1898 none at all.
The peninsula was still largely marsh when they were drawn, which is why.

Nine further sheets touch the district but are too coarse to read at ≤3 m/px —
1912 (4.3), 1900 (5.1), 1815 (6.4), 1930 (8.4), 1922 (8.8), 1791 (11.3), 1920
(74.6), 1958 (255.4). Lower the bar with `--max-mpp` if a claim only needs
blocks rather than buildings.

## Digitalizing only the district

The sheets are big and the district is a small part of most of them, and the
georeference already knows which part. Run the AOI backwards through a sheet's
annotation and you get the rectangle to crop in its own source pixels;
`collection_aoi.mjs` does that and queues it as the job's `neatline`, which
`vma_worker.py` passes to `ocr.py --crop`, which restricts the tile grid and so
the IIIF region requests.

```bash
# look first — prints the crop per sheet and what it saves
node --env-file=.env scripts/collection_aoi.mjs --aoi district4

# then queue it
node --env-file=.env scripts/collection_aoi.mjs --aoi district4 --enqueue-ocr

# nothing runs until a worker claims it
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --worker $(hostname)
```

Across the six sheets that is 669 Mpx of paper down to 55 Mpx of District 4 —
8% of the pixels, 25 tiles in total. On the 1930 Gia Định province sheet the
district is 0.4% of the paper, which is the difference between a sensible job
and an absurd one.

**Spend the saving on resolution, not on speed.** Each tile is `tile_size`
source pixels rendered to `render_size` before the model sees it, so what
reaches Gemini is the sheet's own m/px times `tile_size / render_size`. The
stock 2400/1024 is a 2.34x downsample *on top of* the scan, which was putting
the 1959 sheet in front of the model at 6.5 m/px and the 1942 at 4.0 — far too
coarse for a street name, on the scan each was measured on. (1959's 6.5 was
never wrong, it just stopped being the pipeline's number — see the correction
right after the table.) These jobs queue 2048/2048 instead: 1:1, the scan's own
ceiling.

| Year | Source | Scan (px) | To the model, before | Now (1:1) |
|------|--------|-----------|----------------------|-----------|
| 1882 | 0.34 m/px | not established | 0.80 | **0.34** |
| 1923 | 0.85 m/px | not established | 1.99 | **0.85** |
| 1968 | 1.27 m/px | not established | 2.97 | **1.27** |
| 1895 | 1.68 m/px | not established | 3.93 | **1.68** |
| 1942 | 1.69 m/px | 7479×6314 | 3.95 | **1.69** |
| 1959 | 2.80 m/px † | 5000×3790 † | 6.55 † | **2.80** † |

† **Superseded, 2026-09-10.** This whole row describes the 5,000×3790 scan
`collection_aoi.mjs` measured on 2026-09-04. The OCR pipeline now reads a
14,000×10,773 scan of the same sheet — `docs/pipelines.md`'s crop evidence
(`work/ocr/outputs/34d4edb2-*/runs/idx-20260910/run_config.json`, a
`1148,775,11704,9221` crop, which alone puts the image at ≥12,852 px wide) and
`scale.py`'s GCP fit (0.999 m/px, asserted in its self-check) agree, and
`tests/mpp-parity.spec.ts` pins the two estimators to 0.24% of each other on
real control points. Both 2.80 and 0.999 were correct measurements; they were
never comparable, because neither said which scan it was measuring — that is
the fault, not the arithmetic. At the pipeline's current scan the same 2.34x
downsample this section is about delivers **~2.34 m/px, not 6.5**, and the
2048/2048 jobs this section recommends deliver **~0.999 m/px 1:1, not 2.80**.
None of the other five rows are known to have changed; 1942's own layout job
(2026-09-05) still reports 7479×6314, matching this table, though nothing
newer than that exists in the repo to check against.

`render_size` was not even reachable from a job payload until now — the worker
hardcoded the default — so every queued OCR run to date was downsampled 2.34x
whatever the sheet. `--render-size` is the knob; equal to `--tile-size` is 1:1,
and higher only upsamples and buys nothing real.

Past 1:1 the limit is the scan itself, and **re-mirroring cannot help**:
`scripts/tile_map.sh` builds each R2 pyramid from `full/full/0/native.jpg`
(Gallica) or `full/max/0/default.jpg`, so what we hold already *is* the
institution's own maximum. `map_iiif_sources` has no rows for any of the six,
so there is no second copy to compare either.

**2026-09-10: this paragraph is only half true now, and it's the more
consequential half that changed.** It used to name two thin scans, **1959**
(5000x3790, Virtual Saigon/IRD, 2.80 m/px) and **1942** (7479x6314, BnF, 1.69
m/px), and conclude that raising either meant "a new digitization or a
different holding copy, not a re-download — an acquisition question, not a
pipeline one." For 1959 that acquisition question turned out to already be
answered: the OCR pipeline now reads a 14,000×10,773 scan of the same sheet
(0.999 m/px — see the correction two sections up), so whatever supplied it,
that already happened, and it is not still open. 1959 is no longer one of the
thin scans.

**1942 is the one confirmed thin scan left**, and only that: its own layout job
(run 2026-09-05) still reports the same 7479×6314, and nothing later touches
that map anywhere in the repo. That is not the same as confirming it *hasn't*
changed since — it means there is nothing on disk newer than 2026-09-05 to
check, the way there was for 1959. Whether 1942 gets the same upgrade 1959 did
is unverified, not ruled out. The other four sheets are still believed to be
12k-16k px, on the same footing as before (not independently re-checked here).

The first run made that ceiling look closer than it is, and the diagnosis is
worth carrying because it nearly cost a re-digitization.

At 2048 px tiles the 1959 sheet (2.80 m/px on the 5,000×3790 scan this
experiment ran against — since superseded, see above) returned 5 labels and no
street name, against 1942 (1.69 m/px) returning 21 with ten street names. The
obvious reading was that 2.80 m/px is below the floor for street type and the
scan needs replacing. That was wrong. Holding the crop and the 1:1 rendering
fixed and changing only the tile, counting **distinct labels that warp back
inside the district**:

| Tile | Ground per call | Distinct D4 labels |
|------|----------------|--------------------|
| 2048 px | 5.7 km | 1 |
| 1024 px | 2.9 km | 2 |
| ~500 px | 1.4 km | 6, and 5 on a repeat |

(Ground-per-call above is `tile_px × 2.80 m/px` — i.e. computed against the
5,000×3790 scan, because that is what existed when this was run. The pipeline
now reads a finer scan of 1959, so a repeat today would start from a different
ground-per-call at the same pixel tile size. That does not touch the finding —
the point below is that ground per call is what starves a read, at whatever
m/px produces it, which is exactly why `--tile-metres` sizes the tile from the
sheet's own scale instead of a fixed pixel count.)

Five to six times the yield off an unchanged scan, and only the finest runs
found *QUẬN 4* — the district's own name, printed on the sheet. Rendering was
ruled out separately: 1024 px rendered 1:1 and at 2x gave byte-identical
output, so upsampling past the scan buys nothing. **What starves the read is
one call being asked to cover too much ground.**

Two cautions, both learned by over-claiming first. Repeat the same
configuration and you get 6 labels one time and 5 the next, and the
disagreement is mostly the same feature transcribed differently (*KINH BẾN
NGHÉ* against *Kinh Bến Nghé*) — so single-run differences of one or two mean
nothing, and the `category` a label is given is noisier still than its text.
And a single sheet does not generalise: applied across the whole collection the
same change gave **+19%**, not 5x, because the gain only appears where the
ground per call actually drops a lot (the 1959 row again is `2048 px ×
2.80 m/px`, the 5,000×3790 scan measured at the time, not the 14,000×10,773 one
the pipeline reads now — see above):

| Year | Ground/call before → after | D4 labels |
|------|---------------------------|-----------|
| 1942 | 3.46 → 1.40 km | 13 → **23** |
| 1959 | 5.73 → 1.40 km | 1 → **5** |
| 1895 | 3.44 → 1.40 km | 9 → **11** |
| 1923 | 1.74 → 1.40 km | 15 → 13 |
| 1968 | 2.60 → 1.40 km | 9 → 7 |
| 1882 | 0.70 → 1.39 km | 11 → 10 |

The three sheets made much finer all improved; the two barely changed drifted
within noise; and 1882 — the only sheet the rule made *coarser*, because a
0.34 m/px sheet needs a 4118 px tile to reach 1400 m — was the only regression.
Hence the 2048 px cap in `collection_aoi.mjs`: the rule may make a sheet finer,
never coarser. The numbers above predate that cap, so 1882 should recover.

A fixed pixel tile means a different thing on every sheet — 2048 px is 1.7 km
on the 1923 sheet and 5.7 km on the 1959 one. So the knob is ground, not
pixels: `--tile-metres` (default 1400) sizes each sheet's tile from its own
m/px, which also makes sheets comparable to each other, which a time series
needs anyway. 1400 m is a working default from thin evidence, not a tuned
optimum.

The honest remaining statement about scans, updated 2026-09-10: **1942**
(7479x6314) is the one confirmed thin sheet left, and a better scan of it would
still help — though whether one is already sitting somewhere, the way it was
for 1959, is not something this repo can currently answer, since nothing later
than 2026-09-05 touches that map here. **1959 is no longer thin**: the pipeline
now reads a 14,000×10,773 scan (0.999 m/px), not the 5,000×3790 one this
section was originally measured against. Either way, a better scan is a
marginal gain, not the blocker it appeared to be, and nothing should be
re-acquired before a sheet has been read at a sane tile size.

One expected artefact: a label falling in the 512 px tile overlap is extracted
twice, once per tile. `ocr_extractions` is unique on
`(map_id, run_id, tile_x, tile_y, text)`, so both rows are kept by design and
the duplicate is collapsed at review, not at ingest.

Two things to know about the crop:

- **It is a rectangle around a diagonal peninsula**, so it necessarily includes
  some of District 1 and District 7. That is fine for OCR — the labels are
  filtered by position later — but it is why the *measurement* AOI is the
  polygon and not this rectangle.
- **A study area that reaches the edge of the mapped area pulls in
  marginalia.** On the 1959 Đô thành Sài Gòn sheet the street-name index column
  starts within 200 px of the river, so the crop pad is deliberately small
  (100 px, `--pad-px`). A generous pad there fed a dense column of index
  entries to OCR as if they were places on the ground.

A legend or title outside the AOI is *not* read by these jobs. For a study-area
pass that is the point; reading a sheet's legend is a separate whole-sheet run.

## The AOI is a polygon, not a box

District 4 is a diagonal peninsula, so its bounding box is 7.62 km² against
4.46 km² of land — the box reaches across the Bến Nghé into District 1 and
across the Tẻ into District 7. Because `built_share` and `road_density` both
divide by the AOI's area, measuring the box halves every ratio *and* clips in
features that were never in the district.

`district4.geojson` is the peninsula: a ring built from the two canal
centrelines (OSM ways 289925742 and 289925740) joined at their shared western
junction and closed across the river frontage between their mouths. It measures
4.459 km² against the published 4.18 km²; the 7% excess is mostly the half of
each canal's width that a centreline puts inside the ring.

The old default, `106.695,10.752,106.715,10.772`, was worse than a plain
bounding box: it clipped ~940 m off the western apex and ~790 m off the river
frontage while overshooting 290 m north into District 1 — throwing away the
ground the sheets cover best. `metrics.py --self-check` now asserts the shipped
polygon is still a polygon, because replacing it with its own bbox would halve
every published ratio silently.

District 4 stopped existing administratively in Vietnam's 2025 ward merger, so
there is no boundary left to query. The peninsula is the stable definition, and
it is what the historical sheets show anyway.

This is not a theoretical worry. The 46 volunteer traces on the 1882 cadastral
sheet all sit in District 1, the nearest 68 m north of the Bến Nghé canal.
Measured against each candidate AOI:

| AOI | Traces counted | Built | `built_share` for D4 in 1882 |
|-----|---------------|-------|------------------------------|
| the polygon | 0 of 46 | 0 m² | **0.000%** — correct, nothing is traced inside D4 yet |
| its bounding box | 2 of 46 | 13,046 m² | 0.171% |
| the old shipped bbox | 7 of 46 | 55,167 m² | 1.140% |

The old default would have published a built-up figure for 1882 District 4 out
of seven buildings in District 1.

## Three facts that will otherwise bite you

1. **It will print zeros today.** As of 2026-09-02 production holds 46
   hand-traced footprints on one map and no segmentation output at all, so
   every row will read empty until footprints are reviewed in
   `/contribute/review`. That is the honest state, and the reason `series.py`
   emits a zero row with a note rather than skipping the year: a table with
   three empty rows tells you what to go and review.
2. **The export serves `approved` only.** A polygon sitting in the review queue
   is invisible here on purpose — an unreviewed trace is a claim, not a
   measurement. If a year looks empty, check the queue before the code.
3. **Warp error is per sheet and sometimes metres.** Every row carries
   `max_geom_rmse_m`, the worst control-point residual among the maps it drew
   from. An 1878 sheet with a handful of control points cannot support a claim
   about a single building; it can support one about a block. Report the column
   alongside any figure taken from this table.

## What runs today, and what does not

| | |
|---|---|
| Runs | `metrics.py` (measurement + self-check), `series.py` (fetch, table, CSV) |
| Runs, empty | the real series — the code is fine, the reviewed data is not there yet |
| Does not exist | figures. No plotting here yet: a chart of three zero rows is worse than no chart. Add it when the table has numbers, and read the palette guidance before choosing colours. |

## How the measurements are defined

Areas and lengths are computed in the UTM zone containing the study area, not
on a geodesic — over a few square kilometres that difference is far below the
warp error above. `built_share` is the union of building polygons over the AOI
polygon, so overlapping traces cannot double-count. A traced line arrives as a
closed ring, so its length is the ring perimeter halved. Rows whose geometry
could not be warped are dropped and counted in `unwarped_dropped`; they carry
pixel coordinates, and measuring them would add a polygon the size of a
continent.

## The other output

The polygons reviewed for this study are also the segmentation evaluation set
the roadmap has been waiting on (C5, "blocked on data, not code"): ~20
hand-checked tiles is exactly what comes out of reviewing eight sheets over one
neighbourhood. Export them before re-running MapSAM2, and record the numbers in
`work/ocr/EVAL-BASELINE.md` — including a null result.

## 2026-09-10, later — the four unestablished scans, and 1942 is not settled

A corpus-wide audit (`ocr.py scale --all`, cross-checked against each sheet's
annotation `target.source`, its `maps.iiif_image` `info.json` and every
reachable `map_iiif_sources` row) filled in the four `Scan (px)` cells this
revision had to leave open: **1882 12102×8982, 1923 16064×14027, 1968 Sài Gòn
10816×13523, 1895 13654×8964.** On all of them those three sources agree
exactly, so the 1959 fault does not repeat anywhere in the corpus.

**The claim above that 1942 is "the one confirmed thin sheet left" is too
strong.** Its 7479×6314 is what we hold, but its Gallica row sits at
`sort_order` 1 and is unmeasured, and Gallica was unreachable during the audit.
`scripts/tile_map.sh` cuts each R2 pyramid from the then-primary source's
`full/full`, so where the Gallica row is `sort_order` 0 the dimensions we hold
*are* Gallica's native maximum by construction — but 1942 is not one of those.
Read it as **unresolved, one `curl` away from an answer**, not as confirmed.

**1895 reads 1.68 here and 1.709 in the audit, on the same 13654×8964 scan.**
That is not a second 1959: it is this file's District-4-local area ratio against
a whole-sheet affine over 11 thin-plate-spline control points. 1.7% apart, and
`tests/mpp-parity.spec.ts` measures 0.24% between the same two estimators on a
helmert sheet, so a thin-plate fit drifting a little further is expected.

The audit's own finding, for the record: of 25 sheets above 1.1 m/px, 14 are
genuinely the paper they were printed on, 9 are unresolved, and **2 are cases of
the pipeline reading a smaller copy than the institution serves** — the 1863
Palanca Gutierrez Huế sheet (we read 4876×8396, Humazur serves 6501×11195, a
clean 4/3 downscale whose `source_url` already points at the larger copy) and
the 1968 Huế 1:50,000 Sheet 6541 IV (we read a 0.9 MB JP2 at 1660×2147 where
UTexas holds an 11.2 MB JPEG). Neither is an acquisition; the first is a
re-mirror from a source already recorded. Full table in the audit report.

**The 1863 one is done** (2026-09-10). R2 now mirrors Humazur's 6501×11195, the
annotation's GCPs and mask were rescaled to match, and `ocr.py scale` reads
**1.353 m/px** where it read 1.804 — the ratio's predicted figure exactly. The
sheet stays on this list, since 1.353 is still above 1.1; it is 25% less severe
and cost nothing. The 1968 Sheet 6541 IV case is still open.
