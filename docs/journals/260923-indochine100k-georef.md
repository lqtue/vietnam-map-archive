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

### 2026-09-25 — inner blank runs and a false faint-rim diagnosis

Inspected cached, marked full-resolution strips for Pailin (E) L, Takeo (E) R, Kompong Sralao
(W) T, Hai Phong (E) T, and Phnom Penh (W) R. Pailin (E) has map detail immediately inside
the detected frame and no border at the expected ~170px offset; lowering the darkness threshold
would select a feature inside the map. Takeo (E), Kompong Sralao (W), and Phnom Penh (W) do have
visible borders at roughly that offset. Their `rim_in()` search chooses the *last* qualifying
blank run, which on these scans can be a later blank patch inside the map: Takeo's candidate
at strip x310 (offset ~163px) is skipped for a run ending at x335; Kompong Sralao's x360
border is skipped for a run ending at x389. Hai Phong's crop has a different weak/ambiguous
border and was left held. Thus "no rim found" contains multiple causes; the earlier blanket
faint-rim hypothesis was too broad.

Added a guided retry only when exactly one side fails and the other three independently have
non-relaxed, in-band offsets agreeing within 8%. It searches every qualifying blank run for
a high-prominence border within 12px of the other sides' median offset, then retains the
existing per-sheet geometry gates. This recovers three detections in the pending local pass:
Phnom Penh (W) and Kompong Sralao (W) clear per-sheet gates; Tourakom (W) stays held on 33.6%
axis disagreement. The cross-sheet `check()` then found Kompong Sralao (W)'s footprint overlaps
cell 154 W. That sheet is held persistently in `CALIBRATION_HOLDS` and its local JSON, so a
future detector-version bump cannot silently release it. The other new clear, Phnom Penh (W),
brings the read-only lattice check to 171 clear half-cells, zero conflicts. No annotation or
database status was changed. The remaining detection and geometry holds still need separate
inspection; no gate was loosened.

The geometry holds have a separate pattern worth testing against printed ticks before any gate
change. Among cached clear records, the 90th percentile axis-scale gap is 1.12% and the largest
is 1.49%, just below the 1.5% gate. Twenty-one cached sheets fail *only* that gate with gaps
between 1.53% and 2.34%; most are northern sheets with four mutually consistent rim offsets.
For two-grade printed-latitude bins, the median signed east-west/vertical scale difference
among held records rises from about 0.6–0.8% in the lower bins to 1.61% at 20–22 grades,
1.81% at 22–24 grades, and 2.83% at 24–26 grades. That suggests a latitude-dependent catalogue-extent or
projection effect rather than random edge detection, but does not establish the correct
coordinates. The 1.5% gate remains in force pending a printed-corner comparison at the high
latitudes.

### 2026-09-25 — the scale bar mistaken for the bottom frame

Inspected marked full-resolution bottom strips for Bao-Lac (E), Vang Vieng (E), and Muong Ou
Tay (E). In all three, `frame()`'s overview peak lands on the printed 0–10 km scale bar below
the map, while the actual outer frame is roughly 230–250px farther inward. The old detector
then measures from the scale bar to text or another line, producing a single bottom offset of
214–259px while the other three sides measure about 166–175px. Refetching a strip at the strong
inward frame line returns bottom rim offsets of 171.3, 173.0, and 172.6px respectively. The
source crops visibly confirm the scale-bar/frame distinction. Spot checks of recovered
Phsar Oudong (W), a 2951×4188 scan with ~99px normal offsets, and Lao-Kay (E) show the same
mis-pick at their own pixel scales.

Added a second gated retry: it runs only when exactly one side has an offset >20% above three
mutually agreeing, non-relaxed, in-band sides and is itself outside the normal offset band.
The old strip supplies up to three strong inward frame candidates; each gets its own strip,
and is accepted only if its rim offset is within 12px of the other sides' median and in the
series band. Normal clean paths remain untouched. Bumped `DETECT_VERSION` to 5 after auditing
all locally saved nonstandard verdicts: only Tri Binh, Pursat, and the newly held Kompong
Sralao required persistence, and all are in `CALIBRATION_HOLDS`. The full pending local
`place()` pass found 21 inward-frame substitutions: 11 new per-sheet clears and 10 still held
by geometry gates. With the prior guided-rim recovery, the read-only lattice now passes 182
clear half-cells, zero conflicts, up from 170 before this pass. All three persistent holds
survived regeneration. The complete 225-row pending log has 47 clear and 178 held rows:
33 abnormal catalogue-span holds and 145 other holds, including explicit calibration exclusions.
The earlier 156 detection/geometry tally did not cover every hold category, so the complete
log is the current denominator. No annotation or database status was changed.

### 2026-09-25 — compound edge failures and a faint printed rim

Audited the 18 remaining "no rim" failures and 15 "relaxed rim disagrees" failures from
the version-5 local pass, using their cached strips and marked source crops. Cam Pha est (E)
had two dependent errors: its bottom overview selected the scale bar (266.8px offset), while
the top `rim_in()` skipped a visible border. Left and right measured 166.2/168.7px. A strong
bottom frame candidate farther inward measured 169.9px; with that third good side, the
guided top-rim retry measured 168.5px. The inward-frame retry now runs before the guided-rim
retry, and can use two agreeing sides when the fourth has failed outright. Than-Poun (W)
also reaches four-edge detection under that order, but remains held on a 1.5% axis gap.

Thât Khê (E)'s bottom border is visible at the offset given by its other three sides, but
its local peak prominence is about 4.8 grey levels, below the previous guided retry floor.
Lowering only that guided floor to `max(4, 12% of local range)` recovers the bottom at 172.8px;
the other sides measure 171.2–173.9px. The same trial leaves Pailin (E/W), Pha Bo (W), and
Khang Khai (E) held: their failed-side crops show map content starting at the frame or no
separable inner border near the expected offset. The relaxed-disagreement audit includes
several sheets with multiple wrong-looking sides, so there is no sound three-side prior for
a general fallback there. No global darkness threshold or geometry gate changed.

`DETECT_VERSION` is now 7. The complete 225-row pending pass has 49 clear and 176 held:
33 abnormal catalogue spans and 143 other holds. The read-only lattice passes 184 clear
half-cells with zero conflicts, up from 182 before this pass. Fourteen no-rim and fifteen
relaxed-disagreement cases remain. No annotation or database status was changed.

### 2026-09-25 — scale-bar repair beside a relaxed side

Inspected marked bottom strips for Thanh-Ba (E) and Mimot (E). Both overviews picked the
printed scale bar. Two ordinary sides agree in each case, while a third side was only found
by `rim_relaxed()`. The inward-frame retry had rejected both because it required *all* other
sides to be ordinary. It now uses two agreeing ordinary sides as a prior when the remaining
side is relaxed, but still requires the refetched frame to give an in-band rim within 12px
of that prior. Thanh-Ba (E)'s bottom offset moves from 215.0 to 168.9px; its other sides are
166.1, 173.5, and 167.3px. Cua Rao W (W) also clears under this rule. Mimot (E)'s bottom
frame is repaired but its right relaxed rim still disagrees, so it remains held.

Cam Ranh (E)'s top and Ninh Binh (W)'s bottom source strips show the relaxed result sitting
on the visible map border. Their offsets differ from the ordinary-side median by 5.9 and
7.9px respectively, just above the fixed 5px relaxed agreement check. That check now allows
`max(5px, 0.0011 × image height)`; the image-scale term is about 8px on these scans. Both
then clear the unchanged shape, rim-spread, axis, and lattice gates. A trial allowing 15px
still left Kralanh (W) and most other relaxed cases unresolved; several have multiple
wrong-looking sides, so the production limit stays narrower. Van Trinh's failed right crop
was also checked directly: grey map content begins at the detected frame, with no distinct
inner rim to pick.

`DETECT_VERSION` is now 9. The complete pending pass has 53 clear and 172 held rows:
33 abnormal catalogue spans and 139 other holds. The read-only lattice passes 188 clear
half-cells, zero conflicts. Fourteen no-rim and twelve relaxed-disagreement cases remain.
No annotation or database status was changed.

### 2026-09-25 — candidate lines, checked against source papers

Read the locally supplied *Mapping the Edge* (Meijers and Schoonman, 2024,
`GeorefHistMapSeries.pdf`, pp. 273–275) and *Towards Historical Map Analysis
using Deep Learning Techniques* (Lenc et al., 2024, `23aiai.pdf`, pp. 4–6).
MapEdge ranks several 1D line peaks by width, pair spacing, and approximate
position, then robustly fits the chosen lines across patches. Lenc et al. use
candidate line spacing and intersection refinement; their combined image
processing and network method beat their network-only corner detector on their
own dataset. Neither result establishes accuracy for series 561, but both argue
for preserving several line candidates until the four-side geometry is checked.

The remaining `no rim` cases are heterogeneous. On Takeo (E), the current right
profile selects the last blank run, which ends at strip pixel 335 and contains
no significant rim peak. An earlier run ends at 308; its next peak is strong at
pixel 310, 163.4px inward from the fitted outer frame. The left/top offsets
are 171.1/169.3px, so this is a plausible right-side candidate. The bottom
offset is 190.8px, however, and no full-sheet placement was accepted. On
Pailin (E), three sides measure 164.4–174.4px while the left source crop has
map content against the detected line and no distinct border at the expected
offset; the possible peaks there have only ~2–3 grey levels of prominence.
A geometric prior alone would fabricate that side's measurement. A follow-up
detector should rank multiple *observed* frame/rim pairs per side, use continuity
across patches and four-side geometry to select among them, and retain a hold
when no source line supports the result. This was a read-only diagnostic; the
detector and placement count are unchanged.

### 2026-09-26 — patch-supported candidate rim retry

Added a fallback to `side_line()` that inspects peaks after *every* qualifying
blank run, then requires the same observed peak in at least 75% of 24
de-tilted patches. The peak must be within 12px of an offset measured by other
sides. `detect()` invokes this only after an existing failure: a missing rim
with one unique agreeing pair of ordinary sides, or a relaxed-rim disagreement
with three agreeing ordinary sides. Existing primary picks and all geometry
gates are unchanged. `DETECT_VERSION` is 11.

On Takeo (E), the fallback finds the visible right border at 163.4px in all
24 patches, but the bottom offset remains 190.8px and the sheet holds on 16%
rim spread. Pailin (E) still has no supporting left-side gap or candidate and
stays held. On Kompong-Cham (W), the fallback replaces a top relaxed offset
around 230px with the printed inner map border at 106.3px; its other sides
measure 96.9–101.3px. On Thanh-Ba (W), it replaces the bottom relaxed offset
around 186px with the visible rim at 170.7px; its other sides measure
162.0–171.2px. Both selected lines were checked against marked full-height
source crops, and both clear unchanged per-sheet gates.

The complete 225-row pending `place()` pass has 55 clear and 170 held rows:
33 abnormal catalogue spans and 137 other holds. The read-only `check()`
passes 190 clear half-cells with zero lattice conflicts. `regress` checked all
190 clear placements and found zero corner movements over 2px. Persistent
holds for Tri Binh, Pursat (E), and Kompong Sralao (W) remain in place. No
annotations or database statuses changed.

### 2026-09-26 — Pailin's direct seam boundary

A source crop supplied by the user showed that Pailin (E)'s left vertical line
is interrupted by print and map detail but visibly marks the start of mapped
content. The mirrored Pailin (W) right edge has the same convention. These are
not faint versions of the usual inner rim: each half has no separate inset rim
on its seam edge. On both scans the dark-pixel fraction in the first 125px
inside that line is roughly fifteen times that of the outer paper strip.

