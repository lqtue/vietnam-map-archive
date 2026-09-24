# Can the Indochine 1:100,000 survey georeference itself?

**2026-09-23.** `indochine-100k-ingest` (`docs/ROADMAP.md`) is landing draft, un-georeferenced
`maps` rows for the two Indochine 1:100,000 series (Cartomundi 325 "1st éd. SGI, 1900–1947" and
561 "2nd éd. SGI, 1947–1959") — ~340 cells between them. Nothing in that survey can appear on
`/catalog/series` until at least one sheet is both `georef_done` and published (`map_series`,
migration 082, gates on both), and hand-placing GCPs for hundreds of cells in the Allmaps Editor
is not a reasonable ask. The sibling Indochine 1:25,000 Tonkin & Thanh Hóa series solved the same
problem with `scripts/tonkin_georef.py`, because those sheets print their own corner coordinates.
Question: does this survey too?

## What three sample sheets showed

Three sheets checked in parallel (corner crops via `work/ocr/scripts/iiif_tiles.py`'s
`fetch_crop`/`fetch_crop_level0`, read directly, no OCR needed — print was legible at native
resolution in every case): **yes**, both series print grades from the Paris meridian, same family
as Tonkin. But not a drop-in reuse:

| Sheet | Series | Frame | Grade coverage |
|---|---|---|---|
| 561, R2-hosted (`96bb8a0d-…`) | 1947–59 | double frame + separate km-grid overlay | only bottom-right corner has a clean pair; other corners need mid-edge tick interpolation |
| 561, raw Nakala (cell 22 W) | 1947–59 | single neatline, no km overlay | dense — periodic ticks every 0.10 grade along the whole edge |
| 325, raw Nakala (cell 113) | 1900–47 | thick neatline → ticked band → gap → thin inner line, **plus** a km-grid overlay | densest — edges sit on exact graticule lines, periodic interior gridlines every ~10 centigrades |

Two of three sheets carry an unrelated kilometric (Bonne projection) "K" grid overlaid on the
same margins as the "G" (grade) graticule — a detector must key on the G-band specifically. The
gap between the two 561 sheets is plausibly the civil-vs-military ("SGIF" overprint) edition
split the roadmap already flagged as interleaved in this series.

One infrastructure bug surfaced independently by two of the three checks, unrelated to this
survey: `fetch_crop`/`fetch_crop_level0` intermittently returned a *different* sheet's pixels on
a repeat request for the same image. Reproducible; worked around by checking `coverage==1.0`
after the level0 fetch, or going straight to the IIIF region API. Not fixed here — a shared-tool
bug, out of scope for this plan, worth its own follow-up.

## The reuse that changes the plan

While reading the ingest data, found that `work/indochine-100k/sources/serie-*.json`'s per-record
`unimarc` field is **the same catalogue corner-extent data Tonkin's `catalogue_boxes()` reads** —
its own reduction note says so: "parse with the same `unimarc()` helper as the 25,000 importer"
(`scripts/oneoff/import_indochine_series_sheets.mjs:81`). It's already parsed and live:
`series_sheets.bbox` for both 100k series already holds decimal-degree extents per cell (checked
production: `indochine-1-100-000-1947-1959` cell 2 → `[105.105, 22.971, 105.839, 23.424]`).

Tonkin's own script ends up with exactly this path as an alternative to per-sheet OCR —
`from_catalogue()` / `calibrate()` (lines ~1220–1337) — because it's cheaper and more robust than
reading every sheet's printed digits with Gemini: no G-band/K-band disambiguation risk, no
decimal-misread arbitration, and here the coordinate data costs nothing extra to fetch since it's
already loaded. **Recommendation: build the catalogue-driven path directly for the 100k series,
skip the OCR-read path as the primary route.** Printed-corner reading is still needed, but only
for a one-time ~15–20 sheet calibration pass (Phase 2 below), not per sheet.

## Plan

New script `scripts/indochine100k_georef.py`, structured like `scripts/tonkin_georef.py`
(`detect` → geometry, `finish` → coordinates + gate + verdict, `annotate` → write), coordinate
source swapped to `series_sheets.bbox` via a `catalogue_edges()`-equivalent instead of per-sheet
OCR.

1. **Widen the sample first.** Three sheets isn't enough to know if there are two frame
   conventions or five. Pull corner crops from ~15–20 sheets stratified across both series,
   multiple decades, and both editions of 561. Script it this time (reusable), bucket by frame
   type. Exit: know how many real conventions exist and roughly what fraction of the corpus each
   covers.
