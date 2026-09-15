# Pipelines

Pipelines that live outside the SvelteKit app. Each section is the canonical reference — CLAUDE.md only links here.

## Is every map where it says it is? (`scripts/geo_audit.mjs`)

```bash
node --env-file=.env scripts/geo_audit.mjs          # the whole archive
node scripts/geo_audit.mjs --self-test              # no database, no network
```

Exits 1 on any FAIL. Run it before publishing a sheet and after any mosaic
rebuild.

Every position in the archive is asserted by exactly one authority and, until
Sept 2026, never cross-examined: a warped sheet is where its annotation says, a
mosaic cell was where its GeoPDF's CRS said. That is how 285 of 437 sheets
shipped ~470 m off. **So every check here compares two things that were arrived
at independently**, and none needs a person to say what is true:

| check | third party | level |
|---|---|---|
| the annotation resolves and carries ≥3 control points | — | FAIL if published, WARN if draft |
| the drawn sheet lands inside Vietnam | a box round the country | FAIL |
| the sheet sits on its printed 15′ cell | `work/l7014/lattice.json` | FAIL if published |
| a cell held twice agrees with itself | the other holding | FAIL |
| `maps.bbox` still matches its annotation | — (a copy vs its source) | WARN, coarse — see below |

Two distinctions the script turns on, both of which produce a confident wrong
answer if collapsed:

- **The drawn paper is not the control-point hull.** On a sheet with three
  interior GCPs the hull sits kilometres inside the paper while being perfectly
  correct — up to 360 km on *Cochinchine Francaise*. The cell check therefore
  uses the georeference **mask**, forward-transformed through the sheet's own
  control points, and **skips a sheet that has no mask** rather than failing it.

  `maps.bbox` was the hull until 929ecbf4 (15 Sept 2026) and is now the warped
  mask extent, which is the ground the renderer covers. The bbox check here went
  on measuring against the hull for a day and so reported **39 sheets adrift by
  up to 359 km while every one of them was right** — a checker comparing a row
  against a definition it no longer uses. It now measures against the mask.

  Even so it stays **coarse, at 10 km**. This script recovers a plain
  least-squares affine from the control points; the backfill pushes the mask
  through the map's own transform with each edge densified 24×. Measured over
  all 132 georeferenced maps with the backfill reporting `0 differ`, the
  remaining gap is median 0.0 km, p90 0.1 km, max 3.8 km — all of it this
  script's approximation. So the check catches a bbox pointing at a different
  place and nothing subtler. **The exact answer is the backfill itself**, which
  is idempotent by construction:

  ```bash
  node --env-file=.env scripts/oneoff/backfill_map_bbox.mjs --dry --force  # must say "0 differ"
  ```
- **The lattice is an artifact, not a formula.** `l7014_mosaic.py corners`
  writes `work/l7014/lattice.json` — 627 cells, four WGS 84 corners each — and
  this script reads it. A JS reimplementation of the Indian 1960 Helmert would
  be a second place for the exact fault this audit exists to catch. `work/l7014/`
  is gitignored, so that file and the mosaic manifest are **local build
  artifacts**: on a machine that has not built the mosaic the audit still runs
  and says which checks it had to skip, rather than passing quietly with two of
  them switched off.

`--self-test` runs the geometry against inputs it must refuse: a cell with the
datum shift skipped (482 m, rejected), collinear control points, an axis swap
landing off West Africa. A check that cannot fail is not one, and the one this
replaces returned `2e-12`.

**Reading today's run (15 Sept 2026).** 0 fail, 143 warn. Of those, 142 are
drafts with no resolvable annotation — 121 that carry none at all, and 21 L7014
backdrop drafts whose `allmaps_id` 404s at Allmaps. That second group is not as
benign as it reads here; see `catalog_audit.mjs` below. The one substantive
warning is the duplicate draft *Huế — Việt Nam 1:50,000 (Sheet 6541 IV)*, 5.4 km
off cell 6541-4 — the published row for the same cell is not, and the two share
a `source_url`, so one of them should be retired. Zero bbox warnings, which the
backfill's `0 differ` independently confirms.

## Is a row consistent with its own table? (`scripts/catalog_audit.mjs`)

```bash
node --env-file=.env scripts/catalog_audit.mjs      # the whole catalogue
node --env-file=.env scripts/catalog_audit.mjs --quiet
node scripts/catalog_audit.mjs --self-check         # no database, no network
```

Exits 1 on any FAIL. Read-only, no network, about a second — so it can run after
every ingest. Three checkers divide the archive and none should grow into
another: `geo_audit.mjs` asks whether the paper is where the annotation says,
`check_series_index.mjs` whether `series_sheets` still agrees with `maps`, and
this whether a row contradicts the rest of its own table.

| check | level |
|---|---|
| published but not yet georeferenced — live, and drawing nothing yet | WARN |
| `status` outside `draft`/`public`/`featured`; published with no annotation or no `iiif_image` | FAIL |
| published with no bbox, thumbnail, year, `holding_institution` or `source_url` | WARN |
| empty or duplicate `slug`; a slug that is both canonical and an alias; an alias pointing at a deleted map | FAIL |
| bbox malformed, inverted, zero-area, or outside Vietnam | FAIL |
| one `iiif_image` serving two maps | FAIL |
| 2–3 maps sharing one `source_url` | WARN |
| `source_type` outside mig 027/041; an impossible `year` | FAIL |
| `year` appearing nowhere in `year_label`; one holder spelled two ways | WARN |
| two primary IIIF sources, none primary, or a primary disagreeing with `maps.iiif_image` | FAIL |
| a published map with no non-r2 IIIF source, so the Allmaps Editor cannot open it | WARN |
| a job out of retries, held past 3 h, or pointing at a deleted map | WARN / FAIL |

**What it deliberately does not report.** A map carrying `allmaps_id` with
`georef_done` false reads like a fault: the id is a SHA-1 of the canonical IIIF
URL, minted locally by `bulk_upload_local.sh` whether or not a control point
exists, and migration 062 gates publishing on `annotation_url is not null or
allmaps_id is not null` — so on paper a sheet satisfies the gate with a hash of
its own URL. This file called that a finding, over 21 L7014 drafts, until the
code that consumes the pair turned up.

It is a **work queue**. `POST /api/admin/maps/sync-georef` selects exactly
`allmaps_id is not null and georef_done = false`, probes
annotations.allmaps.org and flips `georef_done` on a hit; the admin *Sync georef
from Allmaps* button is its trigger. The id is how the archive remembers a sheet
is uploaded and waiting for someone to place control points. Clearing it, or not
writing it at upload, would empty the queue — a volunteer's georeference would
arrive and nothing would ever notice. Publishing on the strength of it is
deliberate too: mig 080 exists *because* georeferencing usually happens after
publishing, and `tests/write.spec.ts:596` pins that path.

So the count prints as status, not as a finding, and whether those annotations
resolve is a network question — `geo_audit.mjs`, which already reports each one
as `annotation HTTP 404`. The lesson is the general one: a column that looks
like stale data may be the state another process is waiting on. Find the
consumer before calling it a fault.

**No bbox size heuristic, on purpose.** A sheet-sized box and a regional one
differ by three orders of magnitude and both are correct; every threshold tried
flagged the three `map_type: regional` sheets and nothing else. Whether a bbox is
*right* is `geo_audit`'s question, answered exactly by the backfill's `--dry
--force`.

`--self-check` hands every rule input it must refuse and the healthy row that
must pass beside it — 28 cases, no database. A checker that only ever runs
against a healthy archive reports the same thing whether it works or not, which
is how `check_series_index` once reported clean over 79 sheets it could not see.

**Reading today's run (15 Sept 2026).** 274 maps, 131 published, **0 fail, 53
warn**: 24 published maps the Allmaps Editor cannot be opened on, 13 with no
`holding_institution` and 3 with no `source_url`, 6 layout jobs out of retries, 5
`year`/`year_label` disagreements, one holder spelled two ways (Perry-Castañeda,
word order), and the duplicate Huế pair. Plus a status line: **21 maps queued for
georeferencing**, which is the sync button's backlog, not a fault.

**What it does not cover.** The 63 Indochine sheets carry sheet numbers but no
lattice index, so nothing checks their position; and the "held twice" check
found **0 pairs**, because the nine city sheets are deliberately out of the
mosaic and the fifteen backdrop sheets have no annotation to compare against.
Keeping a cell both ways only buys a standing check once both holdings are
actually georeferenced.

## AMS Series L7014 mosaic (`scripts/l7014_mosaic.py`)

The US Army Map Service's 1:50,000 coverage of Vietnam, as **one raster PMTiles
archive** rather than 509 catalogue rows. It is served exactly the way the
street basemap is — an object in `vma-tiles` behind `tiles.maparchive.vn`, read
by byte range — but it is a **layer, not a basemap**: it joins the overlay stack
as the raster `part` of one `SeriesRef`, sharing its opacity, eye and position
with the nine warped city sheets that fill its Saigon-shaped hole, and is
switched on from the **Series** row of the map controls. A basemap was the first attempt and
was wrong in two ways — a sheet series is one thing among the archive's others
and wants an opacity slider, and underneath it the ~99 missing sheets showed the
*basemap*, which in dark mode is near-black, so every gap read as a hole punched
in the page.

```bash
python3 scripts/l7014_mosaic.py index           # scrape the PCL index
python3 scripts/l7014_mosaic.py fetch --jobs 4  # download the GeoPDFs (~4 GB)
python3 scripts/l7014_mosaic.py warp            # clip to neatline, reproject
python3 scripts/l7014_mosaic.py tile            # mosaic -> MBTiles -> PMTiles
python3 scripts/l7014_mosaic.py upload          # rclone to r2:vma-tiles/overlay/
python3 scripts/l7014_mosaic.py manifest         # one outline per sheet in the archive
python3 scripts/l7014_mosaic.py fit             # where every warped sheet actually landed
python3 scripts/l7014_mosaic.py check           # prove the datum check can fail
```

> **The live archive `l7014-20260913` is wrong and a rebuild is pending.** 285 of
> its 437 GeoPDF sheets shipped without the Indian 1960 datum shift and sit
> ~470 m northwest of where they belong; `fit` reports 341 of 452 sheets more
> than 150 m off their cell. The cause and the fix are trap 1 below. The fix is
> committed and `fit` now fails on the shipped archive, but nothing has been
> re-warped or re-uploaded — do that before trusting a measurement taken off
> these tiles. The 24 hand-georeferenced sheets are **not** affected: their
> control points fit to 2.3–19.0 m rms (`residuals`), and the ~460 m step a
> reader sees where one of them meets the mosaic is the mosaic edge moving.

Every phase is resumable — it skips what it already produced — so a failed run
is re-run, not restarted. Needs GDAL with the PDF driver, the `pmtiles` CLI,
and rclone's `r2:` remote. Wall clock for the full series is roughly two hours,
most of it the download.

**Why there is nothing to georeference by hand.** Each PCL GeoPDF carries eight
NGA control points in pixel space, its printed neatline as a polygon, and an XMP
block with the sheet's title, edition, date and graticule corners. The pipeline
clips each sheet to its own neatline (which is what removes the collar, so
sheets butt together instead of overlapping their margins), warps it to Web
Mercator, and tiles the lot. Where two sheets were warped the same way their
edges agree to **2.5–14 m** — inside the series' own ±25 m drafting accuracy,
and grid lines and streams run unbroken across a join. What *is* visible at such
a seam is tone: the scans differ in brightness sheet to sheet.

That "warped the same way" is load-bearing, and it is how the datum fault above
was found. Over all **750** adjacent seams in `l7014-20260913` the median is
19 m, but **56 are over 300 m** — those are the joins where an unshifted sheet
meets a shifted one — and **every one of the 33 seams where a hand-georeferenced
sheet meets the mosaic measures 447–504 m**. A seam is the cheapest measurement
here because it needs no outside data at all, only two sheets that claim to
share an edge; four sheets is not enough of them to notice a fault that splits
the corpus 285/151.

**Five things that will silently produce a plausible wrong result.** All five
are handled; all five are worth knowing before editing this script. Every one of
them was found by looking at the output, not by reading the code.

