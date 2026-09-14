# Admin tooling

Admin controls live inline in `/catalog` (gated by `role === 'admin' | 'mod'`). There is no separate `/admin` route — except for the scout and bulk-upload sub-pages noted below.

## Catalog admin mode

**`/catalog`** renders `src/lib/features/catalog/CatalogUnifiedSearch.svelte` unconditionally — there is no `?v=` switch and no legacy view. It hits `/api/search` once per `q` / `include=scout` change; facet chips filter and re-tally client-side so chip toggles are instant.

- `src/lib/ui/FacetRail.svelte` — multi-select chip groups with "all-but-this-dimension" tallies; two-way binds the selection.
- `src/lib/features/catalog/CatalogTable.svelte` — the result rows (curated + scout). `src/lib/ui/CatalogGrid.svelte` / `CatalogCard.svelte` are the card-grid counterparts.
- `src/lib/features/catalog/CatalogDetailDrawer.svelte` — row detail. Staff (`role === 'admin' | 'mod'`) get an **✎ Edit** action on curated rows only; it dispatches `edit` up through `CatalogUnifiedSearch`.
- Staff also get an **Include scout queue** toggle in the toolbar. Non-staff never see scout rows — `/api/search` drops `include=scout` server-side.

**The catalog page owns the modal, not the search component.** `src/routes/(editorial)/catalog/+page.svelte` listens for `on:edit`, loads the row via `fetchMapRow`, and renders `MapEditModal`; on save it calls the component's exported `refresh()`.

## MapEditModal

`src/lib/features/admin/MapEditModal.svelte` — **four tabs, all unconditional**: About · Source · Hosting & Georef · Pipeline (`activeTab: 'about' | 'source' | 'hosting' | 'pipeline'`). There is no GCPs tab; `NeatlineEditor.svelte` renders inside the Hosting & Georef branch.

| Tab | Component | Content |
|-----|-----------|---------|
| **About** | `MapEditAboutTab.svelte` | name, original_title, year, year_label, creator, dc_publisher, location, map_type, dc_coverage, dc_subject, dc_description, physical_description, language, custom `extra_metadata` pairs |
| **Source** | `MapEditSourceTab.svelte` | source_type, holding_institution, collection, shelfmark, ia_identifier, source_url, rights |
| **Hosting & Georef** | `MapEditHostingTab.svelte` | IIIF source list (primary indicator), Mirror to R2, Allmaps ID + annotation_url + Fetch-from-Allmaps + Editor link, IA image upload, `NeatlineEditor` |
| **Pipeline** | `MapEditPipelineTab.svelte` | georef_done / legend_done flags, legend mode + text, label categories, OCR pipeline controls |

Supporting modules in `src/lib/features/admin/`: `NeatlineEditor.svelte`, `neatlineDatum.ts`, `neatlineViewport.ts`, `GeorefSyncPanel.svelte`, `ScoutCard.svelte`. The admin API client is `src/lib/data/admin/adminApi.ts`; the PATCH body is assembled in `src/lib/data/admin/mapEditPayload.ts`.

## Bulk upload (`/admin?tab=bulk`)

Spreadsheet-style page for batch-creating draft `maps` rows. Admin pastes file paths (one per line, tab/CSV optional for per-row `name`/`year`/`collection`/`map_type`/`location`); names auto-parse from filenames matching `<sheet#> <Place> <YYYY>.jpg`. "Create batch" inserts via `POST /api/admin/maps` and outputs a copy-paste shell script of `./scripts/tile_map.sh <uuid> '<path>'` lines. Tiling still runs locally (vips constraint). After tiling, "Backfill thumbnails" fetches each map's info.json and PATCHes `thumbnail` + `iiif_image`.

Companion CLI scripts:
- `scripts/bulk_upload_local.sh <file-list.txt> [--collection ...]` — tiles + inserts `maps` + `map_iiif_sources` rows in one pass. Logs to `scripts/bulk_upload_<timestamp>.log`.