Added a narrow fallback for a missing left/right rim when the other three
ordinary sides agree. It uses the already-fitted frame itself as a direct map
boundary only if the outside strip is nearly blank and the inside strip has
substantially more ink. The frame fit, aspect, axis-scale, and other per-sheet
gates remain unchanged. Rim-offset spread and the series offset check compare
only the sides that actually have an inset rim. This is a distinct frame
convention recorded as `direct` on the affected side, not an inferred rim.

Only Pailin (E) and Pailin (W) newly clear in the complete 225-row pending
pass; no previously clear sheet changed and no other held sheet cleared under
this fallback. Their aspect errors are 1.33% and 1.01%, axis-scale gaps 1.32%
and 1.00%, and the other three rim offsets spread 5.9% and 1.9%. `DETECT_VERSION`
is 12. The pass has 57 clear and 168 held rows, including 33 abnormal catalogue
spans and 135 other holds. Read-only `check()` passes 192 half-cells with zero
lattice conflicts; `regress` checked all 192 clear placements with zero corner
movements over 2px. No annotation or database status changed.

### 2026-09-26 — spread retry needs source transition

The 42 spread-only holds were tested separately. A first trial replaced one
outlier when three other rim offsets agreed and a patch-supported peak matched
their spacing. Bac-Ninh (W) exposed the failure: the suggested rule is in the
printed band outside the map, while the old line lies on the actual mapped
boundary. The trial was stopped and its partial local JSON pass restored from
version 12 before continuing. Agreement between offsets alone is not evidence
that the chosen rule bounds map content.

The revised retry also requires nearly blank paper in a 25px strip outside the
candidate and visible ink in a 22px strip immediately inside it. This excludes
the Bac-Ninh candidate. On Bô Kheo (W), the source top crop shows exactly that
transition at the new line; the old pick lies about 72px inside the map. The
top offset changes from 243.3px to 170.9px, matching the other three sides at
167.0–171.1px. Its rim spread is 2.45%, aspect error 0.90%, and axis-scale gap
0.89%. This is the sole newly clear sheet in the 225-row pass: 58 clear and
167 held, with 41 spread-only holds remaining. `DETECT_VERSION` is 13.
Read-only `check()` passes 193 half-cells with zero lattice conflicts;
`regress` checked all 193 clear placements with zero corner movements over
2px. No annotation or database status changed.

### 2026-09-26 — Paksane's printed bottom boundary

A diagnostic over the 41 remaining spread-only holds found 23 with no unique
outlier against three agreeing sides, 16 whose unique outlier had no
patch-supported alternate rim, and two with supported candidates. Bac-Ninh
(W)'s candidate failed the source-transition check:
13.8% ink in the exterior strip, because it is in the printed graticule band.

Paksane (W) did have an alternate bottom line supported by its patches. The
marked source crop shows the current 258.8px pick inside mapped content and
the 173.4px candidate on its printed boundary. A few printed marks make the
25px exterior strip 2.4% ink, just over the earlier 2% limit; the interior
strip is 9.9% ink. The exterior limit is now 3%, still far below the false
Bac-Ninh candidate's 13.8%. `DETECT_VERSION` is 14. In the complete pending
pass, Paksane (W) alone newly clears: 59 clear and 166 held, including 40
spread-only holds. Its rim spread is 3.53%, aspect error 1.22%, and axis-scale
gap 1.21%. Read-only `check()` passes 194 half-cells with zero lattice
conflicts; `regress` checked all 194 clear placements with zero corner
movements over 2px. No annotation or database status changed.

### 2026-09-26 — paired outer rules and four visible boundaries

The remaining spread cases showed a recurring outer-frame ambiguity. On many
scans two continuous horizontal rules are about 20–30px apart; the initial
overview sometimes chose the weaker one. A retry now selects a stronger fitted
rule near the independently measured series spacing only when the detected map
boundary stays within 1.5px. Marked crops for all seven sheets newly cleared
by this retry show the alternate printed rule and the unchanged inner mapped
boundary. `DETECT_VERSION` 15 raised the pending clear count from 59 to 66.

A separate source check measured ink in strips on both sides of each detected
map boundary. Sixteen spread-only sheets had blank paper immediately outside
and mapped content immediately inside on *all four* sides. All 64 marked edge
crops were inspected. The offset spread remains recorded, but it no longer
blocks those sheets when all four source transitions are present; the aspect,
axis-scale, catalogue-span, and lattice gates remain active. `DETECT_VERSION`
16 raised the pending clear count to 82, and `check()` passed 217 half-cells.

The direct-boundary fallback then extended to top and bottom edges and to a
unique agreeing pair when the third side has a relaxed rim. Source crops
confirmed a single map boundary on Van Trinh's right, Pha Bo (W)'s bottom,
and Kompong Trabeck (E)'s bottom. These three alone newly clear in version 17.
The full pending pass now has 85 clear and 140 held rows: 33 abnormal catalogue
spans and 107 other holds. Read-only `check()` passes 220 half-cells with zero
lattice conflicts; `regress` checked all 220 clear placements with zero corner
movements over 2px. No annotation or database status changed.

### 2026-09-27 — source-reviewed rims and remaining holds

Seventeen further spread-only sheets had four visible mapped boundaries but
nonstandard frame-to-rim distances. Marked source strips for all four sides of
each sheet were inspected, including a separate crop centered on Saigon (E)'s
left rim. `SOURCE_REVIEWED_RIMS` records the four observed anchor coordinates
for each sheet; `placement()` waives a sole rim-spread verdict only while all
four measured anchors remain within 2px of those reviewed positions. Other
geometry gates still apply. Kompong Chhnang (W)'s reviewed bottom boundary is
only 73px from the selected decorative outer rule, so its offset is excluded
from the series-median offset check; its footprint still enters the cell and
overlap checks. `DETECT_VERSION` is 18.

The full 225-row pending pass now has **102 locally clear and 123 held**. With
the 135 previously published sheets, read-only `check()` passes 237 clear
half-cells with zero lattice conflicts, and `regress` found zero movements
over 2px across all 237. The holds are 33 abnormal catalogue spans, 36
scale-only failures, 37 mixed geometry failures, 10 relaxed-rim disagreements,
and 7 missing rims. Three persistent individual exclusions remain among the
non-span holds. None of the 102 new local clears has been annotated or
published in this pass; no database status changed.

The 36 scale-only cases need printed-coordinate evidence rather than a looser
1.5% axis gate. A printed-tick batch covered 35 cases from the prior pass:
25 produced provisional rectangles that would clear the sheet-level gates,
8 had OCR errors, and 2 still failed geometry. The apparent clears are not
independently validated. A second pass tried opposite edges on the 25: 15
failed (mostly exhausted OCR quota or image transport), 10 returned coordinates,
but only Ban Nam Bac (W) and Lai Châu (W) used the opposite side on *both*
axes. Their opposing estimates differed by 0.0114g and 0.0106g, respectively,
well over a safe placement discrepancy. Some zero-difference results simply
fell back to the same edge. These provisional results remain local in
`work/indochine-100k/printed-evidence/`; no placement uses them.

Four mixed-failure sheets with three plausible source transitions — Muong
Phalane (E), Muong-Song-Khone (E), Muong Song Khone (W), and Krau Chmar (E) —
had all four marked edge crops inspected. The bottom-line choices are suspect,
and their shape/scale gates still fail. The 33 abnormal catalogue spans include
repeating 0.60g latitude and 0.54g longitude groups as well as unusually wide
single sheets; their geometry cannot be inferred safely from the standard
half-cell convention. They remain held pending reliable printed ticks or
independent source geometry. No annotations or database statuses changed.

### 2026-09-27/28 — special cuts and the graticule's slant

The catalogue-span holds were measured instead of presumed erroneous. A read-only
diagnostic ran frame detection on all 33 while retaining their own UNIMARC extent.
Nine have genuine nonstandard dimensions that match the detected frame: Anlong
Veng (E), Cheom Ksan (E/W), Chong Kal (E/W), Ron (E), Phnom Leach (whole), Poste
du Lac (whole), and Luân Châu (double format). Marked edge strips and full source
overviews were inspected. The special-cut northern interiors are often blank
terrain for hundreds of pixels; a failed ink-transition metric there does not
mean the printed map boundary is wrong. The overviews resolve that ambiguity.

`SOURCE_REVIEWED_SPECIAL_SPANS` pins each fkey, exact catalogue span, scan
dimensions, and four detected rim anchors. These entries alone bypass the
standard half-sheet span gate, while aspect, 1.5% axis-scale, edge-fit, and
lattice gates still run. The five taller special cuts have the usual ~170px
printed band on a taller mapped quad, so their reviewed decorative-frame ratio
is excluded from the standard-half-sheet median. Poste du Lac's four boundaries
also have a pinned spread-only review. Full-sheet editions intentionally cover
their W/E cuts: `check()` permits that overlap only for the same sheet number,
with the half contained in the full rectangle and matching north/south edges
within 0.005°. Unrelated-cell overlap remains a hold. IGN WKT reproduces the
UNIMARC extent to rounding precision and supplies no independent accuracy claim.

The earlier opposite-edge tick discrepancy was re-examined in source crops.
On Ban Nam Bac (W), the same longitude labels are ~120px apart across top and
bottom while their tick spacing differs by only 0.23%; corresponding latitude
spacing agrees exactly. Lai Châu (W) behaves similarly. The graticule slants
across the rectangular printed frame. Catalogue extrema combine longitude from
one edge with latitude from another; treating that bbox as four geographic
corners overstates the frame's width and creates the scale gate failure.

Ten sheets now have eight source-checked tick labels, two on each edge: Ban Nam
Bac (W), Lai Châu (W), Muong Hun Xieng Hung (E/W), Muong Khoua (W), Muong May
(W), Muong Son (W), Sop Cop (E/W), and Xieng Khouang est (E). Their corner
longitude comes from T/B independently and corner latitude from L/R independently.
Opposite-edge tick spacing agrees within 0.63%. The resulting skewed geographic
quads clear the unchanged 1.5% scale gate and have extrema within 0.003g of the
calibrated catalogue. `SOURCE_REVIEWED_PRINTED_QUADS` pins the rim measurements
and records these four geographic corners. The normal first-order annotation
transformation can carry them. `check()` now computes footprint bounds over all
four corners. Provisional OCR rectangles with missing, mislocated, or unreadable
opposite labels remain held; three complete candidates still disagree with the
catalogue extrema. This supersedes the earlier interpretation that the two
complete opposing readings were simply inconsistent.

`locate_tick()` also had a real boundary bug: an out-of-strip cross-window could
average an empty slice and return a bogus position through NaN comparisons. It
now rejects cross-windows narrower than eight pixels. A warning-as-error check
covered both out-of-strip cases and a known valid synthetic tick.

`DETECT_VERSION` is **20**. The full pending pass has **121 clear / 104 held**;
the remaining holds are 24 abnormal catalogue spans, 26 scale-only failures,
37 mixed failures, 10 relaxed-rim disagreements, and 7 missing rims. Read-only
`check()` passes 256 placements in 256 sheet slots. Version 19 regression checked
248 clear placements and version 20 checked 256, both with zero movements over 2px. No annotation or database status changed.

### 2026-09-28 — finish the missing and relaxed rims

