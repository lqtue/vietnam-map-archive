# L7014 rebuild checklist

> **Naming:** the ROADMAP item this checklist executes is **N1**; it was called **I3** when this
> file was written, and both names appear below. The I-series entry now lives in
> `docs/roadmap-record.md`.

A verified, ordered checklist for rebuilding and republishing the AMS Series L7014 raster
archive with the committed datum fix. Written after tracing `scripts/l7014_mosaic.py`
(`index`/`fetch`/`warp`/`manifest`/`fit`/`tile`/`upload`), `scripts/geo_audit.mjs`, every
reference to the dated key, `src/lib/data/maps/seriesSheets.ts` /
`src/lib/map/rasterSeries.ts`, `work/l7014/regen/REGEN.md`, and the disk/log state on this
machine on 2026-09-20. Nothing in this document was executed as part of writing it — see
"Verified today" below for what was actually run and what was only read.

**One correction to the brief this was written from:** `work/l7014/cogs/` holds **1,326**
files, not 1,311 — 437 `.tif` + 437 `.gpkg` + 452 `.src.vrt`. The extra 15 `.src.vrt` are
orphans from failed warp attempts (`write_cutline`/`gdal.Translate` write the `.src.vrt`
before `gdalwarp` runs; a `gdalwarp` failure removes only the `.tif`) — with no matching
`.tif` or `.gpkg`, and skip logic looks only at the `.tif`, so they're inert, just untidy.
The 437 `.tif`s match `warp --no-datum-shift`'s logged `ok=437` exactly (the corrected pass
logged `ok=436`), which **confirms** the brief's claim that the COG directory currently
holds the faulty pass.

## Verified today (read-only)

- `work/l7014/regen/REGEN.md` and `work/l7014/regen/*.log` record a full **dry run** of both
  the corrected and faulty warp on 2026-09-20 (commit `7ee5d947` + the two source changes
  below, both now committed at `0aa04f0b`). **`tile` and `upload` were never run — production
  R2 is untouched**, exactly as REGEN.md states.
- `git status --porcelain scripts/l7014_mosaic.py` is clean: the `--no-datum-shift` flag and
  the `graticule_error` axis-order fix that REGEN.md calls "two uncommitted changes" are
  **already committed** (`0aa04f0b fix(l7014): the graticule check was rejecting its own
  datum correction`, present on this branch). No source patch is needed before rebuilding.
- Tools: `rclone` v1.73.4 (remote `r2:` configured), `pmtiles` CLI, `gdal_translate`/
  `gdaladdo`/`gdalwarp`/`gdalbuildvrt` (GDAL 3.13.3) all resolve on `$PATH`. Did not list the
  R2 bucket or otherwise authenticate.
- The 510 symlinked GeoPDFs under `work/l7014/pdfs/` and the symlinked `index.geojson` still
  resolve to real files under `~/Work/Maps/l7014/` — nothing needs re-fetching.
- `du -sh work/l7014/*`: `cogs` 23G, `jpgs` 222M, `pdfs` 16M (symlinks), `build` 864K, rest
  negligible. `df -h .`: **55Gi free** on `/dev/disk3s1` (73% used).
- From `work/l7014/regen/driver.log` (wall-clock, this machine, `--jobs` default of 6, all
  inputs already local): `warp` (corrected) took **13m39s** for 510 rows (436 ok); `warp
  --no-datum-shift` took **16m11s** for 437 ok. `manifest` and `fit` each ran in **1–2
  seconds**. **No timing exists for `tile` or `upload`** — they were never run, so any
  duration for them below is explicitly unmeasured, not estimated.
- `manifest --key l7014-fixed` (the corrected pass) produced **436** features, not 452 or
  437. This is the number a real rebuild will most likely reproduce, since it's the same
  code, the same PDFs, and nothing in `warp`/`manifest` is nondeterministic.

## Constants and files that reference the dated key