## R2 / IIIF worker

Self-hosted IIIF tile serving via Cloudflare R2 + Worker at `https://iiif.maparchive.vn/iiif`.

- `worker/` — Cloudflare Worker source + `wrangler.toml`; proxies IIIF tile requests to R2.
- `scripts/tile_map.sh <map-uuid> <source-image-url-or-path> [original-iiif-base] [--new-version | --version N] [--dry-run]` — downloads (or copies a local file), tiles with `vips dzsave --layout iiif3 --tile-size 256`, uploads to R2 at `tiles/<map-uuid>/`. **A re-tile of a map that is already mirrored takes `--new-version`**, which writes `tiles/<map-uuid>/v<N>/` instead and prints the versioned service id to put in the database — see *Re-tiling a mirrored map* below. `--dry-run` prints the keys and the service id and stops. The mirror-r2 API and `/admin?tab=bulk` return the exact command, always unversioned: they only ever mint a first tiling.
- After mirroring: `maps.iiif_image` and the primary `map_iiif_sources` row point to `https://iiif.maparchive.vn/iiif/<map-uuid>`; `maps.annotation_url` becomes the Supabase Storage public URL of the updated annotation JSON (mig 047 — earlier code overloaded `allmaps_id` for this; the column now holds only bare image IDs).

**info.json patching:** the worker patches `vips dzsave`'s info.json on the fly — injects `tiles[0].height` (defaults to width per spec but required by OL's IIIFInfo parser) and a `sizes` array computed from scaleFactors. Without these, OpenLayers renders stretched/seamy tiles. Served with `Cache-Control: public, max-age=0`.

Deploy: `cd worker && npx wrangler deploy --env production`. A bare `wrangler deploy` updates only the default env (orphan worker on `workers.dev`) and does NOT update the production route.

**Edge cache (2026-09-06):** the worker stores every successful tile response in
`caches.default` and checks it before touching R2. A Worker response is not
cached unless the Worker caches it, so until this landed every tile request —
including one for a tile the same colo had already served to someone else — was
a round trip to R2 storage: 310-950 ms TTFB from HKG, no `cf-cache-status`
header at all, 7.1 s for 12 sequential tiles. After: ~130 ms warm (the floor,
matching an edge-cached Pages asset from the same location) and 1.9 s for the
same twelve. The `immutable` header we had always sent only ever reached the one
browser that asked for the tile.

`info.json` is cached too, at `s-maxage=3600`. The rewrite it goes through is a
pure function of the request URL — the `id` it injects is that URL minus
`/info.json` — so a URL-keyed cache cannot serve a wrong answer, and it is worth
caching because it is head-of-line: the renderer needs the image's dimensions
before it can ask for one tile. 300-600 ms → ~130 ms. The hour (rather than a
year) is because a re-tiled map can change size; **after re-running
`tile_map.sh` on a map that is already live, wait the hour or purge that URL**.
With `--new-version` there is nothing to wait for — the versioned `info.json`
lives at an id no cache has ever seen.
`HEAD` is excluded (`cache.match` keys on GET), as is anything with
`?force_proxy`. Only `response.ok` is stored, because a 404 means the tile is
absent from R2 *and* refused by the origin, and either can change.

The app also preconnects to `iiif.maparchive.vn` and the Supabase host in
`src/app.html`: both handshakes measured 70-180 ms and neither began until the
bundle asked for something.

Two things this does not cover, in the order they are worth doing:

- **The basemap is still uncached.** `cache.put()` rejects a 206 and every
  PMTiles read is a range read. The fix is an R2 custom domain for
  `basemap/*`, where Cloudflare's CDN serves ranges natively with no Worker in
  the path — a dashboard change plus `BASEMAP_PMTILES_URL`.