1. **The datum, twice over, and the second one shipped.** GDAL cannot map every
   NGA LGIDict code: on `IND-I` and `INF-A` it emits a warning, falls back to
   WGS84, and *the warp still succeeds* — putting the sheet ~450 m off with no
   error anywhere. So the projection is rebuilt from what GDAL did parse (its
   central meridian names the UTM zone exactly) or, failing that, the sheet's
   XMP.

   That is only half of it, and the other half reached production. **A sheet
   that says `Indian_1960` plainly gets no shift either**, because PROJ's
   `EPSG:4131` → `EPSG:4326` pipeline has an area of use covering part of the
   country and, for a point outside it, GDAL returns the input **unchanged**
   rather than failing. Probed: `106.00,16.00` moves 470 m, `109.25,13.25`
   moves 0. `phase_corners` already spelled the Helmert out by hand for exactly
   this reason; `warp` did not, and 285 of 336 sheets that declare Indian 1960
   in their own PDF shipped with the shift silently skipped. The shift is now
   `INDIAN_1960_PROJ4` — Everest 1830 (1937 Adjustment) plus
   `+towgs84=198,881,317` — and is never looked up.

   **The check that was supposed to catch this could not.** `graticule_error`
   reads the sheet's control points into the sheet's *own* datum and compares
   them with the graticule the sheet itself prints. Both sides move together
   when the datum is wrong, so it returns ~0 for precisely the fault it looks
   like it is guarding — A Luoi's `graticule_err` is `2e-12` — and it is blind
   by construction, not by accident. What replaces it is an **outside opinion**:
   `pick_crs` warps the neatline under both readings, the sheet's declaration
   and Indian 1960 with the Helmert, and keeps whichever lands on the sheet's
   15′ lattice cell. That is a measurement between two candidates ~470 m apart
   against a third party good to ~15 m, so the choice is never close; a sheet
   that misses on **both** readings is refused rather than warped in at the
   smaller miss. Dry-run over all 437: median miss 430 m → **0 m**, p95 9 m,
   max 115 m, none over 150. `fit` is the same measurement over a built archive
   and exits 1, so it belongs between `tile` and `upload`. `check` still runs a
   real sheet through WGS84 on purpose and asserts the graticule test rejects
   it — that test is fine at what it does see, which is a wrong zone.
2. **The UTM zone must come from the sheet's centre, never an edge.** Many
   sheets end at longitude 108.000, exactly the zone 48/49 boundary; taking the
   east edge puts them a zone over. That is a clean 6.00001° error, and it looks
   like a datum fault rather than the off-by-one it is.
3. **The COG driver cannot carry a fourth band through JPEG compression.** Ask
   for `-dstalpha` with `-of COG -co COMPRESS=JPEG` and GDAL quietly demotes the
   alpha to an internal mask; `gdalbuildvrt` then drops the mask, and the mosaic
   loses its transparency without a word — every hole becomes an opaque
   rectangle sitting on the basemap. Plain GTiff + DEFLATE for the
   intermediates, which cost ~41 MB a sheet (~21 GB for the series, deletable
   once tiled).
4. **The pixels nothing ever shows still get averaged.** `-dstalpha` leaves the
   area outside the neatline black at alpha 0. Invisible — until every
   resampling step blends it into the visible edge and draws a dark outline
   around each hole. `-wo INIT_DEST=255,255,255,0` puts white there instead.
5. **`TILE_FORMAT=JPEG` has no alpha**, so the holes would paint black over the
   basemap; and **`ZOOM_LEVEL_STRATEGY=UPPER` invents a zoom level** past the
   scans' own resolution, quadrupling the archive for detail that is not in the
   paper. WEBP and `LOWER`.

Also: `gdalbuildvrt` defaults to **average** resolution, which would quietly
downsample the 300 dpi sheets to match the 150 dpi ones. `-resolution highest`.

**The one flaw left, and its price.** WEBP discards the RGB under fully
transparent pixels, so the white from trap 4 is gone by the time `gdaladdo`
averages a half-covered edge, and a thin dark line survives around each hole.
`--tile-format PNG` removes it completely and costs **nine times the bytes** —
35 GB against 3 GB, measured on the same four sheets — on every tile a reader
pans across. Hence a flag rather than a different default.

**On the browser side**, `PMTilesRasterSource` returns an empty `Uint8Array` for
a tile the archive does not hold, and a sparse archive is mostly misses. The
canvas renderer throws on array data outright; the WebGL one paints it black,
hiding the street basemap underneath. `SparsePMTilesSource` in `basemapStyle.ts`
wraps the loader and substitutes a transparent canvas — **at the archive's own
tile size**, because a `DataTileSource` assumes every tile is the size its grid
declares, and a 512 px blank where the grid says 256 renders the neighbouring
tiles as black bands.

**The hole over Saigon.** 25 of the 534 sheets are published as plain JPGs with
no georeference at all, and they are the ones that matter most here — Thành phố
Hồ Chí Minh (6330-4), Biên Hòa, Nhơn Trạch, Cần Giuộc, Cần Giờ, Gò Công, Huế,
Đà Nẵng, Hải Phòng. They are recorded in `work/l7014/sheets.json` with
`kind: "jpg"` so what the mosaic is missing stays legible. Their geographic
corners are *not* unknown — the series is a regular 15′ lattice, so any sheet
number's cell is computable exactly from its neighbours' XMP. What is missing is
the four neatline corners in each JPG's pixel space, which is four clicks a
sheet, twenty-five times.

PCL sits behind a bot check that challenges anything claiming to be a browser
and waves curl's own user agent through, which is why both fetches shell out to
curl instead of dressing `urllib` up as Chrome.

The predecessor of this script was `scripts/l7014_pipeline.py` (deleted in
`27f8e79f`, with `pipeline_sheets` dropped in migration 036). It scraped corner
coordinates from Texas Tech's Virtual Vietnam Archive, guessed every sheet's
neatline from one hand-calibrated set of fractions, and uploaded each sheet to
the Internet Archive for a IIIF service. None of that is needed once the PDF
carries its own control points.

## The worker (`work/worker/vma_worker.py`)

Since migration 053 the app does not run a pipeline itself: "Run OCR" writes a `pipeline_jobs` row, and a worker claims it. Everything below still runs by hand — the worker only assembles the same command lines from a job payload.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --kinds ocr --worker $(hostname)  # poll forever
python work/worker/vma_worker.py --once                            # drain one job, exit
python work/worker/vma_worker.py --once --python /usr/bin/true     # exercise the loop, run nothing
```

Claiming goes through the `claim_job(kinds, worker)` RPC, which is a single `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`: several machines can poll the same kinds with no coordination. `finish_job(id, status, result, error)` closes a job out, and a failure with `attempts < max_attempts` goes back to `queued` instead of `failed`, so a worker dying mid-run costs one retry rather than the job.

The worker holds **no database credentials**: it authenticates with a `worker_keys` token against `/api/pipeline/claim` and `/api/pipeline/results`, so a compromised pipeline machine can write extractions and close its own jobs, nothing else.

```bash
node --env-file=.env scripts/mint-worker-key.mjs macbook-m1     # prints the token once
# on the worker machine's .env:
VMA_API_URL=https://maparchive.vn
VMA_WORKER_KEY=<token>
```

The worker exports both variables into each job's subprocess, so `ocr.py … --db` posts its rows through the same endpoint — `supabase_client.py` picks its transport from them. Run by hand without those variables, it falls back to PostgREST with the service key, which is what `clean`, `join_labels` and `eval` still use.

`seg` has a runner too, but its machine is not normally a laptop: MapSAM2 wants a GPU, so the intended host is a Colab notebook running this same worker with `--kinds seg`. A GPU session becomes a worker, and the Segmentation panel's command stops being something a human copies by hand. Its flag set mirrors `segCommand.ts` — keep the two in step. `MAPSAM2_DIR` and `MAPSAM2_CHECKPOINT` come from the environment, because they describe the machine rather than the job; a job payload may override either.

`--write-supabase` writes `pixel_polygon` (the outer ring, full-image source px — the same grid `ocr_extractions.global_*` uses), `confidence` from SAM2's IoU, `source='sam-auto'` and the run id. Holes are dropped: the column holds one ring. Before migration 055/057 this path could not insert at all — it posted three columns that do not exist and a `source` the check constraint refused.

The scripts no longer report a pipeline stage — `update_pipeline_status()` is a stub since migration 056, because `map_pipeline_status` is a view over the job queue. Opening and closing the job *is* the stage change.

`work/ocr/EVAL-BASELINE.md` records the measured quality gate. (Two hand-drawn companion diagrams used to live here; they went stale faster than the pipeline changed and were deleted — this file is the reference.)

Measured quality gate + the one recorded negative result: **`work/ocr/EVAL-BASELINE.md`**. Read it before changing anything in the core loop.

## OCR (`work/ocr/`)

Gemini Flash vision pipeline that extracts toponyms, street names, and institutional labels from IIIF map tiles. Uses `google-genai` with structured JSON output.

**There is no repo-root `.venv`.** The only venv in the tree is `work/ocr/.venv` (see *Local passes* below for how it is created); it also serves the Gemini passes once `google-genai` is installed into it.

```bash
source work/ocr/.venv/bin/activate

# Single tile
python work/ocr/scripts/ocr.py run \
  --map-id <uuid> --iiif-base <url> \
  --crop x,y,w,h --render-size 2048 \
  --run-id <name> --preview

# Full-map macro scan (scout pass, no crop)
python work/ocr/scripts/ocr.py scout --map-id <uuid> --iiif-base <url> --run-id <name>

# Batch over all tiles (row-sequence is ON by default)
python work/ocr/scripts/ocr.py batch --map-id <uuid> --iiif-base <url> --scout --run-id <name> [--db]

# Fuzzy dedup + spatial fragment join → ocr_extractions
python work/ocr/scripts/ocr.py clean \
  --local work/ocr/outputs/<map-id>/runs/<run-id> \
  --map-id <uuid> --run-id <clean-run-id> --min-confidence 0.1 [--apply]
