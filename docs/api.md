# API routes (`src/routes/api/`)

Reference for every server route. The rules that every handler follows are in `src/routes/CLAUDE.md`
→ API routes; this file is the per-route detail, moved out of `CLAUDE.md` in September 2026 so the
map stays short. Keep the two in step: a new route gets a line here, and only a new *rule* touches
`CLAUDE.md`.

Every handler follows the same shape: `requireRole → adminClient → query → json`, using the
`$lib/server` helpers `requireRole`/`getRole` (`auth.ts`), `adminClient` (`supabaseAdmin.ts`), and
`assertUuid`/`dbError` (`http.ts` — 400 on a malformed id, and no raw Postgres message ever reaches
the client).

Admin map CRUD:

- `/api/admin/maps/` — POST create (accepts all DC columns). **No GET** — the list comes from the
  client via `data/maps/service.ts`.
- `/api/admin/maps/[id]/` — PATCH update, DELETE.
- `/api/admin/maps/[id]/image/` — POST upload to Internet Archive.
- `/api/admin/maps/[id]/annotation/` — PATCH update Allmaps GCPs.
- `/api/admin/maps/[id]/iiif-sources/` — GET, POST. `.../[sourceId]/` — PATCH (incl. `is_primary`),
  DELETE.
- `/api/admin/maps/[id]/mirror-r2/` — POST: fetch the annotation we already have → rewrite source
  URL to R2 (`iiif.maparchive.vn`) → Supabase Storage → upsert R2 row as primary → return
  `tile_command`.