| location | what it is | must change? |
|---|---|---|
| `src/lib/map/basemapStyle.ts:89` | `L7014_PMTILES_URL` | **yes** — the constant itself |
| `src/lib/map/basemapStyle.ts:145` | `RASTER_ARCHIVES.l7014.dev` (local-pmtiles path) | **yes** — must name the new build file |
| `scripts/geo_audit.mjs:35` | `const KEY` default | **yes**, or always pass `--key` explicitly |
| `scripts/oneoff/fix_l7014_editions.mjs:29` | `MANIFEST` path constant | only if this one-off is ever re-run; it's a completed migration script, flag rather than silently update |
| `src/lib/map/rasterSeries.ts:45` | `RASTER_SERIES[0].sheets` (**452**, hand-maintained) | **yes** — see "Sheet count" below |
| `tests/series-rows.spec.ts:20,96` | mirrors the `452` literal and asserts the `'452 sheets'` label | **yes**, together with the above or the test fails |
| `docs/architecture.md`, `docs/pipelines.md`, `docs/ROADMAP.md` (I3) | prose describing the *current, faulty* archive by name and by its seam/fit numbers | **yes** — becomes stale prose the moment the archive changes |
| `docs/paper/draft.md` §7.6, `docs/paper/blind-by-construction.tex`, `docs/paper/figures.md` §3.3 | explicitly frame `l7014-20260913` as **not yet rebuilt**, as a deliberate evidentiary point | **editorial decision, not a mechanical find-replace** — see hazard 8 |

Not affected: `tests/layer-stack.spec.ts`, `tests/series-sheets.spec.ts`, `tests/ingest-cells.spec.ts`,
`tests/mpp-parity.spec.ts` — none of them assert on the dated key or the sheet count, only on
the stable `'l7014'` layer key and unrelated fixtures. `src/routes/(editorial)/+page.svelte`'s
`l7014Held: 461` / `l7014Total: 627` describe survey coverage (what PCL published / what
exists), not mosaic warp success, so they don't move with this rebuild.

## Sheet count: `452` will not survive a correct rebuild

`rasterSeries.ts`'s own comment says to "read it off `work/l7014/build/<build>.geojson` …
counting anything else is counting a survey rather than an archive" — it is a **hand-maintained
literal**, not computed from the manifest at build or run time. Today's dry run of the
corrected code path produced **436** mosaic sheets, not 452. Since the live manifest 404s
(the fact this task started from), there is no way to confirm what the *currently live*
archive actually holds — `452` may already be wrong. After this rebuild, count features in
the freshly built `{key}.geojson` and hand-edit both `rasterSeries.ts` and
`tests/series-rows.spec.ts` to match; nothing will do it for you, and nothing but `npm run
test` will catch a forgotten update (the label assertion at `tests/series-rows.spec.ts:96`).

## The checklist

Legend: 🔴 destructive (deletes or overwrites local or remote state) · 🌐 outward-facing
(changes what a production reader sees) · plain = safe/read-only/reversible.

### Phase A — preflight (safe)

**1. Confirm tools and remote.**
```bash
rclone --version && pmtiles convert --help >/dev/null && gdal_translate --version
rclone listremotes | grep -q '^r2:$' && echo "r2 remote present"
```
*Before:* nothing. *Works if:* all three succeed; `r2:` is listed. Do not run `rclone lsd
r2:vma-tiles` as part of this step — that's a bucket listing, not a tool check, and isn't
needed to proceed.

**2. Confirm the inputs are still there.**
```bash
ls work/l7014/pdfs/*.pdf | wc -l        # expect 510
test -e work/l7014/index.geojson && echo ok
```
*Works if:* 510 and `ok`. If either fails, the symlinked source at `~/Work/Maps/l7014/` has
moved and `fetch` (needs network, ~4 GB, ~2 hours per `docs/pipelines.md`) becomes necessary
again — confirm before assuming it isn't.

**3. Check free disk.**
```bash
df -h .
```
*Works if:* comfortably more than the ~23 GB the COG pass needs plus a few GB for the
intermediate `.mbtiles` and final `.pmtiles` (the live archive is 4.9 GB; the corrected pass
will be close to that). 55 GiB was free at investigation time — re-check immediately before
running, since this machine has other work in progress on the same volume.

**4. Pick the new key and record it.** e.g. `l7014-20260920` (today's date, matching the
convention `L7014_PMTILES_URL` documents). Use it verbatim in every `--key` flag below —
this is where the *live* archive went wrong: `manifest` and `tile`/`upload` were run (at some
point) under a key that didn't match, so `upload` found no `{key}.geojson` and shipped
pixels only. **Do not let any two of `manifest`, `fit`, `tile`, `upload` disagree on `--key`.**

### Phase B — rebuild locally (destructive to `work/l7014/cogs` and `build/` only; nothing remote yet)

**5. 🔴 Clear the COG directory.**
```bash
rm -rf work/l7014/cogs
```
*Before:* confirmed (step 4) that this is a fresh, correctly-keyed run, not a resume. *Why
mandatory:* `warp_one` returns `"skip"` for any sheet whose output `.tif` already exists.
`work/l7014/cogs/` right now holds the **faulty** (`--no-datum-shift`) pass — 437 `.tif`s
from the 2026-09-20 dry run. Running `warp` without clearing this directory first would
silently keep those 437 faulty files and produce nothing new for most of the archive. This
is the single highest-value step in this whole checklist to get right.
*Works if:* `ls work/l7014/cogs` is empty or the directory is gone.