```

Subcommands (15): `run`, `batch`, `scout`, `stitch`, `clean`, `dedup`, `merge`, `preview`, `list-models`, `detect-layout`, `grid`, `numerals`, `legend`, `street-index`, `street-index-fixture`.

**Two passes, then agree (the default from the queue).** One `batch` reads 39 of the 43
validated labels on the gate sheet; the misses are labels the model never returned, not
fragments and not box convention (`EVAL-BASELINE.md`, 2026-09-08). A second `batch` with
`--grid-offset tile/2` moves every seam onto the first pass's tile interior, and
`merge --runs a,b --run-id r --db` votes the two into one run: 41/43. The vote matters —
`dedup_items` keeps the higher self-reported confidence, which one prompt hands out at 1.00
on a box at IoU 0.06, so a plain union scored *below* a single pass. `ensemble_items` takes
the spelling most passes wrote and the box that overlaps the others most. An `ocr` job with
`passes: 2` (what `enqueue_ocr_all.mjs` and the Run OCR button now send; `--single-pass`
opts out) becomes three worker commands: `batch <run>-a`, `batch <run>-b --grid-offset`,
`merge → <run> --db`. Twice the tokens of one pass, a third of the input from the prefix
cache, ~14 min a sheet. `passes: 3` adds a 1200 px pass (`<run>-c`) for small type — it read
`POSTE DE POLICE`, which no 2400 px pass ever did, but fragments long labels, so it only
rides along with the other two. ~45 min a sheet.

**Prompt.** `DEFAULT_PROMPT` is `seq-v1` (2026-09-08): v8 with whole-label assembly for the
row-sequence path and abbreviations transcribed as printed — `R.` is `Rue` before a French
road and `Rạch` before a Vietnamese name on the water, and the sheet decides, not a rule.
The system + task prompt go into an explicit Gemini context cache per (key, model, text),
1 h TTL; each call sends only its images. `GEMINI_EXPLICIT_CACHE=0` sends them inline.

**Model.** `gemini_client.DEFAULT_MODEL` is `gemini-3.8-flash` ($0.75/$3.75 per 1M in/out) since 2026-09-04; it was `gemini-3-flash-preview`, which still answers but is absent from Google's pricing page — no published rate, no stated support window. `--model` overrides per run, an `ocr` job payload's `model` overrides per job (the worker passes it through), and `scripts/enqueue_ocr_all.mjs --model NAME` sets it for a whole batch. Measured on this corpus at 5,156 in / 1,810 out tokens per call and 30–60 calls per sheet, that is roughly $0.50 a map, or $0.06 on `gemini-2.5-flash-lite`. Rate limits are no longer published per model — read them at <https://aistudio.google.com/rate-limit>. `GEMINI_API_KEYS` (comma-separated) rotates keys when one hits its daily cap; `GEMINI_API_KEY` is the single-key fallback.

**That $0.50-a-map figure predates the correction below (2026-09-10) and is understated.** "1,810 out tokens per call" is `output_tokens` — the visible-candidates field `gemini_client._log_call` writes (`getattr(usage, "candidates_token_count", …)`, `gemini_client.py:384`) — not what Gemini bills. Billed output is `total_tokens − input_tokens`, which also carries the model's thinking tokens, and on every run since measured directly it has come to 3.5–4× the visible figure (see *Cost*, below, and the same note in `work/ocr/EVAL-BASELINE.md`). The exact 49-call sample this line was measured from is no longer isolable on disk, so it is not recomputed here; scaling the visible-output term by ~4× puts the honest figure nearer **$1.4 a map**, not $0.50. The `gemini-2.5-flash-lite` figure carries the same defect and is not restated, for the same reason — it has never been measured directly.

**Reading an R2-hosted map.** `fetch_crop` asks for an arbitrary region at an arbitrary scale; `worker/` renders nothing and serves only the tiles `vips dzsave` wrote, so every such request 404s and, until 2026-09-04, OCR failed on its first tile for all 39 georeferenced maps. `fetch_crop_level0` composes the region from the pyramid instead: scale factor from `scaleFactors` (degrading if the top one was advertised but never written), origin a multiple of `tile_size · sf`, region clipped to the image, and rendered `size = ceil(region_w / sf)` — a constant `256,` 404s on clipped edge tiles. `info.json` said `profile: level2` until 2026-09-14 and does not any more — it reports `level0` and lists only sizes that resolve — but nothing about the addressing changed, and `fetch_crop` still 404s. `iiif_tiles.py --self-check` covers the addressing.

**Overview resolution matters more than it looks.** `compute_tile_densities` measures local 8×8 std-dev, which at a heavy downscale reads dense city hatching as *smooth*. Measured on the 1882 Saigon cadastral, centre-tile vs edge-tile mean density was inverted at 600, 1024, 1513 and 1700px and only correct at 2048 — so `--auto-priority` on the old 1024px overview demoted the densest, most label-rich tiles. `OVERVIEW_WIDTH = 2048` in `ocr.py`; do not lower it. The companion colour/wash pass scored 0.000 on every tile of that sheet at every saturation gate, because its hue bands (60–260°) miss a warm-toned scan entirely — treat it as unmeasured.

**The layout pass.** `scout` returns `regions`: one labelled rectangle per part of the sheet — `sheet`, `main_map`, `title`, `legend`, `name_list`, `inset`, `scale_bar`, `north_arrow`, `stamp`. A sheet is not one thing, and tiling all of it reads the legend as if it were terrain, paying full price to OCR a key. `--save-triage` writes them to `maps.triage.regions` (migration 070) in source pixels, where `/scan?mode=prepare` draws them for a person to correct — the model proposes, a human decides, and a corrected region is marked `source: 'human'`.

Run it as a job (`kind = 'layout'`, the worker's default set) rather than by hand: the digitalize **Detect** button enqueues one and polls. `--save-triage` merges rather than replaces, so a re-run cannot discard somebody's neatline.

The payoff is `main_map`. `enqueue_ocr_all.mjs` crops to it in preference to the neatline, because the neatline is the *printed border* — a legend or a street index printed inside the border is inside the neatline too, and gets tiled at full resolution for nothing.

**Queueing a batch.** `scripts/enqueue_ocr_all.mjs` queues only sheets with a saved triage in `maps.triage` (migration 069) — the neatline, tile size, overlap and per-tile priorities someone set in `/scan?mode=prepare` and pressed **Save triage** on — and spreads them into the payload unchanged. A triaged sheet therefore runs with `--crop` and no scout pass, because there is nothing left to guess. `--untriaged` also queues the rest, which fall back to `--scout` and the defaults; `--dry` prints the split first.

**Two things mean "neatline" and they land in the same payload field.** `enqueue_ocr_all.mjs` means the sheet's own printed border, read from `maps.triage`. `scripts/collection_aoi.mjs` means a study area, computed from an AOI polygon through the inverse georeference — which is why it queued all six District 4 sheets while zero of them carried a saved triage. Both are correct and neither reads the other. Unify them only with that distinction in hand.

`--auto-priority` fills the Triage grid without a human: text density decides blank → skip and sparse → low_res, then a colour pre-pass (`compute_tile_colours`, HSV) demotes any tile that is mostly water or vegetation wash one further step. Demotion only — a misread wash costs resolution, never a tile — and a monochrome scan scores ~0, so nothing happens on grey maps. `--wash-above` (default 0.6) is the threshold.

Useful `batch` flags: `--row-sequence` / `--no-row-sequence` (default on, `--max-row-frames 4`), `--adaptive`, `--target-calls N`, `--smart-grid`, `--skip-sparse`, `--auto-priority`, `--wash-above`, `--aoi-px x0,y0,x1,y1`, `--tile-overrides '{"x_y_w_h":"skip|low_res"}'`, `--crop x,y,w,h`, `--prior-run <dir>`, `--legend`, `--db`.

`--aoi-px x0,y0,x1,y1` limits a run to a study area (District 4 is the first one). It takes **source-image pixels, not lng/lat**: the Allmaps georeference lives on the JS side (`src/lib/server/transformer.ts`), so the caller warps the four WGS84 corners with `GcpTransformer.transformToResource` and passes the pixel bbox. `--aoi` exists only to fail with that instruction. The filter runs *after* `--auto-priority` / `--tile-overrides`, and only ever demotes: a tile overlapping the AOI keeps whatever priority it had, a tile outside becomes `skip`, and a tile straddling the boundary counts as inside. So an AOI covering the whole map changes nothing.

`--clahe` turns on an adaptive-contrast pre-pass before a tile's bytes reach the model. Faded colonial scans lose their thin hand-lettered toponyms into the paper: locally the ink-to-paper gap is a handful of grey levels while the sheet still spans the full range, so a plain histogram stretch does nothing and CLAHE equalizes per region instead. `--clahe-clip` (default 2.0) caps the amplification so flat paper between strokes does not become noise; `--clahe-grid` (default 8, or `RxC`) sets the region grid. It runs on **luminance only** — equalizing per RGB channel would move hue and saturation, and `compute_tile_colours` scores the water and vegetation wash in HSV. It is also applied after both tile caches and after the shared overview the colour pass reads, so the caches keep raw pixels, an A/B run reuses the same cached tiles, and the wash scores are structurally out of reach.

**Off by default, and it must stay off until it is measured.** The idea is borrowed from Pastmaps, which runs adaptive contrast on every sheet so computer vision can read faded copperplate, but borrowed practice is not evidence about *our* corpus. To measure it, run the eval set both ways against the ground truth in `work/ocr/EVAL-BASELINE.md`:

```bash
python work/ocr/scripts/eval.py --run-id baseline-noclahe
python work/ocr/scripts/eval.py --run-id baseline-clahe --clahe
```

Default it on only if recall improves and precision does not fall — a pre-pass that finds two more street names while inventing three is a loss. Record the numbers in `EVAL-BASELINE.md` either way, including a null result, so nobody re-runs this experiment blind.

### Files (`work/ocr/scripts/`)

| File | One line |
| --- | --- |
| `ocr.py` | The CLI: `scout`, `batch`, `layout`, the local passes, `--db` writes. Everything below is a helper it imports |
| `gemini_client.py` | Gemini wrapper: key rotation across `GEMINI_API_KEYS`, retries, model default |
| `prompt.py` | Versioned prompts `v1`–`v8`, `seq-v1`, `seq-v1-idx` + scout, the JSON schemas, and the canonical coordinate contract |
| `iiif_tiles.py` | IIIF tile fetcher and grid utilities: scale levels, level0 addressing, colour pre-pass, CLAHE. `--self-check` |
| `local_vision.py` | Offline passes with no API call (geometry, digits) that run free on the M-series |
| `cache.py` | Disk cache for Gemini results keyed by SHA256(image + prompt + model + schema version) |
| `supabase_client.py` | DB access with two transports: worker API (`VMA_API_URL` + key) or service key when run by hand |
| `join_labels.py` | Level-aware label ↔ footprint join (writes `footprint_id`). `--self-check` |
| `dictionary.py` | Offline gazetteer of every name read so far → `outputs/dictionary.{json,md}`. `--self-check` |
| `eval.py`, `eval_metrics.py` | The quality gate: score an OCR or seg run against reviewed ground truth. Baseline in `EVAL-BASELINE.md` |
| `modern_prior.py` | 2023 geodata (HCMC buildings, OSM) warped into a sheet's own source-pixel grid: blocks, road centrelines + junctions, built fraction, survivors. Saigon-only sources; **not** a positive seed source as-is — read its docstring on the epoch gap. `--self-check` |
| `backfill_full800.py` | One-off: store the `full/800,` derivative in R2 for every published map. `--self-check` |
| `fix_info_scalefactors.py` | One-off: drop scale factors a stored `info.json` advertises but the pyramid does not hold. `--self-check` |

### Local passes (no API — run on the M-series for free)

Two subcommands offload the geometry/digit parts of map OCR to local tools, keeping Gemini for semantic text (place names, legend descriptions). Both live in `work/ocr/scripts/local_vision.py`.

They need only `numpy`, `scipy`, `Pillow`, `pytesseract` + the `tesseract` binary (`brew install tesseract`) — **not** `google-genai`. The venv is created with `--system-site-packages` to reuse brew numpy/scipy/PIL, since Homebrew Python is PEP-668 externally-managed:

```bash
python3 -m venv --system-site-packages work/ocr/.venv
work/ocr/.venv/bin/pip install pytesseract

# Find legend/cartouche/title boxes (scipy ruled-rectangle finder)
work/ocr/.venv/bin/python work/ocr/scripts/ocr.py detect-layout \
  --map-id <uuid> --run-id <name>          # → runs/<name>/layout.json (legend_region boxes)

# Spot standalone numerals / legend refs (Tesseract, digit whitelist)
work/ocr/.venv/bin/python work/ocr/scripts/ocr.py numerals \
  --map-id <uuid> --run-id <name> [--db]   # → runs/<name>/numerals.json; --db writes category='legend_ref'
