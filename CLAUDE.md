# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

Vietnam Map Archive (VMA) — a SvelteKit 5 app for exploring georeferenced historical maps of Saigon/Ho Chi Minh City. Integrates Allmaps with OpenLayers.

## Where to look first

- `docs/db-guidelines.md` — schema conventions; all migrations must follow these
- `docs/architecture.md` — **the map runtime**: MapShell/ImageShell, the stores, route groups, the /explore rails, the contribute tools, the PMTiles basemap and the series layers. Was §Architecture of this file until Sept 2026; split out because 66 kB of it rode every session
- `docs/conventions.md` — the reasoning behind the one-line rules below: fonts, the gazetteer key, the generated types, the realtime stub, the component/theme vocabulary
- `docs/testing.md` — what each of the 280 tests pins, and the failure it exists to catch
- `docs/system-guidelines.md` — layering rule, page structure, component patterns, route map, known debt
- `docs/design-system.md` — tokens, the CSS file map, page template
- `docs/ROADMAP.md` — **the one tracker**: ship/harden · architecture steps · OCR↔SAM2 product · burn-down
- `docs/time-machine-plan.md` — label search · temporal fabric · period sources (Track E detail)
- `docs/time-walk-plan.md` — the walk-through surface (Track F): HACW forked for a District 4 route, warped sheets as a year slider, and the frozen-JSON seam between the two apps
- `docs/platform-design.md` — one workspace for VMA + HACW: what is shared (contracts, basemap, deploy, docs) and what stays per-app, with sequencing
- `docs/digitalize-guide.md` — **operator guide** for `/scan?mode=prepare`: propose-then-accept, what each layout category means, the ground-per-call target, and the failure modes that return plausible output while dropping data
- `docs/api.md` — every server route, its auth class and its contract
- `CHANGELOG.md` — version history, 1.0 (Apr 2025, one `index.html`) to **7.0** (current). The numbers continue the ones the commits already used, so the SvelteKit rewrite is 3.x; the number moves on a structural change, not a build. 6.0 and 7.0 in full, earlier versions summarised, and the three ancestor repos recorded at the foot. **Its public twin is `/changelog`**, whose source is `src/routes/(editorial)/changelog/releases.ts` — plain language, shorter, a different audience. Nothing generates one from the other: add a release to both.
- `docs/deploy.md` — Cloudflare Pages: env in the dashboard, no root `wrangler.toml`, the blank-page-after-deploy effect
- `docs/pipelines.md` — OCR + MapSAM2 command reference and design rationale. §*Getting more out of OCR* is the ranked list of what to do next and what not to re-attempt; `work/ocr/EVAL-BASELINE.md` is the measured gate behind it. `scripts/` holds the living operator scripts; `scripts/oneoff/` the backfills that have already run and stay only as a record.
- `docs/admin-tooling.md` — MapEditModal, Bulk Upload, Scout, R2 worker, holding-institution model
- `docs/strategy.md` (funder-facing), `docs/theory.md`, `docs/user-guide.md` — vision and outward-facing prose, not engineering reference. `docs/journals/` holds dated research notes (`YYMMDD-slug.md`).
- `contracts/` — JSON Schemas for the shapes VMA shares with other apps (`context`, `label-hit`, `footprint-feature`); checked by `tests/schemaCheck.ts`.
- `docs/ponytail-debt.md` — generated ledger of `ponytail:` shortcuts. Regenerate with `/ponytail-debt`; never hand-edit.
- `docs/archive/` — frozen: historical plans, personal application material, and the record of the August 2026 cleanup (`cleanup-2026-08.md`). Do not cite as current; the live debt table is `docs/system-guidelines.md` §11.
- `work/MapSAM2/` — fine-tuned SAM2 fork (LoRA, training notes) in `TECHNICAL.md` + `VMA_SETUP.md`. Runs on Colab, not locally.
- `work/ocr/` — OCR pipeline, its own venv at `work/ocr/.venv`, plus `EVAL-BASELINE.md` (measured quality gate).

## Commands