**6. Corrected warp — no `--no-datum-shift`.**
```bash
time python3 scripts/l7014_mosaic.py warp --jobs 6 2>&1 | tee work/l7014/regen/warp-rebuild.log
```
*Before:* step 5 done; step 2 confirmed. *Measured basis:* the corrected pass took 13m39s in
today's dry run under identical conditions (same machine, same `--jobs`, same already-local
PDFs) — expect roughly that, not the ~2-hour figure in `docs/pipelines.md`, which is
dominated by a download this run doesn't need.
*Works if:* the tally line reads `warp: nogeo=62, offcell=11, offgrid=1, ok=436` (today's
dry-run numbers) or close to it — a materially different `ok` count means something about
the input set changed and is worth stopping to understand before continuing. Zero `FAIL`
lines.

**7. Build the sheet manifest.**
```bash
python3 scripts/l7014_mosaic.py manifest --key l7014-<newdate> 2>&1 | tee work/l7014/regen/manifest-rebuild.log
```
*Before:* step 6 ok. *Works if:* `manifest: 436 sheets -> work/l7014/build/l7014-<newdate>.geojson`
(no `UNKNOWN`/`ASTRAY` lines; the phase already refuses to exit 0 if any sheet lands outside
Vietnam).

**8. Fit gate — must pass.**
```bash
python3 scripts/l7014_mosaic.py fit --key l7014-<newdate>
echo "exit: $?"
```
*Before:* step 7 with the same `--key`. *Works if:* exit code is **0** and the printed line
reads `fit: 434 sheets on cell, median ~10 m, worst ~95 m` (today's dry-run numbers; 2 sheets
— `6630-4` and `6349-4` — are flagged as off-cell for reasons unrelated to the datum fault,
see REGEN.md). **`fit` is advisory in the code** — nothing stops `tile`/`upload` from running
whether or not this passed. Treat a nonzero exit here as a hard stop by discipline, not
because the tool enforces it.

**9. `geo_audit.mjs` — the second, independent gate ROADMAP I3 names explicitly.**
```bash
node --env-file=.env scripts/geo_audit.mjs --key l7014-<newdate>
echo "exit: $?"
```
*Before:* step 7 (it reads `work/l7014/build/{key}.geojson` locally — it does **not** need
anything uploaded yet). *Needs:* `.env` with `PUBLIC_SUPABASE_URL` / `SUPABASE_SERVICE_KEY`
(database read, for the `maps.bbox` cross-check) and `work/l7014/lattice.json` (already
present, 627 cells). *Works if:* exit 0, no `FAIL` lines.

### Phase C — tile (local only, unmeasured — time and watch disk)

**10. Build MBTiles + PMTiles.**
```bash
time python3 scripts/l7014_mosaic.py tile --key l7014-<newdate> 2>&1 | tee work/l7014/regen/tile-rebuild.log
```
*Before:* steps 6–9 all clean. *No local timing exists for this phase* — REGEN.md is explicit
that `tile` was never run this cycle. Do not assume the ~2-hour `docs/pipelines.md` figure;
that bundles the download. Budget disk for a transient `.mbtiles` plus the final `.pmtiles`
on top of the 23 GB of COGs already on disk (WEBP quality 80, the default, produced roughly
3 GB against 4.9 GB for the previously-shipped archive per the script's own comments — PNG
would be ~9× that, ~35 GB, and is not the default for a reason). Re-run `df -h .` partway
through if it's long-running.
*Works if:* the final printed line is `tile: 436 sheets -> work/l7014/build/l7014-<newdate>.pmtiles (~NNNN MB)`
followed by `pmtiles show`'s own header block (zoom range, bounds, tile count, tile compression)
with no errors. Record the actual wall-clock time in `work/l7014/regen/` — this checklist
should stop being blind about this phase for the *next* rebuild.