- `/api/admin/maps/[id]/sync-allmaps/` — POST: same, but re-reads from allmaps.org first ("Fetch
  latest from Allmaps" in MapEditHostingTab). Both share `$lib/server/annotationMirror.ts`, which
  writes **twice**: `annotations/{mapId}.json` (what the app reads) and
  `annotations/{mapId}/{ISO}.json` as history, since Storage has no versioning.
- `/api/admin/maps/fetch-iiif-metadata/` — POST `{ manifestUrl }` → parsed IIIF metadata + Allmaps
  probe.
- `/api/admin/maps/lookup-allmaps-id/` — POST `{ iiifImage }` → derive Allmaps image ID + probe.
- `/api/admin/maps/sync-georef/` — POST: probe the Allmaps annotation server for every map with
  `allmaps_id` and `is_georeferenced = false`, flip on hits. Idempotent; cron-safe. Returns
  `{ checked, flipped, ids }`. The flip itself enqueues `mirror_annotation` for an already-published
  map (mig 080's trigger), so no separate mirror call is needed.

Pipeline:

- `/api/admin/maps/[id]/triage/` — Admin **or mod** (`requireRole(locals, ['admin', 'mod'])`),
  unlike the rest of `/api/admin/maps/*`, which take `requireRole(locals)` and so default to admin
  alone — accepting a crop is review work. POST writes part of `maps.triage`, one key at a time
  through the `set_triage_key` RPC (`neatline`, `neatline_src`, `tile_size`, `overlap`,
  `tile_overrides`, `regions`, and `legend`: `'none'` or `null`, "this sheet prints no legend"), and `{ validate: true }` stamps `validated_at`/`validated_by` — the
  acceptance `enqueue_ocr_all.mjs` gates OCR spending on. Replaces PATCHing `maps` with a whole
  `triage` object, which dropped every key the page did not model (`grid`, `grid_at`, `regions_at`,
  `neatline_src`).
- `/api/admin/maps/[id]/layout/` — POST enqueues a `layout` job (202, or 409 when one is in flight);
  GET the saved regions plus the latest layout job. The worker runs `ocr.py scout --save-triage`.
- `/api/admin/maps/[id]/ocr/` — GET run summaries + the latest `pipeline_jobs` row for the map; POST
  enqueues an `ocr` job (202 `{ job_id, run_id, status }`, or 409 when one is already in flight).
- `/api/admin/maps/[id]/ocr/apply/` — POST: turn `ocr_labels` above a confidence threshold into
  `label_pins` (bbox centre in source-image px). Body `{ run_id?, min_confidence? }`.
- `/api/admin/maps/[id]/ocr-review/` — GET extractions + runs (`all=true` returns the whole sheet with
  paged database reads and derives counts from those rows); POST manual bbox; PATCH update
  text/category/status/coords/`rotation_deg`/`label_w`/`label_h` (the label rectangle and the box
  around it arrive together, so only a coord change re-warps); PUT batch status (`?window=` reverts
  the last N minutes).
- `/api/admin/maps/[id]/ocr-review/groups/` — POST ordered original IDs and combined text/Type;
  DELETE the combined label to restore its originals. The Text editor stages both locally;
  these endpoints are called only on explicit Save drafts. Save uses existing write endpoints,
  acknowledges each completed operation, and retains the unsaved remainder on failure.
- `/api/admin/maps/[id]/ocr-review/revert-recent/` — GET count, POST undo the current reviewer's
  recent validations (thin wrapper over `$lib/server/ocrReview.ts`).
- `/api/admin/maps/[id]/pipeline/` — GET the composed stage + timestamps; PATCH records a **human**
  stage (`reviewed`, `seg_reviewed`, `exported`, `idle`) via `set_review_mark`. The machine stages
  come from `pipeline_jobs` and are rejected with a 400.
- `/api/admin/footprints/` — GET/PATCH SAM2 review (staff only).
- `/api/admin/stories/` — GET the `submitted` queue, PATCH a decision (`approved` / `rejected` /
  `draft`) via `set_story_status`. Admin **or mod**.
- `/api/contribute/footprints/` — POST a hand-traced polygon. Any signed-in user; `user_id` comes
  from the session, never the body, and `assertUnderRateLimit` caps it at 300/hour.
  `data/supabase/footprints.ts:createFootprint` posts here rather than inserting directly.

Worker-authenticated (`Authorization: Bearer <worker_keys token>`, **not** a user session — see
`$lib/server/workerAuth.ts`):

- `/api/pipeline/claim/` — POST `{ kinds, worker }` → the claimed job or `{ job: null }`. A key
  scoped to certain kinds cannot claim outside them; the claim is bound to the key ID.
- `/api/pipeline/results/` — POST with a required `job_id`. Results must match the claimed job's
  owner, kind, map and OCR run. `extractions` (≤500 rows) accept only machine-output fields and
  are inserted on `(map_id, run_id, tile_x, tile_y, text, global_xi, global_yi)` without
  overwriting existing reviewed rows. The reply reports offered and already-present counts.
  The body may also carry `map_id` +
  `triage_regions` / `triage_grid` (the layout pass, written one key at a time through the
  `set_triage_key` RPC so it cannot clobber a hand-drawn neatline — and regions whose `source` is
  `human` are kept, so a second **Detect** no longer discards every correction), and/or
  `status` (→ `finish_job`). There is no stage field: closing the job advances the stage.
- `/api/pipeline/execute/` — POST `{ job_id }` for the kinds whose work belongs on the server
  (`mirror_annotation`, `sync_allmaps`): they need the service key, which a worker deliberately
  lacks. The handler runs the mirror and closes the job itself. Kinds with real compute (`ocr`,
  `seg`, `tile_to_r2`) are rejected with a 400 — those run on the worker.

Mint a token with `node --env-file=.env scripts/mint-worker-key.mjs <name> [kinds]`; it prints once
and only the sha256 is stored. Revoke by setting `worker_keys.revoked_at`.
- `/api/export/footprints/` — **public** GET, no auth: it builds its own client from
  `PUBLIC_SUPABASE_URL` + `PUBLIC_SUPABASE_ANON_KEY`, so it sees exactly what an anonymous reader
  sees and never the service key. Query: `map_id` (one uuid or a comma-separated list; required for
  `format=coco`), `status` (**default `approved`** — a reviewed polygon is the only kind an
  anonymous consumer should be handed, so `?status=submitted` is the explicit opt-in that returns
  the raw, unreviewed queue), `year` (`from-to`, on the source map's year), `bbox`
  (`minLng,minLat,maxLng,maxLat`, applied **after** the warp so it selects by where the feature is
  on the ground — features that could not be warped are dropped when `bbox` is given, since they
  have no position), `format` (`geojson` default, or `coco`), `limit` (default 5000, max 20000 —
  without `map_id` this would otherwise stream the whole archive on one request), and COCO-only
  `pad` (crop padding px, default 128) and `size` (IIIF crop size, default 1024). COCO returns
  `images[]` (one per footprint, with a IIIF crop URL and dimensions), `annotations[]` (segmentation
  relative to each crop) and `categories[]` (`feature_type` classes) — a dataset ready for
  segmentation training. Note `ringIntersectsBbox` is envelope overlap rather than true
  intersection, so `bbox` is deliberately over-inclusive.

Public / other:

- `/api/maps/[id]/open/` — **public** POST. Records one published-map view through the bounded
  `record_map_view` RPC and returns `{ recorded }`; direct table inserts are closed.
- `/api/maps/[id]/annotation/` — **public for published maps** GET; drafts require a signed-in
  session. Streams the stable annotation from the private Storage bucket. A `?version=` history
  request requires staff MFA. Direct Storage object URLs are no longer public.
- `/api/series/[key]/annotation/` — **public** GET, published and georeferenced sheets only. One
  Georeference Annotation Page merging every such sheet's stable annotation, so
  `viewer.allmaps.org/?url=<this>` shows the survey whole. `[key]` is `maps.series_key`; capped at
  60 sheets (one Storage download each), so a large series such as L7014 needs a pre-merged file.
- `/api/maps/[id]/legend-points/` — **public** GET. Numbered-legend references placed on the ground:
  each body numeral (`category = 'legend_ref'`) warped to lng/lat via the map's Allmaps
  georeference, joined to its `legend_entry` for a name. Legend-internal numbers are dropped.
  Rendered by `src/lib/features/shared/LegendPointsLayer.svelte`. Reviewed manual positions
  override numeral/grid positions. Staff with MFA also receive `canEdit` and `entries`,
  including entries without a position. Responses are private and not cached.
- `/api/admin/maps/legend-stats` — **admin or mod with MFA** GET: `{ [mapId]: { total, placed } }`,
  entries read off each sheet's legend and how many have a pixel position (`px=` only). One paged
  read over every sheet; feeds the progress badges and status chips in the `/scan?mode=legend`
  map picker.
- `/api/admin/maps/[id]/legend-points/` — **admin or mod with MFA** GET: the legend in **image
  pixels**, for `/scan?mode=legend`. `{ entries: [{ id, n, name, vn, grid, x, y, src: 'manual'|null,
  more: [[x, y]…], validated }], candidates: [{ n, x, y, inCell: boolean|null, labelId }], grid, legendRects }`.
  No georeference is read, so drafts work; `inCell` is whether a body numeral agrees with its
  entry's grid reference (`null`: nothing to check). A legacy ground `point=` has no pixel and reads
  as unplaced. Shares its reads with the public GET (`$lib/server/legendRead.ts`). Same route,
  PATCH
  `{ id, name, vn, grid, x, y }` (image pixels) or `{ id, name, vn, grid, lng, lat }` or `{ entries: [...] }` (up to 200 entries). Corrects existing
  numbered OCR legend entries; the batch response returns `{ saved: [id], failed: [{ id, message }] }`
  so clients can retain and retry only failed drafts. The request validates every entry before writing
  and preserves raw OCR text and unrelated notes. A manual position is saved in **image
  pixels** as `px=x,y` in its existing notes — a ground click is taken back through the map's own
  annotation first (409 if it has none) — so it follows any re-georeference; the GET warps it.
  Pre-2026-10-05 rows carried `point=longitude,latitude` and are still read
  (`scripts/oneoff/legend_points_to_pixels.mjs` converts them). Null coordinates restore automatic
  positioning. Review stamps go through `set_extraction_status`. A ground-click entry may carry
  `find: { query, osmType, osmId, osmName, lng, lat }` — the place search that led the editor there;
  each saved one is appended to `legend_finds` (mig 119) as today's ground truth for the entry. A
  malformed `find` is a 400; a failed `legend_finds` insert leaves the entries saved and adds
  `warning` to the batch response.
  `more` is the entry's further pixel positions — a number printed on several plots (1878's №21, a
  depot of two yards). The first stays `px=`; the rest are `more=x,y|x,y` in the notes, at most 20,
  dropped when the entry has no first point. The public GET keeps `points` one per number and adds a
  separate `more: Point[]` that only the map's pins read.
- `/api/admin/maps/work-state` — **admin or mod** GET, `?map=<uuid>` narrows to one: `{ [mapId]: WorkFacts }`
  (`$lib/core/sheetWork.ts`), what has been done to each sheet — triage state, which regions the
  layout found (title, legend, index), which kinds OCR read, OCR/segmentation ran, text/shapes
  reviewed, and the person's "no legend" mark. Derived on every call from `maps.triage`,
  `ocr_labels.category` and `map_pipeline_status`, never stored; a sheet nobody has touched has no
  key. `Cache-Control: private, no-store`. Feeds the catalog table, grid and drawer (`SheetStatus`,
  `WorkPips`), `SheetWork` on `/catalog/[id]` and the `/scan?mode=legend` picker. The index pass is not in it.
- `/api/admin/series/` — admin GET: every `series` row (`id,key,name,code,scale_denominator`), for the
  map editor's series picker.
- `/api/admin/sheet-printings/` — admin GET `?series_id=&sheet_number=` the cell's `sheet_printings`
  and its source items; POST creates one on that cell. `.../[id]/` — PATCH its fields
  (`$lib/server/sheetPrintingFields.ts` decides which). `/api/admin/cell-printings/[id]/` — PATCH
  links or unlinks one institution source item to a printing (`{ printing_id }`, `null` clears).
- `/api/admin/scout/`, `/api/admin/scout/[id]/` — see `docs/admin-tooling.md`.
- `/api/admin/status/` — GET the tallies behind `/admin?tab=status` (`head: true` counts, plus the
  small failed-job list). Admin or mod.
- `/api/context/` — **public** GET `?lng=&lat=&radius=&year_from=&year_to=&limit=`: everything the
  archive knows about a spot — covering maps, nearby OCR labels and reviewed footprints, story
  points — via the `context_at` RPC (mig 066). Every item carries `distance_m` and `geom_rmse`;
  ungeoreferenced maps are absent by construction. Design in `docs/platform-design.md` §0.
  The route adds `legend: [{ map_id, year, n, name, vn, lng, lat, src, distance_m }]` — numbered
  legend references from the public maps the RPC returned, warped per request through the same
  `warpLegend` as `/api/maps/[id]/legend-points` (so `src` is `manual | numeral | grid`; a `grid`
  point is a cell centre, not a position), kept within `radius`, sorted by distance and capped at
  `limit`. `year` is the map's, and the RPC's `year_from`/`year_to` already decided which maps count.
  Draft maps contribute none, even to staff. Labels are the five gazetteer categories only
  (street, hydrology, place, building, institution) as of mig 115 (in production 2026-10-06); before it a legend entry or a
  title could come back as a label.
- `/api/press/` — **public** GET `?q=&year=&window=&limit=&provider=&variants=`: newspaper hits ±N
  years for a label, from Gallica and the National Library of Vietnam. No auth, no database,
  edge-cached a day; always 200 so a provider outage thins the /explore panel instead of erroring.
  Also returns `curve.nlv` — `{ total, decades }` across the **whole** archive, not just the window
  — which comes free with the NLV response (its results page carries a decade facet). Gallica has no
  facet, so there is no `curve.gallica`; a curve there would be one request per decade. NLV is
  queried directly at `baochi.nlv.gov.vn`, which is http-only, so thumbnails route through an https
  image proxy — see `docs/pipelines.md`.
- `/api/search/` — unified GET over `maps` + (admin/mod) `scout_candidates`. Postgres tsvector via
  `.textSearch('search_vector', q, { config: 'simple' })`. Query:
  `q, area, region, institution, type, period, source, scoutSource, category, georef, include=maps,scout,labels, limit, offset`.
  `area` accepts comma-separated pre-July-2025 province names and matches any entry in
  `maps.regions`, falling back to `region` for older rows. It constrains map results only;
  `facets.area` ignores its own selection while respecting the other map facets. Slim area
  queries filter before pagination. Catalog text search also matches both province arrays,
  with accents folded in the browser; the API's `q` still uses its existing text index.
  `region` accepts comma-separated geographic region keys from `catalogRegions.ts`
  (for example `mekong-delta`, `southeast`, `red-river-delta`). Membership derives from
  the pre-merger province list; a map can belong to multiple regions. It combines
  with `area` using AND; `facets.region` excludes its own selection. Slim queries
  apply both coverage filters before pagination.
  Returns `{ maps, scout, labels, total, facets, periods, role }` — map rows carry `slug` (mig 088)
  in both the full and slim column sets, because the catalog drawer and the command palette link
  onward and a row without it falls back to a uuid link; facet tallies are declarative via
  `$lib/server/facets.ts` ("all-but-this-dimension"). Public users get
  `status IN ('public','featured')` server-enforced; `include=scout` is silently dropped for
  non-admin/mod. **`include=labels`** searches *inside* the maps: the `search_labels` RPC (mig 065,
  `pg_trgm` word-similarity ≥ 0.5 over unaccented `ocr_labels` text, one row per map × label,
  drafts gated by role) and each hit's bbox centre warped to lng/lat via
  `$lib/server/transformer.ts`. Rendered by `LabelHits.svelte` on /catalog (links to
  `/explore?map=<id>&at=<lng>,<lat>`) and in /explore's browse pane (stacks the map, lands on the
  spot). Only maps that have been OCR'd can hit — `scripts/enqueue_ocr_all.mjs` queues the rest —
  triaged sheets only, unless `--untriaged`.
- `/sitemap.xml` — **public** GET, no auth (`src/routes/sitemap.xml/+server.ts`). Not under `/api/`,
  but a server route with a contract: the crawl entry the server-rendered half of the site never
  had. Emits the editorial pages in `LOCALIZED_PATHS` (twice, once per locale), `public`/`featured`
  maps only, the place pages nothing else links to (`place_names` has been published-only since
  migration 068) and the blog posts. Cached an hour — long enough to be worth generating, short
  enough to follow a publish. It uses `adminClient` to read but filters to published rows itself.
- `/auth/callback/`.

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce
references.

`/catalog/area/[slug]` is a server-rendered coverage destination. The pilot
registry is `src/lib/core/catalogAreas.ts`: Hồ Chí Minh, Hà Nội and Thừa Thiên Huế,
using the pre-July-2025 province labels already stored in `maps.regions`.
Pages list published maps chronologically and distinguish estimated coverage
from an attested historical place name. An empty area returns 404 and is omitted
from the catalog band and sitemap. `/catalog?area=<province>` initializes the
existing Area facet; arbitrary filter combinations do not get sitemap entries.
The catalog also offers six geographic-region browse links and a Region filter,
initialized by `/catalog?region=<key>`. Legacy `maps.location` labels such as
`Saigon-HCMC` no longer stand in for calculated coverage in the table, drawer or
individual map record. Province coverage labels explicitly identify the boundary period.
