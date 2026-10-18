# scripts/

Commands that act on the live system or build its artifacts. Run them from the repo root
(`node scripts/queue/enqueue_seg.mjs`, `python3 scripts/l7014/l7014_mosaic.py --help`).

**Root** holds the commands wired into npm and CI (`check-bundle.mjs`, `seed-test-db.mjs`,
`mint-worker-key.mjs`, `run_selfchecks.py`, `check_workspace_layout.py`) and the cross-cutting
audit and georeference-write tools (`georef_write.mjs`, `allmaps_*.mjs`, `*_audit.mjs`, ...).

| Folder | What is in it |
|--------|---------------|
| `l7014/` | AMS L7014 series pipeline: mosaic, neatline, autoplace, seams, hand fixes, TTU, metadata; the paper's seam and fault-injection checks |
| `l909/` | AMS L909 series: GeoPDF check, georeference, publish |
| `indochine100k/` | Indochine 1:100,000 grid and georeference |
| `tonkin/` | Tonkin sheet georeference and thin-frame corners |
| `scout/` | Finding sources: scout crawlers, scoring, load to `scout_candidates`, NLV press queries, legend timeline, place reports |
| `queue/` | Enqueue worker jobs (OCR, layout, warp, seg) and dedupe OCR rows |
| `gen/` | Generators: i18n, hero media, changelog shots, system graph, paper render, md to PDF |
| `lib/` | Shared modules the scripts import |
| `oneoff/` | Dated fixes and backfills, kept as a record |
| `vn1971/` | 1971 provincial atlas grid georeferences |

Scout runs write their data files (`scout_all_<ts>.json`, `scout_review.csv`) to `scripts/`
itself; they are gitignored.

# Audit and georeference-write commands

Moved here from `docs/guides/pipelines.md` on 2026-10-17, word for word.

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
`check_series_index.mjs` whether `series_cells` still agrees with `maps`, and
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
| `year` appearing nowhere in `date_label`; one holder spelled two ways | WARN |
| a path, filename or markup in `name`/`original_title`; an `original_title` that is only digits; a name that says the half twice (`Cam Pha est (E)`) | WARN |
| a published map with no `map_type`; an L7014 `sheet_number` that is not `NNNN-Q`; a `0` / `0 bis` placeholder | WARN |
| two primary IIIF sources, none primary, or a primary disagreeing with `maps.iiif_image` | FAIL |
| a published map with no non-r2 IIIF source, so the Allmaps Editor cannot open it | WARN |
| a job out of retries, held past 3 h, or pointing at a deleted map | WARN / FAIL |

**What it deliberately does not report.** A map carrying `allmaps_id` with
`is_georeferenced` false reads like a fault: the id is a SHA-1 of the canonical IIIF
URL, minted locally by `bulk_upload_local.sh` whether or not a control point
exists, and migration 062 gates publishing on `annotation_url is not null or
allmaps_id is not null` — so on paper a sheet satisfies the gate with a hash of
its own URL. This file called that a finding, over 21 L7014 drafts, until the
code that consumes the pair turned up.

It is a **work queue**. `POST /api/admin/maps/sync-georef` selects exactly
`allmaps_id is not null and is_georeferenced = false`, probes
annotations.allmaps.org and flips `is_georeferenced` on a hit; the admin *Sync georef
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
must pass beside it — 40 cases, no database. A checker that only ever runs
against a healthy archive reports the same thing whether it works or not, which
is how `check_series_index` once reported clean over 79 sheets it could not see.

**Reading today's run (15 Sept 2026).** 274 `maps` rows (every status, drafts included), 131 published, **0 fail, 53
warn**: 24 published maps the Allmaps Editor cannot be opened on, 13 with no
`holding_institution` and 3 with no `source_url`, 6 layout jobs out of retries, 5
`year`/`date_label` disagreements, one holder spelled two ways (Perry-Castañeda,
word order), and the duplicate Huế pair. Plus a status line: **21 maps queued for
georeferencing**, which is the sync button's backlog, not a fault.

**What it does not cover.** The 63 Indochine sheets carry sheet numbers but no
lattice index, so nothing checks their position; and the "held twice" check
found **0 pairs**, because the nine city sheets are deliberately out of the
mosaic and the fifteen backdrop sheets have no annotation to compare against.
Keeping a cell both ways only buys a standing check once both holdings are
actually georeferenced.