```bash
npm run dev          # Dev server
npm run build        # Production build (wipes .svelte-kit/output first — see note below)
npm run check        # Type-check (primary verification) — currently 0 errors / 0 warnings
npm run lint         # prettier --check . && eslint .
npm run format       # prettier --write .
npm run test         # Playwright smoke suite, read-only (tests/smoke.spec.ts)
npm run db:test      # Start the local Supabase stack + seed the write-test fixtures
npm run db:test:reset  # Replay every migration from scratch, then reseed
npm run test:write   # Write-path smokes against that local stack (tests/write.spec.ts)
npm run deploy       # Build + deploy to Cloudflare Pages via wrangler
npx wrangler pages dev .svelte-kit/cloudflare  # Local CF preview
```

There is no root `wrangler.toml` on purpose — see Deployment. The R2 tile worker has its own `worker/wrangler.toml`.

**A blank page right after a deploy is edge propagation, not a bug** — chunks 404 for a minute or two, and with `ssr = false` one missing chunk is a blank document. Wait and hard-reload first; details and the `curl` check in `docs/deploy.md`.

`build` wipes `.svelte-kit/output` and runs `scripts/check-bundle.mjs`, which fails the build if an emitted chunk imports one that wasn't written. That guards against a genuinely inconsistent bundle — it does **not** address the propagation lag above, which no build-time check can see.

Never import a Node builtin bare (`import('path')`); the CF Functions bundle errors with `Could not resolve "path"` and publishes nothing. Use the `node:` prefix.

`npm run test` starts a dev server on 5173, or reuses one already running. It runs **280** tests: eleven read-only smokes in `tests/smoke.spec.ts` (they hit the real Supabase project but never write) plus 269 browser-less pure checks riding the same runner. **What each one pins, and why it exists, is `docs/testing.md`** — read it before changing a check or adding one, because most of them exist to catch a failure that looks like data rather than like a bug.