- **Misses still cost a full R2 trip per edge machine.** A colo's cache is not
  shared between its machines; repeat requests measured ~130 ms with occasional
  420 ms outliers, which is a machine that had not seen the tile. Tiered Cache
  does **not** fix this, despite being free on this plan: it works on `fetch()`
  to an origin, and this worker reads R2 over a binding, so there is no origin
  request for it to tier. The version that would work is reading R2 over an
  **R2 custom domain** with `fetch(url, { cf: { cacheEverything: true } })`
  instead of the binding — that puts the read on the normal CDN path, which
  Tiered Cache and range requests both understand, and would fix the basemap in
  the same move. Costs one extra hop on a miss.

### Re-tiling a mirrored map

A second tiling of a map that is already live goes to a new version:

```bash
./scripts/tile_map.sh <uuid> <source> --new-version     # or --version N to name it
./scripts/tile_map.sh <uuid> <source> --new-version --dry-run   # keys + service id, no writes
```

Keys land at `tiles/<uuid>/v<N>/` and the image service becomes
`https://iiif.maparchive.vn/iiif/<uuid>/v<N>`. N starts at 2 — there is no v1, because a map's
first tiling is the unversioned prefix and stays there forever. The scheme is **additive**: no
migration, no re-upload, nothing renamed, and every existing map keeps the keys and the
`maps.iiif_image` it has.

`--new-version` asks R2 for the highest `v<N>` already under the map and takes max+1, rather than
making the operator supply the number. Supplying it is the same failure one level down: guess a
version that already exists and you overwrite *that* render in place, immutably, having taken the
precaution that was supposed to prevent it. `--version N` exists for one case — resuming a
versioned upload that died halfway, where you need the same prefix again, not a fresh one.

**Overwriting in place looks like it works and does not.** Two reasons, and they compound:

- **Tiles go out `Cache-Control: public, max-age=31536000, immutable`.** That is the point of
  pre-tiling, and it means any browser or edge machine already holding a tile will not ask again
  for a year. The operator reloads, sees the new render — their own cache was cold for those
  keys — and calls it done; every reader who had opened the sheet keeps the old one.
- **`rclone copy` never deletes.** A rebuild that emits fewer levels (a smaller source, a corrected
  `scaleFactors` trim) leaves the old deep levels in the bucket, still answering 200. The new
  `info.json` stops advertising them, but a client holding the old `info.json` keeps asking, and
  gets one sheet served half from each render.

The version lives in the **image service id** rather than a query parameter or a response header
because that is the only thing a IIIF client takes tile URLs from: it derives every one of them
from `info.json`'s `id`. Change anything else and the client goes on constructing the old keys.
Same discipline as `basemap/vietnam-20260906.pmtiles` and `overlay/l7014-<date>.pmtiles`, and what
`docs/platform-design.md` means by "derived is disposable, immutable, content-addressed, no
`latest`".

**The upload is inert until the database moves.** `tile_map.sh` writes nothing to Supabase — on
purpose; applying a change to production is a person's job, not a script's side effect — and prints
the exact statements at the end of a versioned run. Four things name the old service id, and all
four move together:

| What | New value |
|------|-----------|
| `maps.iiif_image` | `<base>/v<N>` |
| `maps.thumbnail` | `<base>/v<N>/full/800,/0/default.jpg` |
| the primary `map_iiif_sources` row (`source_type = 'r2'`) | `<base>/v<N>` |
| the annotation JSON at `maps.annotation_url` | its source URL rewritten to `<base>/v<N>` |

The last is the one that gets forgotten, and it fails silently: the georeference still resolves and
the old tiles still answer, so a warped view draws the *previous* render over correct control
points and nothing reports an error anywhere. **Do not reach for Mirror to R2 to fix it** —
`mirrorAnnotation` (`src/lib/server/annotationMirror.ts`) builds its base as `${R2_BASE}/${mapId}`
with no version, so it would rewrite the annotation back to the unversioned id and undo the other
three updates on its way past. Until that is parameterised, a versioned re-tile is re-pointed by
hand.

`sources/<uuid>`, the proxy-fallback origin, is deliberately left unversioned: the upstream library
behind a miss is a property of the map, not of a render, and every version wants the same one.