```

- `detect-layout` finds **bordered** boxes only; borderless legends fall back to a manual region or the whole-image legend pass. The regions feed the (Gemini) structured `legend` pass.
- `numerals` writes `category='legend_ref'` rows — a later join `legend_ref.text == legend_entry.number` links each map numeral to its legend entry (pure SQL, no model).
- `legend` (Gemini) reads a sheet's numbered legend into `{n, name, grid}` rows: `--regions x,y,w,h;…` (a sheet may print more than one block — see *Two printed indexes on one sheet* below; `--region` still works as a spelling of it), or omit it with `--map-id` to take every `legend` region the layout pass found. Also `--bilingual`, `--consensus N` (cross-check across N models and flag disagreements), `--db` → `category='legend_entry'`.
- All three accept `--local-image <path>` to skip IIIF entirely. Self-check: `work/ocr/.venv/bin/python work/ocr/scripts/local_vision.py`.
- **Known limit:** Tesseract single-digit recall is mediocre (rotated glyphs missed). Upgrade path if recall is too low — swap `spot_numerals()` for a PaddleOCR detector in a Python 3.11 venv, keeping the same `[{text, bbox, confidence}]` shape.

### Name dictionary

```bash
python work/ocr/scripts/dictionary.py            # → outputs/dictionary.{json,md}
python work/ocr/scripts/dictionary.py --self-check   # asserts only, no DB
```

One entry per distinct name across the whole corpus, with every sighting (map, year, run, confidence, source pixel). An offline artefact for review: OCR errors that are invisible one bbox at a time are obvious in an alphabetical list. `--min-confidence`, `--category` (repeatable), `--include-rejected`, `--include-furniture` (title/legend/other, excluded by default).

Diacritics are **not** folded — "Sài Gòn" and "Sai Gon" are different readings and the difference is the point. Entries whose only difference is accents are cross-linked in a "Same name, other accents" column instead, because a French label printed in caps loses its accents on the sheet itself. The `place_names` view (mig 067) makes the opposite call and folds them; it is the gazetteer of record, and ROADMAP item 4b is to rebuild this script on top of it rather than keep two normalisation rules.

### Label ↔ footprint join

```bash
python work/ocr/scripts/join_labels.py <map-id>       # link
python work/ocr/scripts/join_labels.py --self-check   # PIP + nesting assertions, no DB
```

Point-in-polygon assignment of each `ocr_extractions` row to the `footprint_submissions` polygon it names, writing `ocr_extractions.footprint_id` (migration `050_ocr_footprint_link.sql`, `ON DELETE SET NULL`). Level-aware: a bare numeral routes to a `building`, a name routes to the enclosing block; ties break to the **smallest** containing polygon. Rejected extractions never link; `category_validated` (the human fix) wins over `category`.

### Reading a sheet's margins: index, numerals, grid (measured 2026-09-10, 1959 Đô thành Sài Gòn)

The 1959 sheet was re-OCR'd after its scan was replaced with a 14000×10773 one.
Everything below is measured on that sheet, in one afternoon, and it changed
what the pipeline should do first.

**Ground per call is the lever, not the prompt.** At the default 2400px tile
that sheet is 5.7 km per Gemini call and returned ~1 usable label in the study
area; at `--tile-metres 1400` (a 1404px tile, rendered 1:1) the same crop
returned 627 rows. Pass `--tile-metres 1400` on any sheet whose m/px is
unknown — the rule only ever refines a tile, never coarsens it.

**`seq-v1` suppresses bare integers, and on an indexed sheet that is most of
the content.** "Do NOT extract bare integers inside plot areas" is right on the
1882 cadastral (wall-to-wall parcel numbers, and the eval gate) and wrong here:
`seq-v1` returned 11 numerals as leakage against its own instruction, filed
under `other`; `seq-v1-idx` (same prompt, suppression lifted) returned 114.
Choose per sheet — if the layout pass finds a numbered `name_list`, the sheet
has an index. Do **not** edit `seq-v1`; it is the measured gate.

**A printed table must never be shown to the model two column groups at a
time.** Asked for `{n, name, grid}` on a wide crop it renumbers from the first
number column it sees and pairs one group's names with the next group's
numbers — 156 rows, no gaps, no conflicts, and wrong in the tail. Voting across
overlapping windows does not fix it (it votes between two wrong bindings), and
pairing by returned bboxes does not either (the boxes are not that precise).
What works, and got 156/156:

1. Find the ruled columns locally, no API: a full-height ink column is a rule,
   and the repeating unit on this sheet is a ~537px name column plus three
   ~63px columns (number, grid letter, grid digit).
2. One call per column group.
3. Refuse the write unless the group's numbers come back contiguous.

**Keep the tile pass out of the printed blocks.** The tile grid covers the
whole crop, and on a sheet whose `main_map` region is its neatline the printed
legend and street directory are inside it. A tile of a directory shows
`52  C 10  Marché Central` and nothing in the picture says that 52 is a line of
a table rather than a numeral stamped on a building, so the whole directory
comes back as labels pinned to the margin: on the 1942 Saigon–Cho Lon sheet,
**1535 of 4052 rows** — 719 streets, 630 institutions, and the index column's
own 1…29 sitting in `legend_ref`. `ocr.py batch --exclude x,y,w,h;…` discards
reads whose centre falls in those rectangles (`tests` → `work/ocr/scripts/test_exclude_printed.py`);
`enqueue_ocr_all.mjs` fills it from every `legend` and `name_list` region the
layout pass found, so a triaged sheet gets it for free. Nothing is lost — the
`legend` and `street-index` passes read the same blocks as tables, with the grid
cell each line names. `scripts/oneoff/reject_printed_index_reads.mjs` rejects
the rows already written (dry run by default).

**Two printed indexes on one sheet.** The 1942 Saigon–Cho Lon sheet prints
**two** `legend` blocks, and until Sept 2026 `ocr legend` read one of them:
`--region` was singular and typed by hand, while `--exclude` was given both. So
the tile pass dropped the numerals inside block two and no structured pass ever
picked them up — erased twice. `--regions` now takes the list, and with
`--map-id` and no flag it reads every `legend` region the layout pass found;
`street-index` does the same over `name_list`, falling back to `legend`.

Reading both raises the question the numbers alone cannot answer. Either the
blocks **continue one sequence** — 1…99, then 100…236 — and joining a map
numeral to its entry by number is exactly right; or they are **two independent
tables both numbering from 1**, and that join hands one table's name to the
other table's numerals wherever they overlap. Merging keeps the first writer, so
nothing downstream can see it happen. The run answers it from the sheet's own
ink and says which case it is: `legend_block_collisions` flags a number two
blocks name **differently** (the name, not the number — the same line read twice
agrees with itself). Rows then carry `block=<i>` in `notes`, and only on a
multi-block sheet, so every single-block sheet reads exactly as before.
`ambiguousNumbers` in `src/lib/features/contribute/ocr/legendIndex.ts` is the
same check over the stored rows, and adds an `ambiguous-entry` flag to every
numeral of a contested number in the review table. Checks:
`work/ocr/scripts/test_legend_blocks.py` and `tests/ocr-suspects.spec.ts`.

**The printed index is an answer key.** It names every number that exists
(1–156 here) and gives each a grid cell, so numeral recall has a real
denominator and each miss has a place to look. The tile pass placed 104/156;
cropping the claimed cell and asking for that one number — a lookup, not a
search — took it to 144/156. Every hit is gated to the cell it was cropped
from, so a misread cannot enter as a plausible point. Two identical runs of the
same 18 cells returned 45 and 41 hits, so **run it twice and union**; a third,
finer pass returned 0.07 labels/call and is not worth making.

**Measure the grid, do not ask for it.** `ocr.py grid` read 12 rows `A…M` off a
2048px overview; the sheet has 9, `A…I`, no `J`. The margin tick labels give it
exactly — right-margin letters at y = 1345, 2350, 3351 … 9343, pitch ≈1000 —
and those labels are the border-grid rows a numeral sweep would otherwise
reject as furniture. Keep them. With the grid correct, an index entry whose
numeral was never spotted can still be placed at cell centre (~1 km), and the
grid arbitrates when one piece of ink is read as two different numbers: 14 such
collisions were resolved by asking which number's claimed cell contains the
point.

**Colour separates the two classes on this sheet**: index numerals are bold
black on a red building fill; the reference grid is thin magenta with labels
only in the margins. `iiif_tiles.compute_tile_colours` already exists, and a
colour test would beat a position rule tuned per sheet.

**Cost against value, per call, all on the same sheet:**

| step | calls | yield | per call |
|---|---|---|---|
| street index, both margins in bands | 14 † | 384 streets, each with a cell range | **27.4** |
| margin index, one group at a time | 16 | 156 entries + the number join | **9.8** |
| map body, 2 passes + merge | 72 | 627 rows | 8.7 |
| numeral pass (`seq-v1-idx`) | 36 | 114 numerals | 3.2 |
| cell sweep, ×2 for the union | 36 | 45 numerals | 1.3 |
| quadrant re-sweep (abandoned) | ~60 | 4 numerals | **0.07** |

† 14 **billed**, not the 15 the tool prints. `ocr.py street-index` counted
bands attempted, and a band whose crop and prompt are already in the
model-response cache returns before the call is logged — so it is free, and it
still yields its entries. Measured over
`outputs/34d4edb2-*/runs/streetindex-20260910/calls.jsonl`: 28 logged calls
across two passes of 14, split by a 127-second gap, against 15 bands per pass
derived independently from the region heights in `street_index.json`
(7853 px + 9221 px at `--band-height 1300 --overlap 150` gives 7 + 8). The
counter is now called `n_bands`, which is what it always was. No cost path read
it — `vma_worker.py` counts `calls.jsonl` lines — so nothing downstream was
wrong, only the number a person reads off the terminal.

So: margins before a second body pass, numerals twice and then stop, and hand
the tail to `?mode=shapes&tab=validate` — a person clicks the last twelve in a couple of
minutes, and no render size beats that. `pipeline_jobs.result` now carries
`calls`, `tokens`, `extractions` and `per_call` for every run (summed from the
`calls.jsonl` each run already writes), and `payload.max_calls` stops a plan
between steps, so a fleet run can spend a fixed budget per sheet instead of an
unbounded one on whichever sheet someone is watching. `enqueue_ocr_all.mjs
--max-calls N` sets it.

**The street index is the cheapest thing on the sheet, and the only free check
on everything else.** `BẢNG CHỈ DẪN ĐƯỜNG PHỐ` runs down both margins in two
798px columns — a four-column table: the road-type word alone (`Đường`, `Đại
Lộ`, `Bến`, `Rạch`, `Hẻm`), the name, then `TỪ` and `ĐẾN`, the grid cell the
street starts in and the one it ends in. `ocr street-index` reads it in
overlapping horizontal bands, ~27 rows per call:

```bash
work/ocr/.venv/bin/python work/ocr/scripts/ocr.py street-index \
  --map-id <uuid> --run-id <name> \
  --regions "350,2143,798,7853;12852,775,798,9221" [--db]
```

Omit `--regions` with `--map-id` and it reads every `name_list` region the
layout pass found, falling back to `legend` — on the 1942 sheet the layout pass
called both printed directories `legend`.

**15 calls, 384 entries, ~$0.03** — against the sheet's own claim of 384 named
streets. Every row carries a position, because the table states one: `--db`
writes each street's box as the union of its two cells, `notes` recording
`grid=C9→C10; cells=2/2`. A run of cells is not a point and the box says so; it
is also not the *neatline*-wide guess a name with no reference gets.

Two details that each lost streets silently. An end may itself name a run —
`J 5,6`, the form `ocr grid`'s own docstring uses — and taken literally it
resolved to nothing and the street was dropped from the run with no mark;
`_expand_ref` splits it, and `cells=<got>/<want>` in the notes says when the
grid could place only part of what the entry states. And entries merge on
`(generic, name)`, first writer wins, which is right for one directory read in
overlapping bands and wrong for two directories indexing two areas: a repeat
stating **different** cells is now reported at the end of the run instead of
being dropped as a duplicate.

**~$0.03 was a guess, not a measurement, and it was low either way (2026-09-10
correction).** `work/ocr/outputs/34d4edb2…/runs/streetindex-20260910/calls.jsonl`
holds two full runs of this command (28 logged calls — one band per pass is
served from the response cache and never reaches `calls.jsonl`, so 14 billed
calls per 15-band pass, not 15). Costed straight off that log at $0.75/$3.75
per Mtok in/out: **USD 0.24–0.27 billed** per pass (`total_tokens − input_tokens`,
thinking included) against **USD 0.08** read the old way, off `output_tokens`
alone. Cheap either way, but nearer a quarter than three cents.

The one-group-at-a-time rule above still holds but does not bite here: the table
is one column group, and the bands run across it. `TỪ`/`ĐẾN` arrive in separate
schema fields, so there is no pairing to get wrong — the probe band matched the
image on all 27 rows including the generic column.

**Then the two readings check each other.** Of 372 body labels that match a
directory row, **350 (94%) sit inside the cell range the index states** (±1
cell, since a street is labelled somewhere along its length, not between its
endpoints). Neither reading knows about the other, so that is a real
measurement: it validates the body pass, the index pass and the grid at once,
and the 22 that disagree are a review queue rather than a mystery. Read the
margins **first** — this is the denominator every later pass wants.

**Row `J` is the inset's grid, not a missing row.** Five directory rows and
index entry `44` reference `J1`/`J2`; the sheet's printed rows stop at `I`.
Refitting the row set against 373 observations settles it: `A…I` scores 310/373,
`A…J` scores the same only with a grid 9920px tall — past the bottom of the map
body. All six are on the southern waterfront (`Bến Mê Cóc`, `Bến Nguyễn Duy`,
`Bến Phạm Thế Hiển`, `Bến Phú Định`, `Đường Rạch Cát`, `Chợ Rạch Cát`), which is
what the inset at `[4634, 8747, 2338, 1249]` shows — a separate map continuing
the lettering. `_cell_rect` returns nothing for them rather than guessing, and
each is named in the run's output.

**Left undone on that sheet**: 12 of 156 numerals unplaced, all in the dense
`C8/C9/C10/D9` core except `44`, above. Two directory rows are unplaceable and
reported by name — `Đường Rạch Cát` (`J2`, the inset) and `Đường Lý Văn Phức`,
whose cells came back blank.

### Getting more out of OCR: what to do next, in order

Where the effort pays, measured on this corpus rather than reasoned about. Read
`work/ocr/EVAL-BASELINE.md` for the experiments themselves, including the
rejected ones — this section is the forward-looking half.

**1. Get a denominator before tuning anything.** The 1959 sheet's dedupe was
deleting real streets for a week and nothing failed: it held 452 street rows and
367 distinct names against the sheet's own printed claim of 384, which reads
like a good result. The bug was found by asking a different question — *is Lê
Lợi in the database?* — and it was not, nor Hàm Nghi, Công Lý or Phan Chu Trinh,
the four most prominent streets on the sheet. A sheet that prints an index or a
street directory tells you how many labels exist; read it **first**, and every
later pass has a score instead of a row count.

**2. Count distinct names, never rows.** Row count is the metric that hid the
bug, because a wrong merge removes a name and a shattered cluster adds rows, and
both move the total in directions that look fine. `_label_core` + `_fold` in
`ocr.py` give the comparison key; the number to watch is distinct cores.

**3. Ground per call is still the biggest single lever.** At the default 2400px
tile the 1959 sheet was 5.7 km per call and returned ~1 usable label in the
study area; `--tile-metres 1400` returned 627 rows from the same crop. Pass it
on any sheet whose m/px you have not checked.

**4. Build a per-sheet gate out of what the sheet already prints.** This is the
cheapest unexploited thing in the pipeline. `work/ocr/EVAL-BASELINE.md`'s ground
truth is 85 hand-validated labels on **one French sheet**, and it demonstrably
cannot see a Vietnamese failure: re-deduping it after the fix above moved recall,
char_acc, mean_iou and category_acc by exactly zero, while the same change
recovered 33% more distinct names on the 1959 sheet. `Rue Catinat` and `Rue
Charner` survive character comparison; `Đại Lộ Lê Lợi` and `Đại Lộ Lê Lai` do
not.

A printed street index fixes that for free:

```bash
work/ocr/.venv/bin/python work/ocr/scripts/eval.py index-agreement \
  --map-id <uuid> [--run-id <body run>] [--slack-cells 1] [--save]