**11. Sanity-check the archive locally before shipping it.**
```bash
cp work/l7014/build/l7014-<newdate>.pmtiles work/l7014/build/ 2>/dev/null  # already there; just confirming path
npm run dev   # RASTER_ARCHIVES.l7014.dev tries /local-pmtiles/<name>.pmtiles first, in DEV only
```
Update `src/lib/map/basemapStyle.ts:145` (`dev:`) to the new filename *before* this step, or
point at the file already sitting under `work/l7014/build/` with that name (it's the same
directory `phase_tile` wrote to, so no copy is actually needed — just get the `dev:` string
right). Open `/explore?series=l7014` locally and visually confirm the mosaic no longer shows
the ~450 m seam jump where it meets the hand-georeferenced sheets, and that no new dark
outline artifacts appeared around holes beyond the known WEBP cosmetic one.
*Works if:* the layer draws, holes are transparent (not black), and known trouble sheets
(`6630-4`, `6349-4` from step 8) look plausible rather than badly torn.

### Phase D — publish (🌐 outward-facing; 🔴 writes to production R2)

**12. 🔴🌐 Upload.**
```bash
python3 scripts/l7014_mosaic.py upload --key l7014-<newdate>
```
*Before:* steps 8, 9, 10, 11 all clean — per ROADMAP I3, "require `fit` and `geo_audit.mjs`
before treating the new build as usable." *What it does:* `rclone copyto` the `.pmtiles` to
`r2:vma-tiles/overlay/l7014-<newdate>.pmtiles`, then — only if `work/l7014/build/l7014-<newdate>.geojson`
exists with that exact key — the `.geojson` to the sibling key. This is exactly the step that
went wrong for `l7014-20260913`: if the manifest step (7) used a different `--key` than this
one, `upload` prints "no sheet manifest built … uploading pixels only" and silently ships a
404 for the `.geojson`, reproducing the original defect. **Do not proceed past this step
without visually confirming the second `uploaded:` line printed for the `.geojson`, not just
the first for `.pmtiles`.**
*Works if:* two `uploaded: https://tiles.maparchive.vn/overlay/…` lines print, and:
```bash
curl -sI https://tiles.maparchive.vn/overlay/l7014-<newdate>.pmtiles | head -1   # expect 200/206
curl -sI https://tiles.maparchive.vn/overlay/l7014-<newdate>.geojson | head -1   # expect 200
```
**Do not delete `overlay/l7014-20260913.pmtiles`** as part of this step. ROADMAP I3: "Preserve
the old build until the replacement passes." The old faulty archive stays live in R2 so that
any client still running old JS (pointing at the old key) degrades gracefully — per
`basemapStyle.ts`'s own `attachArchive` comment, a 404 there draws nothing rather than
breaking the page, but only if the *file* is actually gone; while it's present the stale
client just keeps showing the faulty mosaic, silently, until it reloads.

**13. 🌐 Point the app at the new archive.** Edit, in order:
- `src/lib/map/basemapStyle.ts:89` — `L7014_PMTILES_URL` to the new URL.
- `src/lib/map/basemapStyle.ts:145` — `dev:` to `/local-pmtiles/l7014-<newdate>.pmtiles`.
- `src/lib/map/rasterSeries.ts:45` — `sheets:` to the count from step 7's manifest (436 in
  today's dry run — **verify against your actual rebuild's `manifest` output, don't copy this
  number blind**), and `bounds:` if `pmtiles show`'s reported extent (step 10) differs
  meaningfully from what's there now.
- `tests/series-rows.spec.ts:20,96` — the mirrored `452` literal and the `'452 sheets'` label,
  to match.
- `scripts/geo_audit.mjs:35` — the default `--key`, to the new key (or decide to always pass
  `--key` explicitly and leave a comment saying so).

**14. Verify.**
```bash
npm run check   # 0 errors / 0 warnings is the pinned baseline
npm run lint
npm run test     # tests/series-rows.spec.ts is the one this rebuild can break
```
*Works if:* all three are clean, in particular the `'452 sheets'` assertion now reads the
number you actually put in `rasterSeries.ts`.

**15. 🌐 Build and deploy.**
```bash
npm run deploy
```
*Before:* step 14 clean, on a branch/commit the user wants in production. *This is the step
that changes what real readers see* — everything before it is either local or an R2 object
nothing yet references. Per `CLAUDE.md`: a blank page immediately after is edge propagation,
not a bug; wait and hard-reload, or use the `curl` check in `docs/deploy.md`, before
concluding something is wrong.

**16. Post-deploy check.**
Open `https://maparchive.vn/explore?series=l7014` (or `vmabeta.pages.dev`, which 301s there)
and confirm: the L7014 layer draws, opacity/eye controls work, and the seam at any
hand-georeferenced sheet (e.g. one of the 24) no longer shows the ~450 m jump.

### Phase E — close the loop on the record (not code; still part of "republish")