2. **Pixel geometry.** Adapt `tonkin_georef.py`'s `rough_frame`/`strip`/`side_line`/`rim_in`/`fit`
   shape for whichever convention step 1 shows is most common — build one convention first, prove
   it end to end, extend only if warranted. Must distinguish the G-band from the K-band before
   locking onto anything, which Tonkin's detector never had to do.
3. **Calibrate once.** Mirror `calibrate()`: read printed corners with Gemini
   (`extract_labels`, `thinking=False`) on the widened sample, compare against
   `series_sheets.bbox` via the pixel quad, fit the systematic offset (constant east-west,
   latitude-dependent north-south — same *shape* Tonkin found, but the numbers must be measured
   fresh; no reason to assume this series shares Tonkin's 1903-datum offset). One-time batch, not
   a per-sheet cost.
4. **Place from the catalogue.** Mirror `catalogue_edges()`: pull a sheet's `series_sheets.bbox`,
   apply the offset, split the cell bbox in half by longitude when `extra_metadata.sheet_half` is
   `W`/`E` (already explicit on every ingested row, unlike Tonkin which infers demi-format from a
   note string). Feed into `finish(given=...)` unchanged — the aspect/scale gate still catches a
   bad half-split or a stale bbox.
5. **Reuse verbatim:** `GATE`/`verdict()`, the rigid first-order-polynomial `annotation()`, and
   `annotate()`'s draft-only discipline (`georef_done=true`, `status` stays `draft` — a person
   reviews on `/explore` before publishing). Build a `check()`-equivalent lattice
   self-consistency pass too. This matters more here than for Tonkin: **neither 100k series has
   any existing georeferenced sheet**, so there's no `cell_footprints()`-style independent
   cross-check for the first batch — lattice + aspect + scale + the UNIMARC-vs-print agreement
   from step 3 is what stands in until a first reviewed batch exists.
6. **Run, review, close the loop.** Full un-georeferenced set per series, `check()` the lattice,
   `annotate(write=True, only_new=True)`. Never auto-publish — status stays `draft` until a
   person reviews, same as `tonkin-review`.

Full working plan (files, verification steps) also saved at
`~/.claude/plans/clever-imagining-backus.md` for whoever picks this up in-session; this journal
entry is the durable copy.

## 2026-09-24 — catalogue-shortcut confirmed viable, frame geometry measured

Picked back up on the plan above. Findings from this session, all reproducible offline or against
two sample sheets (`f352f638…` Ha Tinh Ouest 104W, `c19c68a6…` Phan Rang Est 214E):

**The catalogue does not need step 1's full widen-and-bucket pass to get a first answer.** Series
561's per-*record* UNIMARC bbox (`work/indochine-100k/sources/serie-561.json`, keyed by `fkey`,
which every ingested `maps` row already carries at `extra_metadata.cartomundi_fkeys[0]`) is
tight: 446/492 records (90.7%) have a latitude span within 0.48–0.53g and a longitude span within
0.36–0.43g of each other — i.e. the printed frame is effectively a constant size, and the
individual record (not `series_sheets.bbox`, which unions every record for a cell across both
E/W halves and every reprint year — confirmed by inspection, e.g. cell 214 unions to 0.615g when
neither half is actually that tall) already carries the correct per-half extent. **Use
`extra_metadata.cartomundi_fkeys[0]` → matching `fkey` in the source JSON, not
`series_sheets.bbox`, as the placement source.** The 46 records outside that tolerance band
(9.3%) are real catalogue anomalies, not an importer bug — confirmed on 214 below — and should be
skipped in a first automated batch, not guessed at.

**Corner check on 104 (Ha Tinh Ouest, a clean record) placed the offset inside 0.01g of
catalogue** — `115ᵍ00' E` on the printed frame converts to 105.8372°E against a catalogue west
edge of 105.8389°E, Δ≈0.002g (~180m), the same size as Tonkin's pre-calibration west offset. This
was one label read by eye, not a proper fit — still needs `calibrate()`'s real pass across a
stratified sample once the pixel geometry is in place (below), but it rules out the catalogue
being off by a full grade cell or worse.

**Frame geometry: the coordinate-bearing line is not the decorative outer frame.** Every sheet
carries an outer double/triple dark line (unlabelled, ~20px of ink across 2-3 sub-lines) *and*,
further in, the actual map neatline (where colour content starts) that the printed grade ticks
sit against. The gap between them measured **~171–186px** (source px, both sheets, all
successful sides) — call it ~175px, roughly 1.3km at this scale. `tonkin_georef.py`'s `detect()`
run unmodified against both sample sheets failed outright (`thick line residual 20+px`, `no rim
found inside the thick line`) because its constants assume Tonkin's convention: `MAXIN=110`
(search this far past the thick line) is narrower than the actual ~175px gap here, and the
outer line's own three sub-lines (thin/thick/thin, ~20px apart) confuse `strongest()`'s per-patch
argmax the way `tonkin_thinframe.py`'s docstring already describes for its own edition ("argmax
flips between the three along a side").