```

Ground truth is the sheet's own `street-index-v1` rows — ~384 `name → cell-range`
pairs read for well under a dollar (~$0.25 billed, corrected — see the note
under *The street index is the cheapest thing on the sheet*, above), no human
labelling. Two numbers come out, and both are things the corpus never had:

- **`name_recall`** — of the names the sheet says it prints, how many did the
  body pass read? This is the denominator a row count never was.
- **`agreement`** — of the body labels that match a directory row, how many sit
  inside the range the index states? Two unrelated readings, so one number
  scores the body pass, the index pass and the grid at once.

Measured on the 1959 sheet, before and after the dedupe fix of 2026-09-10:

| | before | after |
|---|---|---|
| `name_recall` | 0.7493 (281/375) | **0.7947** (298/375) |
| `agreement` (±1 cell) | 0.9588 | 0.9434 |

The French gate moved by exactly zero on that change; this saw it. Agreement
dips slightly because 356 more body labels entered the comparison, fragments
among them — which is why both numbers are tracked and neither alone is the
score. `--slack-cells 0` asks the strict question (0.8679 on the same run);
±1 cell is the default because a street is labelled somewhere along its length
and the printed cell is itself approximate.

`--save` writes `work/ocr/index-baselines.json`, and a later run prints the
delta against it. `--pred-run-dir` scores a candidate run straight out of its
output directory, so a prompt can be measured without writing into the shared
table.

**Baselines recorded** (`work/ocr/index-baselines.json`, 2026-09-10):

| sheet | printed names | `name_recall` | `agreement` |
|---|---|---|---|
| 1959 Đô thành Sài Gòn | 375 | 0.7947 (298) | 0.9434 |
| 1968 Sài Gòn | 367 | **0.0245 (9)** | 1.0000 (9/9) |

The 1968 row is what the metric is for. That sheet holds **14** body labels
against 367 printed street names, so it has effectively never been read — which
was previously a hunch and is now a number, on a sheet already published and
georeferenced. Its 9/9 agreement is a small sample, but it says the grid and the
index are consistent, so a body pass can be scored the moment one runs.

**Which sheets can have this:** 7 of the 39 published maps carry a `name_list`
region, and 2 of those have a `triage.grid` — both are baselined above. The
other five (1799, 1878 Saigon; 1942, 1951 Hanoi; 1968 Hanoi) need `ocr grid`
first. Every sheet that gets a grid and an index read gains a permanent gate for
nothing.

**Table shape differs per sheet, and the layout is what to check.** 1959 prints
one four-column group down each margin, so horizontal bands across the whole
width are safe. 1968 prints the same `From`/`To` columns but as **four repeating
groups side by side** — the arrangement the rule above says never to show the
model at once — so it is read one group per call, which `--regions` already
allows (four x-offsets, each banded vertically). Two details that sheet also
needs: the window has to be wide enough to include the group's `To` digit, which
sits at its right edge, and the sheet prints an **em-dash** for its commonest
road type (`Đường`) and spells out only the exceptions. A dash generic is
dropped rather than mapped — which word it stands for is the sheet's business.

**5. Precision is uninterpretable while the ground truth is partial.** A correct
prediction absent from GT counts as a false positive, so anything that raises
recall lowers precision. Watch recall, `char_acc`, `mean_iou`, `text_recall@0.3`
and the distinct-name count. Do not tune against precision, and do not read its
drop as a regression.

**6. `_CLOSE_FACTOR` is a per-sheet knob, and it is meant to be turned.** It is
how far apart two boxes may sit and still be one label, in multiples of the
text's height, and the right value depends on the sheet's scale and scan
resolution — neither of which the code can see. On the 1959 sheet 2.5 → 6.0
moves distinct names by two and row count by 12%; 4.0 is what is committed.
Tune it by re-merging from cached tiles (free) and reading the distinct-name
count, not the row count.

**7. Then the things that need a model change, roughly by value:**

- **`label_w` / `label_h` stay null** because the model returns an axis-aligned
  box plus an angle, not an oriented box's own dimensions. The mig-076 columns
  and the review UI's rotated handles are both waiting on a prompt that asks for
  width-along-the-baseline. Nothing in the corpus can fill them today.
- **The inset needs its own grid.** Six references on the 1959 sheet name a row
  `J` its printed grid does not have; all six are on the southern waterfront,
  which is what the inset at `[4634, 8747, 2338, 1249]` shows. `triage.grid` is
  one grid per sheet, so an inset's references cannot be placed at all.
  `SavedTriage` would need a grid per region.
- **Colour separates the label classes** on an indexed sheet: index numerals are
  bold black on a red fill, the reference grid is thin magenta with labels only
  in the margins. `iiif_tiles.compute_tile_colours` already exists, and a colour
  test beats a position rule tuned per sheet.
- **Category confusions are concentrated**, not diffuse:
  `building↔institution` is 6 of 9 errors on the gate sheet. A worked example
  pair in the prompt is cheaper than anything structural.

**8. Do not re-attempt** neighbour-window batching, the fragment join as a
recall lever, or a resolution bump as a default. All three are measured
regressions with the reasons written down in `work/ocr/EVAL-BASELINE.md`. Read
it before touching the core loop.

### Design notes

- Gemini bboxes are **0–1000 normalized space**; render with `img_dim / 1000`.
- `ocr_extractions.global_x/y/w/h` already store full-image pixel coords.
- Model: `DEFAULT_MODEL = "gemini-3.8-flash"` (`work/ocr/scripts/gemini_client.py`), overridable per-subcommand with `--model`. Key in `.env` as `GEMINI_API_KEY` / `GEMINI_API_KEYS` (comma-separated for rotation). `ocr.py list-models` enumerates what the key can actually reach.
- Outputs versioned at `work/ocr/outputs/<map_id>/runs/<run_id>/` with `run_config.json` for reproducibility.
- Prompts in `work/ocr/scripts/prompt.py`: `v1`–`v8`, `seq-v1`, `seq-v1-idx` and `scout`. **`DEFAULT_PROMPT = "seq-v1"`** since 2026-09-08 — see *Prompt* above for what it changed. This line claimed `v8` until 2026-09-10, two sections after the one that had it right, which is worth knowing because a stale default here is unfalsifiable from the outside: a run records the version it was handed, so a doc naming the wrong one just makes every run look deliberate. v8 was the high-recall revert of v6's 0.5 confidence floor, and it **failed the gate** on the row-sequence path (recall −0.14, `char_acc` −0.027) — do not restore it as the default. `prompt.py:786` is the value; `work/ocr/EVAL-BASELINE.md` is the measurement.
- **The selected prompt only started reaching the row-sequence path on 2026-09-08.** `extract_labels_sequence()` carried a hardcoded fallback prompt naming an "1882 Saigon cadastral map" and `cmd_batch` passed no prompt, so the production default sent that fallback for every sheet — 1968 Vietnamese ones included — while each tile's `_meta` recorded `"prompt": "v8"`. The caller now composes `PROMPTS[<version>] + sequence_frame_rules(n)`, `user_prompt` has no default, and `test_prompt_plumbing.py` fails if either regresses. Every run before that date was v8 in name only; do not read `_meta.prompt` on an older run as evidence of which prompt was sent.
- `clean` writes to `ocr_extractions` (correct target for the digitalize review UI); legacy `dedup` writes to `label_pins`.

### Sizing a grid from the sheet's own scale (2026-09-10)

`work/ocr/scripts/scale.py` reads the ground control points off the map's Allmaps
annotation and returns metres per source pixel. The annotation was already being
fetched — `iiif_tiles.get_iiif_base_from_allmaps` pulls it and reads one field —
so the scale cost nothing new to obtain. Three sheets, all confirmed against
tile sizes that had been chosen by hand: 1882 cadastral 0.343 m/px, 1959 Đô
thành Sài Gòn 0.999, 1968 Sài Gòn 1.273.

```bash
# What a run would do, for nothing: two HTTP GETs, no model call, no tile fetch.
python work/ocr/scripts/ocr.py scale --map-id <uuid>
python work/ocr/scripts/ocr.py scale --all          # every georeferenced sheet