**17. Update prose that names the old key or the old numbers.** `docs/architecture.md`,
`docs/pipelines.md` (including its own `> The live archive l7014-20260913 is wrong…` callout),
and `docs/ROADMAP.md` (tick I3, or move it to done with the actual measured numbers — expect
436 sheets / ~436 on-cell, not the dry run's 452/750-seam figures the paper currently cites).

**18. Decide what happens to the paper's framing — do not silently rewrite it.**
`docs/paper/draft.md` §7.6, `docs/paper/blind-by-construction.tex`, and
`docs/paper/figures.md` §3.3 all currently say, deliberately, that `l7014-20260913` "has not
been re-warped or re-uploaded" and frame that as **part of the paper's evidentiary structure**
("reporting the dry run separately prevents it from being mistaken for a measurement of the
current serving layer"). Once a rebuild ships, that sentence is simply false, and the fix is
an editorial one — probably a new paragraph reporting the actual rebuilt-archive numbers
(436 sheets, the real `fit`/seam results from the live `{key}.geojson`, not the dry run's) —
not a find-and-replace of the key. Flagging this rather than doing it, since it changes what
the paper claims to have measured.

## What could go wrong (from REGEN.md and the phase code)

1. **The COG-skip trap.** `warp_one` treats an existing `.tif` as done. `work/l7014/cogs/`
   currently holds the *faulty* pass (confirmed: 437 `.tif`s, matching `warp
   --no-datum-shift`'s logged `ok=437`, not the corrected pass's `ok=436`). Skipping step 5
   is the one mistake in this checklist that produces a plausible, silently wrong archive.
2. **Key mismatch across `manifest`/`fit`/`tile`/`upload`.** Nothing enforces that all four
   `--key` flags agree. A mismatch doesn't error — `upload` just prints "no sheet manifest
   built … uploading pixels only" and ships pixels with no `.geojson`, which is very likely
   how `l7014-20260913` reached production this way in the first place.
3. **`fit` and `geo_audit.mjs` are advisory, not enforced.** Nothing in the code stops
   `tile`/`upload` from running regardless of whether either gate passed. The gate is this
   checklist, not the tooling.
4. **WEBP's hole-outline artifact is a known, accepted cost, not a new bug.** WEBP discards
   RGB under fully transparent pixels, so `gdaladdo`'s averaging leaves a thin dark line
   around every gap; PNG avoids it for ~9× the bytes (35 GB vs. ~3 GB, per the script's own
   measured comment). The default (WEBP, quality 80) reproduces this cosmetic defect on
   purpose — don't mistake it for a rebuild regression, and don't "fix" it by silently
   switching `--tile-format` without deciding that's actually wanted.
5. **`gdalbuildvrt -resolution highest` is load-bearing.** The default `average` strategy
   would quietly downsample every 300 dpi sheet to match the 150 dpi ones. `phase_tile`
   already hardcodes `highest`; the hazard is only in hand-rolling a substitute VRT-build
   command instead of running `tile` as written.
6. **15 orphaned `.src.vrt`/`.cutline.gpkg` files with no matching `.tif`** exist in the
   current `cogs/` from an earlier/interrupted attempt. Harmless to correctness (the skip
   check only looks at `.tif`), but step 5's `rm -rf` clears them too — worth noting so
   nobody spends time trying to explain them separately.
7. **Stale clients.** Any browser holding an older JS bundle keeps requesting the *old* key
   until it reloads. `attachArchive` degrades that gracefully to "draws nothing" only once
   the old object is actually gone from R2 — while it's still there (which ROADMAP I3 says it
   should be, until the replacement is verified), those clients keep showing the **faulty**
   mosaic, indefinitely, with no error surfaced anywhere.
8. **The paper's own claims are keyed to the unrebuilt archive.** §7.6 of `draft.md` and the
   matching passage in `blind-by-construction.tex` treat "not yet rebuilt" as evidentially
   significant, not incidental. A rebuild without a corresponding paper edit leaves published
   or near-published prose asserting something the live site now contradicts.
9. **`rasterSeries.ts`'s `sheets: 452` is hand-maintained and already unverifiable** against
   the live (404) manifest. A rebuild is very likely to produce **436**, not 452 — update it
   and its test mirror deliberately; nothing will catch a stale count except the one test
   assertion in `tests/series-rows.spec.ts:96`.
10. **`tile`/`upload` timing is a genuine unknown**, not merely an estimate — they've never
    been run. Don't schedule around the ~2-hour figure in `docs/pipelines.md`; that includes
    a download this rebuild skips. Time it and log it this time.