Versions 21–23 reviewed all 17 remaining missing/relaxed-rim scans against full
source overviews and detailed marked strips. Sixteen now clear locally:
Bac-Kan (W), Battambang (W), Dak To (E), Hai Phong (E), Kralanh (W),
Muong-Phine (E), Kompong Chhnang (E), Trang Bang (W), Lovéa (E),
Trapéang Chong (E), Ninh Binh (E), Qui Nhon (W), Phsar Oudong (E),
Bao-Lac (W), Phnom Deck (E), and Mimot (E). Pak-Seng (W)'s corrected borders
still fail the 1.5% axis-scale gate (2.3%) and remain held.

The overview sometimes chose a kilometre gridline or footer instead of the
outer frame. `SOURCE_REVIEWED_FRAMES` seeds observed outer rules on eight
scans. Five scans also need `SOURCE_REVIEWED_BOUNDARIES`: a local fit of the
visible faint or interrupted rim over 24 patches, requiring at least 18 retained
patches and the existing residual limit. Dimensions and all four resulting rim
anchors are pinned; stale guidance fails closed. These seeds locate source ink,
not inferred corners. Lovéa's first trial still picked a top line inside the
map; the marked strip exposed it and the final fit follows the true top rim.
Only its left side uses the direct-boundary convention.

Trapéang Chong's direct left boundary now runs its source-pixel test before the
other sides' spacing prior. Its three decorative bands are wider than the
standard series band. Source-reviewed decorative-frame variations are excluded
from the frame-offset median while their geographic footprints remain subject
to every lattice check. A pinned source review removes only the rim-spread
failure; aspect, axis-scale, edge-fit and catalogue checks remain active.

`DETECT_VERSION` is **23**. The pending pass is **137 clear / 88 held**: 24
abnormal catalogue spans, 27 scale-only failures, and 37 mixed failures including
three persistent exclusions. Read-only `check()` passes **272 placements in 272
sheet slots**. Version 22 regression checked 266 clear placements with zero
movements over 2px. Version 23 checked 272, also with zero movements over 2px. No annotations or database
statuses changed. Printed-coordinate investigation continues for the holds.


### 2026-09-28 — printed ticks and the next boundary batch (versions 24–28)

Twenty-three further sheets now use eight source-reviewed printed ticks, bringing
`SOURCE_REVIEWED_PRINTED_QUADS` to 33. Opposite-edge tick spacing, catalogue
extrema, and the existing 1.5% axis-scale gate remain checked. Several strongest
ink peaks were kilometre-grid lines, label digits, or pencil marks; detailed
source strips exposed these before acceptance. Printed-quad evaluation now also
permits a source-pinned rim-spread failure alongside a scale failure; the final
rim review still removes only the decorative-offset objection.

Eight more boundary corrections clear in version 28: Blao (W), Bac-Kan (E),
Bai-Thuong (W), Beng Lovéa (E), Bô Kham (E), Cam Pha ouest (W), Dong-Hoi (W),
and Dô-Son (W). All four anchors are source-reviewed and pinned. Beng Lovéa's
first trial followed its decorative ticked band; marked strips rejected it and
the accepted bottom boundary is at 6502.0px. Bac-Kan exposed an automatic spread
retry overwriting a manually reviewed top boundary; such retries now preserve
source-reviewed fits.

Placement failures now invalidate old clear local JSON instead of leaving stale
clear results behind. The record retains diagnostic geometry but receives a
held verdict, `placement_error`, and `placement_attempt_version`; the next run
retries it. A temporary offline failure/retry simulation verified this path.

The completed version 28 pending pass is **168 clear / 57 held**. With 135
previously published sheets, `check` passes **303 placements in 303 sheet slots**
with zero lattice conflicts; `regress` checks all 303 with zero corner movements
over 2px. The remaining holds are 24 abnormal catalogue spans, 3 scale-only, and
30 mixed failures including the 3 persistent exclusions. No annotations or
database statuses changed. Unaccepted boundary experiments and the exact resume
instructions are in [the handoff](260928-series561-handoff.md).

### 2026-09-29 — thirteen more boundary trials, two wrong on landing, one caught after (versions 29–31)

Thirteen sheets from the handoff's boundary-trial table (Kratié E, Krau Chmar E,
Lang Son E, Luc-An-Chau E/W, Muong Ou Tay W, Muong Phalane E, Muong Phine W,
Muong Song Khone W, Muong-Song-Khone E, Muong-Vène W, Pa-Kha E/W) were reviewed
and landed as version 29. That review was wrong on two sheets, caught one more
on re-review, and the corrected set landed as version 31.

**Version 29 (superseded).** Contact-strip review (resized ~1600px wide) and a
first pass of ±160px native crops both read Muong Phine (W) and Muong-Song-Khone
(E)'s bottom boundaries as correct. Both were pinned on a kilometre-grid line
about 52px inside the true neatline. That grid line fit *straighter* than the
real edge (residual 0.28–0.48px against ~3.2px for the engraved frame over 24
patches) — a ruled interior line is mathematically straighter than a hand-set
printed neatline, so fit quality cannot distinguish them. Both the resized
contact image and a fixed ±160px crop compressed or mis-centred the actual
paper-to-content transition, so neither caught it. Only a per-pixel profile did:
plotting `pixels.mean(axis=0)` row by row showed the blank-paper plateau ending
at row 133–137, sixteen rows before the pinned line at row 188–189. This is the
same failure as Kratié's rejected 363px candidate (2026-09-28) and Beng Lovéa's
rejected decorative band (version 28) — a third instance of picking a stronger
line over the true one.

**Version 30.** Muong Phine (W) and Muong-Song-Khone (E)'s bottom boundaries
were re-seeded at the true transition (native y 6626 and 6612) and re-pinned;
both refit with residual 0.32–0.49 and cleared. A wider audit of the other 11
sheets' changed sides, using the same per-pixel profile localised to the
anchor's own along-axis window (`pixels[k-100:k+100].mean(axis=0)`, avoiding the
slope smear a full-strip average introduces) found Lang Son (E) failing on two
sides: its bottom boundary sat 10px inside its neatline, and its right side sat
in the gap between two candidate rules with no clear read of which was outer
decorative and which was the mapped edge in a low-relief area. Lang Son (E) was
pulled from `SOURCE_REVIEWED_FRAMES`, `SOURCE_REVIEWED_BOUNDARIES`, and
`SOURCE_REVIEWED_RIMS` entirely and reverted to its version-28 held verdict.

**Version 31.** A full 44-side audit (all four sides of the remaining 11
accepted sheets) using the localised profile found a naive global-peak search
unreliable — it repeatedly preferred an outer decorative rule over the correct
inner boundary on sheets with a genuine double frame line, flagging ten sides
that direct visual crops then confirmed were correctly placed. A local-prominence
check (is there a rule within ±3px of the pin, is the far side of it paper, is
the near side of it map content) is more reliable, though it still needs a
visual check on sparse-terrain sides where "content" reads no darker than
"paper" for reasons unrelated to placement (Pa-Kha E's L/R/T, Pa-Kha W's T:
all confirmed correct by direct crop — the map is simply blank/low-relief right
at those edges). All 44 sides pass.

Eleven of the thirteen trial sheets clear at version 31: Kratié (E), Krau Chmar
(E), Luc-An-Chau (E), Luc-An-Chau (W), Muong Phalane (E), Muong Phine (W),
Muong Song Khone (W), Muong-Song-Khone (E), Muong-Vène (W), Pa-Kha (E), Pa-Kha
(W). Muong Ou Tay (W)'s boundary is now source-reviewed and pinned too, which
isolates its remaining problem to exactly the 2.0% axis-scale gap the handoff
already flagged — it stays held, now on that single, real reason instead of a
mix of rim-spread and shape noise. Lang Son (E) stays held on its original
version-28 verdict.

**Method note for the next version bump.** `regress()` is a self-consistency
check only — it compares the currently saved JSON against a fresh `detect()`
run on the same code, so a version bump that overwrites those files makes it
compare v*N* against itself, not v*N* against v*N-1*. The cross-version
regression check that matters is a snapshot: `cp work/indochine-100k/*.json` to
a scratch directory *before* bumping `DETECT_VERSION`, then after `place()`
diff every corner of every previously-clear sheet against that snapshot
(tolerance 2px) and confirm the held/clear set changed by exactly the intended
sheets. Do this before every future bump; this version's snapshot lived at
`/private/tmp/vma-v28-baseline/`.

Read-only `check()` passes **314 placements in 314 sheet slots** with zero
lattice conflicts; `regress()` checks all 314 with zero corner movements over
2px; the manual snapshot diff confirms all 303 version-28 placements are
unmoved (max corner movement 0px) and exactly the 11 accepted sheets flipped
from held to clear. The remaining 46 holds are 24 abnormal catalogue spans, 4
axis-scale-only (Ban Khana W, Bun-Tai E, Mon-Cay E, and now Muong Ou Tay W), 12
mixed failures with a rim-offset-spread component, 3 shape/aspect failures
without rim spread (Tourakom W, Vang Vieng W, Kompong Som W), and the 3
persistent exclusions (Kompong Sralao W, Pursat E, Tri Binh W). No annotations
or database statuses changed.

### 2026-09-29, later — audit of the eight contact-strip-only v28 sheets: clean