# Size the grid from the ground instead of from a pixel count picked by hand.
python work/ocr/scripts/ocr.py batch --map-id <uuid> --tile-metres 1400
```

`--tile-metres` overrides `--tile-size`, `--overlap` and `--render-size`, wins
over `--target-calls`, and falls back to `--tile-size` *and says so* when the
georeference cannot support it. Three GCPs are enough (thirteen sheets in the
corpus carry exactly three); what it refuses is control points that are nearly
collinear, since those fit a line and the cross-axis scale they imply is noise.
The derived `tile_size`, `overlap`, `render_size`, `tile_metres` and
`metres_per_pixel` all land in the run's `run_config.json`.

Two bounds are worth knowing because they change what the flag does rather than
just trimming it. A **tile floor of 640 px** stops a coarse sheet asking for an
absurd grid: the 1930 Giadinh survey is 8.5 m in every pixel, where 1400 m of
ground is a 167 px tile and 8,175 calls to read a road map whose labels are
towns. When the floor binds, `TileFit.holds_target` is false and the tool prints
the target that *would* hold. And above **1.1 m per source pixel** the scan is
the ceiling and no flag moves it — `ocr.py scale --all` ends with that list (16
of the georeferenced sheets, today). 1959 at 0.999 m/px reads 0.712 of its
printed names in one pass; 1968 at 1.273 reads 0.327. Two points, so treat it as
a flag to raise at triage, not a refusal.

**The scout now proposes the grid and the priorities.** It already fetched a
full-sheet overview and located the layout regions, which is everything a tiling
decision needs, so `scout` writes `tiling` and `priorities` into `scout.json`
(and to `maps.triage` with `--save-triage`) instead of leaving the tile size to
be picked by hand and the priority grid to be derived inside the batch run, at
spend time, where nobody reviews it. It crops to `main_map` when the layout pass
found one, for the same reason `tilingCrop` does. It refuses to propose
priorities from an overview under 2048 px wide: below that the density signal
**inverts** and rates the dense city centre lower than the margins, so the
proposal would skip exactly the tiles worth reading.

### Two corrections this work forced (2026-09-10)

**`--render-size` was inert, twice over, and every render-size result before this
date is void.** First the cache: the tile PNG key was `x_y_w_h_tile.png` with no
render size in it, so once a sheet had been tiled *any* later run was served
those bytes no matter what `--render-size`, `--low-res-render` or `--adaptive`
asked for. Not overridden — silently ignored, which means a run that changed one
reported a number it had not measured. The key now carries the rendered width
(`x_y_w_h@1024_tile.png`), a legacy file is reused only when it happens to hold
the requested size, and `work/ocr/scripts/test_tile_cache.py` is the check that
fails if the render size falls out of the key again. Legacy files are read but
deliberately never renamed: these directories are shared with a running worker.

Second, and more surprising: **render size barely matters at the API.** Measured
on the 1882 gate sheet, a 2400 px frame and a 1024 px frame of the same tile
cost the same ~1032 input tokens, because the image is normalised to a patch
budget before the model sees it (1032 tokens is four 768 px patches, so the
effective ceiling is around 1536 px — that step is inferred from the token
count, not measured directly). Scores moved a wash: matched 71 → 73,
`text_recall@0.3` 0.906 → 0.878, 13% more wall clock. `scale.py` therefore caps
render at 1536 as a *cost* measure and never upsamples.

The useful consequence is the one to carry forward. If the frame is normalised
to a fixed budget whatever its pixel size, then the only thing setting how much
detail reaches the model is how much **ground** is inside the frame — which is
why tile size is the lever this document has always said it is, and why no flag
rescues a coarse scan.

**And the 1959 number is settled, 2026-09-10: both figures were right, for
different scans.** § *Full resolution* above says the 1959 sheet is 2.80 m/px;
`scale.py`'s GCP fit says 0.999. Neither estimator is wrong, and the 2.8x was
never a disagreement about method — the two numbers describe two different
digitisations of the same sheet.

`work/analysis/district4/README.md` states the scan it measured: 1959 is
"5000x3790, Virtual Saigon/IRD, 2.80 m/px". At 5,000 px that is 14.0 km of
ground, which is right for the Đô thành. The scan the OCR pipeline reads is
much larger: the crop in `work/ocr/outputs/34d4edb2-*/runs/idx-20260910/run_config.json`
is `1148,775,11704,9221`, which alone puts that image at 12,852 px wide or
more. The exact figure is **14,000 x 10,773**, and this file already said so
340 lines above -- "the 1959 sheet was re-OCR'd after its scan was replaced
with a 14000x10773 one" -- with `scale.py`'s own self-check fitting
`(0.999, 14000, 10773)` for it. The two figures reconcile exactly: 14,000 px
at 0.999 m/px is 13,986 m, 5,000 px at 2.80 m/px is 14,000 m, and 14000/5000
is 2.80 to the digit. The same 14 km of city, twice.

**The answer was in this file the whole time, 340 lines from the question.**
The paragraph this replaces asked whether one of two estimators was broken
while a line further up recorded the scan replacement that explains both. A
figure stated without the scan it was measured on cannot be checked even by a
reader holding the evidence.

`tests/mpp-parity.spec.ts` now pins the two estimators against one sheet's real
GCPs: they agree to **0.24%**, and the residual is the degrees-to-metres
constants each carries rather than the method. They were never 2.8x apart on one
annotation; they were compared across two scans, and nobody noticed because
**neither figure said which scan it came from.** That is the fault worth fixing
in prose: a metres-per-pixel figure needs the pixel dimensions of its scan
written beside it, or it cannot be checked or compared later. This one survived
in these docs for weeks.

So the derived claims in § *Full resolution* — the "6.5 m/px delivered", the
"cannot resolve a street name" — were true of the 5,000-px scan and are **stale,
not wrong**. At 0.999 m/px the stock 2400/1024 ratio delivers about 2.34 m/px.
`work/analysis/district4/README.md`'s resolution table, its "spend the saving on
resolution" advice and its conclusion that 1959 needs "a new digitization, not a
re-download — an acquisition question, not a pipeline one" are all downstream of
the thin scan; for 1959 that acquisition question looks already answered by
whatever supplied the larger one. That file has not been revised.

Neither implementation was changed, and neither should be deleted on the
strength of the other.

Scripts: `ocr.py` (CLI), `gemini_client.py` (key rotation + retries), `iiif_tiles.py` (crop fetch, IA fallback, IIIF v2/v3 detection), `supabase_client.py` (direct REST), `prompt.py`, `local_vision.py`, `join_labels.py`, `eval.py` + `eval_metrics.py`, `cache.py`, `scale.py` (metres per pixel from the georeference; `python scale.py` self-checks). Self-checks, all offline: `python scale.py`, `python eval_metrics.py`, `python test_prompt_plumbing.py`, `python test_tile_cache.py`.

## NLV press harvest (`scripts/scout_nlv_press.mjs`)

The National Library of Vietnam's newspaper archive (`baochi.nlv.gov.vn`, 81
titles, 1865–2013) has no API, but it runs **Veridian**, whose search is a plain
GET and needs no session:

```
baochi/cgi-bin/baochi?a=q&r=<1-based>&results=1&txq=<query>&txf=txIN&ssnip=img&o=50
                     &puq=<publication id>&dafyq=<from year>&datyq=<to year>
```

`r` is the index of the first result and `o` the page size (50 is the largest the
form offers). The script pages that, parses the results HTML, and appends
`work/press/nlv.jsonl` — one row per `oid`, the archive's own article key, deduped
against what is on disk. Neither the jsonl nor `--images` output is in git.

```bash
node scripts/scout_nlv_press.mjs --selftest
node scripts/scout_nlv_press.mjs --pubs                     # the 81 titles + ids
node scripts/scout_nlv_press.mjs --queries scripts/nlv-queries.txt
node scripts/scout_nlv_press.mjs '"bản đồ"' --pub RbD,WHfY  # southern papers only
node scripts/scout_nlv_press.mjs '"bản đồ"' --from 1920 --to 1945
node scripts/scout_nlv_press.mjs --report
```

Measured 2026-09-13: the fifteen phrases in `scripts/nlv-queries.txt` are **2,921
rows in about 90 seconds**, every query paged to 100%.

### The app queries it directly too

`src/lib/server/press.ts` used to reach the archive through
`baochi-tvqg.vercel.app`, the endpoint behind
<https://hanoimaps.github.io/news>. That site
(`github.com/hanoimaps/hanoimaps.github.io`, one repo, author Tran Minh Tri)
contains **no NLV code at all** — it is 150 lines of `fetch()`; the whole proxy
is a closed Vercel function. It is 8–16 s per call against 3–5 s direct
(up to 20 s on a cold CGI — the archive's own variance, not the page size),
states no result total, and exposes none of the filters. `/api/press` now queries the
library directly, which also made two things possible:

- **A decade curve for free.** The results page carries a decade facet, so
  "when was this place in the news" comes off the same response as the
  clippings — no second request. It is returned as `curve.nlv` and drawn as a
  strip above the list in `PressPanel`. Gallica has no facet and a curve there
  would be one request per decade, so the curve is the Vietnamese press only
  and the caption says so.
- **Thumbnails that are the clipping.** Each result states `crop=x,y,w,h`, the
  archive's snippet box — ~120 kB against ~1.4 MB for the whole newspaper page
  the panel used to load. It is the matched line for an advertisement but the
  article's *heading* for an article-level hit, so it is a thumbnail, not proof
  the phrase is in the picture — see the place report below.

**The archive answers on http only** — there is no https listener. A server-side
subrequest is fine with that, but a browser on an https page blocks a
mixed-content image, so thumbnails still go through the hanoimaps proxy, which
is https and passes `crop` straight through. That is now the only thing the
proxy is used for.

### Three things that decide what can be collected

- **`txq` ANDs words. It does not match phrases.** `bản đồ` and `đồ bản` both
  return **15,154** — every page carrying *bản* and *đồ* anywhere on it, nearly
  all of it noise. Quoting asks for the phrase: `"bản đồ"` is **838**. Every line
  in `scripts/nlv-queries.txt` is quoted for that reason, and the count beside
  each line is its measured total. An unquoted query is a different and much
  noisier question; the 74,524 "results" the unquoted list first reported were
  this mistake.
- **Geography is not a query term.** `"bản đồ" "Sài Gòn"` is 41 rows: a Saigon
  paper printing a city map rarely names the city in the same breath. The paper
  itself is the evidence of where, so the HCMC corpus is a **publication** split —
  `--pub`, or `scripts/nlv-southern-pubs.txt`, whose ids `--report` subtotals.
  Of the 2,921 rows, **928 are southern press, 1890–1988** (Sài Gòn 302, Công luận
  báo 177, Sài Gòn Giải phóng 77, Lục Tỉnh Tân Văn 70, …). That file is tagged by
  eye — the archive publishes no place-of-publication field.
- **There is no text, only the scan** — and its coordinates. A result carries the
  headline, the document type, the publication, the date (packed into the `oid`,
  so no Vietnamese date parsing), and `crop=x,y,w,h`: the archive's snippet box,
  which the proxy throws away. Both the crop
  and the full page come off the same image server:

  ```
  baochi/cgi-bin/imageserver/imageserver.pl?oid=<oid>&area=1&crop=<x,y,w,h>&width=<w>&color=all&ext=jpg
  baochi/cgi-bin/imageserver/imageserver.pl?oid=<oid>&area=1&width=2000&color=all&ext=png
  ```

  Full page at 2000px is ~220 kB and ~1.7 s; a crop is ~11 kB and ~0.3 s.

### Ceilings

- **Politeness, not throughput.** This is a national library's public search.
  Sequential, one request at a time, 1.2 s apart, one retry. Do not parallelise.
- **`--max` is a per-run page budget, not the size of the archive.** Each (query,
  publication, year-range) pair's next `r` is remembered in
  `work/press/offsets.json`, so re-running the same list continues where it
  stopped rather than re-paying for pages it already has. `--restart` ignores it.
- **The parser is regexes over Veridian's HTML.** `--fixture` saves one results
  page to `work/press/fixture-results.html` and `--selftest` pins the parser
  against it, asserting a full page's worth of rows and a non-zero total — so a
  template change fails loudly instead of reading as an archive with nothing in
  it. `--selftest` exits non-zero. Re-run `--fixture` if the page size changes.

## Legend timeline (`scripts/legend_timeline.mjs` + `legend_press.mjs`)

Four Saigon sheets carry a numbered legend that OCR has read, which is four dated
lists of the same city's institutions:

| sheet | year | entries | language |
|---|---|---|---|
| Plan de la Ville de Saigon | 1878 | 29 | French |
| Saigon - Cholon | 1923 | 182 | French |
| Plan de Saigon - Cho Lon | 1942 | 235 | French |
| Đô thành Sài Gòn | 1959 | 156 | **Vietnamese** |

`legend_timeline.mjs` matches them to each other; `legend_press.mjs` hangs a
per-decade press curve off each match, from the NLV (Vietnamese) and Gallica
(French) archives. Output is `work/legend/{entries,timeline,press,baseline}.json`,
none of it in git.

```bash
node scripts/legend_timeline.mjs --selftest
node scripts/legend_timeline.mjs                 # read the DB, match, report
node scripts/legend_press.mjs --baseline         # the corpus's own shape, once
node scripts/legend_press.mjs --threads cross    # only threads crossing 1959
node scripts/legend_press.mjs --report           # normalised; --raw for counts
```

### Matching across a language change

The 1959 sheet renamed everything, so this is not a string join. Both languages
write a legend entry as `<type> <proper name>`, and the proper name stays a proper
name across the rename — `Marché de Binh Tây` / `Chợ Bình Tây`, `Hôpital Grall` /
`Bệnh-viện Đồn Đất (Grall)`. So the key is **(canonical type, folded proper
name)**, with a ~27-word French↔Vietnamese type lexicon (`Marché↔Chợ`,
`Hôpital↔Bệnh-viện`, `Cimetière↔Nghĩa-địa`, `Commissariat↔Cảnh-Sát-cuộc`) and
nothing else translated. An institution whose *name* also changed lands in the
unmatched list rather than being guessed at.

Measured: 602 entries → 447 threads, 85 on more than one sheet, **12 surviving
into the 1959 Vietnamese legend**.

Three things the lexicon has to get right, each of which failed silently first:

- **Longest pattern first.** `bảo-sanh viện` must beat `viện`, `palais de justice`
  must beat `palais`, and `poste de police` must beat `poste` — a police post typed
  as a post office can never meet a 1959 `Cảnh-Sát-cuộc`. 17 entries were wrong
  this way. `bureaux` is listed beside `bureau`: the 1923 sheet uses the plural.
- **The connector comes off the name, not just the key.** `Marché de Binh Tây` →
  `Binh Tây`. The name is what gets sent to Gallica, and `adj "de Binh Tay"` is a
  different phrase — leaving it on cost two thirds of the hits.
- **Threads partition the entries.** A parenthetical naming another thread is a
  **link**, never a merge. `(Grall)` is one-to-one and is a rename; the seven 1942
  cemeteries carrying `(Phú Thọ)` are a consolidation into one 1959 municipal
  cemetery, and merging flattened that into the first case while claiming the same
  1959 row seven times. The selftest asserts the partition.

### Press curves, and why they are normalised

`legend_press.mjs` queries the **proper name**, not the whole entry: the type word
is noise the period press does not repeat (`"Chợ Bình Tây"` is 4 hits, `"Bình Tây"`
is 60). One NLV request returns the whole curve — Veridian's results page carries a
decade facet with counts. Gallica has no facet, so it is one request per decade.

- **Every Gallica query is scoped to Saigon** (`and (gallica adj "Saigon")`).
  Gallica is all of France: `Cimetière Européen` scored 52,075 before this. Querying
  the *full* entry instead does not work — the press writes `marché de Binh-Tây` with
  its own accents and hyphens, so `adj` over four words returns 0 where the name
  alone returns 145.
- **Specificity is measured, not guessed.** One extra request per name compares its
  scoped total against its unscoped one: `Binh Tay` 0.77, `Européen` 0.26. Under 0.4
  the row is flagged, because that curve is the word and not the place.
- **The numbers are corpus-corrected before they are read.** Both archives thin
  out after 1940 for reasons that have nothing to do with Saigon's markets, so
  every curve is divided by its archive's own shape per decade. The two
  denominators are **different universes** and are not comparable with each
  other — every Gallica query is already Saigon-scoped, so its baseline is
  documents naming Saigon (20,672); the NLV queries are unscoped, so its baseline
  is `"và"`, the commonest Vietnamese word, standing for how much text the archive
  holds per decade (196,639 — 80,288 pages for the 1930s against 3,676 for the
  1960s). **Not `"Sài Gòn"`**: as an exact phrase that is 21 hits in the whole
  1930s, because the period press wrote *Sàigòn* and *Sài-gòn*, and using it put
  normalised values above 1,000‰.
- `--report` then **indexes each row 0-99 against its own peak**, which is what
  makes the shape readable: per-mille is honest but unreadable on the NLV side,
  where every single place is a vanishing fraction of all Vietnamese print.
  `--rate` shows the per-mille and `--raw` the counts. A decade the baseline does
  not cover prints `?`, never `0` — Gallica is only asked about 1860–1959.
- The CQL builder is a **second copy** of the one in `src/lib/server/gallica.ts`
  (a `.mjs` script cannot import the TypeScript). `--selftest` pins it against the
  exact string `tests/press.spec.ts` asserts, because a drift between them would
  look like an archive with nothing in it.

Politeness is the same rule as the NLV harvest: sequential, ~1.2 s apart, one
retry, two public archives.

## Place report (`scripts/place_report.mjs`)

A cited, dated evidence report for one place from both period archives.

```bash
node scripts/place_report.mjs --selftest
node scripts/place_report.mjs "Khánh Hội" --max 14
node scripts/place_report.mjs "Khánh Hội" --variants "Khanh Hoi,Khánh-Hội"
```

Writes `work/reports/<slug>.md` (gitignored): the decade curve, a synthesis, then
every source numbered with its date, archive and URL. The synthesis is written by
Gemini from the evidence table **and nothing else**, with `[n]` citations into it,
so a reader checks rather than trusts.

The two archives answer in different media, and that is the whole design:

- **Gallica** has OCR'd full text, so `services/ContentSearch` returns the actual
  sentence — quotable as it stands.
- **The NLV returns no text at all.** Each clipping is *read* from the scan by a
  vision model before it can be cited, and every entry links its image.

Three things this gets right that a naive version gets wrong, all of them silent
failures that return confident, irrelevant evidence:

- **All three endpoints match loose words unless told otherwise, and each spells
  it differently**: NLV `txq` takes `"…"`, Gallica SRU takes `gallica adj "…"`,
  Gallica ContentSearch takes `"…"`. Unquoted, ContentSearch for `Khanh Hoi`
  returns 18 hits on *quan*, *Quant* and *quand* and one on the place.
- **The crop is not always the match.** Veridian crops the matched line for an
  advertisement but the article's *heading* for an article-level hit — the 1918
  *Lục Tỉnh Tân Văn* hit crops to the section header "TẠP TRỞ (Variétés)", which
  says nothing about the place. So the crop is widened for context and the model
  is asked whether the name is actually visible; on the Khánh Hội run **8 of 14
  were not**, and those are printed as "the name is not visible in this crop"
  rather than quoted as though the headline were the source.
- **A catalogue hit with no locatable sentence is a lead, not evidence**, and is
  dropped — so the Gallica count is smaller than the catalogue would report.

Even with all three, `adj "Khanh Hoi"` still matches Vietnamese prose where
*Khánh* is followed by *hỏi* ("Khánh asked"), because Gallica's index is
unaccented. The Khánh Hội synthesis caught those itself and named them as
typographical matches — which is the argument for the numbered table sitting
under the prose rather than instead of it.

## MapSAM2 inference (`work/MapSAM2/`)

SAM2/MapSAM2 segmentation: IIIF tiles → masks → polygons → `footprint_submissions`. Colab (GPU) or local M1 (base SAM2 only).

No venv is checked in or currently set up for this pipeline — create one per your platform and install the SAM2 deps. Training/LoRA details, the paper reading and the improvement backlog are in **`work/MapSAM2/TECHNICAL.md`**; Colab config is in `work/MapSAM2/VMA_SETUP.md`.

```bash
# Local test (base SAM2, small region)
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/sam2.1_hiera_small.pt \
  --region 4800,4300,1024,1024 --out-json test.json --preview

