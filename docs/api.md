# API routes (`src/routes/api/`)

Reference for every server route. The rules that every handler follows are in `src/routes/CLAUDE.md` → API routes; this file is the per-route detail, moved out of `CLAUDE.md` in September 2026 so the map stays short. Keep the two in step: a new route gets a line here, and only a new *rule* touches `CLAUDE.md`.

Every handler follows the same shape: `requireRole → adminClient → query → json`, using the `$lib/server` helpers `requireRole`/`getRole` (`auth.ts`), `adminClient` (`supabaseAdmin.ts`), and `assertUuid`/`dbError` (`http.ts` — 400 on a malformed id, and no raw Postgres message ever reaches the client).

Admin map CRUD:

- `/api/admin/maps/` — POST create (accepts all DC columns). **No GET** — the list comes from the client via `data/maps/service.ts`.
- `/api/admin/maps/[id]/` — PATCH update, DELETE.
- `/api/admin/maps/[id]/image/` — POST upload to Internet Archive.
- `/api/admin/maps/[id]/annotation/` — PATCH update Allmaps GCPs.
- `/api/admin/maps/[id]/iiif-sources/` — GET, POST. `.../[sourceId]/` — PATCH (incl. `is_primary`), DELETE.
- `/api/admin/maps/[id]/mirror-r2/` — POST: fetch the annotation we already have → rewrite source URL to R2 (`iiif.maparchive.vn`) → Supabase Storage → upsert R2 row as primary → return `tile_command`.
- `/api/admin/maps/[id]/sync-allmaps/` — POST: same, but re-reads from allmaps.org first ("Fetch latest from Allmaps" in MapEditHostingTab). Both share `$lib/server/annotationMirror.ts`, which writes **twice**: `annotations/{mapId}.json` (what the app reads) and `annotations/{mapId}/{ISO}.json` as history, since Storage has no versioning.
- `/api/admin/maps/fetch-iiif-metadata/` — POST `{ manifestUrl }` → parsed IIIF metadata + Allmaps probe.
- `/api/admin/maps/lookup-allmaps-id/` — POST `{ iiifImage }` → derive Allmaps image ID + probe.
- `/api/admin/maps/sync-georef/` — POST: probe the Allmaps annotation server for every map with `allmaps_id` and `georef_done = false`, flip on hits. Idempotent; cron-safe. Returns `{ checked, flipped, ids }`. The flip itself enqueues `mirror_annotation` for an already-published map (mig 080's trigger), so no separate mirror call is needed.

Pipeline:

- `/api/admin/maps/[id]/triage/` — POST writes part of `maps.triage`, one key at a time through the `set_triage_key` RPC (`neatline`, `neatline_src`, `tile_size`, `overlap`, `tile_overrides`, `regions`), and `{ validate: true }` stamps `validated_at`/`validated_by` — the acceptance `enqueue_ocr_all.mjs` gates OCR spending on. Replaces PATCHing `maps` with a whole `triage` object, which dropped every key the page did not model (`grid`, `grid_at`, `regions_at`, `neatline_src`).
- `/api/admin/maps/[id]/layout/` — POST enqueues a `layout` job (202, or 409 when one is in flight); GET the saved regions plus the latest layout job. The worker runs `ocr.py scout --save-triage`.
- `/api/admin/maps/[id]/ocr/` — GET run summaries + the latest `pipeline_jobs` row for the map; POST enqueues an `ocr` job (202 `{ job_id, run_id, status }`, or 409 when one is already in flight).
- `/api/admin/maps/[id]/ocr/apply/` — POST: turn `ocr_extractions` above a confidence threshold into `label_pins` (bbox centre in source-image px). Body `{ run_id?, min_confidence? }`.
- `/api/admin/maps/[id]/ocr-review/` — GET extractions + runs; POST manual bbox; PATCH update text/category/status/coords/`rotation_deg`/`label_w`/`label_h` (the label rectangle and the box around it arrive together, so only a coord change re-warps); PUT batch status (`?window=` reverts the last N minutes).
- `/api/admin/maps/[id]/ocr-review/revert-recent/` — GET count, POST undo the current reviewer's recent validations (thin wrapper over `$lib/server/ocrReview.ts`).
- `/api/admin/maps/[id]/pipeline/` — GET the composed stage + timestamps; PATCH records a **human** stage (`reviewed`, `seg_reviewed`, `exported`, `idle`) via `set_review_mark`. The machine stages come from `pipeline_jobs` and are rejected with a 400.
- `/api/admin/footprints/` — GET/PATCH SAM2 review (staff only).
- `/api/admin/stories/` — GET the `submitted` queue, PATCH a decision (`approved` / `rejected` / `draft`) via `set_story_status`. Admin **or mod**.
- `/api/contribute/footprints/` — POST a hand-traced polygon. Any signed-in user; `user_id` comes from the session, never the body, and `assertUnderRateLimit` caps it at 300/hour. `data/supabase/footprints.ts:createFootprint` posts here rather than inserting directly.

Worker-authenticated (`Authorization: Bearer <worker_keys token>`, **not** a user session — see `$lib/server/workerAuth.ts`):

- `/api/pipeline/claim/` — POST `{ kinds, worker }` → the claimed job or `{ job: null }`. A key scoped to certain kinds cannot claim outside them.
- `/api/pipeline/results/` — POST `extractions` (≤500 rows, upserted on `(map_id, run_id, tile_x, tile_y, text, global_xi, global_yi)`; the reply carries `extractions_offered` too whenever the database accepted fewer than were sent), `map_id` + `triage_regions` / `triage_grid` (the layout pass, written one key at a time through the `set_triage_key` RPC so it cannot clobber a hand-drawn neatline — and regions whose `source` is `human` are kept, so a second **Detect** no longer discards every correction), and/or `job_id` + `status` (→ `finish_job`). There is no stage field: closing the job advances the stage.
- `/api/pipeline/execute/` — POST `{ job_id }` for the kinds whose work belongs on the server (`mirror_annotation`, `sync_allmaps`): they need the service key, which a worker deliberately lacks. The handler runs the mirror and closes the job itself. Kinds with real compute (`ocr`, `seg`, `tile_to_r2`) are rejected with a 400 — those run on the worker.

Mint a token with `node --env-file=.env scripts/mint-worker-key.mjs <name> [kinds]`; it prints once and only the sha256 is stored. Revoke by setting `worker_keys.revoked_at`.
- `/api/export/footprints/` — data export (`?format=coco&map_id=`).

Public / other:

- `/api/maps/[id]/legend-points/` — **public** GET. Numbered-legend references placed on the ground: each body numeral (`category = 'legend_ref'`) warped to lng/lat via the map's Allmaps georeference, joined to its `legend_entry` for a name. Legend-internal numbers are dropped. Rendered by `src/lib/features/explore/LegendPointsLayer.svelte`.
- `/api/admin/scout/`, `/api/admin/scout/[id]/` — see `docs/admin-tooling.md`.
- `/api/admin/status/` — GET the tallies behind `/admin?tab=status` (`head: true` counts, plus the small failed-job list). Admin or mod.
- `/api/context/` — **public** GET `?lng=&lat=&radius=&year_from=&year_to=&limit=`: everything the archive knows about a spot — covering maps, nearby OCR labels and reviewed footprints, story points — via the `context_at` RPC (mig 066). Every item carries `distance_m` and `geom_rmse`; ungeoreferenced maps are absent by construction. Design in `docs/platform-design.md` §0.
- `/api/press/` — **public** GET `?q=&year=&window=&limit=&provider=&variants=`: newspaper hits ±N years for a label, from Gallica and the National Library of Vietnam. No auth, no database, edge-cached a day; always 200 so a provider outage thins the /explore panel instead of erroring. Also returns `curve.nlv` — `{ total, decades }` across the **whole** archive, not just the window — which comes free with the NLV response (its results page carries a decade facet). Gallica has no facet, so there is no `curve.gallica`; a curve there would be one request per decade. NLV is queried directly at `baochi.nlv.gov.vn`, which is http-only, so thumbnails route through an https image proxy — see `docs/pipelines.md`.
- `/api/search/` — unified GET over `maps` + (admin/mod) `scout_candidates`. Postgres tsvector via `.textSearch('search_vector', q, { config: 'simple' })`. Query: `q, institution, type, period, source, scoutSource, category, georef, include=maps,scout,labels, limit, offset`. Returns `{ maps, scout, labels, total, facets, periods, role }`; facet tallies are declarative via `$lib/server/facets.ts` ("all-but-this-dimension"). Public users get `status IN ('public','featured')` server-enforced; `include=scout` is silently dropped for non-admin/mod. **`include=labels`** searches *inside* the maps: the `search_labels` RPC (mig 065, `pg_trgm` word-similarity ≥ 0.5 over unaccented `ocr_extractions` text, one row per map × label, drafts gated by role) and each hit's bbox centre warped to lng/lat via `$lib/server/transformer.ts`. Rendered by `LabelHits.svelte` on /catalog (links to `/explore?map=<id>&at=<lng>,<lat>`) and in /explore's browse pane (stacks the map, lands on the spot). Only maps that have been OCR'd can hit — `scripts/enqueue_ocr_all.mjs` queues the rest — triaged sheets only, unless `--untriaged`.
- `/auth/callback/`.

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce references.