### Why pre-tiled

Historical scans never change, so tiling once means zero compute at request time and no dependency on Internet Archive or Gallica staying up. `vips dzsave` takes any JPEG/PNG/TIFF directly — no pyramidal TIFF step. R2 egress is free, so tile serving costs storage only (~$0.15/mo at 20 maps × ~500 MB; ~$1.50/mo at 200).

### Layout and config

- Bucket `vma-tiles`, binding `TILES` (`worker/wrangler.toml`). Keys under `tiles/{mapId}/…`, `info.json` at `tiles/{mapId}/info.json`. A re-tile adds a sibling prefix `tiles/{mapId}/v{N}/…` served at `/iiif/{mapId}/v{N}` — the original keys are never touched (*Re-tiling a mirrored map* above).
- Production route `iiif.maparchive.vn/iiif/*` on zone `maparchive.vn`. (Older notes say `iiif.vmaproject.org` — that host was never live; a stale comment survives at `scripts/tile_map.sh:11`.)
- Tiles are served `Cache-Control: immutable`; `info.json` is served `max-age=0` because the worker patches it per-request.
- `Access-Control-Allow-Origin: *` is required on **both** `info.json` and tile responses — Allmaps will not load the overlay without it.
- Source scans stay in Supabase Storage as the re-tiling input; they are never served directly (egress).

### Prerequisites and gotchas

- `vips --version` and `rclone listremotes` (must show `r2:`) — `wrangler` cannot upload a directory, so `tile_map.sh` uses rclone.
- Tile size 256 is standard; 512 cuts request count on very large maps but enlarges the first tile. `Q=85` is the right quality band for archival scans (limited palette).
- BnF Gallica: download the highest-res JPEG from the viewer, not via the manifest (slow). IA: `https://archive.org/download/{identifier}/{file}.jpg`.
- Running mirror-r2 *before* the tiles are uploaded points `maps.iiif_image` at R2 while the objects are missing — the worker then falls back to the origin proxy and can 500. Tile first, or expect a gap.
- Keep the pre-mirror URL in `extra_metadata.iiif_image_original` as a fallback reference.

Full historical plan (phases, worker source draft, cost table): `docs/archive/iiif-r2-plan.md`.

## Scout & ingest (`/admin?tab=scout`)

External-source discovery + curate + bulk-ingest pipeline. Surfaces candidates from Gallica, Humazur, David Rumsey, Library of Congress, UWM AGDM as a reviewable grid. Admin approves rows → bulk-ingest as `draft` `maps` rows with full DC + `holding_institution`.

**Data flow:** scout JSON → `scout_candidates` table → admin review UI → approved → POST ingests as `maps` rows.

**The review UI** is two views over one queue, chosen by a pill toggle and remembered in `vma-scout-view-v1`: the **card grid** (judge a sheet by its picture) and a dense **table** on `.data-table.is-dense` (scan a thousand titles, spot the near-duplicates). Sorting is the server's — `?order=&dir=` — because the page holds 60 of 1041 rows and re-ordering only those would label the oldest sheet *on this page* as the oldest in the queue.

`ScoutDecision.svelte` is the approve/reject control both views mount, so a verdict behaves identically in each: preset reasons plus free text, Enter commits, Escape cancels, and a blank reason is allowed — the keyboard sweep (`a`/`r`) decides with no reason at all, which is the trade for clearing a page of obvious rows in seconds. The reason lands in `scout_candidates.review_note` (mig 078), which is the *person's* column: `reasons` belongs to the scorer and `load_scout_to_db.mjs` overwrites it on every re-load. Bulk approve/reject takes one reason for the batch.

**The score is no longer shown.** The loader still computes it and `score`/`reasons` still exist, but neither the chip nor the min-score filter is in the UI — 822 of 1041 rows score ≥ 40, so it never separated anything a person needed separated. A candidate with no usable image source carries a `no image` flag instead, which is the fact that actually decides whether ingest can proceed.