**Write paths** are covered separately by `npm run test:write` (`tests/write.spec.ts`, 25 tests) against a **local** stack, never production: `npm run db:test` runs `supabase start -x vector -x logflare` and seeds one staff user + one map via `scripts/seed-test-db.mjs`. The suite throws unless `PUBLIC_SUPABASE_URL` is a loopback address, and deletes every row it writes. Credentials come from `.env.test` (the CLI's published demo keys, committed on purpose) which Vite loads for the `--mode test` dev server on port 5199. Server-route auth is done by letting `@supabase/ssr` mint the session cookies, so chunking and encoding match the app exactly.

Local ports are **54421** for the API and **54420** for the shadow DB, not the CLI defaults — 54321/54320 collide with another local project. `-x vector -x logflare` is needed under colima: those containers bind-mount `/var/run/docker.sock`, which colima cannot provide.

Supabase project ref `trioykjhhwrruwjsklfo` (Sydney) is already linked. `supabase db push` and `supabase migration list` both work directly (verified 2026-09-10 — `migration list` prints the local/remote table without a password prompt). `supabase db pull` still asks for a direct DB password; use the Dashboard SQL Editor or `db push` instead of pulling. Repair migrations with `supabase migration repair --status applied|reverted <id>`.

**Adding a migration** — drop a new `supabase/migrations/NNN_*.sql` (incrementing from the current head, **086**), `supabase db push`, then regenerate types: `supabase gen types typescript --linked 2>/dev/null > src/lib/data/supabase/types.ts`. Run `npm run check` to catch fallout.

## Conventions

**Svelte syntax — legacy, NOT runes.** Use `$:`, `export let`, `createEventDispatcher`, `$store`. Do not use `$state`, `$derived`, `$effect`.

**Svelte MCP server** (plugin `svelte`, from `sveltejs/ai-tools` — see https://svelte.dev/docs/ai/skills). Available tools:

- `list-sections` — call first to discover documentation sections; pick by the `use_cases` field.
- `get-documentation` — fetch the full text of every section relevant to the task.
- `svelte-autofixer` — run on any Svelte code before showing it; re-run until it reports no issues.
- `playground-link` — offer a playground link after a standalone component (not for project-file edits).

Delegate `.svelte` / `.svelte.ts` work to the `svelte-file-editor` agent when it is more than a small edit; it iterates with the autofixer in its own context.

**Caveat for this repo:** the autofixer and the Svelte skills assume runes, and their "avoid legacy features" list is exactly this repo's house style (line above) — `$:`, `export let`, `on:click`, `<slot>`/`<svelte:fragment>`, `<svelte:component>`, `<svelte:self>`, `createEventDispatcher`, stores, `use:action`, `class:`. Ignore every suggestion to modernise those; act only on the rest (missing `{#each}` keys, effect cleanup, scoped-CSS and a11y findings, real bugs).

**Svelte house rules live in one place**: the `svelte-core-bestpractices` skill (`.agents/skills/`, symlinked into `.claude/skills/`). It is a **project fork** of the upstream `sveltejs/ai-tools` skill, rewritten for this repo's legacy dialect and merged with <https://github.com/spiegelgraphics/svelte-best-practices>. **Load it before creating, editing or reviewing any `.svelte` file.** It covers the dialect, the HTML→CSS→template→JS ladder, `$:` discipline, reassign-don't-mutate, keyed `{#each}`, scoped CSS, component size and teardown. `skills-lock.json` still carries the upstream hash, so `npx skills add` would revert the fork.

**Layering rule (enforced by `@typescript-eslint/no-restricted-imports` in `eslint.config.js`; type-only imports are exempt):**

> `core → data → map → features → routes`; `ui` is leaf primitives with zero domain imports; `server` is `$lib/server` only.

A directory may import only from directories to its **left**. Routes stay thin: load + wire, no business logic.

**Feature isolation (also lint-enforced):** a feature may import another feature only through a declared seam — `src/lib/features/shared/` (cross-cutting UI: the layer panels, `SidebarCard`, `MapViewerSidebar`, `LabelHits`, and the `catalogSearch` client) or `src/lib/features/<x>/shared/` (that feature's public API — `stories/shared`, `contribute/shared`, `catalog/shared`). Everything else under another feature is private. Routes may import anything under `features/`.

```
src/lib/
├─ core/      pure — no OL, no Supabase        geo/ iiif/ utils/ (+ utils/persistence/)
├─ data/      DB/HTTP access + canonical types  supabase/ maps/ admin/
├─ server/    $lib/server — SvelteKit blocks client import
│             auth.ts supabaseAdmin.ts http.ts storage.ts ia.ts mapFields.ts
│             facets.ts transformer.ts allmaps.ts ocrReview.ts
├─ map/       the OpenLayers runtime, one home  shell/ stores/ annotations/ types.ts constants.ts
├─ features/  one dir per product surface       explore/ catalog/ stories/ annotate/ contribute/ admin/
└─ ui/        generic primitives only           NavBar EditorialFooter PageHero MapCard Tabs SortHeader LocationSearch …
```

`$lib/server/*` is import-guarded by SvelteKit — a client-side import of the service key is a build error, not a code-review catch.

**Environment variables:**

```
PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY   # anon key = the sb_publishable_… key
SUPABASE_SERVICE_KEY            # admin API routes only; the sb_secret_… key
IA_S3_ACCESS_KEY, IA_S3_SECRET_KEY   # Internet Archive upload
VMA_API_URL, VMA_WORKER_KEY     # worker machines only — never the web app
```

List reads go through `LIST_COLUMNS` in `src/lib/data/maps/service.ts` — exactly the columns `toMapListItem` projects. `select('*')` was 120 kB of row for the catalog (37 kB over the wire), most of it `extra_metadata` and the long source fields no list renders; the named list is 9 kB. `fetchMapRow` still takes the whole row, because the admin editor writes back columns no list carries.

**The fonts are self-hosted** (`src/styles/fonts.css` + `static/fonts/`, latin · latin-ext · vietnamese only, Inter variable). Do not reintroduce the Google Fonts link or the Translate widget — `docs/conventions.md` §Fonts.

**One place, not one spelling.** The gazetteer (`place_names`) groups by `core_key`, and the rule exists twice — `place_core_key()` in Postgres and `placeCoreKey` in `$lib/core/utils/placeKey.ts`. The two must agree or a place page 404s. `docs/conventions.md` §The gazetteer key.

**Supabase types:**

- Insert/Update types: use `?:` optional fields — **not** `Partial<{...}>` (resolves as `never`).
- `src/lib/data/supabase/types.ts` is generated and current against migration head **086**. Nothing regenerates it automatically — do it after every push. Prefer real types over `as any`. Drift history and the `--local` trap: `docs/conventions.md` §Supabase types.
- The generic belongs on the client: `createClient<Database>(...)`. A bare `createClient(...)` is what forces most `as any` casts downstream.
- **Realtime is stubbed out of the browser bundle** (`vite.config.ts` aliases `@supabase/realtime-js`). The day a real `.channel()` appears, the alias and the stub both come out.

**The component vocabulary is one of each**: `.btn` is an action and `.chip` a choice; `.section-card` is the one card; `$lib/ui/Tabs.svelte` the one tab strip; `.sb-search` the one search field; `$lib/ui/DataTable.svelte` + `SortHeader` + `core/utils/tableSort.ts` the one table and one sort. All CSS in `src/styles/` via `$styles`; colours are `var(--token)`, canvas ink is `INK`/`inkAlpha` in `core/ink.ts`. Two themes, one value each — `light-dark()` in `tokens.css`, and four things deliberately do not flip. **Before adding any of these, read `docs/conventions.md` §Component vocabulary** — it lists the twenty-seven selectors these eleven replaced, so a second one is a regression, not a new component. `tests/screens.spec.ts` fails if a retired name reappears.

**The top bar is two tiers**: `Catalog · About · Blog` in the bar, every tool behind one `Tools ▾` menu with the staff rows and `All pages → /directory`. Nav and footer come once from `(editorial)/+layout.svelte`; a new page needs a row in `NavBar.svelte`, `EditorialFooter.svelte` and `paletteDestinations.ts`.

## Architecture

**Full reference: `docs/architecture.md`.** Read it before touching any of this — it is this
section's old text, unabridged, including every trap. What follows is only the shape.

- **One OpenLayers map per page.** `src/lib/map/shell/MapShell.svelte` owns it; children call
  `getShellContext()`, never `new Map()`. `LayerRenderer.svelte` is the single component that
  renders **all** layers off `layersStore`, and every new subscription that changes what is on the
  map goes through its `queueSync`, not straight to `syncBase`/`syncOverlays`.
- **Exception: `ImageShell.svelte`** — the IIIF-canvas counterpart for pixel work (`/scan`,
  `NeatlineEditor`). Own map, own context (`getImageShellStore()`), no global stores. OL uses
  `ol_y = -image_y`; the flip helpers are `src/lib/core/geo/rectUtils.ts`.
- **Map stores** (`src/lib/map/stores/`): `layersStore` (what is rendered — base + overlays, max 10,
  persisted `vma-layers-v1`), `mapStore` (camera + active map), `layerStore` (per-shell view
  settings), `urlStore` (hash carries camera + basemap; the selected map is `?map=<id>`).
- **Route groups**: `(editorial)` public pages with nav/footer, `(app)` full-screen tools with
  `ssr = false`. Modes are query params, not routes — `/explore` is the MapShell surface, `/scan`
  the ImageShell one, each a ~10-line `{#if}` dispatcher. `/vi/<path>` is the Vietnamese address of
  `<path>` (`src/hooks.ts` reroute). Retired paths 301 from `src/hooks.server.ts`.
- **Command palette** is mounted once by the root layout: `features/shared/CommandPalette.svelte`,
  ⌘K, searching pages · maps · places · labels through `/api/search`.
- **Canonical types** live in `src/lib/data/maps/` (`types.ts`, `footprintTypes.ts`,
  `triageTypes.ts`, `service.ts`, `iiifManifest.ts`, `georef.ts`). `src/lib/map/types.ts` is UI-only.
- **Basemap and overlays are self-hosted PMTiles** on `tiles.maparchive.vn` — see
  `docs/architecture.md` §Map libraries before changing a URL, a zoom range or a build key.
- **`@allmaps/openlayers` is loaded on demand** — one runtime importer, `createWarpedLayer` in
  `map/shell/warpedOverlay.ts`, which is why it is `async`. Keep any new importer type-only or
  151 kB goes back in front of /explore's first paint.

### Modes

| Route | Purpose | Source |
|-------|---------|--------|
| `/explore` | MapShell dispatcher | `src/routes/(app)/explore/` |
| `/explore?mode=browse` | Browse maps, play stories | `src/lib/features/explore/ExplorePage.svelte` |
| `/explore?mode=annotate` | Free-form annotation + timeline animation | `src/lib/features/annotate/` |
| `/explore?mode=story` | Author stories | `src/lib/features/stories/editor/` |
| `/scan` | ImageShell dispatcher | `src/routes/(app)/scan/` |
| `/scan?mode=inspect` | IIIF inspector, public read-only | `src/lib/features/contribute/inspect/` |
| `/scan?mode=prepare` | Layout · neatline · tile grid · save · queue OCR | `src/lib/features/contribute/digitalize/` |
| `/scan?mode=text` | Check what came back: Names · Index · Numbers · Other | `src/lib/features/contribute/ocr/` |
| `/scan?mode=shapes` | Draw · Segment · Validate, `?tab=` | `src/lib/features/contribute/{trace,review}/` |
| `/trip/[id]` | Story playback | `src/lib/features/stories/play/` |
| `/catalog` | Faceted catalog + inline admin | `src/lib/features/catalog/`, `src/routes/(editorial)/catalog/` |
| `/contribute/georef` | Georeference via Allmaps Editor | `src/routes/(editorial)/contribute/georef/` |
| `/admin?tab=` | Bulk upload · Scout · Status | `src/lib/features/admin/` |

Code shared across the story lifecycle (markers, playback state, point ops) lives in `src/lib/features/stories/shared/`. All app modes except the IIIF-canvas contribute tools share MapShell + the map stores.


## API routes (`src/routes/api/`)

Per-route reference: **`docs/api.md`**. The rules:

- Every handler is `requireRole → adminClient → query → json`, using the `$lib/server` helpers `requireRole`/`getRole` (`auth.ts`), `adminClient` (`supabaseAdmin.ts`) and `assertUuid`/`dbError` (`http.ts` — 400 on a malformed id, and no raw Postgres message ever reaches the client).
- Three auth classes: **admin/mod session** (`/api/admin/*`), **any signed-in user** (`/api/contribute/*`, `user_id` from the session, rate-limited by `assertUnderRateLimit`), and **worker token** (`/api/pipeline/*`, `Authorization: Bearer <worker_keys token>` via `$lib/server/workerAuth.ts`; mint with `scripts/mint-worker-key.mjs`). `/api/search`, `/api/context`, `/api/press`, `/api/maps/[id]/legend-points` are public and enforce `status IN ('public','featured')` server-side. `/api/search` takes `include=maps,scout,labels,places`; `places` searches the mig 067 gazetteer and is what the command palette turns into `/place/<slug>` rows.
- Enqueue, never execute: routes that start pipeline work insert a `pipeline_jobs` row and return 202 (409 if one is in flight). Nothing runs until a worker claims it. `/api/pipeline/execute` is the one exception, for kinds that need the service key.
- Human pipeline stages (`reviewed`, `seg_reviewed`, `exported`, `idle`) are the only ones PATCHable; machine stages derive from jobs and are rejected with 400.

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce references.

## Database

Schema: `supabase/migrations/` (head **086**, pushed 2026-09-13). Table-by-table reference and the rules behind each constraint: **`docs/db-guidelines.md`** §11. The rules in one breath:

- `maps.status` is `draft | public | featured` and is the **only** visibility model (mig 060). Draft maps are readable by any signed-in user, never anonymously (mig 063). A published map must carry `annotation_url` **or** `allmaps_id` (mig 062), and publishing enqueues `mirror_annotation` + `tile_to_r2` (mig 058).
- **Status transitions live in Postgres**, not the API: `set_extraction_status`, `revert_recent_validations`, `set_footprint_status`, `set_review_mark`, `claim_job`, `finish_job`. All `security definer`, `service_role` only. New write paths reuse them.
- `pipeline_jobs` is the queue (one live job per kind × map); `map_pipeline_status` is a **view**; `map_review_marks` holds the three human stages.
- Full-text search uses the `simple` tsvector config on purpose — the corpus is French/Vietnamese/English.

## Admin tooling

Map CRUD is inline in `/catalog`, gated by `role === 'admin' | 'mod'`: `CatalogUnifiedSearch.svelte` dispatches `edit`, and the **route page** `src/routes/(editorial)/catalog/+page.svelte` renders `MapEditModal`. Plus the dedicated pages `/admin?tab=bulk` and `/admin?tab=scout`. There is no general `/admin` route. Full reference in `docs/admin-tooling.md`.

## Pipelines

Full command reference and design rationale in `docs/pipelines.md`:

- **The worker** (`work/worker/vma_worker.py`) — claims `pipeline_jobs` via the `claim_job` RPC (`FOR UPDATE SKIP LOCKED`) and shells out to the pipeline scripts. Run it wherever the venv lives:

  ```bash
  source work/ocr/.venv/bin/activate
  python work/worker/vma_worker.py --worker $(hostname)   # poll forever (ocr + join)
  python work/worker/vma_worker.py --once                 # drain one job
  ```

  `--kinds` decides what it takes, and the default is **everything this machine can run**: `ocr`/`join`/`layout` locally, `mirror_annotation`/`sync_allmaps`/`warp` claimed and handed to `/api/pipeline/execute`, and `tile_to_r2` (via `scripts/tile_map.sh`) only when vips + rclone are on PATH. `seg` is opt-in — it runs where a GPU is, which means a Colab notebook running this same worker with `--kinds seg`. A worker left running therefore finishes what publishing enqueues. It needs `VMA_API_URL` + `VMA_WORKER_KEY` and **no database credentials** — claim and results both go through `/api/pipeline/*`. The worker exports both into the job's subprocess, so `ocr.py --db` writes the same way (`supabase_client.py` switches transport on those two variables; the analysis-only subcommands still use the service key when run by hand). The `seg` runner's flags mirror `segCommand.ts`, and `MAPSAM2_DIR` / `MAPSAM2_CHECKPOINT` come from the machine's environment rather than the job.
- **OCR** (`work/ocr/`) — Gemini Flash → `ocr_extractions`; `join_labels.py` writes the `footprint_id` join (mig 050). Venv: `work/ocr/.venv`.
- **MapSAM2 inference** (`work/MapSAM2/`) — IIIF tiles → polygons → `footprint_submissions`. `--mode prompted --ocr-run-id <run>` seeds SAM2 from OCR boxes via `to_sam2_seeds.py` (area categories only, one owner per seed by centroid, clipped to the tile); those polygons are written with the label already attached. Runs on Colab against an upstream clone; there is no local venv for it. Its polygons and `ocr_extractions.global_*` share **one full-image pixel grid** (both scale tile-render → source px and offset by the tile origin, off the same `info.json`), which is what makes the C1 join possible; tile sizes differ and do not matter.

(The legacy `scripts/vectorize.py` colour-profile pipeline was removed — MapSAM2 supersedes it, and `work/vectorize/` is gone from the tree.)

## Deployment

Cloudflare Pages adapter, output `.svelte-kit/cloudflare`, deployed by `npm run deploy` (`wrangler pages deploy .svelte-kit/cloudflare --project-name vmabeta`). The full story, including the ten dead builds: **`docs/deploy.md`**. The rules:

- **No root `wrangler.toml`.** One that carries `pages_build_output_dir` replaces the dashboard's whole environment, secrets included. The R2 worker's `worker/wrangler.toml` is separate and fine.
- **Environment lives in the Cloudflare dashboard**, per environment (Production and Preview each hold their own copy; nothing inherits). `PUBLIC_*` are Text variables; `SUPABASE_SERVICE_KEY`, `IA_S3_*` are Secrets. Build command, output dir and `nodejs_compat` are dashboard settings too.
- **Secrets resolve at build time** via `$env/static/private`. `$env/dynamic/private` returns undefined in Pages Functions. So every environment that builds needs all three present, or the build fails on the first import. CI copies `.env.test` to `.env` before `check` and `build`.
- Never import a Node builtin bare; use the `node:` prefix or the Functions bundle publishes nothing.
- A blank page right after a deploy is edge propagation, not a bug. Wait, hard-reload, then debug.
- **The repo is `lqtue/vietnam-map-archive`** (renamed from `svelte-beta`, Sept 2026; GitHub redirects the old URL and the local directory is still called `svelte-beta`). The Pages project is still `vmabeta`, because renaming it would change the deploy target and the `.pages.dev` host for nothing.
- **`vmabeta.pages.dev` 301s to `maparchive.vn`** — `hooks.server.ts`, exact host match, so preview deploys at `<hash>.vmabeta.pages.dev` stay reachable. Two indexable addresses for one site, one of them saying `beta`, was the reason.