## Storing a script-made georeference (`scripts/georef_write.mjs`)

Our own `annotations` bucket is where every series pipeline stores its
annotations. Allmaps can also be written to: `POST live.allmaps.org/maps` takes a
Georeferenced Map (`@context` must be the single string
`https://schemas.allmaps.org/map/2/context.json`), and `PATCH live.allmaps.org/maps/<mapId>`
updates one. Re-POSTing creates a second map on the same image. No key is needed.
The 1971 pilot used this on 2026-10-06 for four sheets; its code and the 44 prepared
maps are in `work/vn1971/`. `georef_write.mjs --allmaps` now pushes a stored sheet
(below). What comes back from Allmaps is only ever *pulled* for sheets edited there
(`sync-allmaps`, `sync_district4_annotations.mjs`), never for a script-made one.
Each pipeline used to store annotations its own way. Now every pipeline follows the
same three steps:

1. **Place** — series-specific, and stays in the series script: Tonkin and Indochine
   100k detect frame corners, L7014 reads GeoPDF corners or hand corners, L909
   fits its neatline, the 1971 provincial maps read their UTM grid.
2. **Build** — `scripts/lib/georef_annotation.py` `annotation(iiif, w, h, gcps, mask,
   transformation=None)`. It writes one JSON per sheet to `work/<series>/annotations/<map-uuid>.json`.
   The mask is the neatline/rim quad. `transformation` is an Allmaps dict
   (`polynomial(2)`, `{"type": "thinPlateSpline"}`, `{"type": "helmert"}`); the default
   is a first-order polynomial (the docstring says why).
3. **Store** — `node --env-file=.env scripts/georef_write.mjs [--apply]
   [--replace-public] <files>`, or `georef_annotation.store(files, apply=...)` from
   Python. It is a dry run without `--apply`. For each file it:
   - refuses an unparsable file, fewer than 3 GCPs, no mask, a source that is not
     the row's `iiif_image`, or a pixel size that source does not serve;
   - refuses a non-draft row that already has a georeference (`annotation_url`) unless
     `--replace-public` is passed; a public row with none is written;
   - requires `--method` (`utm-grid`, `printed-corners`, `catalogue+calibration`,
     `geopdf`, `hand`, `allmaps-editor`) and records it with `--datum`, `--derived-from`
     and `method_ref` (the calling script at its git short sha; `store()` fills it from
     `sys.argv[0]`). Python callers pass `method` as the second argument of `store()`;
   - writes the history copy `annotations/<map>/<stamp>.json` plus its
     `georef_versions` row (`origin` `script`, and the provenance columns of migration
     118), then the live file, which it reads back and compares;
   - sets `annotation_url` (the app route), `is_georeferenced` and `bbox`. The
     `bbox` is the warped mask extent, from `scripts/lib/sheet_extent.mjs`, the
     same function `backfill_map_bbox.mjs` uses.

   - with `--allmaps`, pushes each stored sheet to `live.allmaps.org` — POST the first
     time, PATCH after, using the newest `georef_versions.allmaps_map_id` for that map —
     records the map id on the version row, then reads `annotations.allmaps.org/maps/<id>`
     back and prints any GCP, transformation or mask difference. The push is
     `scripts/lib/allmaps.mjs`. **Run it only on a map whose GCPs you mean to publish: a
     POST creates a public map nobody can delete but Allmaps.** The map's own `id` is
     not kept by Allmaps (the read-back id is Allmaps'), so the link runs one way, from
     the version row to Allmaps. (Whether Allmaps keeps a field of ours was not tested.)

   `node --env-file=.env scripts/allmaps_drift.mjs [<map-uuid>...]` compares every pushed
   map's live Allmaps GCPs with ours and exits 3 on a difference. It reads only: Allmaps is a
   push-only mirror, and the next `--allmaps` PATCH puts our version back.

   It exits 3 when it refused any file, or when an `--allmaps` push failed. It never sets `status`: a person publishes,
   after looking at the sheet in /explore.

Methods the existing callers pass: Tonkin `printed-corners`; Indochine 100k
`catalogue+calibration`; `l7014_annotate.py` `hand`; `l7014_annotate_pdf.py` `geopdf`, `hand`
for `--hand`, `catalogue+calibration` for `--auto` (detected corners against the lattice
cell). Tonkin, Indochine 100k and both L7014 scripts go through this path; the L909
scripts do not yet. A new series script writes only step 1 and calls the other two.