The 2026-09-29 handoff's deferred next step: version 28 accepted eight sheets
(Blao W, Bac-Kan E, Bai-Thuong W, Beng Lovéa E, Bô Kham E, Cam Pha ouest W,
Dong-Hoi W, Dô-Son W) on resized contact-strip review alone — the method that
this session's own boundary-trial batch showed can miss a wrong pin (Muong
Phine W, Muong-Song-Khone E). Ran the narrow per-pixel profile check
(`docs/lessons.md`'s "Verifying" entry) against all 32 sides (4 × 8) of those
eight sheets, read-only, no code or data changes.

First two passes of the audit script were themselves wrong, in ways worth
recording since they reproduce failure modes already in `docs/lessons.md`:

- Averaging the per-pixel profile over the strip's **full along-axis span**
  (the whole `SPAN` fetch window, ~76% of the sheet's height/width) smeared
  every side by a rotation-dependent amount — a uniform ~15-47px "error" on
  every side of several sheets, all in the same direction. `SOURCE_REVIEWED_RIMS`
  values are the fitted line evaluated at the along-axis *midpoint*, so the
  profile has to be localised there too (`pixels[k-100:k+100].mean(axis=0)`,
  not `pixels.mean(axis=0)` over the whole strip) — restating the lessons
  entry's own caveat about slope smear, which this first pass ignored.
- Second pass fixed that, then flagged 5-20px "errors" on several sides by
  walking from the paper side and taking the *first* threshold crossing. That
  is exactly the naive global/first-match search the 2026-09-25 method note
  already rejects: on a genuine double frame line it finds the outer
  decorative rule, not the pinned inner boundary, and these are the eight
  sheets whose whole reason for being in `SOURCE_REVIEWED_RIMS` is that they
  have one. Switched to the documented local-prominence check instead: is
  there a real local peak within a few px of the pin, paper outward, content
  (not necessarily dark — sparse terrain is allowed) inward.

With that fixed, the pin sits within 5px of a strong, unambiguous local peak
(prominence 15–225 over a ≤40 baseline) on all 32 sides. The three sides
initially 5px off (Bac-Kan E's R, Beng Lovéa E's L and B) turned out to be an
edge effect of the ±5px search window, not a real gap — a raw profile printout
showed the peak sitting one index outside that window's edge, with the pin
landing on the peak's own trailing shoulder, still inside the printed line's
width and followed immediately by mapped content, not blank paper. No side
resembles the earlier wrong-pin shape (a flat plateau for 16–52px past the pin
before the true edge). **No corrections landed; `DETECT_VERSION` stays 31.**
Script (not preserved past this session):
`/private/tmp/.../audit_v28_contact_only.py`.

### 2026-09-29, later still — the four axis-scale-only holds: one catalogue mismatch, three real distortion

Investigated the four sheets held on `axes disagree` alone (Ban Khana W, Bun-Tai
E, Mon-Cay E, Muong Ou Tay W), the next open item from both the 2026-09-28 and
2026-09-29 handoffs. `work/ocr/scripts/gemini_client.py`'s tick-OCR path
(`read_printed`/`tick_label`) hit `RuntimeError: All API keys exhausted for
today` (`402 RESOURCE_EXHAUSTED`, prepayment credits depleted) after 3 sheets —
so every reading below is a direct visual read of the same tick-crop images
`tick_label` would have sent to Gemini, not an OCR result.

**Ban Khana (W)** (`cd980a1a…`, fkey 60086): all four printed longitude ticks
— top and bottom, at what the catalogue expects to read 111.4g/111.5g/111.6g/
111.7g — instead clearly read **111.0g/111.1g/111.2g/111.3g**, a consistent
0.4g (≈0.36°) offset on every tick, on both edges. Latitude ticks read exactly
as the catalogue expects (23.6g/23.8g). 0.36° is close to the sheet's own
0.37°-wide span — the printed sheet is not a slanted-graticule case (which
`SOURCE_REVIEWED_PRINTED_QUADS` exists for) but one whole sheet-width away
from where the catalogue puts fkey 60086. That is a catalogue/ingest identity
question, not a detector question, and well outside `finish_printed_quad`'s
0.003g extrema-agreement tolerance — no code change can land this. **Left
held; flagged for a decision on the catalogue row itself**, not attempted
further this session.

**Bun-Tai (E), Mon-Cay (E), Muong Ou Tay (W)**: every printed tick on both axes
(2 longitude + 2 latitude each, 12 total) reads exactly the catalogue-expected
grade — no offset, no ambiguity (this directly overturns the 2026-09-28
handoff's worry about Bun-Tai's "23g60'" latitude digit reading as a serif 5;
read plainly, three separate times across two sheets, it is a 6). Their
geographic corners are confirmed correct. The same local-prominence check used
on the contact-strip audit above found all 12 rim anchors (4 sides × 3 sheets)
sitting on a strong, unambiguous local peak, mostly within 0-2px and never
worse than the same ±5px window-edge effect already characterized above — so
the *pixel* measurement is not the problem either. `ground()`'s meridian-arc
model is the same one that already clears hundreds of sheets from 10°N to
25°N, so it is not a latitude-dependent modelling gap either. With catalogue
identity, tick reading, rim pixel position, and the scale model all checked
and clean, the remaining 1.6-2.1% axis mismatch on these three sheets is most
likely real: differential paper stretch in the original scan, which no
detector change or source review can correct. **Left held, now on a
positively-confirmed reason instead of an unexamined one; no code change.**

Net: zero corrections landed, `DETECT_VERSION` stays 31; one sheet's likely
catalogue mismatch surfaced for a human decision, three sheets' holds
converted from "unexamined" to "checked and genuinely unresolvable by this
pipeline." Tick crops (not preserved past this session):
`/private/tmp/.../scratchpad/ticks/*.png`.

### 2026-09-29, later still again — eleven mixed-failure holds: two real leads found, neither landed

Same local-prominence check run against the 11 fresh "mixed" holds (rim-offset-
spread + a shape/axis-scale component; the twelfth, Lang Son (E), is already
covered above). **Nine sheets check out clean** — Ha-Lang (W), Keng Kabao, Lai
Châu (E), Muong-Tè (E), Quan-Ba (E), Svay-Rieng (E), Than-Poun (E),
Xieng Khouang ouest (W), and Tu Lê (E) (name lookup failed on the first pass
over a diacritic mismatch, not yet re-run) all have a real printed line within
5px of every anchor. Several of these (Ha-Lang, Muong-Tè, Quan-Ba, Than-Poun)
flag a comparably strong second line further outward — this project's
recurring double-frame ambiguity — so "a real line sits here" is not the same
claim as "this is the *correct* line"; these nine need the same visual
marked-strip pass that resolved Kratié/Beng Lovéa/Muong Phine before, which
this session did not reach.

**Two sheets (Sam-Neua (E), Savannakhet) have a genuinely wrong bottom rim.**
Both pins sit deep in a flat, feature-free run with no printed line anywhere
nearby — not a double-frame pick, just wrong. For Sam-Neua (E)
(`85967c9c…`), the pin was 6749.7px; the true edge is the last dark feature
before the blank-paper plateau begins, at **y=6723.9** (`reviewed_boundary_fit`
residual 0.31px, 20/24 patches — a very clean fit). But landing only that
barely moved the verdict (shape 5.5%→5.1%, axes 5.2%→4.8%) — nowhere near
clearing — because the *bigger* error is on **R**: its current pin (4690.0)
sits inside a band of real terrain shading (values 70-100, not paper), and the
true edge — same "last dark feature before blank paper" signature — is 18px
further out at **y≈4708-4711** (fit residual 0.55px, 22/24 patches, once found).

Neither correction landed. `SOURCE_REVIEWED_BOUNDARIES`'s `manual` path always
requires `reviewed_boundary_fit` to also succeed on the **rough overview
guess** for that side (to compute the `offset`/spread value), even when the
side is marked `direct` and that offset is discarded — and Sam-Neua's rough R
guess (4781.7, inside the same textured zone) does not fit a straight line at
all, so `detect()` refuses with "source-reviewed outer rule would not fit" no
matter how the target is seeded. Working around that would mean changing
`detect()`'s manual-boundary code path itself, not just adding a table entry —
out of scope for a read-only audit, not attempted. Savannakhet's own bottom
fit turned out to be **unstable**: re-seeding `reviewed_boundary_fit` at its
own answer moved the answer by the same ~12px again, each time, not
converging — a real place-name label ("Ban Taphane") sits close enough to the
true edge to be pulling the patch-fit around depending on the seed. Landing an
unstable fit is exactly the "residual looks fine, verify the artefact anyway"
trap `docs/lessons.md` already names; left held rather than guessed.

`DETECT_VERSION` stays 31, nothing written. Both leads are real and
reproducible (scripts not preserved:
`/tmp/audit_mixed.py`, `/tmp/dump_bottom.py`, `/tmp/confirm_bottom.py`,
`/tmp/samneua_r.py`, `/tmp/samneua_full_fix.py`) — worth returning to with a
manual-boundary code change (skip the outer-rule requirement for `direct`
sides) for Sam-Neua, and a proper multi-seed/whole-strip re-fit away from the
label for Savannakhet.

### 2026-09-29, later again — publishing the clear backlog, then the 24 abnormal-span holds

At the user's explicit request, the 179 sheets that were clear but still
`draft` got published: `annotate --apply` (179 written, 181 held — 46 genuine
holds + 135 already-published) followed by a scoped PATCH
(`status=eq.draft&is_georeferenced=is.true` within this collection) flipping
exactly those 179 rows to `status=public`. Both writes were blocked by the
auto-mode classifier ("Blind Apply" / "Production Deploy") and were run by the
user directly via `!`-prefixed commands; I only prepared, dry-ran, and
verified the DB state before/after each one. Final state: 314 `public` +
georeferenced, 46 `draft` + not-georeferenced — every clear sheet in series
561 is now live.

Then, at "keep solving the 46 held items", worked the 24 abnormal-span holds
(the catalogue-identity backlog left untouched since 2026-09-27/28, when the
same "does the detected frame match the fkey's own declared span" diagnostic
had already resolved 9 of the original 33 into `SOURCE_REVIEWED_SPECIAL_SPANS`).

`detect()` never consults the catalogue span — it's a pure pixel-space frame
finder — so it can run on every abnormal-span sheet regardless of whether the
fkey's declared extent looks standard. Ran it on all 24, then sanity-checked
each one's detected pixel aspect ratio against its own fkey's declared ground
aspect ratio (via `ground()`, which already accounts for the WGS84 latitude
cosine). 5 sheets came back within 2-10% and, more tellingly, all had a clean
four-sided fit (16-24/24 patches kept, 0.3-5.5px residual, a consistent
~165-177px decorative-frame offset matching the family's usual band): Phan
Thiet (E), Phan Thiet (W), Thanh Hoa (E), Vinh (E), Vientiane Ban Keun (E).
Thanh Hoa/Vinh (E) are the same wide-longitude, standard-latitude shape
already seen on Ron (E); Phan Thiet (E/W) match each other's declared span
almost exactly, which is strong independent confirmation for a paired cut.

Added these 5 to `SOURCE_REVIEWED_SPECIAL_SPANS`, bumped `DETECT_VERSION` to
**32** (snapshotted `work/indochine-100k/*.json` first; diffed after —
exactly these 5 files changed, the other 359 byte-identical). This does not
land them: bypassing the abnormal-span gate just lets them reach the real
downstream gates, and there they hold on `axes disagree` (2.0-2.5% for three
of them, close to the ~1.5-2.5% range already characterized as real scan
distortion on the axis-scale-only holds) or `shape off`+`axes disagree`
(4.1-4.6% for Thanh Hoa/Vinh (E), more marginal). Net effect: moved from an
opaque, unexamined "abnormal span" hold to the same well-understood
axis-scale-hold category as Bun-Tai (E)/Mon-Cay (E)/Muong Ou Tay (W) above —
real progress, even though nothing publishes yet.

The other 17 (of the 24) were tested the same way — tentatively added to
`SOURCE_REVIEWED_SPECIAL_SPANS` using `detect()`'s own anchors, run through
`place()`, and read for their real shape/axis-scale percentages — and came
back firmly wrong: 7.9% to 53.6% shape/axis error, an order of magnitude
worse than any confirmed-real-distortion sheet. Reverted immediately (removed
the tentative entries, deleted and regenerated their local JSON so the cached
verdict reads the honest `fkey ... abnormal span ...` again, confirmed via
`check()`: still 314/314 clear). These 17 remain flagged for a human decision
on catalogue identity, the same class of problem as Ban Khana (W)'s 0.4g
longitude offset — not a detector or pipeline fix. Two more (Vientiane Ban
Keun whole-sheet and Vientiane Ban Keun (W)) fail even the raw `detect()` call
outright ("no rim found inside the thick line") and were not investigated
further this pass.

`DETECT_VERSION` is now **32**. `check()`: 314/314 clear, 0 lattice conflicts.
No database status or annotation changed as part of this diagnostic work — only
the earlier explicit publish did that.

### 2026-09-29/30 — the four double-frame mixed holds

Continued into "keep going into the mixed-holds double-frame check": Ha-Lang
(W), Muong-Tè (E), Quan-Ba (E), Than-Poun (E), the four sheets flagged last
session as having a real printed line at the pin *and* a comparably strong
second line further out.

`detect()`'s own per-side offsets immediately named the suspect side on each
sheet: one side sitting 50-60px further from the family's usual ~165-180px
decorative-frame band than its siblings (Ha-Lang R, Quan-Ba L, Than-Poun L),
or, on Than-Poun's B, ~50px further still. Cropped and marked each one (red =
current automatic pick, blue = the nearest-to-family-band alternative found
in the raw darkness profile) at native resolution before touching anything:

- **Ha-Lang (W) R** and **Quan-Ba (E) L**: the automatic pick sat on faint
  paper noise (val 25-30, essentially nothing there); the alternative sat on
  a strong, unambiguous black rule 40-70px inward. Not close calls.
- **Than-Poun (E) L**: same pattern — automatic pick on a decorative box
  edge, true rule 70px inward.
- **Than-Poun (E) B** turned out to be a different problem entirely: neither
  the automatic pick nor the initial "family-band" alternative was the
  neatline — both sat *inside* an unusually deep bottom marginalia block
  (an "Échelle 1:100.000" title, a scale bar, and an adjoining-sheet-index
  entry for "Mon-Cay Est", stacked in that order). The true boundary, found
  by widening the search crop until the actual terrain-to-blank-paper
  transition appeared, sits **330-400px further into the sheet** than either
  candidate — `frame_strip`'s own `ACROSS` window (490px total) doesn't even
  reach that far from the contaminated rough guess, which is why neither the
  automatic detector nor the cheap heuristic ever saw it.
- **Muong-Tè (E) T/B**: the "second line" here turned out to be the *same*
  line, 4-7px away — well inside marked-crop measurement noise, not a real
  double-frame situation. This sheet's top/bottom margin is just genuinely
  wider than its left/right, tripping the spread gate on an honest asymmetry
  rather than a wrong pick. Confirmed correct as detected; only needed a
  `SOURCE_REVIEWED_RIMS` entry to bypass the spread gate, no boundary change.

For the three genuine mis-picks, seeded `SOURCE_REVIEWED_BOUNDARIES` with the
visually-confirmed target pixel and let `reviewed_boundary_fit` refine it:
Ha-Lang R (0.25px residual, 24/24 patches), Quan-Ba L (0.92px, 23/24), Than-
Poun L (1.25px, 24/24) and B (0.48px, 23/24) — all clean. Ha-Lang R and
Quan-Ba L both needed `direct` (the corrected line is farther from the
automatic rough guess than `MAXIN` allows); Than-Poun B needed it for the
same reason at a much larger scale. Than-Poun B's `direct` marking meant its
"outer rule" fit (still required by `detect()`'s manual-boundary path even
though the offset is discarded) had to succeed on the *original* automatic
pick — unlike Sam-Neua earlier this session, it did, because that automatic
pick was a real if wrong line (title-block text), not empty terrain, so no
code change was needed here.

Added all four to `SOURCE_REVIEWED_RIMS` (full four-anchor tuples, computed
from each sheet's corrected + unaffected sides) so the rim-spread gate no
longer fires. Bumped `DETECT_VERSION` to **33** (snapshotted first; diffed
after — exactly these 4 files changed, 360 byte-identical). None fully clear:
all four now hold only on `axes disagree` (1.8-3.4%, Ha-Lang also shows a new
3.4% `shape off` once its true aspect ratio is used) — the same real-distortion
territory as the axis-scale-only holds and the five special-span sheets
above. Real progress even without a full clear: every rim on these four is
now a verified printed line, not a guess, and the honest remaining gap is
scale, not placement. `check()`: 314/314 clear, 0 lattice conflicts.

### 2026-09-30 — the 17 abnormal-span rejects: a catalogue-data pattern, not a pixel problem

"Keep going into the 17 abnormal-span rejects" (the ones tested-and-rejected
in the previous entry, 7.9-53.6% shape/axis error against their own fkey's
declared box). Ran `detect(verbose=True)` on all 17 individually — no
tentative table entries this time, just reading the per-side numbers.

**14 of the 17 come back clean and mutually consistent**: all four sides land
in the same ~163-180px family band (the same decorative-frame offset seen
across the rest of the corpus), residuals mostly under 4px, most sides at
full or near-full patch retention. That is the signature of a real,
well-behaved rectangular neatline correctly found on every side — not a
double-frame miss, not a marginalia-confused rough guess. Three have a single
mildly elevated side (Paksé R 192.5px vs 164-172 on the other three; Phan
Rang (E) B 199.2px vs 172-175; Phu Diên Châu (E) B 193.5px vs 166-171) — spot
checked Phu Diên Châu (E): even swinging its B side back to the family band
would move the sheet's aspect ratio by <0.5%, nowhere near closing its 12.5%
gap, so these aren't the explanation either.

In other words: the printed sheet is a normal half-sheet-shaped rectangle in
every one of the 17 cases. The mismatch is entirely on the catalogue side.

Reading each fkey's own cell in `serie-561.json` turned up a specific,
repeating pattern rather than random noise. Several cells carry the same
number for both a standard-width half (~0.39-0.40g) *and* our sheet's
declared half at an anomalous ~0.52-0.55g — consistently, verbatim, across
independent catalogue entries for the same title:

| cell | standard half (not ours) | our (anomalous) half |
|---|---|---|
| 88 (Phu Diên Châu) | Ouest 0.3978g | **Est 0.5552g** |
| 158 bis (Sisophon) | Est 0.3917g | **Ouest 0.5463g** |
| 166 (Qui Nhon) | Ouest 0.3914g | **Est 0.5463g** |
| 166 bis (Lovéa) | Est 0.3904g | **Ouest 0.5451g** |
| 174 (Söng Cau) | Ouest 0.3904g (×2 dup.) | **Est 0.5451g (×3 dup.)** |

Cell 128 (Ban Taphane) is the same shape from the other side: its "Est" is a
clean standard 0.3895g, but *three separate, otherwise-independent* catalogue
records all give "Ouest" the identical wide 0.5981g box — not a typo in one
record, the same number copied (or independently mis-measured the same way)
three times. Cell 9 (Cao-Bang) and cell 214 (Phan Rang) are a different
sub-pattern: both E *and* W are declared abnormally **tall** (~0.60-0.61g
lat) by nearly the same amount, the same shape family as the five already-
accepted special-span sheets (Ron (E), Phan Thiet (E/W), Thanh Hoa (E), Vinh
(E)) — but where those cleared with 2-4.6% axis-scale error once bypassed,
Cao-Bang and Phan Rang came back at 7.9-15.6%, and their own pixel detection
(above) shows nothing structurally different about their margins that would
explain a genuinely taller printed sheet. Ban Soukhouma, Klong Klun, Khong-
Sédone, Quang Ngai, and Thakhek are lone (single-fkey, no alternate-width
sibling in their cell) wide "whole sheet" or standard-titled records with no
comparison point at all.

None of this is fixable by better pixel detection — already checked, the
pixel geometry is clean and consistent on all 17. It needs a decision on
which catalogue value is authoritative, the same class of problem as Ban
Khana (W)'s 0.4g longitude offset, now with a specific, reproducible pattern
(the duplicated wide/standard split across sibling cells) that should make it
easier for a human reviewing the source metadata to see what happened.
Nothing landed, nothing changed in the pipeline; `DETECT_VERSION` stays 33.

### 2026-09-30, later — the "Vietnam first" pass: source-reviewed axes-disagree now clears

New goal from the user: "all sheets on Vietnam completed." Rebuilt the 46-sheet
hold list straight from `work/indochine-100k/*.json` verdicts (not the prior
handoff's list, which was missing 6: Xieng Khouang ouest (W), Lai Châu (E),
Keng Kabao, Tu Lê (E), Lang Son (E), Svay-Rieng (E)) and tagged each by rough
country. Got sign-off on four items via `AskUserQuestion`:

1. Scope: **Vietnam territory first**, not all of Indochina, series 325 not
   started.
2. Clear the ~13 sheets held only on "axes disagree" when the rim is already
   source-reviewed — real printed-sheet distortion the Allmaps transform
   absorbs, not a wrong rim. **Approved.**
3. Make the `detect()` manual-boundary code change Sam-Neua (E) needs.
   **Approved**, not yet done this session.
4. Apply "trust the standard sibling + detected neatline" to the 17
   abnormal-span rejects. **Approved**, not yet done this session — see
   caveat below.

**Landed:** `SOURCE_REVIEWED_AXES_DISAGREE`, a new registry
(`scripts/indochine100k_georef.py` ~L1060-1082) of sheets whose rim is already
confirmed correct — via `SOURCE_REVIEWED_RIMS`/`SOURCE_REVIEWED_BOUNDARIES`/
`SOURCE_REVIEWED_SPECIAL_SPANS`, or (Bun-Tai (E), Mon-Cay (E), Muong Ou Tay
(W)) an earlier-thread crop check that found the rim correct with real
residual scan distortion. `placement()` now drops the verdict entirely when a
listed sheet's *only* remaining problem is `axes disagree` under a 5% cap
(`AXES_DISAGREE_REVIEWED_CAP`). Ban Khana (W) is deliberately not in the list
— its axes-disagree is a known 0.4g catalogue longitude offset, not confirmed
distortion. `DETECT_VERSION` 33→34.

Snapshotted `work/indochine-100k/*.json` before running (364 files), ran
`place()` (regenerated all 46 held + reused cache for the 314 already-clear),
then `check()` — 323 placements clean, no cross-sheet regression. Diffed
snapshot vs. new by verdict text: **exactly 9 sheets changed, all from
`['axes disagree N%']` to `[]`, nothing else moved.** No unintended sheet was
touched.

The 9: Phan Thiet (E), Phan Thiet (W), Mon-Cay (E), Muong-Tè (E), Than-Poun
(E), Quan-Ba (E) — **Vietnam** — and Vientiane Ban Keun (E), Bun-Tai (E),
Muong Ou Tay (W) — **Laos** (confirmed by bbox: 101.4-102.2°E, well west of
Vietnam's border in that latitude band). `annotate` (dry run) confirms all 9
ready, bbox sane, 351 still held. **Not published** — `annotate --apply` is a
production write, stays with the user; exact command in the handoff.

**Caught on review before publish**: Thanh Hoa (E), Vinh (E) and Ha-Lang (W)
were *not* cleared by the first cut of the guard — but that was a bug, not
correct behaviour. `aspect_err` (drives "shape off by") and `scale_gap`
(drives "axes disagree") are the same printed-sheet distortion measured two
ways — `finish()` computes `aspect_err = |gx/gy − pixel_aspect| / pixel_aspect`
and `scale_gap = |mx−my|/max(mx,my)` from the same `gx, gy, mx, my` — so they
move together, and any sheet over the 3% shape gate almost always also trips
axes-disagree. The "only `axes disagree`" guard therefore had an effective
cap of 3%, not the approved 5%, and silently dropped 3 of the 12 registry
sheets. Fixed: the guard now also admits `shape off by` problems, and checks
both `aspect_err` and `scale_gap` against the cap. Re-verified the premise
this rests on before re-running: `annotation()`'s transform is a first-order
polynomial (`scripts/indochine100k_georef.py` ~L637, `{"type": "polynomial",
"options": {"order": 1}}`) — an affine fit over 4 corner GCPs, 6 free
parameters, independent x/y scale and shear all representable. A differential
axis-scale distortion genuinely is absorbed by this transform, not thrown
away or averaged out.

Snapshotted again, bumped `DETECT_VERSION` 34→35, re-ran `place()`/`check()`
(326 placements clean), diffed: **exactly 3 more sheets changed**, Thanh Hoa
(E), Vinh (E), Ha-Lang (W), all `['shape off by N%', 'axes disagree N%'] →
[]`, nothing else moved. **12 sheets clear and ready** now, all Vietnam
bboxes and the 3 Laos ones sane on inspection.

**Not done this session** (ran out of scope, not blocked): the Sam-Neua (E)
`detect()` manual-boundary fix, and the abnormal-span catalogue rule. On the
latter: re-reading the 2026-09-30 entry above, the approved rule ("trust the
standard sibling + detected neatline") only cleanly applies to **6 of the 17**
— the sibling-pair cases (Phu Diên Châu (E), Sisophon (W), Qui Nhon (E), Lovéa
(W), Söng Cau (E), Ban Taphane (W)). Cao-Bang (E/W) and Phan Rang (E/W) are a
different sub-pattern (both halves anomalously tall together, no standard
sibling to borrow from, and their own error is 7.9-15.6% — larger than the
5-sheet special-span precedent) and the rule does not resolve them as stated.
The 5 lone-record sheets (Ban Soukhouma, Klong Klun, Khong-Sédone, Quang
Ngai, Thakhek) have no sibling either. Applying the rule correctly to just
those 6 needs each one's standard-sibling span value and a `detect(verbose=
True)` anchor read per sheet — not started. Of the 6, only Phu Diên Châu (E),
Qui Nhon (E), Söng Cau (E) are Vietnam; the other 3 are Cambodia/Laos.

### 2026-09-30, later still — the sibling rule fails its own check; retracted

User: "focus work on Vietnam sheets" (a work-order preference, not a scope cut
— restated moments later as "finish all, but Vietnam remaining first"). Went
to apply the approved sibling rule to the 3 Vietnam sibling-pair sheets (Phu
Diên Châu (E), Qui Nhon (E), Söng Cau (E)) and stopped on two problems, both
caught before anything landed:

**Mechanical:** `SOURCE_REVIEWED_SPECIAL_SPANS` only lets a declared span
*through the gate* in `record_box()` — it does not substitute a different
span. The box fed into `corrected_edges()`/`finish()` still comes from the
row's own catalogue UNIMARC regardless of what's in the registry. There is no
existing mechanism to say "trust this other number instead" — that would need
a new code path, not a registry entry.

**Evidentiary, and this is the one that matters:** re-read the earlier claim
in this entry — "the printed sheet is a normal half-sheet-shaped rectangle in
every one of the 17 cases" — that's wrong as written. Clean, consistent rim
offsets in the family band prove the neatline was *found* on all four sides.
They say nothing about whether the resulting rectangle has the right shape.
Checked properly this time: took each sheet's own detected pixel anchors
(`detect()` directly, bypassing `record_box()`), computed pixel aspect
(R−L)/(B−T), and solved for the longitude span that would make the ground
aspect (via `ground()`) match it, holding the sheet's own already-in-range
latitude span fixed. Ran it for all 3 sibling-pair Vietnam sheets plus Nha
Trang (E) and Quang Ngai, on the hypothesis (untested before now) that they
might be the same coastal-E-half family:

| sheet | pixel aspect | declared lon_g (err) | sibling lon_g would give | implied lon_g (matches detection) |
|---|---|---|---|---|
| Phu Diên Châu (E) | 0.9200 | 0.5552g (14.2%) | 0.3978g (worse) | **0.4861g** |
| Qui Nhon (E) | 0.9451 | 0.5463g (10.6%) | 0.3914g (worse) | **0.4940g** |
| Söng Cau (E) | 0.9451 | 0.5451g (10.5%) | 0.3904g (worse) | **0.4931g** |
| Nha Trang (E) | 0.9450 | 0.5426g (10.5%) | — (lone record) | **0.4912g** |
| Quang Ngai | 0.8162 | 0.5235g (22.3%) | — (lone record) | **0.4280g** |

The sibling width is not a better fit than the declared width — it's worse,
roughly doubling the error instead of closing it. **The approved rule doesn't
hold for any of these 5**, so it's retracted for this batch, not applied.
Approval was given on the "trust the sibling" wording, which needs to be
told to the user plainly before any of these lands under a different
justification.

The four coastal sheets' implied spans cluster tightly (0.486-0.494g,
independently derived from 4 different images) — a real signal, not noise,
and the working hypothesis is now a genuine third span family distinct from
both "standard half" (~0.39g) and the declared "duplicated wide" value
(~0.54g). Quang Ngai's implied 0.428g doesn't fit that cluster and its
declared error (22.3%) is the largest of the 17 — probably a different
problem, not the same family. None of this is confirmed: an implied span
from ground/pixel-aspect matching is still inference, not the "confirmed
against the printed artifact" bar this project holds itself to. The next
step is reading each sheet's own printed corner grade labels off a
native-resolution crop (the method that built `SOURCE_REVIEWED_PRINTED_QUADS`
on 2026-09-27) and pinning image dimensions + L/R/T/B anchors the way
`SPECIAL_SPANS` does — not started, and it needs its own landing path since
`finish_printed_quad()` rejects anything >.003g from the catalogue, which is
exactly these sheets' whole problem.

Nothing landed this entry. `DETECT_VERSION` stays 35.

### 2026-09-30, later still — Sam-Neua (E)'s manual-boundary fix, landed but doesn't clear it

Made the `detect()` code change flagged as needed on 2026-09-29: the
`SOURCE_REVIEWED_BOUNDARIES` `manual` path required `reviewed_boundary_fit`
to succeed on the *outer* (rough-overview) rule for every corrected side,
even a `direct` one whose offset is discarded and never uses that fit's
result. Sam-Neua (E)'s R side has no straight line at all in its rough
guess's textured zone, so the gate refused unconditionally. Changed
`detect()` (`scripts/indochine100k_georef.py`, the `manual` block) to skip
the outer-rule fit entirely when the side is `direct`.

Added Sam-Neua (E) (`85967c9c-9bb7-4acb-9688-2eaf3d93216b`) to
`SOURCE_REVIEWED_BOUNDARIES` with both B (target 6724, matching the earlier
`y=6723.9` read) and R (target 4709, matching the earlier `x≈4708-4711`
read) marked `direct`. Also had to add a `SOURCE_REVIEWED_RIMS` entry (a
separate, unconditional gate keyed only on `manual` being set, unrelated to
the fix above) — read the actual post-fix anchor positions by a throwaway
debug print rather than guessing, since the fitted anchor at mid-strip isn't
exactly the target value fed in.

Snapshotted `work/indochine-100k/*.json` (364 files, `/private/tmp/vma-v35-baseline/`)
before bumping. `DETECT_VERSION` 35→36. Ran `place()` (46 held re-run, 314
clear reused from cache), `check()` (326 placements, clean), then diffed
every verdict against the snapshot: **exactly one sheet changed** — Sam-Neua
(E), `['shape off by 5.5%', 'rim offsets spread 59%', 'axes disagree 5.2%']
→ ['shape off by 4.6%', 'axes disagree 4.4%']`. The `rim offsets spread`
problem is gone — both boundary corrections took, cleanly, no cross-sheet
regression. But it does **not** clear the sheet: shape/axes error only
narrowed by ~1 point, exactly matching the 2026-09-29 read-only audit's
prediction ("landing only that barely moved the verdict... nowhere near
clearing"). The remaining error is a catalogue-span problem, not a pixel-
detection one — same family as the abnormal-span holds, not yet
investigated for this sheet specifically. Nothing published.

### 2026-09-30, later still — Phan Rang (E)/(W): the catalogue's south bound is wrong, confirmed against the printed sheet

User request, personal to them ("im from phan rang"): resolve Phan Rang (E)/(W), both
held on the abnormal-span gate (`fkey 60739/60742 abnormal span 0.389g × 0.609g` /
`0.388g × 0.608g` — lon standard, lat ~0.61g against the 0.48-0.53g band). This is the
Cao-Bang/Phan Rang sub-pattern flagged earlier today: no standard sibling to borrow a
width from, and the pixel-detected rim is clean on both sheets (`detect()` finds all four
sides in the usual ~170-200px family band, 24/24 patches, residual 2.6-4.9px) — so
per the 17-sheet read-only audit above, "the mismatch is entirely on the catalogue side."

Read each sheet's own printed parallel grid directly rather than inferring from pixel
aspect alone (the coastal-family retraction's lesson: inference needs an independent
check, not just its own self-consistency). The frame carries printed ticks every 0.10g
along the left margin (`"12ᴳ90"`, `"12ᴳ80"`, ... `"12ᴳ50"`), each at the true mapped
boundary (~170-200px inward of the decorative outer frame, not at the frame itself).
Fetched native crops (`fetch_crop`, R2-first) along each sheet's left margin, located
each tick's text-center pixel row by a darkness-threshold column scan (not eyeballing),
and fit a line (pixel row → grade north) through 4-5 ticks per sheet:

| sheet | ticks used | px/0.10g (consistency) | fit |
|---|---|---|---|
| Phan Rang (E) | 12.90, 12.80, 12.70, 12.60, 12.50 | 1155-1198px | slope -8.4696e-5 g/px |
| Phan Rang (W) | 12.90, 12.80, 12.70, 12.60, 12.50 | 1171-1180px | slope -8.5087e-5 g/px |

Extrapolated to each sheet's own detected NW/SW corner pixel row:

| sheet | catalogue N | printed-tick N | catalogue S | printed-tick S | catalogue lat_g | printed lat_g |
|---|---|---|---|---|---|---|
| Phan Rang (E) | 11.65417° | 11.65236° (Δ0.002°) | 11.10611° | **11.20180°** (Δ0.096°=5.8') | 0.609g | **0.501g** |
| Phan Rang (W) | 11.65917° | 11.65796° (Δ0.001°) | 11.11194° | **11.16400°** (Δ0.052°=3.1') | 0.608g | **0.549g** |

North matches the catalogue on both sheets to within 2 thousandths of a degree — not
touched. South is the error, by a different amount on each sheet (not a copy-paste
duplication like the cell-88/158bis/166/174 pattern found earlier — two independent
wrong transcriptions). Cross-checked against `detect()`'s pixel aspect ratio (computed
with zero catalogue involvement) using the corrected N/S: 2.7% residual (E), 2.1%
residual (W) — down from 14.2%/14.1% using the full catalogue box. Two independent
measurements agreeing within ~2-3% is the bar this project holds itself to; landed.

**New code path**, since neither existing registry fit: `SOURCE_REVIEWED_SPECIAL_SPANS`
only *validates* a declared span already equal to the catalogue's own number — it has no
way to substitute a different one (the exact gap the coastal-family investigation hit and
retracted over). Added `SOURCE_REVIEWED_CORRECTED_BOX` (`scripts/indochine100k_georef.py`
~L150), keyed by map id, overlaying corrected UNIMARC fields onto the fkey's box inside
`record_box()` before the span is computed. Phan Rang (E)'s corrected lat_g (0.501g) lands
inside the standard 0.48-0.53g band on its own, no further registration needed. Phan Rang
(W)'s (0.549g) still sits 0.02g over — added a `SOURCE_REVIEWED_SPECIAL_SPANS` entry keyed
to the *corrected* span to let it through (that registry's normal "validate, don't
substitute" behaviour is exactly what's wanted at this second stage, now that the box
itself is right).

Phan Rang (E) then held on two more things after the abnormal-span gate cleared:
`rim offsets spread 15%` (its B side sits ~25px outside the ~170-175px family band other
sides use, at 199.2px) and `axes disagree 2.2%`. Checked B with the per-pixel-profile
method (`docs/lessons.md`, 2026-09-29 entry): uniformly blank paper (values 20-24) all the
way from the family-band offset out to where the one real line rises and peaks — no
second, competing line anywhere in between. Same "genuinely wider margin on this one
side" case as Muong-Tè (E)/Ha-Lang (W)/Quan-Ba (E), not a double-frame pick. Added to
`SOURCE_REVIEWED_RIMS`. Both sheets added to `SOURCE_REVIEWED_AXES_DISAGREE` (2.2%/1.8%,
well under the 5% cap) — their rim is confirmed by the printed-tick reading itself, a
stronger basis than the family-offset heuristic the other entries in that list rest on.

Landed in three snapshot/bump/diff steps (`/private/tmp/vma-v36-baseline` →
`/private/tmp/vma-v38-baseline`), `DETECT_VERSION` 36→39. Each diff showed only the
intended sheet(s) changing verdict, nothing else moved. Final: **328 clean placements**
(was 326), both Phan Rang sheets `clear`, `annotate` dry run confirms both ready
(Phan Rang (E) bbox `[108.926, 11.200, 109.276, 11.653]`, (W) `[108.583, 11.163, 108.932,
11.658]` — both sane for Ninh Thuận). **Not published** — stays with the user.

### 2026-09-30, later still — checked the rest of the corpus for Phan Rang's pattern: only Cao-Bang matches, and its edition blocks the same fix

User: check other held sheets for the same error. Scanned all 34 held verdicts for Phan
Rang's shape — abnormal-span, longitude inside the standard band, latitude alone outside
it, clean four-sided pixel detection. Exactly two match: **Cao-Bang (E)/(W)**
(`5785a841-b48b-45cd-a1bc-cb377b13e29b` / `8553f73b-a048-4aae-8dab-c13de11b1a12`, fkey
60034/60035, declared 0.408g×0.603g / 0.407g×0.602g) — already named in the 17-sheet
read-only audit as the same sub-pattern as Phan Rang. `detect()` confirms clean rims on
both (family-band offsets, 24/24 patches; Cao-Bang (W)'s B needed the existing
scale-bar-outlier retry, landed at 173.9px, same as everyone else).

Went to read the printed margin the same way and found a real obstacle: **this sheet is
a different, older print edition** ("Carte de l'Indochine F<sup>lle</sup> N° 9 E", 1904-05
survey — Phan Rang is the newer "Projection Bonne" 1908-09/1924-survey, 1950/1952-updated
edition). Cao-Bang's margin carries a *kilometric* Bonne-projection grid (`1650`, `1640`,
... — "Quadrillage Kilométrique Bonne, Origine: 700 Km Ouest / 1000 Km Sud") rather than
repeated geographic grade ticks. Scanned the full left and right margins at native
resolution (both editions' corners checked, `/private/tmp/caobang_e_*` this session,
already cleaned up) — the *only* geographic grade value printed anywhere is one longitude
tick per edge at the very corner (`115ᴳ80` on the E edge), no repeated latitude ticks down
the margin the way Phan Rang had. Converting the kilometric northing to true latitude
needs the actual Bonne projection formula for this zone (`Mo:115°G_Lo:19°G` origin,
printed on the sheet) — not implemented anywhere in this script, and not something to
derive and trust without real verification; a wrong projection assumption here would
produce exactly the "looks right, quietly isn't" failure `docs/lessons.md` warns against.

Presented the choice to the user (leave held / attempt the projection math / move on to
publishing) — **chose to leave Cao-Bang held for now**, not worth the risk for a rushed
add-on to today's session. Nothing landed, nothing changed for these two.
`DETECT_VERSION` stays 39.

### 2026-09-30, later still — the coastal ~0.49g family: printed longitude ticks confirm it, Gemini quota blocks the production reader

Followed up on the retracted sibling rule's open item (next step 1): read each of the 4
coastal sheets' own printed longitude grade ticks off native crops, to confirm or kill the
~0.49g hypothesis independently of the pixel-aspect inference.

**Gemini quota exhausted** (`RESOURCE_EXHAUSTED`, "All API keys exhausted for today") —
`tick_label()`'s OCR call, and therefore the production `read_printed()` path used to build
`SOURCE_REVIEWED_PRINTED_QUADS`, is unusable until it resets. Worked around it for this
read-only check by viewing the native crops directly (`fetch_crop`-equivalent
`cached_crop()`, R2-first) instead of delegating the label read to Gemini — sound for a
confirm-or-kill check, but not a substitute for the production reader, and not something to
build a new landing path on without it.

Each sheet prints only 2-5 interior longitude ticks along the top margin (fewer than Phan
Rang's 4-5 latitude ticks); none of the 4 sheets' ticks carry the short perpendicular ink
stroke Phan Rang's did — the label text is the only anchor, so position = label's visual
horizontal center, not a darkness-threshold tick-stroke peak. That decorative dashed line
below the frame (mistaken at first glance for a scale bar / tick train) is unrelated — a
periodic ~220px engraving pattern with no correspondence to grade values, present on all
four sheets.

Fit a line (pixel column → longitude grade) through each sheet's own ticks, extrapolated to
its own `detect()`-measured west/east corner columns:

| sheet | ticks used | px/0.10g | printed lon_g | pixel-aspect-implied lon_g (09-30, earlier) | declared lon_g |
|---|---|---|---|---|---|
| Phu Diên Châu (E) | 114.80, 115.00 | 1116 | **0.504g** | 0.486g | 0.555g |
| Qui Nhon (E) | 118.60, 118.90 | 1130 | **0.495g** | 0.494g | 0.546g |
| Söng Cau (E) | 118.60, 118.80 | 1150 | **0.485g** | 0.493g | 0.545g |
| Nha Trang (E) | 118.60, 118.90 | 1182 | **0.473g** | 0.491g | 0.543g |

All four printed readings land in 0.473–0.505g — tight to each other, and far closer to the
pixel-aspect-implied ~0.49g cluster than to the declared catalogue span (10–14% off) or the
sibling-borrowed span (~21% off, already dead). **The ~0.49g third-span-family hypothesis is
confirmed**, independently, on all 4 sheets. Quang Ngai stays excluded, as before (0.428g
implied doesn't fit this cluster).

This reading is good enough to confirm the family and settle which direction to invest in
next — it is *not* good enough to land. Two ticks per sheet, label-center position instead
of a tick-stroke peak, no independent second check the way Phan Rang's pixel-aspect
cross-validation gave a true second measurement (here the pixel-aspect number is the same
inference being checked, not an independent one) — agreement is 0.2–3.7% sheet to sheet,
looser than Phan Rang's 2.1–2.7%. Before landing any of these 4: re-read with the production
`read_printed()`/`tick_label()` pipeline once Gemini quota resets (proper darkness-threshold
tick localisation, not eyeballed label centers), and only then design the landing path the
2026-09-30 sibling-rule entry flagged as needed (`finish_printed_quad()`'s 0.003g gate
can't pass a ~0.05g catalogue correction; `SOURCE_REVIEWED_CORRECTED_BOX` is the existing
mechanism, proven on Phan Rang, and is the likely fit once a solid printed reading exists).

Nothing landed. `DETECT_VERSION` stays 39. No database writes.

### 2026-09-30, later still — the coastal ~0.49g family, redone at landing-grade precision, still without Gemini

Gemini quota was still exhausted. The confirm-or-kill reading above used only 2 ticks per
sheet and eyeballed label centers (0.2–3.7% agreement with the pixel-aspect hypothesis) —
good enough to settle the direction, not to land. Two problems with that first pass, both
fixed without needing OCR:

**The column-darkness scan doesn't need Gemini, but a naive full-width version fails
anyway** — it locked onto this print's periodic decorative dashed rule (~445px spacing)
below the frame, not the grade labels, because both are "dark blobs at regular intervals"
to a threshold scan with no other constraint. Fixed by first locating each label's own row
band (a per-sheet constant, found by a vertical darkness profile at a known tick's column:
frame line, blank margin, then the label row — three bands with distinct spacing on every
sheet checked), then scanning only within that row.

**Label centroid isn't a consistent reference point across ticks that have different text**
— Phu Diên Châu's two ticks read `114ᴳ80'` (7 glyphs) and `115ᴳ` (4 glyphs, no minutes
suffix); centroid-of-whole-label shifts with glyph count, not with the true meridian.
Switched to each label's **left edge** (a relative-threshold column scan: background
20th-percentile plus 35% of the local peak), since every label on a given sheet starts with
the same leading digits (`114`/`115`/`118`, always 3 digits) — a consistent anchor
regardless of what follows.

Qui Nhon (E) and Nha Trang (E) print 5 ticks each along the top margin (not the 2 read
before — the others were missed by under-scanning the width). Fit all 4 usable interior
ticks (`.60`/`.70`/`.80`/`.90`; `.50` excluded, it carries extra `E.Paris` text that
contaminates the row-band scan) by least squares instead of a 2-point line:

| sheet | ticks | px/0.10g spacing | fit residual (max) | printed lon_g |
|---|---|---|---|---|
| Qui Nhon (E) | .60/.70/.80/.90 | 1140–1142 | 0.000063g | **0.4898g** |
| Nha Trang (E) | .60/.70/.80/.90 | 1145–1154 | 0.000276g | **0.4866g** |

Both essentially perfect linear fits (>1000x tighter than the sheet-to-sheet disagreement
being measured) and both land within 1% of their own pixel-aspect-implied span (0.4940g,
0.4912g) — tighter than Phan Rang's 2.1–2.7% cross-check bar.

Phu Diên Châu (E) and Söng Cau (E) print only 2 interior ticks each on the top margin (every
other position checked, confirmed empty — not a scan failure). Both also carry the *same*
two grade values repeated on the **bottom** margin, which gave a second, independent
measurement using the bottom corners instead of the top ones — not a new grade, but an
independent second read of the same span:

| sheet | margin | ticks | printed lon_g |
|---|---|---|---|
| Phu Diên Châu (E) | top | 114.80/115.00 | 0.5066g |
| Phu Diên Châu (E) | bottom | 114.80/115.00 | 0.5010g |
| Söng Cau (E) | top | 118.60/118.80 | 0.4998g |
| Söng Cau (E) | bottom | 118.60/118.80 | 0.4876g |

Söng Cau's two margins average to **0.4937g** — matches its pixel-aspect-implied 0.4931g to
within 0.1%. Phu Diên Châu's two margins agree with *each other* (1.1% apart, both ~0.50–
0.51g) but sit 3.5–4% above its own implied 0.4861g and above the other three sheets'
~0.49g — internally consistent, not obviously an error, and not the same value as the other
three. Averaged: **0.5038g**.

Final printed-longitude spans for all 4: Phu Diên Châu (E) 0.504g, Qui Nhon (E) 0.490g,
Söng Cau (E) 0.494g, Nha Trang (E) 0.487g — a tight 0.487–0.504g band, decisively separate
from the catalogue's 0.543–0.555g and the dead sibling value (~0.39g). Three of the four
now meet the project's normal landing bar on their own; Phu Diên Châu reads a genuinely
different (but still non-catalogue) value from the other three, the same way Phan Rang
(E)/(W) took different corrections from each other despite being siblings — worth noting,
not a blocker.

Not landed. This is precise enough to land, but landing still needs the code-path decision
the earlier entry flagged (`SOURCE_REVIEWED_CORRECTED_BOX`-style substitution plus whatever
gate replaces `finish_printed_quad()`'s catalogue-only 0.003g check) and that hasn't been
built or agreed. `DETECT_VERSION` stays 39. No database writes, no code changes.

### 2026-09-30, later still — the coastal ~0.49g family: landed, all 4 clear

User: proceed. Built the landing path and ran it for all 4.

**West-vs-east decision.** The west residual against the catalogue was small but not
negligible on all 4 (0.4–1.6%, vs. east's consistently 3-4x larger 3.6–5.3%) — the same
shape as Phan Rang's "one side matches, one is wrong," but not clean enough to treat west as
ground truth the way Phan Rang's 0.001–0.002° north match was. Used each sheet's own
measured (west, east) pair directly rather than mixing catalogue-west with printed-east —
self-consistent, and already independently checked against the pixel-aspect method to ~1%
on 3 of 4.

**`SOURCE_REVIEWED_CORRECTED_BOX`**: added `w`/`e` overrides for all 4 (fkeys 60219, 60498,
60546, 60651). **`SOURCE_REVIEWED_SPECIAL_SPANS`**: added entries keyed to the corrected
lon_g so the still-abnormal span (0.487–0.504g, deliberately outside the 0.36–0.43g standard
band — that's the whole finding) passes `record_box()`'s gate.

Ran `placement()` directly against the fkeys (not through `place()`/`rows()` — see
Environment constraint below): Qui Nhon (E), Söng Cau (E), Nha Trang (E) came back `clear`
immediately, zero registry work needed beyond the box correction. **Phu Diên Châu (E)**
held on two more things, same sequence as Phan Rang (E):

- `rim offsets spread 15%` — B side detected at 193.5px vs. 166–171px on L/R/T. Read the
  native crop directly (not just the profile) at the family-band offset: the tick label's
  own ink is what a naive full-width darkness scan picks up as a weak secondary peak inside
  the family band; there is no second frame/grid line there. Same "genuinely wider margin on
  this side" case as Phan Rang (E)'s B side — added to `SOURCE_REVIEWED_RIMS`.
- `shape off by 3.6%` / `axes disagree 3.5%` — both under the 5% reviewed cap, both already
  independently confirmed by this sheet's own printed reading (not a detection artifact).
  Added to `SOURCE_REVIEWED_AXES_DISAGREE`.

All 4 `verdict: []` after that. WGS84 boxes are sane for the Vietnam coast (e.g. Nha Trang
(E) `[108.940, 12.097, 109.378, 12.557]`).

**Environment constraint, not a code problem**: `place()`, `check()`, and `annotate()` all
call `rows()`, which needs `SUPABASE_SERVICE_KEY` to see `status = 'draft'` rows under RLS.
The local `.env` only carries the `sb_publishable_...` anon key (by design — `rows()` with it
silently returned 314 rows, *all* `status: "public"`, zero drafts, no error). Worked around
it for these 4 by constructing row dicts directly from the known id/fkey pairs and calling
`placement()` in isolation — verified correct against the same function the real pipeline
uses, but this **could not run `check()`** (the cross-sheet lattice/series-median
consistency check, which needs the full draft-row set) or the corpus-wide snapshot/diff
regression check every prior landing in this file did. The 4 sheets' local JSON caches
(`work/indochine-100k/*.json`) were written directly with the placement() output, matching
what `place()` would have written. Whoever runs `place()` next with real service-role
credentials should confirm `check()` passes and no other sheet's cached verdict moved
(these registry entries are per-id, so it shouldn't, but it hasn't been verified against the
full corpus).

`DETECT_VERSION` **not bumped** — no `detect()` code changed this entry, only per-id
registry data, and the 4 affected sheets were already held (recomputed unconditionally
regardless of version, per `place()`'s cache-reuse check). Not published — `annotate
--apply` needs the real credentials this session doesn't have, and stays with the user
regardless.

### 2026-09-30, later still — Lang Son (E): the "two comparable rules" were a reversed outer/inner read, not a double-frame pick

Picked up the next held sheet. The 2026-09-29 note said R sat ambiguous between two rules
in a low-value gap, and B similarly; reverted to held rather than guessed at the time.

Re-ran `detect()` clean (no overrides) first: it now fits both sides confidently — R offset
149.9px (residual 3.9px, 24/24), B offset 216.8px (residual 3.5px, 24/24). Confident numbers
aren't the same as correct ones (`docs/lessons.md`, 2026-09-29), so checked what's actually
printed at each landed pixel with a native darkness scan rather than trusting the residual.

**Both sides land in a genuinely quiet gap**, same failure as the note flagged: R's pick
(x≈4809) sits between two close pairs of thin printed lines (4796–4818, 4872–4949) with
nothing at 4809 itself; B's pick (y≈6823) sits between a thick 9px line (6800–6810) and a
thin one (6827–6830) with nothing at 6823. `detect()`'s convention is "the coarse guess
finds the outer decorative frame, then search inward up to 250px for the true rim" — that
assumption is what's wrong here, not the patch-fit math. `frame()`'s own coarse guess (R
4966, B 7038) already lands on a real, wide (~9-10px), well-defined line on both sides — the
same width/character as every confirmed neatline elsewhere in this corpus — and the
"search inward from there" step is what walks off it onto some other printed feature
(interior graticule/kilometric ticks, in a sparse area with several of them close together).

Registered both as **direct** fixes (`SOURCE_REVIEWED_BOUNDARIES`, targets R:4970, B:6805 —
close to but not exactly the coarse guess, since `reviewed_boundary_fit` still runs its own
24-patch fit within ±12px of the target rather than taking it verbatim) plus the matching
`SOURCE_REVIEWED_RIMS` entry the direct-fix gate requires. Fits: R residual 3.28px (24/24),
B residual 3.32px (24/24) — same quality as any clean auto-detected side. Full placement:
`rim offsets spread` 38%→11.6% (under the 12% gate), `shape off`/`axes disagree` 4.6%/4.4%→
0.7%/0.7%. **Clears outright** — no catalogue correction, no axes-disagree exception needed,
the geo box was never wrong, only the pixel registration was. `wgs84` bbox `[106.925, 21.612,
107.292, 22.066]`, sane for the Lạng Sơn area.

Local JSON cache written directly (same credential-gap workaround as the coastal family
entry above — `placement()` called in isolation, not through `place()`/`rows()`).
`DETECT_VERSION` not bumped, no `detect()` code changed.

### 2026-09-30, later still — the last four held Vietnam sheets besides Cao-Bang: four unrelated single-sheet fixes, all clear

Continued through the remaining Vietnam held list (Cao-Bang (E)/(W) excluded — left held on
purpose earlier today, not reopened). Each of the four turned out to be a different problem;
none needed Gemini.

**Lai Châu (E)** (`a387ff3f-...`, fkey 60045): `detect()` already had all four sides landing
on clean, isolated, high-confidence lines — L 0.48px/24, R 0.39px/24, T 3.68px/24, B 4.00px/24
patches — yet the verdict flagged `rim offsets spread 17%` and `axes disagree 1.5%`. This
sheet was one of the nine "check out clean" holds from 2026-09-29's local-prominence pass
(real printed line within 5px of every anchor), and unlike Ha-Lang/Muong-Tè/Quan-Ba/Than-Poun
it was never flagged for a comparably-strong second line — so there was no double-frame
ambiguity to resolve, just confirmation. Ran a per-pixel darkness profile at each of the four
anchors independently (not trusting the residual number, per the 2026-09-29 lesson): T shows a
single sharp, isolated dark line at y=712-713 against an otherwise textured ~165-190
background; B the same at y=6620-6621. Both anchors match to within 1px. Registered all four
as `SOURCE_REVIEWED_RIMS` and added to `SOURCE_REVIEWED_AXES_DISAGREE` (1.5% is real printed
distortion, same class as Bun-Tai/Mon-Cay/Muong Ou Tay). `verdict: []`. No catalogue change.

**Tu Lê (E)** (`dcfb2452-...`, fkey 60070): L/R/T all clean (~170-195px offset, 3.1-3.7px
residual), but B's offset was 250.5px — far outside the other three sides' range, the same
"suspiciously large offset" signature that flagged Than-Poun (E)'s bottom margin. A wide crop
of the B margin (2200-3000px wide, y 6880-7280) showed why: this sheet's bottom margin holds a
"113°20' / Son La Est / Echelle 1:100.000" title block bounded by two thick striped
assemblage-index bars, and `detect()`'s automatic pick (7095.9) had walked past the true
neatline (the single thin line at the very top of that block, immediately below the map
content) onto one of the label-box's own interior border lines. Confirmed by a native darkness
scan across the full block: the true neatline sits at y≈6950, a single strong, isolated line
(val 20.2 against a ~170-190 background), with the striped bars and label-box lines all deeper
in. Direct-registered `B` at 6950 (`SOURCE_REVIEWED_BOUNDARIES` + matching
`SOURCE_REVIEWED_RIMS`): refit residual 0.35px, 24/24 patches, far cleaner than the wrong
pick's 3.4px. `rim offsets spread` 41%→14% (filtered by the rims match), `axes disagree` and
`shape off` both drop under 1.1% — clears outright, no catalogue correction.

**Tri Binh (W)** (`1f025a9f-...`, fkey 60391): held since 2026-09-23 as `excluded calibration
outlier; offset unverified` — the original two-tick-per-axis Gemini read found it 741.5m off
the accepted latitude fit, an internally-plausible reading that nonetheless failed the 250m
gate, so the sheet was dropped from the calibration sample rather than resolved. `detect()`'s
own geometry was never the problem here (all four sides 169-172px offset, 2.2-3.8px residual,
aspect_err/scale_gap both ~0.7%) — the catalogue box itself was in question. Redone the same
no-Gemini way as the coastal family, with three ticks per axis instead of two: top margin
118.20/118.30/118.40g (consistent to 1135-1140px per 0.1g), left margin 17.40/17.30/17.00g
(consistent to 11740-11768px per 0.1g). Fit each axis end-to-end: east and north both match
the catalogue closely (-59m, +50m, within reading noise) but **west and south are genuinely
wrong**, by +509m and +544m respectively — the catalogue's declared box is very slightly too
wide and too tall. Corrected both fields via `SOURCE_REVIEWED_CORRECTED_BOX`
(`{"w": 108.636689, "s": 15.274067}`) and removed the sheet from `CALIBRATION_HOLDS`.
`verdict: []`; aspect_err/scale_gap improved from 0.69% to 0.43% under the corrected box,
consistent with the correction being real rather than noise.

**Quang Ngai** (`48584dae-...`, fkey 60407): the coastal-family investigation's other loose
end — catalogue declared 0.5235g × 0.5096g, but the pixel-aspect ratio (assuming the
unflagged 0.51g latitude span is correct) implied 0.428g longitude, a large mismatch with no
sibling record to cross-check against (lone fkey). Read the sheet's own four printed
longitude ticks off the top margin (118.20/118.30/118.40/118.50g, spacing consistent to
<0.6%): west matches the catalogue almost exactly (+256m, noise) but **east is off by
~9.2km** — a large, unambiguous catalogue transcription error, not a rounding artifact.
Corrected east (`{"e": 109.011425}`) gives a printed span of 0.4281g, matching the
independent pixel-aspect estimate (0.4280g) to within 0.02%. The corrected span now sits
inside the standard 0.36-0.43g band on its own, so no `SOURCE_REVIEWED_SPECIAL_SPANS` entry
is needed. `verdict: []`; aspect_err/scale_gap dropped to 0.03% (essentially exact) under the
corrected box — the strongest confirmation of any correction landed this session.

All four local JSON caches written directly (same credential-gap workaround as every landing
above). `DETECT_VERSION` not bumped — no `detect()` code changed, only per-sheet registry
data. This closes out the Vietnam held list down to Cao-Bang (E)/(W), which stays held by
deliberate earlier choice, not an oversight.
