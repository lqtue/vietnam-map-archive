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