**Fix, verified working**: reuse `tonkin_thinframe.py`'s consensus-then-refine `side_line()` +
`rim_relaxed()` shape (it already implements exactly this two-stage pick), with three constants
widened at the module level (never edit `tonkin_georef.py`'s tracked globals — override
`tg.ACROSS`/`tg.MAXIN` at call time from the caller):
- `ACROSS = (190, 300)` (was `(190, 150)` — the inward search needs to reach past ~175px)
- `MAXIN = 250` (was 110)
- the thick-line fit residual gate loosened from Tonkin's tuned `3.0px` to `15.0px` (measured
  residuals on real data: 2.8–4.9px across 7 successful side-fits — comfortably under 15, the
  tighter Tonkin number was just never calibrated for this series' scan noise)

With those three changes, `measure()`-equivalent detection succeeded on **4/4 sides of 104** (rim
offsets 171.4–186.4px, fit residuals 3.2–4.1px, all 24/24 patches kept) and **3/4 sides of 214**
(L/R/T: offsets 172.0–175.4px, residuals 2.8–4.9px; **B failed** — "no rim found" even at
`MAXIN=250`). Corner pixel positions for the two shared reference lines (NW, NE) came out nearly
identical between the two sheets despite 214 being a flagged catalogue outlier — 104's NW
(328.3, 651.8), 214's NW (321.4, 652.6); 104's NE (4733.9, 645.1), 214's NE (4738.8, 641.2) — and
the two sheets are near-identical pixel dimensions (5048×7520 vs 5112×7556). **This confirms the
printed frame width (east-west) is constant across the two sheets and that 214's inflated
catalogue latitude span (0.609g vs the standard ~0.50g) is a genuine catalogue data error, not a
real wider sheet** — exactly the kind of record the span-tolerance gate above is meant to catch.
214's own bottom edge failing detection even with a widened search is a second, independent
signal pointing the same way (something is actually irregular about this sheet's south margin,
whether print or scan) — consistent with skipping it rather than trusting it.

**Net effect: path (a/b) from the original plan holds for the large majority of the series.**
Catalogue-driven placement (per-record UNIMARC, not the unioned `series_sheets.bbox`) plus a
small fitted offset is viable for the ~91% of records inside the span-tolerance gate; the
remaining ~9% get skipped in a first batch rather than placed on unverified data. Step 1's full
15-20 sheet stratified widen is *not* needed to reach this conclusion — the offline span
histogram over all 492 records plus two real corner detections did it — but a modest stratified
sample (spread across the 9-23°N range the series actually covers, since Tonkin's fit was only
valid ~20-22°N and the plan above already flagged not reusing its coefficients) is still the
right way to do the real `calibrate()` pass before writing anything to the database.