# Full Colab run with LoRA + OCR seeds + Supabase write
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/mapsam2_lora.pth \
  --lora --mapsam2-dir /content/MapSAM2 \
  --mode prompted --ocr-run-id <run_id> \
  --tile-size 1024 --overlap 128 --text-mask --watershed \
  --out-json footprints.json --write-supabase

# The 1882 cadastral, prompted from both seed sources. Generate the prior first
# (free, local, no GPU): modern_prior.py --map-id <uuid> --blocks --out <dir>
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
  --checkpoint /path/to/mapsam2_lora.pth --lora --mapsam2-dir /content/MapSAM2 \
  --mode prompted --ocr-run-id post0910 --prior <dir>/blocks.geojson \
  --tile-size 1024 --overlap 128 --text-mask --watershed \
  --out-json footprints.json --write-supabase

# Evaluate (SODUCO F1=0.59 baseline)
python work/MapSAM2/evaluate.py --predictions footprints.json --map-id <uuid> [--iou-thresholds 0.5,0.75]
```

Key flags: `--mode automatic|prompted`, `--lora`, `--encoder vit_s`, `--mapsam2-dir` (path to the **upstream** MapSAM2 clone), `--text-mask` (erase OCR bbox regions), `--watershed` (Meyer post-processing), `--region x,y,w,h`, `--device cpu|cuda|mps`, `--prior <blocks.geojson>`.

Modes: `automatic` = SAM2AutomaticMaskGenerator grid-scan; `prompted` = SAM2ImagePredictor with box seeds, which need **`--ocr-run-id` or `--prior` or both** (best with LoRA).

**Two seed sources, and on any sheet so far the second is the larger one.**
`--ocr-run-id` seeds from `ocr_extractions`, area categories only, and those
seeds carry their label so the polygon is named at birth. `--prior` seeds from
`modern_prior.py --blocks` — 2023 buildings buffer-dissolved into blocks and
warped into the sheet's own pixel grid — and those arrive nameless, so nothing
downstream stamps a name on them. They **union**, they do not replace: a block a
label already sits on is worth prompting from two boxes rather than one. Measured
on the 1882 cadastral: run `post0910` yields **92** area seeds after clipping to
`main_map`, the block prior **965** from 52,431 modern buildings — that count is
at `BLOCK_BUFFER_M = 4`, and it moves with that value, so read the ratio rather than the number.

`load_seeds_from_prior` had existed since the module was written and had no
caller until 2026-09-10; `--prior` is that caller. The **worker does not forward
it** — `_seg_argv` builds its argv from a fixed list of payload keys, and a
prior is a local file path belonging to the machine rather than to the job, the
same reason `--tile-metres` is not forwarded either. A Colab seg run that wants
a prior passes it by hand.

Scripts: `inference_tiles_as_video.py` (orchestrator; `--write-supabase` also advances `map_pipeline_status` seg_queued → seg_done), `masks_to_polygons.py` (`mask_to_polygon`, `masks_to_polygons` IoU dedup, `shift_polygons`), `evaluate.py` (F1 + geometric quality vs `footprint_submissions` status=verified).

Polygons written to `footprint_submissions.coords` as `[[x,y],...]` pixel-space arrays.

## Pipeline stages (`map_pipeline_status.stage`)

`idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported`

Advances automatically when OCR batch (`--db`) or SAM2 inference (`--write-supabase`) writes. Manual transitions via PATCH `/api/admin/maps/[id]/pipeline`.

## Eval harness (`work/ocr/scripts/eval.py`)

The gate for any core-pipeline change: baseline, refactor, compare. Scores a run against the ground truth the HITL review already produces — validated OCR extractions and verified footprints — so no separate labelling step is needed. Needs `shapely` (seg polygon IoU) + `requests`; `eval_metrics.py` holds the pure scorers (self-check: `python work/ocr/scripts/eval_metrics.py`).

```bash
# OCR: a run's raw extractions vs human-validated rows (box IoU + char-acc)
python work/ocr/scripts/eval.py ocr --map-id <uuid> --run-id <run> [--iou 0.5]

# Seg: predicted footprints vs verified/consensus footprints (polygon IoU)
python work/ocr/scripts/eval.py seg --map-id <uuid> \
  [--pred-status submitted] [--gt-status verified,consensus] [--iou 0.5]