### Scout scripts (read-only, produce JSON)

| Script | What it does |
|--------|--------------|
| `scripts/scout_all_sources.mjs` | Gallica SRU (BnF + federated: Bordeaux 3, Paris, Sorbonne) + David Rumsey Luna API + Library of Congress JSON API + UWM AGDM CONTENTdm API. 15 Vietnam place keywords, `--sources` to pick. |
| `scripts/scout_humazur.mjs` | Humazur Omeka S API (sets 59 Cartothèque ASEMI + 519 Indochine française). `--merge <existing>.json` to combine. |
| `scripts/categorize_scout_results.mjs` | Scores + categorizes candidates. Outputs `scripts/scout_review.csv`. |
| `scripts/load_scout_to_db.mjs` | Loads merged scout JSON into `scout_candidates`. Fixes Humazur manifest URLs (must use `iiif/{item_id}/manifest`, NOT media_id). Derives Gallica thumbnails from ARK pattern. |
| `scripts/scoutDerive.mjs` | Per-source URL derivation, shared by the loader and the backfill so a pattern is written once: Omeka S manifests, the LoC Image API, protocol-relative permalinks. Self-check: `node scripts/scoutDerive.test.mjs`. |
| `scripts/oneoff/backfill_omeka_thumbs.mjs` | Backfills thumbnails for any Omeka S host (Omeka stores them on the media object, not the item — needs `/api/media/{id}`). Picks rows by `source_url` host, since the Bordeaux rows are labelled `gallica`. Throttled 150ms/req, dry-run by default. Replaced `backfill_humazur_thumbs.mjs`, which hardcoded the one host. |
| `scripts/oneoff/fix_scout_iiif.mjs` | Applied `scoutDerive` to the 985 rows loaded before it existed: 41 Bordeaux manifests, 42 LoC image URLs, 5 protocol-relative permalinks. Dry-run by default. |

### Source patterns (for adding new sources)

- **Gallica SRU**: `https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=(dc.type adj "carte") and (dc.title all "{keyword}")&maximumRecords=50&startRecord=1` — federated. Rate-limit ~3s/req, returns 429 if hammered. Use `--use-system-ca` or `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- **David Rumsey Luna**: `https://www.davidrumsey.com/luna/servlet/as/search?q={kw}&dh=50&os=json&so={offset}` — JSON, ~994 raw "Vietnam" hits. Filter on `fieldValues.Country/City/Region` to drop atlas pages.
- **Library of Congress**: `https://www.loc.gov/maps/?q={kw}&fo=json&c=50&sp={page}` — small but high-quality, ~50 total Vietnam hits. **No Presentation manifest is reachable**: item pages and `?fo=json` on an item both answer 403 behind a Cloudflare challenge. The Image API is fine, and the thumbnail names it — `tile.loc.gov/storage-services/service/gmd/gmd7/g7823/g7823g/ct003290.gif` → `tile.loc.gov/image-services/iiif/service:gmd:gmd7:g7823:g7823g:ct003290/info.json`. `deriveImageUrl` in `scoutDerive.mjs` does that, parking the result in `raw.iiif_image`, which ingest writes to `maps.iiif_image`. Rows with no thumbnail derive nothing and cannot be ingested.
- **Omeka S** (Humazur, and Bordeaux 3 via Gallica SRU federation): `{host}/iiif/{item_id}/manifest` — a IIIF v2 manifest. Two of the "gallica" federated hosts are Omeka S, so the BnF ark pattern leaves them with no manifest; `deriveManifestUrl` keys off the `source_url` host.
- **UWM AGDM (CONTENTdm)**: `https://collections.lib.uwm.edu/digital/bl/dmwebservices/index.php?q=dmQuery/agdm/CISOSEARCHALL^{kw}^all^and/{fields}/nosort/{n}/{offset}/1/0/0/0/json` — the American Geographical Society Library's map collection, 55 Vietnam hits, strong on 1920s-1960s French and US sheets. Field nicknames come from `dmGetCollectionFieldInfo/agdm/json` (`map`=creator, `maa`=publisher, `public`=date, `boundi`=bbox, almost always empty). IIIF Image API is level1 at `/digital/iiif/agdm/{pointer}`, manifest at `/iiif/2/agdm:{pointer}/manifest.json`. A `filetype: cpd` record is a **compound multi-sheet object**: its own pointer carries no image, so the single-item thumbnail answers 200 with HTML — take the first `pageptr` from `dmGetCompoundObjectInfo/agdm/{pointer}/json` (12 of the 55 are compound).
- **Humazur Omeka S**: `https://humazur.univ-cotedazur.fr/api/items?item_set_id={set}&resource_class_id=33&per_page=100&page={n}` — `resource_class_id=33` is StillImage. item_sets: 59 (Cartothèque ASEMI, ~417 pure maps), 519 (Indochine française, 1500+ mixed).