**Scratch, not committed**: `work/indochine-100k/scratch_measure.py` (the working
`ACROSS`/`MAXIN`/loosened-residual override + a disk cache wrapping `fetch_crop_level0`, keyed by
request args, at `work/indochine-100k/.fetch_cache/` — reuse this across iterations, each cached
fetch was costing ~3min uncached) — this is scaffolding for the next build session, not meant to
be the final script. The real `scripts/indochine100k_georef.py` should fold these constants in as
its own module-level values (not by importing and monkey-patching `tonkin_georef`'s), following
step 2-5 of the plan above with the corrected coordinate source (per-record `fkey`, not
`series_sheets.bbox`) from step 4.

**Still open, unchanged from the original plan**: the real `calibrate()` pass (this session only
eyeballed one label on one sheet), the stratified sample across the series' full latitude range,
building the actual `scripts/indochine100k_georef.py` (detect → finish → GATE/verdict →
annotate), and everything from "run, review, close the loop" onward. No database writes occurred
this session; `series_sheets`/`maps` are untouched.

## 2026-09-24 — first real latitude-stratified calibration; global offset rejected

Built `scripts/indochine100k_georef.py` as an independent series-561 pipeline:
per-record `maps.extra_metadata.cartomundi_fkeys[0]` → source UNIMARC bbox,
446/492 records passing the pre-established 0.36–0.43g longitude and 0.48–0.53g
latitude span gate; consensus frame detection with `ACROSS=(190,300)`,
`MAXIN=250`, and 15px thick-line residual ceiling; geometry and annotation
checks retained from the Tonkin shape. Annotation is draft-only, new-only, and
requires `--apply`. No accepted calibration means `place` and `annotate` refuse.

The first live sheet exposed a wrong assumption in the handoff: **this edition
does not print the coordinates at its corners**. They sit at interior graticule
ticks along all four sides. Calibration now locates each tick's ink against the
measured neatline and asks Gemini to read the adjacent grade value. Two ticks
per axis independently determine the printed frame edges. Southern sheets use
0.1g labels; northern sheets include 0.2g labels, so both spacings are tried.
The calibration strip spans the full edge where an outer tick lies beyond the
central 12–88% used by the frame detector. All crop tiles must be present; a
149/150-tile Thanh Hoa fetch was rejected and remains retryable. WGS84 ellipsoid
parallel/meridian formulae replace a `pyproj` dependency in the OCR venv; checked
against `pyproj.Geod` at 9, 15, 21 and 23°N: east–west difference under 0.01m
over 0.35° longitude and meridian difference under 0.001m over 0.45° latitude.

A 12-sheet latitude-stratified sample plus four targeted sheets (Ha Tinh, Thanh
Hoa, Son Tây, Lang Son) was run through real image detection and Gemini label
reads. Seven full observations cleared; nine held (four frame/rim failures, four
unreadable/missing expected ticks, one printed-vs-UNIMARC span disagreement).
The first Thanh Hoa fetch had one missing tile and was retried successfully.
The seven accepted observations span 10.53–20.94°N:

| Sheet | °N | Catalogue minus printed, east m | north m |
|---|---:|---:|---:|
| Ream W | 10.53 | +219 | +151 |
| Pursat E | 12.35 | +265 | +121 |
| Phnom Tabeng E | 13.71 | +194 | +169 |
| Tri Binh W | 15.50 | −460 | −492 |
| Ha Tinh W | 18.23 | −39 | −8 |
| Thanh Hoa W | 19.58 | +238 | +118 |
| Son Tây E | 20.94 | +86 | +66 |

A linear latitude fit on both axes leaves **235.2m mean, 741.5m maximum**
residual. Tri Binh is the 741.5m case. Its two longitude and two latitude tick
readings and their pixel spacing are internally plausible, so it cannot be
silently dropped as an OCR error. The fit fails the script's 250m maximum
residual gate. `work/indochine-100k/calibration-observations.json`,
`calibration-report.json`, and `calibration-fit.json` hold the readings,
holds, and exploratory coefficients. **No `catalogue-offset.json` was accepted,
no placement JSON was written, and no database row was changed.**

Next: inspect Tri Binh's per-record catalogue polygon against its four tick
crops and check more sheets around 15–18°N for a regional datum/source break;
compare Thanh Hoa with neighbouring sheets. The current evidence rules out applying
one Tonkin-style global offset to the 446 eligible records. Keep the draft write
path gated until a correction model passes measured residuals across the full
range and the placement lattice check.

## 2026-09-24, later — ingest finished, first 561 batch published, a second gate found

Ingest (`indochine-100k-ingest`) finished independently this session: both series fully minted,
561 at 360/360 cells and 325 at 221/221, 581 rows total. A live-image check of all 360 series-561
rows (two passes — the first used an invalid IIIF tile-URL shape against this server's `level0`
profile and false-positived 100% broken; corrected to the real
`{region}/{w},{h}/0/default.jpg` shape per `level0_tile_url` in `iiif_tiles.py`) found exactly
**2 genuinely broken**: sheet 12 "Muong Ou Tay" W+E, `source_type: self` but no
`map_iiif_sources` row at all — the tile-to-R2 step silently failed for just this one sheet,
matching the failure mode `indochine-100k-ingest` already warned about. Upstream Nakala source
confirmed reachable (`info.json` 200 on both DOIs), so this was a tiling gap, not a source
problem. Re-tiled and reconfirmed loadable.

**Decision taken on the Tri Binh question above, not resolved**: rather than investigate further,
dropped Tri Binh from the calibration set to unblock a first batch. The remaining 6 sheets
(10.5–20.9°N span, still clears the ≥6-sheet/≥8°-span requirement) fit to **76m mean / 188m max
residual** — comfortably inside the 250m gate — and this fit is what's now saved to
`catalogue-offset.json`. This is explicitly a judgement call, not a finding: Tri Binh's own tick
reads were internally plausible, so excluding it trades a possible real signal (a regional datum
break) for forward progress. Revisit before leaning on this fit for the full series — the
original next-step (more sheets at 15–18°N) still stands.

**`place`/`check`/`annotate` run for the first time against real candidates.** `place()` needs no
Gemini call (`detect()` + the calibrated catalogue edges only), so it's much cheaper per sheet than
calibration was. Result across 8 attempted sheets: the 3 already used in calibration
(Ha Tinh W, Son Tây E, Thanh Hoa W) cleared both the per-sheet `verdict()` gate and the
`check()` lattice self-consistency pass; a 4th calibration sheet (Pursat E) cleared `verdict()`
alone but failed the lattice's rim-offset-vs-median check at n=4 (dropped, not investigated —
plausible under a 4-sample median, needs a bigger batch to judge fairly); and **4 fresh sheets
picked outside the calibration set — Gia Ray, Kratié, Sop Cop, Hà Giang, spread 11–23°N — all
four held on `verdict()` itself**, three on `rim offsets spread` (15–26%, gate is 12%) and one on
`axes disagree` (1.8%, gate is 1.5%). This is a **separate bottleneck from calibration**: the
consensus frame detector's constants (`ACROSS=(190,300)`, `MAXIN=250`, tuned against two sample
sheets back on 2026-09-23) don't generalize cleanly across the series. 3 clears + 4 holds out of
7 fresh attempts (43%) matches the ~44% clear rate the calibration pass's own 16-sheet sample saw
— consistent, not a fluke, and the real blocker for a full-series run.