# Offline, no DB — score two JSON files directly
python work/ocr/scripts/eval.py ocr --pred-file p.json --gt-file g.json
```

Reports precision / recall / F1 / mean IoU (+ char-acc for OCR). Reads only, never writes. Distinct from `work/MapSAM2/evaluate.py`, which scores a `predictions.json` against a map rather than against DB ground truth.

**Recorded numbers and the one rejected experiment live in `work/ocr/EVAL-BASELINE.md`** — baseline recall/char-acc/mean-IoU on map `0e02b9d9…`, why `precision` on a partial ground-truth set is not trustworthy, and why neighbour-window batching was built, measured (−16 pts recall) and reverted. Row-sequence stays the default.

---

# Design rationale

Why the two pipelines are shaped the way they are, and what the intended end state is. Merged here from two now-deleted notes — `work/PIPELINE_INTEGRATION.md` (MapSAM2 paper reading, Xia et al. 2025, arXiv:2510.27547) and `work/ocr/TECHNICAL.md`; recover the originals from git history if needed. Historical — parts have shipped, parts have not; the *Status* lines say which.

## Tiles-as-video

The MapSAM2 paper's unifying insight: treat a set of static tiles from one map as a **video**, so SAM2's memory attention shares context across tiles instead of segmenting each in isolation. The paper measures memory attention alone at **+14.3% IoU on vineyards, +16.1% on railways**.

**Status: shipped in shape, not in mechanism.** `inference_tiles_as_video.py` is the VMA entry point and tiles the region sequentially, but still runs SAM2's default FIFO memory. The paper's **self-sorting memory bank** (MedSAM-2, Zhu et al. 2024) is the open change:

- admit candidate embedding `E_t` if IoU confidence `c_t` > threshold;
- keep the top-`K` most **dissimilar**, `D_i = Σ_{j≠i}(1 − sim(E_i, E_j))`, `M_t = TopK(D_i)`;
- for the next tile `F_{t+1}`, resample the top-`k` most **similar**, `p_{i,t} ∝ sim(F_{t+1}, E_i)`.

Highest single-change EV in the backlog, and the most complex.

## Gemini as the prompt source

The paper uses a fine-tuned YOLO to produce instance-level bbox prompts, and shows prompt quality is worth **+12.8% F1** (holding the segmenter fixed, varying only YOLO's training size). VMA substitutes Gemini:

- open-vocabulary, no training, several categories in one call;
- returns the **text** as well as the box — one call, two signals, so OCR and prompt generation are the same pass;
- on a corpus of ~46 annotated Saigon footprints, a 10-shot YOLO is the weaker option.

**Status: shipped.** `--mode prompted --ocr-run-id <run>` seeds SAM2 from `ocr_extractions` bboxes, and `--prior <blocks.geojson>` adds the modern block prior beside them. `--text-mask` erases those regions from the image so label ink is not segmented as building.

The reverse direction closes the loop: once polygons exist, `join_labels.py` assigns each label to the polygon it names (migration 050). Bidirectional — labels prompt the segmenter, footprints then claim the labels.

## Ordering the sequence

Spatial ordering on the Gemini side is the cheap analogue of the paper's self-sorting memory: order tiles so dense urban-core frames come first and sparse edge tiles inherit accumulated context.

**Status: partially shipped, and one variant measured and rejected.** `batch --row-sequence` (default on, `--max-row-frames 4`) sends each row-strip as one sequence call to `extract_labels_sequence()`. A denser ordering was never implemented. The adjacent idea — reading each tile together with its four grid neighbours — *was* built, measured and reverted; see EVAL-BASELINE.md for the numbers and the two root causes (bad `frame_idx` attribution; centroid ownership leaking inside the 300px overlap band).

## Coarse → fine

`scout` reads the whole map at low resolution to find the neatline and the dense regions; `batch` then tiles only the content area (`--smart-grid`, `--crop`, `--auto-priority`, `--wash-above`, `--skip-sparse`) at full resolution.

**Defaults have one home: `vma_worker.py`.** Tile size, overlap, render size,
concurrency, confidence floor, pass count and prompt are all resolved in
`_ocr_batch_argv` / `_render_size` / `_default_prompt`. Neither enqueue path
restates them any more, because restating them is how the Run OCR button came to
run a 2.34x downsample while `enqueue_ocr_all.mjs` ran the same sheet at 1:1, and
how `passes` came to be declared in three files (audit, 2026-09-08). A payload
names only what the caller chose; the worker fills the rest and stamps it into
the command line, so the run's rows record what they used. Two consequences worth
knowing: `render_size` now defaults to `max(tile_size, 1024)` — **1:1 for a
stock 2400 tile**, not the old flat 1024 — and `passes` defaults to 2 rather
than 1, so a hand-written job row gets the measured recipe.

**`passes: 3` is ignored when it would duplicate a pass.** The hi-res pass runs a
1200 px grid, so on a sheet whose `tile_size` is already at or below that (which
`--tile-metres` normalisation can produce) it would be a byte-for-byte copy of
pass a — free in tokens, but counted by the merge as an independent voter, which
inflates `n_passes` and reverts the three-voter tie-break that took
diacritic_recall from 0.864 to 0.955.

**"Full resolution" is `tile_size / render_size`, and the default is not 1:1.** A tile is `--tile-size` source pixels rendered to `--render-size` before the model sees it, so what Gemini reads is the sheet's own ground resolution times that ratio. The stock 2400/1024 is a 2.34x downsample *on top of* the scan: on a 2.80 m/px scan it delivers 6.5 m/px, which cannot resolve a street name (that figure was measured on the 5,000-px 1959 scan; the larger 1959 image now in the pipeline is 0.999 m/px, so the same ratio delivers about 2.34 — see the 2026-09-10 correction below, and note that a m/px figure without its scan's pixel size cannot be checked). Until 2026-09-04 `vma_worker.py` did not pass `--render-size` at all, so **every queued OCR job ran at that ratio regardless of payload** — that was fixed on 2026-09-04, and since the 2026-09-08 audit the worker's own default is `max(tile_size, 1024)`, so a stock 2400 tile renders 1:1 without the payload saying anything. Nothing above 1:1 buys real detail; past it the scan is the ceiling. **And as of 2026-09-10, rather less than 1:1 buys anything either** — see the correction two paragraphs down before planning a render change. Rendering 1:1 costs tiles, which is what cropping to a study area pays for — see `work/analysis/district4/README.md` for the worked case.

**But resolution was the smaller half.** Measured on the 1959 Đô thành Sài Gòn sheet, same crop and same 1:1 rendering, changing only `--tile-size` and counting distinct labels that warp back inside the study area: 2048 px (5.7 km of ground per call) found 1; 1024 px (2.9 km) found 2; ~500 px (1.4 km) found 6, and 5 on a repeat. Five to six times the yield off an unchanged scan, and only the finest runs read `QUẬN 4` printed on the sheet. Across a whole six-sheet collection the same change gave **+19%**, not 5x — the gain appears only where the ground per call actually drops a lot, and repeats of one configuration differ by a label or two, so do not read a single run's small difference as a result. Rendering was ruled out separately — 1024 px rendered 1:1 and at 2x gave byte-identical output, so upsampling past the scan buys nothing. **What starves a read is one call covering too much ground, and a fixed pixel tile is a different amount of ground on every sheet** (2048 px is 1.7 km on the 1923 sheet, 5.7 km on the 1959 one). That is why coarse sheets look empty and get blamed on their scans. `ocr.py batch --tile-metres` (default 1400) sizes the tile per sheet from its own m/px, read from the sheet's georeference — see *Sizing a grid from the sheet's own scale* below. `scripts/collection_aoi.mjs --tile-metres` does the same thing for a collection sweep, by a different method, and the two do not yet agree; that is recorded below too. `enqueue_ocr_all.mjs` still takes a fixed `--tile-size`. Density steers spend: `--adaptive` renders dense tiles at 2048 and sparse ones at 1024, `--target-calls` scales the grid to a call budget. The digitalize Triage UI writes the same decisions as `--tile-overrides`.

## Coordinate contract

Everything downstream of Gemini is **pixel space on the full source image**, which is also SAM2's input space and `footprint_submissions.pixel_polygon`'s space. Gemini returns 0–1000 normalized boxes per tile; `_to_global()` converts to full-image px; `ocr_extractions.global_x/y/w/h` stores that. Georeferencing to WGS84 happens later, via the Allmaps transform, not in the pipeline.

Note for anyone porting Google's spatial-understanding patterns: their notebook uses `[y_min, x_min, y_max, x_max]`; VMA's prompts document `bbox_px: [x, y, width, height]`. Calibrate before mixing the two.

## Prompt design decisions

1. **System prompt establishes map identity first** — priors for a named corpus are far stronger than for "historical map" generically. But the identity has to be the *archive's*, not one sheet's: it names both the French colonial period and the mid-century Vietnamese one, and says explicitly not to assume which. Naming a single sheet ("an 1882 French colonial cadastral map") primes the wrong language for half the corpus, which is the suspected cause of the 9%–100% per-run diacritic spread. If a per-sheet prior is ever wanted, pass it from the map row; do not hardcode one in a shared prompt.
   The prompt also demands diacritics in upper case as well as lower ("CHÂTEAU" not "CHATEAU", "ĐƯỜNG" not "DUONG") — an all-caps street name is where they were being dropped.
2. **bbox within the tile** — coordinates relative to the submitted crop, directly compositable with SAM2 footprints (both pixel space).
3. **`rotation_deg`** — street labels on French cadastral maps follow the road axis; capturing the angle allows correct placement in the label overlay.
4. **`confidence`** — thresholds before human review. Surface everything ≥0.4 to HITL; auto-accept ≥0.85.
5. **`notes`** — deliberately free-form for model observations ("ink bleed", "partially occluded", "possibly Vietnamese transliteration").

The shipped category taxonomy is whatever `work/ocr/scripts/prompt.py` and the review UI's `OCR_CATEGORIES` agree on — including the pipeline-generated `legend_ref` and `legend_entry`. Do not treat any doc as the schema; read `prompt.py`.

## Known issues / risks

- **Hallucination on blank areas** — Gemini may invent text on featureless margin regions. Mitigate with confidence thresholding and a sanity check (extractions should be empty for blank tiles). `--skip-sparse` / `--auto-priority` avoid sending those tiles at all.
- **IIIF server rate limits** — archive.org throttles at ~10 req/s. The fetcher caches to `.tile_cache/` to avoid re-fetching.
- **Model IDs change** — Flash preview IDs get replaced or renamed. Run `ocr.py list-models` on first use of a new key.
- **French + quốc ngữ mix** — early French colonial maps use early Romanized Vietnamese transliterations. The model handles these but accuracy is lower.
- **Diacritic retention varies by run, not by sheet** — measured across the live table: one run read 9% of labels with any diacritic, another read 100%, on the same sheets. It is the single biggest quality lever and no current eval metric captures it; **diacritic retention rate** (share of labels containing a non-ASCII character) is the metric this corpus argues for.
- **`confidence` is not a usable signal as produced** — median 0.9 with p90 = p99 = 1.0, yet the pipeline gates on it (`--min-confidence 0.5` worker default, plus per-category floors in `ocr.py`). A field that is 1.0 for 90% of rows filters nothing and mis-ranks dedup winners. Either give the model a rubric or drop the gate.
- **Edge labels cut off** — a label straddling a tile boundary is read as two fragments; `clean` rejoins them spatially, and sequence mode assembles some of them in-model.

## Cost

Flash-tier vision is cheap enough that resolution, not budget, is the binding constraint: a full pass over one large map is cents to a couple of dollars, not tens of dollars. Per-run token counts are recorded in each run's `run_config.json` — use those rather than any figure written down here, since both pricing and the default model change.

**Correction, 2026-09-10 — every cost figure on this corpus was understated by roughly 4×.** `output_tokens`, as `work/ocr/scripts/gemini_client.py` logs it (`_log_call`, line 384: `getattr(usage, "candidates_token_count", …)`), is the *visible* text a call returned. It is not what Gemini bills. Billed output is `total_tokens − input_tokens` — candidates plus thinking — and on every run measured directly so far that has come to 3.5–4× the visible figure (124k billed against 31k visible on one 1882 pass; 289k against 82k on the 1968 body run). Every cost figure in this file and in `work/ocr/EVAL-BASELINE.md` that predates this date was computed off `output_tokens` alone and should be assumed understated by roughly that factor unless it explicitly says it accounts for thinking tokens. The two measured, corrected anchors are the 1882 gate sheet's two-pass merge (**USD 0.945**, `EVAL-BASELINE.md` §*The recipe of record*) and the 1968 body pass (**USD 1.236**, corrected in place in the same file, §*The 1968 sheet reads a third of its own directory*) — both at the $0.75/$3.75/$0.075 (in/out/cached-read) rate `gemini-3.8-flash` bills at. This is a reporting fix, not a pricing change: nothing about what Gemini actually charges has moved, only what this repo wrote down about it. `gemini_client.py`'s own `DEFAULT_MODEL` comment repeats the old "$0.50 a map" claim; that file is not this note's to fix (see the model paragraph above for the correction), and neither is `docs/ROADMAP.md`'s copy of the same figure — flag both if you touch either.


**2026-09-14 — cost is now computed in the code, not in this file.** The rates
live in `work/ocr/prices.json`, read by `work/ocr/scripts/pricing.py` (Python)
and `scripts/enqueue_ocr_all.mjs` (the dry-run estimate). One file, two
languages, no copy to drift. Four things follow:

- **Every logged call carries `cost_usd`.** `gemini_client._log_call` writes it
  alongside a new `thoughts_tokens` field — the one the API returns and this
  repo had been dropping, which is why the correction above had to be *inferred*
  by subtraction rather than read.
- **Every command that calls the API now logs.** `scout`, `grid`, `legend` and
  `street-index-fixture` did not, so their spend was invisible to `_spend()`
  and to every budget: the 72-sheet layout sweep of 2026-09-13 left no token
  record at all. `numerals` is not in that list — it is a local Tesseract pass
  and makes no API calls.
- **`max_cost_usd` joins `max_calls`** in the job payload
  (`--max-cost USD` on the enqueue script). A call is a poor proxy for money:
  over 1,192 calls on this corpus one ranges \$0.0012 to \$0.155, a 6x spread
  around the median, with the dearest tenth carrying 28% of all spend.
- **`--low-thinking` reaches the worker.** The flag existed in `ocr.py` and no
  enqueue path ever passed it, so every queued job ran with full thinking —
  59% of billed output tokens on 2026-09-13. It changes the answer as well as
  the price, so it stays opt-in per job.
- **The response cache key now covers the thinking level** on the single-image
  path, as it already did on the sequence path. It did not before, which was a
  marked `ponytail:` shortcut reading "set it per run rather than to A/B it —
  fold it into `schema_version` if that ever has to be an experiment". Making
  `low_thinking` a per-job payload field is that experiment: two jobs on one
  sheet can now differ in exactly this and nothing else. Measured on a numeral
  tile, thinking off took thinking tokens 138 to 67 and cost \$0.001514 to
  \$0.001247 for the same five numerals read correctly; before the fix the
  second run was served the first one's answer from cache, with no API call
  and no log line to show it had happened.

**The 4× correction above is still unverified against an invoice, and this
plumbing does not settle it** — `cost_usd` is computed on that assumption, so
if the assumption is wrong every figure it produces is ~2.5x too high. What has
changed is that settling it now costs no new data collection: compare a billing
export's output-token SKU quantity against the sum of `output_tokens` versus
the sum of `total_tokens − input_tokens`. `pricing.call_cost_usd`'s docstring
carries the same note. A model with no published rate — `gemini-3-flash-preview`
— logs `cost_usd: null` rather than a guess, and `_spend` reports those as
`unpriced_calls` so a money budget cannot be silently unenforceable.

## POC acceptance criteria (historical)

The bar the POC was held to, before `eval.py` and EVAL-BASELINE.md replaced eyeballing: ≥80% of visible toponyms on a manually checked tile matched by an extraction; ≤10% of extractions hallucinated; extracted bbox overlapping the real text region by ≥50%. Superseded — use the eval harness.