Skipped: IA (3500+ noisy hits, no clean filter); Cartomundi (JS app, needs headless browser); Princeton GeoBlacklight (geographic-bbox-indexed, 0 hits for "vietnam"); Harvard LibraryCloud (endpoint quirks); HathiTrust (Cloudflare-blocked).

### Workflow

```bash
# 1. Discover (~15 min)
NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/scout_all_sources.mjs
NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/scout_humazur.mjs --merge scripts/scout_all_<ts>.json

# 2. Load into DB (auto-picks latest scout JSON)
node scripts/load_scout_to_db.mjs

# 3. (Optional) Backfill Omeka S thumbnails — dry run, then --apply
NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/oneoff/backfill_omeka_thumbs.mjs
NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/oneoff/backfill_omeka_thumbs.mjs --apply

# 4. Review + ingest via UI
open https://<host>/admin?tab=scout
```

### API endpoints (admin/mod only)

- `GET /api/admin/scout?status=pending&source=humazur&category=urban_plan&minScore=40&q=Saigon&limit=60&offset=0` — paginated list with facet counts on first page.
- `PATCH /api/admin/scout/[id]` — approve/reject/revert (sets `reviewer_id` + `reviewed_at`).
- `POST /api/admin/scout` `{ ids: [...] }` — bulk-ingest approved candidates → `maps` rows (only operates on `status=approved`; sets `status=ingested` + `map_id` on success). Maps holding-institution string to `source_type`: "David Rumsey" → `rumsey`; "Bibliothèque nationale" → `bnf`; else `other`. Stamps `extra_metadata.scout_candidate_id` for traceability.

## Holding institution model

`maps.holding_institution` (mig 044) separates **who holds the original** from **how VMA serves it**.

| Column | Meaning | Example |
|--------|---------|---------|
| `creator` | Who made the map | `Service Géographique de l'Indochine` |
| `dc_publisher` | Who published it | same as creator for govt maps, or `Imprimerie d'Extrême-Orient` |
| `holding_institution` | Where the original lives now | `Bibliothèque nationale de France`, `Humazur, Université Côte d'Azur`, `David Rumsey Map Collection (Stanford)` |
| `collection` | Archival sub-collection | `Département Cartes et plans`, `Cartothèque ASEMI`, `AMS Series L7014` |
| `shelfmark` | Catalog ID at the holder | `GE C-2144` |
| `source_url` | URL of the item page at the holder | `https://gallica.bnf.fr/ark:/12148/btv1b530291797` |
| `source_type` | How VMA serves the image | `bnf` / `ia` / `self` / `rumsey` / `humazur` / `other` |

### Metadata standardisation

The one-off backfills that filled these columns (an audit, an online
verification pass against BnF and Humazur, and the PATCH script that consumed
their diff) were deleted once they had run — git history has them if a second
corpus ever needs the same treatment. `/admin?tab=bulk` and the scout pipeline
cover new maps.

## The shared ingest library (`scripts/lib/`)