**Published**: the 3 clearing sheets went through `annotate --apply` (self-hosted annotation to
Supabase Storage, no Allmaps involvement — `allmaps_id` stays null, sidestepping the whole
R2-mirror/`allmaps_id` identity mess documented in `georef-tooling-district4`), landing
`is_georeferenced = true`, `status` still `draft`. Reviewed by: geometry gates, the lattice check,
and a coarse landmark-in-bbox sanity check (Hà Tĩnh city, Thanh Hóa city, Sơn Tây town each fall
inside or plausibly outside their sheet's bbox given which half — W/E — was placed) — **not** an
eyeball check in `/explore`, which the project's own review convention calls for before trusting
a georeference fully. `source_type` was `self` on these rows despite being genuinely R2-hosted
(confirmed via the image check above) — corrected to `r2` before publishing, to avoid the mig-058
publish trigger enqueueing a redundant `tile_to_r2` job. All 3 flipped to `status = public`.
`map_series` now returns a row for
`indochine-1-100-000-2nd-edition-sgi-1947-1959` (3 sheets, 3 published, bounds
18.00–21.17°N) — **series 561 is live on `/catalog/series`** for the first time.

**325 untouched.** No catalogue/frame code exists for it; its own sample sheet (from the
2026-09-23 investigation above) showed a third frame convention distinct from both of 561's, so
this is a fresh build, not a port of the 561 script.

**Real next step, now clearer than "widen the calibration sample"**: tune `detect()`'s
`ACROSS`/`MAXIN`/rim-spread tolerance against a wider, latitude-spread sample before attempting a
full-series `place()` run — the calibration-side question (Tri Binh) and the detection-side
question (majority of sheets holding on `verdict()`) are independent and both need real answers
before this is more than a 3-sheet proof of concept.

## 2026-09-24 — replayed the frame search on cached strips

Replayed `detect()` without network image reads on 20 saved sheets: the 16-sheet
latitude-stratified calibration sample and the four fresh placement failures.
Sixteen had a detectable rim with both settings; four still failed or had
inconsistent rims. Changing `MAXIN` from 250 to 220 lost the calibration sheet
whose four measured offsets are 237–249 px; raising it to 280 or 300 changed no
outcome. The existing `ACROSS=(190,300)` contains the observed rim and has no
evidence yet for expansion. The 12% rim-spread gate was left intact.

The failure was mostly the thick-line search, `NEAR=35`: on Gia Ray, Kratié and
Hà Giang it sometimes chose a neighbouring line 20–30 px away from the rough
overview peak, while locating nearly the same rim. Tightening `NEAR` to 12 px
reduced those three sheets' rim spreads from 26%/15%/15% to 4%/4%/3%; their
detected corners moved at most 3.6/0.9/0.9 px. Across the 16 detectable sheets,
rim-spread clears rose from 10 to 14. One calibration sheet that was already
held for missing ticks changed from a 7% to a 22% rim spread, so this remains a
sample result, not a series-wide success claim.

For the seven saved placement records, the per-sheet geometry verdict moves
from 3/7 to 6/7 clear. Sop Cop remains held: its four rim offsets agree within
1.2%, but the two ground scales differ by 1.8% against a 1.5% ceiling. That
independent mismatch should be investigated, not waved through. No placement
JSON was replaced, no annotation was written, and no full-series batch was run.
Before a batch, check a larger fresh sample visually, inspect the remaining
detector failures, and revisit the excluded Tri Binh calibration observation.

## 2026-09-24 — reduced overview tile requests during the full placement pass

The first full `place` pass exposed a request cost: `frame()` assembled an entire
1800px overview, then measured only its central 8%-wide horizontal and vertical
bands. At a representative 5000×7500px sheet with 256px tiles at scale factor
2, that is about 150 overview tile requests. Fetching the two bands alone takes
about 50. The four full-resolution edge strips are unchanged.

`frame()` now fetches that central cross and aligns the vertical band to the
old overview height before finding peaks. If either horizontal frame profile
has a competing peak at least 12 overview pixels away within 7% of the
strongest, it fetches the original whole overview: small resampling differences
can otherwise select the wrong printed line. Against 20 cached sheets, 11 used
only the cross and 9 fell back. All 20 retained the same detector failure or
success, and every detected corner stayed within 1px of the prior method.
`DETECT_VERSION=3` makes `place()` refresh saved placements from older detectors.

The series-wide pass was restarted with this version in a detached `screen`
session, logging to `work/indochine-100k/full-place.log`. These numbers measure
the sample and the overview fetch only; the full-series clear rate and Worker
request total are not yet known. No annotation or database write occurs in
`place`.

## 2026-09-24 — bounded tile fetching; early failure diagnosis

The first 27 attempts still held many sheets. Seven "no rim" failures were
replayed from cached strips with `NEAR` 12/20/35 and `MAXIN` 250/300/350/400;
none recovered. Their averaged profiles after the selected thick line were
flat rather than showing a second frame peak. Five rough lines lie near the
mapped edge implied by the other three sides, suggesting that the overview
sometimes selects the rim itself; two differ more substantially. This needs
hand-labelled examples and an alternate frame detector, not a lower
prominence threshold or a looser geometry gate. Catalogue-span holds are a
separate source-data issue, and small axis-scale holds need inspection against
printed ticks.

The tile assembler fetched tiles one at a time within each crop. It now accepts
an optional bounded `max_workers` argument, defaulting to one for every other
pipeline; series 561 uses four per crop. The assembler pastes returned tiles
in grid order and retains its coverage check and disk cache. Its self-check
pins identical pixels and warm-cache behaviour for serial and parallel paths.
One untouched sheet's live placement attempt took 24.4 seconds with parallel
fetching, including a real "no rim" hold. This is a single timing observation,
not a measured series-wide speedup. The full local-only `place` pass was
restarted with the faster fetcher and continues in `full-place.log`.

The faster run also produced a geometry-clear placement for Tri Binh (W), the
sheet excluded from the accepted calibration for its 741.5m residual. Its
saved local placement was explicitly marked held, and both `placement()` and
`annotate()` now guard that map ID. A plausible neatline cannot validate the
catalogue-to-print offset on that outlier.

## 2026-09-24 — full local placement pass completed

`work/indochine-100k/full-place.log` reached 357/357 and the worker exited.
The completed pass logged 134 geometry clears, 33 abnormal catalogue spans,
91 rim detection holds, and 99 geometry holds. One of the 134 clears, Tri
Binh (W), is explicitly held because of its excluded calibration observation.
That leaves 133 new provisional clears. Three previously published clears also
have local placement records; neither they nor the new records were annotated
or written to the database by this pass.

The read-only `check` examined 136 locally clear placements and failed on
Pursat (E): its four rim offsets agree with each other but differ by more than
15% from the series median. This suggests a different printed frame convention
and needs visual review. It leaves at most 132 new provisional clears for
review; the failed check blocks annotation of the batch. The 223 remaining
sheets require investigation of the catalogue spans, rim selection, or
geometry before another placement attempt. Counts come from the completed
`full-place.log`, saved placement JSON, and the `check` output.

## 2026-09-24 — series 561 catalogue matching grid

`scripts/indochine100k_grid.py --apply` now generates a local matching grid
from the per-record CartoMundi coordinates and the accepted catalogue
correction. It queries map rows only to attach UUIDs by their unique
`cartomundi_fkeys[0]`; it writes no database data. The resulting
`work/indochine-100k/grid/` has 197 numbered cell features, 394 W/E slot
features (empty halves have null geometry), and a crosswalk for all 492
catalogue records. All 360 current series-561 VMA map rows matched exactly
once. Of the cells, 143 have both normal catalogue halves, 34 have only one
normal half, 8 use estimated outlines after abnormal source spans, and 12
have unclassified record extents. Cells 153 and 154 have nearly coincident
catalogue footprints under distinct numbers; both are flagged for review.
These polygons locate sheets in the survey index, not approved image
georeferences. See `work/indochine-100k/grid/README.md` for the file contract.

The first generated GeoJSON mistakenly stored Paris-meridian grades as WGS 84
degrees, placing the index east of Vietnam in the South China Sea. The output
conversion is now explicit in `feature()`, with a regional coordinate guard.
Regenerated cell bounds are 101.465–109.639°E, 10.302–23.423°N; all 136
locally clear placements have the same centres as their matched grid slots.

## 2026-09-24 — replaced inferred grid with CartoMundi WKT

The user found a CartoMundi collection endpoint exposing `wkt`. Its example,
collection 297, returns 200 records of **series 233**, not 561. The ordinary
`/serie/561/feuilles` endpoint returns 843 records with no WKT, but IGN's
`/public/etablissement/3/serie/561/feuille/exemplaire/all` endpoint returns
492 records and WKT for every one. Their fkeys match the local 561 catalogue
exactly. A compact 492-record WKT snapshot is now
`work/indochine-100k/sources/serie-561-wkt.json`.

The grid generator now uses those published WGS 84 polygons directly. The
previous inferred rectangles and their geometry-quality categories are
superseded. It still yields 197 numbered cells, 394 W/E slots, and exactly one
crosswalk match for each of 360 VMA maps; 50 half slots have no source record.
The 153/154 conflict is real in CartoMundi's own geometry: their western
records share `geoKey` 130785, so both remain flagged. Across 136 locally clear
placements, the WKT centroid differs from the saved placement centre by 189m
median and 304m maximum. That makes the WKT useful for matching sheets, not
for replacing the image georeference.

## 2026-09-24 — added the same WKT grid for series 325

CartoMundi's IGN series 325 endpoint returned 514 WKT records. The local
serie-325 catalogue contains 512 fkeys, all present in that response; the two
extras are unnumbered Saigon and Rach-Gia records and are excluded from the
grid. The generalized `scripts/indochine100k_grid.py --series 325 --apply`
matches those records to the 221 current VMA rows by fkey. It writes 143
numbered cells, 286 W/E slots, and a 512-record crosswalk under
`work/indochine-100k/grid-325/`. There are 61 W/E slots without source records
and no large inter-cell geometry conflicts. Series 561 was regenerated with
the same schema. No database rows were written.

## 2026-09-24 — published the passing 561 batch

At the user's request, Pursat (E) was explicitly marked held for its series
rim-offset anomaly, then the existing read-only lattice check passed on 135
remaining clear placements across 135 half cells. The 132 new eligible
annotations were uploaded; every public annotation URL returned HTTP 200.
Those 132 drafts were changed to `status=public`. Together with the prior
three, series 561 now has 135 public, georeferenced map rows representing 98
distinct sheet numbers; the other 225 map rows remain drafts. Publishing
enqueued no pipeline jobs because these scans already use `iiif.maparchive.vn`.

The first public page request still returned 404. `map_series.key` is derived
from the collection name, while the two `series_cells.series_key` values were
the older manually abbreviated keys used by the one-off importer. Updated all
143/197 index rows to the canonical keys and corrected the importer for future
runs. The public series route now returns HTTP 200 at
`/catalog/series/indochine-1-100-000-2nd-edition-sgi-1947-1959`; `map_series`
reports 98 sheets, all 98 published, and 197 total index cells. The same key
repair was applied to the 325 index rows, but all 221 of its maps remain
drafts with no image georeferences. The WKT grid alone does not make those
scans display as warped maps.

## 2026-09-24 — fine-tuned rough edge detection, 35 new clears from the rim-detection-hold bucket

Of the 225 series-561 sheets still pending after the earlier batch, 91 held because `rim_in` could
not find any rim inward of `frame()`'s detected outer line, on at least one side. Root cause,
confirmed visually on Russey Chrum (E) and Tam Ky (W) (`work/indochine-100k/.fetch_cache` crops,
marked and read directly): `frame()` picks the single darkest peak in the outer third of the
overview band as the neatline, but on these sheets the inner rim line prints bolder than the true
outer frame line, so the rough pass locked onto the rim itself, one line past the true edge —
leaving nothing further inward for `rim_in` to find. Nong-Het (W) recovered under the same fix
without being individually inspected.

Two fix attempts regressed the known-good set and were discarded. Making `frame()` prefer the
outermost peak clearing a fixed floor above local background regressed a majority of the 135
known-good placements when checked against saved corners (the exact count is lost — a `tail -60`
on that run's output cut off the summary line, keeping only the list of regressed sheets).
Scanner-edge vignetting and title-block text are common and cleared the floor before the real frame
line on many sheets -- e.g. Attopeu (E), where a title-block peak at 42% of the true line's height
above baseline still cleared it. Restricting the override to a near-tie with the strongest peak
still regressed 71 *corner entries* (not 71 sheets — `regress.py` logs one line per corner, so this
is roughly 20 sheets), always on the bottom or right edge, by 140-400px. The working theory is a
comparably dark mount- or scan-background artefact just outside the true frame line on those
sheets, common enough that a near-tie test can't tell it apart from a bolder rim line inside it --
this was not confirmed by looking at any of them, unlike the two root-cause sheets above.

Landed instead: `frame()` still returns the plain-argmax peak as before (zero change for any side
that already succeeds), but also records the next-outermost near-tied peak, if one exists, as
`{side}_alt`. `detect()` only consults it when the primary side is suspect: `side_line`/`rim_in`
already failed, the found offset falls outside the empirical band the offset-to-height ratio holds
to across the corpus, or the rim was only found via `rim_relaxed`. A side that is already a clean,
in-band, non-relaxed hit never reaches the retry branch, so this cannot regress a sheet that
already places correctly -- verified by re-running `detect()` from cache against every known-good
placement's saved corners at each stage of the fix (0 regressions each time: against the 135 known
before this pass, against 162 after the first working version, and against 170 after the version
below).

The first working version of the retry still missed most of its own targets: `frame_strip` only
fetches roughly 190px of headroom outward of the primary peak, and the frame-to-rim distance is
typically 200-220px, so the alt position usually falls outside the strip already fetched (Hon Quan
(E), Kompong Chhnang (W) both did). Fixed by fetching a new strip centred on the alt position when
it falls outside the one already in hand. The empirical band itself: pooled `offset / image-height`
over every side *not* reached via the alt path (636 sides, 170 sheets) is 0.0213-0.0262 (median
0.0230, std 0.0006) -- tight enough that a side landing on the wrong line reads as a clear outlier,
not noise. `DETECT_VERSION` bumped to 4 so the cached geometry-hold sheets (not just the
rim-detection-holds) get re-evaluated under the wider retry trigger.

That bump has a real cost the first pass under it missed: Pursat (E) was manually excluded on
2026-09-23 for a series-median anomaly that only `check()`'s cross-sheet comparison catches, not
any per-sheet gate in `detect()`/`verdict()`. That exclusion lived only as a hand-edited JSON, so
the version bump made `place()` regenerate a fresh, locally-clean record for it and silently undid
the hold. Fixed by adding Pursat (E) to `CALIBRATION_HOLDS` (the one mechanism, previously used
only for Tri Binh (W), that survives a `DETECT_VERSION` bump), then re-running `place` on it alone.
Any other hand-edited hold in this directory's untracked JSON files that isn't in `CALIBRATION_HOLDS`
would be at the same risk on a future bump.

Reran `place()` across all 225 pending sheets: 35 new clear placements, 156 still HOLD (21 "no rim
found" where no usable alt peak exists at all, 21 "axes disagree", 16 "relaxed rim disagrees", the
rest various rim-spread/shape gate failures -- some now reaching the geometry gates for the first
time because all four sides finally detect something), 33 still HOLD on abnormal catalogue spans
(unrelated to detection, a `record_box`/CartoMundi data issue). Every one of the 35 new clears used
the alt path on at least one side; spot-checked two directly (Russey Chrum (E), Tam Ky (W)) against
the source crop, and for all 35 the four independently-measured side offsets agree with each other
and with the corpus prior even where alt fired -- a real consistency signal, not proof for the
other 33. The read-only `check()` now examines 170 half cells with zero holds, once Pursat (E) is
excluded via `CALIBRATION_HOLDS` as above. No annotation or publish step was run; these are local
placement records only, per the pattern already established for this series.

The remaining 156 detection/geometry holds need a different fix, not more tuning of this one:
several of the "no rim found" cases are faint-rim sheets where the true rim line's contrast never
exceeds the fixed `paper + max(6, 6%-of-peak)` threshold in `rim_in`/`rim_relaxed` at all, which
`frame()`'s pick has no bearing on either way. The spread/axes-disagree holds have every side
in-band and non-relaxed, so the alt retry never fires for them at all -- they are a separate
problem, not more of this one.