Four institutional catalogues went into `sheet_sources` in September 2026 — Perry-Castañeda, Texas
Tech, ANU, IGN via CartoMundi and Nakala — and each arrived as its own script in `scripts/oneoff/`.
They share a shape: read a catalogue dump out of `work/`, parse a cell number and a title and a year
and an edition, report, upsert. Only the parsing is per-source. The rest was written fifteen times.

| Module | What it holds |
|--------|---------------|
| `lib/cells.mjs` | **How a sheet of paper is named.** `cellNumber` (Indochine `bis` cells and the catalogue's brackets), `cellOrder`, `cellOf` (an L7014 quadrant off an ANU title), `sheetPart` (demi-format / assemblage / W / E), `partFromTitle` (the same fact off the title's brackets, as an independent check), `printedYear` (a TTU collar), plus `clean` and `yearOf`. |
| `lib/db.mjs` | `serviceClient()` — and an error naming `--env-file=.env` rather than a 401 later. `upsertChunked()`, which takes `onConflict` as a required argument because a re-run without one duplicates instead of correcting. `duplicateKeys()`, the pre-flight that a duplicate item key otherwise turns into rows quietly lost inside a right-looking total. |
| `lib/http.mjs` | `UA` (one string, which identifies us and where to complain — three different ones were in the tree, one a bare `Mozilla/5.0`), `sleep`, and `fetchJson` with a timeout, backoff and throttle that retries a 429, a 5xx or a timeout and never a 404. |
| `lib/cli.mjs` | `willApply()`, `flag()`, `opt()`, `dryNotice()`. |

**Nothing writes without `--apply`.** That is the point of `cli.mjs`. Until 2026-09-14 eight scripts
wrote only with `--apply` and four wrote *unless* you passed `--dry` — same directory, opposite
defaults, and the writing default was the one that looks like an ordinary invocation:
`node --env-file=.env scripts/oneoff/ingest_indochine_nakala.mjs` inserted `maps` rows and tiled
scans. The four (`ingest_indochine_nakala`, `import_indochine_series_sheets`,
`backfill_series_printings`, `normalize_map_locations`) were flipped; `--dry` is still accepted and
now means what it always read as.

### Why the parsers moved

They were copies, and the headers admitted it — "lifted verbatim from `scout_anu_l7014.mjs`",
"verbatim from `import_indochine_series_sheets.mjs`", "same rule as `half()` in
`ingest_indochine_nakala.mjs`, widened" — with nothing keeping any of them so. Measured over the 304
real IGN copy records: the cell-number spellings agreed on all 304, and the three part classifiers
**disagreed on 79** — every assemblage. `ingest_indochine_nakala.mjs` had no assemblage branch and
answered 'whole'.

That never reached the database, because `nakala.json` is a pre-filtered read holding 11 demi-format
and 21 demi-feuille records and no assemblage. It was a landmine: regenerate that file over serie
175, which is *all* assemblages, and 79 two-half cells get minted as single whole-cell sheets, with
nothing in the output saying so. The merged `half()` now throws on one instead, because that script's
row model has no way to represent it.

`tests/ingest-cells.spec.ts` pins all of it on bytes copied out of the four catalogues (20 checks, in
`npm run test`). `node scripts/lib/cells.test.mjs` is the full-corpus run — every old parser beside
its replacement over all 304 IGN records, 160 ANU items and both hand-read TTU tables; the dumps are
42 MB and gitignored, so it skips cleanly when they are not on disk and is worth running after any
re-fetch, which is when a new spelling would arrive.

### What has not moved

`tile_map.sh` and `bulk_upload_local.sh` still each do their own `maps` insert, and
`ingest_indochine_nakala.mjs` shells into the first. Unifying the mirror step is worth doing **after**
the container decision in `docs/journals/260914-iiif-space-efficiency.md` — 119,616 tile objects
against one COG — because packaging it first means packaging it twice.

The other 20 scripts in `scripts/oneoff/` were left alone. They have already run and are kept as a
record of what was done to the data; rewriting them would change the record and buy nothing.

## Other admin scripts
