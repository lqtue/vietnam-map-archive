# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

Vietnam Map Archive (VMA) — a SvelteKit 5 app for exploring georeferenced historical maps of Saigon/Ho Chi Minh City. Integrates Allmaps with OpenLayers.

## Where to look first

- `docs/db-guidelines.md` — schema conventions; all migrations must follow these
- `docs/system-guidelines.md` — layering rule, page structure, component patterns, route map, known debt
- `docs/design-system.md` — tokens, the CSS file map, page template
- `docs/ROADMAP.md` — **the one tracker**: ship/harden · architecture steps · OCR↔SAM2 product · burn-down
- `docs/time-machine-plan.md` — label search · temporal fabric · period sources (Track E detail)
- `docs/platform-design.md` — one workspace for VMA + HACW: what is shared (contracts, basemap, deploy, docs) and what stays per-app, with sequencing
- `docs/digitalize-guide.md` — **operator guide** for `/scan?mode=triage`: the five triage steps, what each layout category means, the ground-per-call target, and the failure modes that return plausible output while dropping data
- `docs/api.md` — every server route, its auth class and its contract
- `docs/deploy.md` — Cloudflare Pages: env in the dashboard, no root `wrangler.toml`, the blank-page-after-deploy effect
- `docs/pipelines.md` — OCR + MapSAM2 command reference and design rationale. `scripts/` holds the living operator scripts; `scripts/oneoff/` the backfills that have already run and stay only as a record.
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
npm run lint         # prettier --check . && eslint . && check-tokens
npm run lint:tokens  # no hex literals in any <style> block
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

`npm run test` starts a dev server on 5173, or reuses one already running. It runs **87** tests: the smokes in `tests/smoke.spec.ts`, which are **read-only** (they hit the real Supabase project but never write), plus 78 browser-less pure checks that ride the same runner — `tests/press.spec.ts` (the Gallica CQL builder and the NLV year window), `tests/explore-keys.spec.ts` (the /explore time scrubber), `tests/tween.spec.ts` (the studio easing that replaced animejs), `tests/search-fold.spec.ts` (diacritic folding in the map picker), `tests/triage-suggest.spec.ts` (level0 tile addressing and the triage proposal), `tests/map-grid.spec.ts` (the printed reference grid, cell to point), `tests/layout-regions.spec.ts` (the layout vocabulary and which rectangle steers the tile grid), `tests/georef-editor-url.spec.ts` (which IIIF source Allmaps Editor is handed when reopening a map's control points) `tests/bounds-probe.spec.ts` (which maps /explore asks Allmaps about — only georeferenced ones without a bbox) and `tests/palette.spec.ts` (which pages the command palette offers each role, and the gazetteer key a label resolves to — that key is computed twice, once in Postgres and once in the client, and a mismatch is a 404). Pure checks live here rather than in a second framework because Playwright is already installed.

**Write paths** are covered separately by `npm run test:write` (`tests/write.spec.ts`, 23 tests) against a **local** stack, never production: `npm run db:test` runs `supabase start -x vector -x logflare` and seeds one staff user + one map via `scripts/seed-test-db.mjs`. The suite throws unless `PUBLIC_SUPABASE_URL` is a loopback address, and deletes every row it writes. Credentials come from `.env.test` (the CLI's published demo keys, committed on purpose) which Vite loads for the `--mode test` dev server on port 5199. Server-route auth is done by letting `@supabase/ssr` mint the session cookies, so chunking and encoding match the app exactly.

Local ports are **54421** for the API and **54420** for the shadow DB, not the CLI defaults — 54321/54320 collide with another local project. `-x vector -x logflare` is needed under colima: those containers bind-mount `/var/run/docker.sock`, which colima cannot provide.

Supabase project ref `trioykjhhwrruwjsklfo` (Sydney) is already linked. `supabase db push` works directly; `supabase db pull` and `migration list` require a direct DB password — use the Dashboard SQL Editor or `db push` instead. Repair migrations with `supabase migration repair --status applied|reverted <id>`.

**Adding a migration** — drop a new `supabase/migrations/NNN_*.sql` (incrementing from the current head, **070**), `supabase db push`, then regenerate types: `supabase gen types typescript --linked 2>/dev/null > src/lib/data/supabase/types.ts`. Run `npm run check` to catch fallout.

## Conventions

**Svelte syntax — legacy, NOT runes.** Use `$:`, `export let`, `createEventDispatcher`, `$store`. Do not use `$state`, `$derived`, `$effect`.

**Svelte MCP server** (plugin `svelte`, from `sveltejs/ai-tools` — see https://svelte.dev/docs/ai/skills). Available tools:

- `list-sections` — call first to discover documentation sections; pick by the `use_cases` field.
- `get-documentation` — fetch the full text of every section relevant to the task.
- `svelte-autofixer` — run on any Svelte code before showing it; re-run until it reports no issues.
- `playground-link` — offer a playground link after a standalone component (not for project-file edits).

Delegate `.svelte` / `.svelte.ts` work to the `svelte-file-editor` agent when it is more than a small edit; it iterates with the autofixer in its own context.

**Caveat for this repo:** the autofixer and the Svelte skills assume runes, and their "avoid legacy features" list is exactly this repo's house style (line above) — `$:`, `export let`, `on:click`, `<slot>`/`<svelte:fragment>`, `<svelte:component>`, `<svelte:self>`, `createEventDispatcher`, stores, `use:action`, `class:`. Ignore every suggestion to modernise those; act only on the rest (missing `{#each}` keys, effect cleanup, scoped-CSS and a11y findings, real bugs).

**Layering rule (enforced by `@typescript-eslint/no-restricted-imports` in `eslint.config.js`; type-only imports are exempt):**

> `core → data → map → features → routes`; `ui` is leaf primitives with zero domain imports; `server` is `$lib/server` only.

A directory may import only from directories to its **left**. Routes stay thin: load + wire, no business logic.

**Feature isolation (also lint-enforced):** a feature may import another feature only through a declared seam — `src/lib/features/shared/` (cross-cutting UI: the layer panels, `SidebarCard`, `MapViewerSidebar`, `LabelHits`, the `catalogSearch` client and the `search/` widgets) or `src/lib/features/<x>/shared/` (that feature's public API — `stories/shared`, `contribute/shared`, `catalog/shared`). Everything else under another feature is private. Routes may import anything under `features/`.

```
src/lib/
├─ core/      pure — no OL, no Supabase        geo/ iiif/ utils/ (+ utils/persistence/)
├─ data/      DB/HTTP access + canonical types  supabase/ maps/ admin/
├─ server/    $lib/server — SvelteKit blocks client import
│             auth.ts supabaseAdmin.ts http.ts storage.ts ia.ts mapFields.ts
│             facets.ts transformer.ts allmaps.ts ocrReview.ts
├─ map/       the OpenLayers runtime, one home  shell/ stores/ annotations/ types.ts constants.ts
├─ features/  one dir per product surface       explore/ catalog/ stories/ studio/ contribute/ admin/
└─ ui/        generic primitives only           NavBar EditorialFooter PageHero MapCard LocationSearch …
```

`$lib/server/*` is import-guarded by SvelteKit — a client-side import of the service key is a build error, not a code-review catch.

**Environment variables:**

```
PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY   # anon key = the sb_publishable_… key
SUPABASE_SERVICE_KEY            # admin API routes only; the sb_secret_… key
IA_S3_ACCESS_KEY, IA_S3_SECRET_KEY   # Internet Archive upload
VMA_API_URL, VMA_WORKER_KEY     # worker machines only — never the web app
```

**Supabase types:**

- Insert/Update types: use `?:` optional fields — **not** `Partial<{...}>` (resolves as `never`).
- `src/lib/data/supabase/types.ts` is current against migration head 070, verified identical to the linked project. Prefer the real types over `as any`; ~25 casts remain, mostly in Svelte components.
- The generic belongs on the client: `createClient<Database>(...)`. A bare `createClient(...)` is what forces most `as any` casts downstream.

**Styling — the Sheet system.** All CSS in `src/styles/`, via the `$styles` alias. Root entry is `global.css`, which imports five files in order: `fonts.css` · `tokens.css` · `base.css` · `sheet.css` · `primitives.css` (~1,100 lines total, replacing the 7,751 across 28 files that preceded it). Page sheets under `components/`, `layouts/` and `pages/` are imported by the component that needs them.

**Two surfaces, not two themes.** `tokens.css` defines **six role tokens** — `--ground` `--ground-raised` `--ink` `--ink-soft` `--rule` `--accent` (plus `--on-accent`, `--status-ok|warn|bad`, `--scrim`) — redefined once under `.surface-paper` (editorial) and once under `.surface-darkroom` (tools). **The route layout picks the surface; the visitor never does.** Tools are dark because historical scans are light and a light UI around a light scan gives the eye nothing to separate them by. Paper roles are also on bare `:root`, so a page that forgets its surface class is still legible.

A component reads roles and **never names a colour**. `npm run lint` runs `scripts/check-tokens.mjs`, which fails on a hex literal inside any `<style>` block. Two things stay literal and are marked `/* token-exempt: why */`: colours handed to OpenLayers (OL cannot read a custom property) and categorical data colours (footprint types, layout regions, tile priorities) whose value encodes *which thing*, not *what role*.

**Faces are self-hosted** from `static/fonts` (`fonts.css`): **Spectral** display, **Be Vietnam Pro** body, **IBM Plex Mono** data. Latin, latin-ext and vietnamese subsets only — 191 KB total, ~54 KB on the usual path. No Google Fonts request anywhere; adding one is a regression.

**Breakpoints are 600 / 900 / 1280.** Three. `ToolLayout`'s mobile split at 900 is the one other components pair with.

**Layout is one primitive.** `src/lib/ui/Sheet.svelte` + `sheet.css`: a printed map sheet puts content inside a **neatline** and its title, scale and legend in the **margin** around it. Chrome goes in the margin, content in the field — an article is a field, a map is a field. Both `+layout.svelte` files own the Sheet, so a page contributes content only: no header scaffold, no max-width, no footer. A block that must break the measure marks itself `.is-wide`.

**Primitives** (`primitives.css`): `.label` · `.btn` · `.field` · `.panel` · `.chip` · `.data-table`. There were four parallel button vocabularies; one survives, and `.sb-btn` / `.tool-btn` / `.pill-btn` / `.sb-card` / `.tool-section` / `.sb-input` are aliased onto the primitives with `:is()` rather than renamed across sixty files. Write the new names in new markup.

New pages use the template in `docs/design-system.md`. Nav and footer come once from the layouts, so a new editorial page only needs its link added in `src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`.

## Architecture

### MapShell — central map pattern

`src/lib/map/shell/MapShell.svelte` owns the single OpenLayers Map and is the entry point for all geo-map pages. It mounts basemap tile layers (`basemapLayers.ts`) and exposes everything via Svelte context (`src/lib/map/shell/context.ts`). Children call `getShellContext()` — never create a second OL map. Basemap *visibility* is owned by `LayerRenderer`, not MapShell.

`src/lib/map/shell/LayerRenderer.svelte` is the single component that renders **all** map layers — base (modern tile OR historical warped) and overlays — by subscribing to `layersStore`. In side-by-side mode it hides overlays past index 0 so the left pane shows only the topmost; `DualMapPane.svelte` independently renders overlays[1] in the right pane.

**Exception — `ImageShell.svelte`** (same dir): IIIF-canvas counterpart to MapShell for pixel-coordinate work. Creates an OL map with a static image extent, exposes via `getImageShellStore()` (`imageContext.ts`), binds `imgWidth`/`imgHeight`. Used by `/scan?mode=triage`, `/scan?mode=trace`, `/scan?mode=review` and by `NeatlineEditor` — none of them use MapShell or the global stores.

**IIIF canvas coords:** OL uses `ol_y = -image_y` (y-flip). Tool components store bboxes image-space (y-down) and flip when creating OL geometries. `src/lib/core/geo/rectUtils.ts` owns the flip helpers (in `core` because `ImageShell` needs them too); `bboxHandles.ts` builds the shared handle features and `createRectEditor` used by both `OcrBboxTool` and `TriageTool`. Polygon/line tools (`TraceTool`, `ReviewTool`) flip inline.

### Map stores (`src/lib/map/stores/`)

- **layersStore** — single source of truth for what the map renders. `{ base: LayerRef, overlays: OverlayLayer[] }` where `base` is either `{ kind: 'basemap', key }` (`'g-streets' | 'g-satellite' | 'none'`) or `{ kind: 'historical', mapId, allmapsId, name?, thumbnail? }`. `overlays` is top-of-stack-first; each item has its own `opacity`, `visible`, and stable local `id`. Max 10 (`MAX_OVERLAY_LAYERS`). Persists to `localStorage` as `vma-layers-v1`. API: `setBase`, `addOverlay`, `removeOverlay`, `removeOverlayByMapId`, `setOpacity`, `setVisible`, `reorderOverlay`, `clearOverlays`, `isOverlay`; plus the free functions `toHistoricalRef(map)`, `toggleOverlayFor(map)`, `clamp01(n)` and the derived `topOverlay`.
- **mapStore** — `{ lng, lat, zoom, rotation, activeMapId, activeAllmapsId }`. Default: Saigon (106.70098, 10.77653) zoom 14. `activeMapId` is `maps.id` UUID and **is** mirrored from `layersStore.topOverlay` — the bridge is wired in `src/lib/map/shell/geoMapSetup.ts` (`topOverlay.subscribe → setActiveMap`). Kept for legacy callers: story playback, share links. `activeAllmapsId` holds the annotation source string — either a bare Allmaps image ID or a full annotation URL; `annotationUrlForSource()` (`src/lib/core/iiif/annotationUrl.ts`) accepts both.
- **layerStore** — per-shell view settings: `{ basemap, viewMode, lensRadius, customBaseUrl }`. View modes: `'overlay' | 'spy' | 'dual'` (UI labels: Stacked / Lens / Side-by-side). The side-by-side split is fixed at 50/50; `sideRatio` was removed.
- **urlStore** — bidirectional URL ↔ store sync. The hash carries **camera + basemap only**: `#@lat,lng,zoomz,rotationr&base=key`. The selected map lives in the **`?map=<id>` query param** — that is what /archive, /scan?mode=triage and every share link point at (`src/lib/features/explore/exploreUrl.ts`). A `map=` found in the hash is a legacy link and is migrated into `?map=` on init.

Other persisted keys (there is no `vma-viewer-state-v1`): `vma-layers-v1`, `vma-story-player-v1`, `vma-story-library-v1`, `vma-annotation-projects-v1`, `vma-bounds-cache-v2`, `vma-explore-sidebar-ratios-v1`, `vma-custom-base-url`, `vma-thumb-cache-v1`, `vma-explore-{tour,welcome}-ack-v1`, `vma-create-saigon-seeded-v2`. Debounced persistence lives in `src/lib/core/utils/persistence/createPersistedStore.ts`; raw read/write in the sibling `storage.ts`.

### Command palette — the one search

`src/lib/features/shared/CommandPalette.svelte` is mounted once by the **root** layout, so it is on every page in both route groups. ⌘K / Ctrl+K anywhere, `/` outside a form field, or the Search button in `NavBar`. It searches four things through `/api/search`: **pages** (`paletteDestinations.ts`, role-gated), **maps**, **places** (the gazetteer) and **labels** (which open `/explore` at the spot).

Open state is `src/lib/core/utils/commandPalette.ts` — a bare boolean store in `core` rather than beside the component, because `NavBar` is in `ui` and the layering rule bars `ui` from importing `features`. `src/lib/core/utils/placeKey.ts` is the client-side twin of Postgres's `place_key()` (mig 067), so a label on screen links straight to `/archive/place/<slug>`; `tests/palette.spec.ts` guards that the two agree.

### Route groups

**Sept 2026 route merge: fifteen surfaces became six.** Modes are query params, not routes. The grouping is **by shell**, not by verb — `/explore` is the MapShell surface and `/scan` the ImageShell one — which is what lets the OL map, the PMTiles source and the warped tiles stay warm across a mode change instead of being torn down and rebuilt. `src/hooks.server.ts` 301s every retired path (`LEGACY_REDIRECTS` for the fixed ones, `LEGACY_PREFIXES` for `/archive/<id>` and `/archive/place/<name>`); `withSearch()` joins with `&` because half the targets already carry a `?mode=`.

- `(editorial)` — public pages with nav/footer: `/`, `/archive`, `/archive/[id]`, `/archive/place/[name]`, `/about`, `/blog`, `/blog/[slug]`, `/screens`, `/profile`, `/login`, `/contribute`, `/admin`. There is no `/signup`.

`/admin` is one console, tab chosen by `?tab=bulk|scout|status` (bulk is the default); the pages live in `src/lib/features/admin/{BulkUploadPage,ScoutPage,StatusPage}.svelte` and each keeps its own role gate. `/contribute` is the on-ramp **and** the georeference worklist — georeferencing is the one contribution task with no canvas of its own, since it hands off to the Allmaps Editor, so `GeorefQueue.svelte` sits in a `#georef` section on that page rather than in `/scan`.

`/archive/place/[name]` is the **gazetteer page**: one server-rendered URL per attested place name (the mig 067 view groups spellings), published maps only. `/screens` renders every design-system component from fixtures — no database, use it to see what already exists before building a second one. `/admin?tab=status` is the archive's own review queue: counts of maps, jobs and failures that used to need hand-run SQL, fed by `GET /api/admin/status` (admin or mod).

`/archive/[id]` is the **share page**: server-rendered from `+page.server.ts` so a crawler sees the title, description and OG image without running JavaScript. Only `public`/`featured` maps resolve — a draft id is a 404. Everything interactive is one click away at `/explore?map=<id>`. The OG image is the map's `thumbnail` column, falling back to a derived `…/full/800,/0/default.jpg`; there is no rendered preview, because the R2 worker is level0 behind a proxy and a IIIF size we know exists beats one we hope for.
- `(app)` — full-screen tools on the darkroom surface: `/explore`, `/scan`, `/trip/[id]`.

`/explore?mode=browse|annotate|story` and `/scan?mode=inspect|triage|trace|review` are **dispatchers**: a title and an `{#if}` chain, ~60 lines each, mounting one feature component. The **mode strip is rendered by `(app)/+layout.svelte`, in the sheet's margin** — the first version floated it over the map at top-centre and it swallowed clicks meant for the panels underneath, which is the failure the margin exists to prevent. `?map=` is carried across a mode switch.

`/trip/[id]` keeps its own URL on purpose: printed QR codes point at it.

Only the home page and the `(app)` tools set `ssr = false`; the rest of `(editorial)` server-renders already.

The home page's hero is `HeroRegistration.svelte`: one georeferenced sheet warped live over the modern city, breathing between 0.12 and 0.88 opacity on a 14s cosine, held at 0.6 under `prefers-reduced-motion`. It bypasses `layersStore` on purpose — that store is the visitor's saved layer stack and a hero has no business writing to it — and attaches its `WarpedMapLayer` straight to the OL map.

Every route lives in one of those two groups. There are **no redirect stub pages**. There is no `/hunt` or `/georef` route.

### Modes

| Route | Purpose | Source |
|-------|---------|--------|
| `/explore` | MapShell dispatcher | `src/routes/(app)/explore/` |
| `/explore?mode=browse` | Browse maps, play stories | `src/lib/features/explore/ExplorePage.svelte` |
| `/explore?mode=annotate` | Free-form annotation + timeline animation | `src/lib/features/studio/` |
| `/explore?mode=story` | Author stories | `src/lib/features/stories/editor/` |
| `/scan` | ImageShell dispatcher | `src/routes/(app)/scan/` |
| `/scan?mode=inspect` | IIIF inspector, public read-only | `src/lib/features/contribute/inspect/` |
| `/scan?mode=triage` | Triage (neatline + tile grid) + OCR review | `src/lib/features/contribute/{digitalize,ocr}/` |
| `/scan?mode=trace` | Polygon/line tracing of footprints | `src/lib/features/contribute/trace/` |
| `/scan?mode=review` | HITL review of SAM2 footprints | `src/lib/features/contribute/review/` |
| `/trip/[id]` | Story playback | `src/lib/features/stories/play/` |
| `/archive` | Faceted catalog + inline admin | `src/lib/features/catalog/`, `src/routes/(editorial)/archive/` |
| `/contribute` | On-ramp + the georeference worklist | `src/lib/features/contribute/georef/GeorefQueue.svelte` |
| `/admin?tab=` | Bulk upload · Scout · Status | `src/lib/features/admin/` |

Code shared across the story lifecycle (markers, playback state, point ops) lives in `src/lib/features/stories/shared/`. All app modes except the IIIF-canvas contribute tools share MapShell + the map stores.

### /explore sidebar + mobile pattern

Same components drive both viewports. The reusable panels are in `src/lib/features/shared/` (moved out of `catalog/` in Sept 2026, when four features turned out to import them):

- **`LayerStackPanel.svelte`** — the layer stack. Whole row is the opacity slider (pointer drag, 6px threshold so clean taps still register as zoom-to-overlay). Reorder via ▲/▼. **Remove (×) only** — no hide/show toggle. Shows year + name; in side-by-side the top 2 get **Top** / **Bottom** badges (mobile dual splits vertically).
- **`LayerControlsPanel.svelte`** — Display mode (Stacked / Lens / Side-by-side) · Base map (Maps / Satellite / None) · Location search (Nominatim, via `src/lib/ui/LocationSearch.svelte`) · "My location" GPS toggle. Single source of GPS on both viewports.
- **`CatalogSidebarPanel.svelte`** (`features/catalog/shared/`) — compact catalog browser used by tool pages other than /explore. It composes the whole catalog feature, so it is catalog's public entry point, not a shared primitive.
- **`CatalogTable.svelte`** / **`CatalogTableCompact.svelte`** (`features/catalog/`) — full and sidebar variants. Compact shows **Year + Name only**. Above the full table, **Show maps of** and **Type** render as two native `<select>` dropdowns (respecting `requireGeoref`). Year and Area row chips are **not** clickable filters.

`/explore`'s own desktop sidebar is `src/lib/features/explore/ExploreSidebar.svelte`, which stacks **Browse → Layers → Controls** (default 40/40/20, draggable splitters, ratios persisted). Its Browse pane is `ExploreBrowsePanel.svelte` + `ExploreArchiveBrowser.svelte`, not `CatalogSidebarPanel`.

Mobile (`< 900px`): `ToolLayout.svelte` shows a full-bleed map with a horizontal 3-tab bottom bar — Layers · Controls · Browse — backed by `MobileDrawerStack.svelte`, one shared drawer body sliding up. Slots: `mobile-layers`, `mobile-controls`, `mobile-browse`; `mobile-sidebar` is the legacy single-drawer fallback other tool pages still use. A tool that fills only `sidebar` gets **that same slot** in the mobile drawer, with `let:compact` true — one component instance, since the desktop rail and the drawer are never mounted together. `/scan?mode=triage` and `/scan?mode=trace` did carry two copies of their sidebar (39 and 20 lines of duplicated wiring) until Sept 2026. Desktop slots: `sidebar`, `right-sidebar`, `floating`, default.

In dual mode, OL attribution + scale live on the **secondary** pane (right on desktop, bottom on mobile) — hidden on the primary via CSS. Map-bounds resolution goes through `resolveBounds()` in `src/lib/core/geo/mapBounds.ts` (`bounds → bbox → annotation_url → allmaps_id`) so R2-mirrored maps and `?map=<id>` deep-links both zoom correctly.

### Contribute tools

**Shared (`src/lib/features/contribute/shared/`):** `ToolSidebarShell.svelte` + `ToolMapPicker.svelte` (the sidebar frame and map selector all three tools use), `ToolPanelHeader.svelte`, `EmptyPanel.svelte`, `SidebarToggleButton.svelte`, `CliCommandBlock.svelte` (copy-paste CLI block), `bboxHandles.ts` (flip helpers live in `$lib/core/geo/rectUtils.ts`), `tableSort.ts` (`createTableSort<T>`), `iiifSource.ts` (`resolveMapIiifInfoUrl`). Data clients: `src/lib/features/contribute/shared/ocrApi.ts` and `src/lib/features/contribute/pipelineApi.ts`. Category/colour/status constants have one home: `src/lib/features/contribute/shared/constants.ts` (with `types.ts` beside it — all three moved from `ocr/` because `MapEditPipelineTab` and `LabelHits` import them). Footprint geometry types live in `src/lib/data/maps/footprintTypes.ts`.

**Digitalize (`/scan?mode=triage`)** — two-phase HITL on a single `ImageShell`, tabs via `PhaseTabs.svelte`:

- **Triage**: `TriageTool.svelte` (neatline rect + tile priority grid; click cycles normal → low-res amber → skip gray), `RegionsTool.svelte` (the layout regions — one labelled rect per part of the sheet, click to select, drag to correct; a dashed edge is the model's proposal and a solid one a person's) and `TriageSidebar.svelte`, whose five steps are **Layout · Neatline · Tiles · Save triage · Run OCR**. **Detect** on step 1 enqueues a `layout` job: one low-resolution look at the whole sheet asking the model where the main map, title block, legend, name list, inset and furniture are. It is a job and not a route because the Gemini key lives on the worker and deliberately not in the web app. The answer lands in `maps.triage.regions` and the page polls for it. **Save triage** writes the neatline, tile grid and per-tile priorities to `maps.triage` (mig 069) — localStorage stays the working draft, but only a saved triage is visible to `scripts/enqueue_ocr_all.mjs`, which by default queues **only** triaged sheets (`--untriaged` includes the rest in auto mode) and crops to the `main_map` region when the layout pass found one, falling back to the neatline. "Run OCR" **enqueues a `pipeline_jobs` row** and returns 202; nothing runs until a worker claims it. Same behaviour in dev and on Cloudflare — the old `child_process` spawn and its `{ cli_only, cli_command }` fallback are gone. `CliCommandBlock` now only serves the segmentation panel.
- **OCR Review**: `OcrBboxTool.svelte` renders + edits `ocr_extractions` bboxes and supports `drawMode` for manual bboxes (POSTs with `model: 'manual'`). `OcrSidebar.svelte` is a filterable table with inline text/category edit and auto-save on blur, split into `OcrFilterBar.svelte` + `OcrRunBar.svelte`, with state in `ocrReviewController.ts`. `BboxPanel.svelte` is the floating selected-bbox editor.
- **Segmentation**: `SegSidebar.svelte` + `segCommand.ts` emit the MapSAM2 CLI command.

The layout job — enqueue, poll, adopt the regions once it closes — lives in `digitalize/layoutJob.ts` (`createLayoutJob`), beside `ocrRunApi.ts` and `triagePrefs.ts`, so the route keeps only layout.

Pipeline stage (idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported) is polled via `GET /api/admin/maps/[id]/pipeline`. Four of those stages are **derived** from the map's latest `ocr`/`seg` job; PATCH accepts only `reviewed`, `seg_reviewed`, `exported` and `idle` — anything else is a 400.

**Trace (`/scan?mode=trace`)** — `TraceTool.svelte` (OL Draw + Select + Modify) + `TraceSidebar.svelte`. Polygon for closed footprints, line for roads/waterways. Submits through `POST /api/contribute/footprints` (rate-limited, author stamped server-side).

**Review (`/scan?mode=review`)** — a queue per kind of contribution, chosen by a tab (`?kind=stories` opens the second one). **Stories**: `StoryReviewPanel.svelte` lists submitted stories and approves / sends back / rejects through `/api/admin/stories`. **Footprints**: HITL for SAM2 `submitted` / `needs_review` polygons: `ReviewMode.svelte` mounts `ImageShell` + `ReviewTool.svelte` + `ReviewSidebar.svelte` (approve/reject, "Mark seg reviewed"). Map list from `fetchMapsWithSubmittedFootprints()`. API `GET/PATCH /api/admin/footprints`; "Mark seg reviewed" PATCHes `/api/admin/maps/[id]/pipeline` → `seg_reviewed`.

### Maps domain

Canonical types live in **`src/lib/data/maps/`**:

- `types.ts` — `MapRecord`, `MapListItem`, `MapSourceType`, `MapStatus`, `IIIFManifestMeta`. **This is the only home** — `src/lib/map/types.ts` no longer re-exports them.
- `footprintTypes.ts` — `FeatureType`, `FootprintSubmission`, `PixelCoord`, `LegendItem`, `geometryKind`, plus `FEATURE_TYPE_LABELS` / `FEATURE_TYPE_COLORS` / `featureTypeFill()`. The colours are the **one** palette for footprints: `FootprintsLayer`, `TraceSidebar` and `ReviewSidebar` each had their own until Sept 2026, so a building was green on /explore, gold in the trace list and blue in the review list.
- `triageTypes.ts` — the saved triage and the layout vocabulary: `LAYOUT_CATEGORIES` (sheet · main_map · title · legend · name_list · inset · scale_bar · north_arrow · stamp), `LayoutRegion`, `SavedTriage`, `parseRegion` (untrusted model output in, valid region or null out) and `tilingCrop` (**`main_map` beats the neatline**, because the neatline is the printed border and a legend inside it is inside the neatline too). Lives in `data` so `$lib/server` and the digitalize UI share one vocabulary.
- `service.ts` — `fetchMaps`, `fetchFeaturedMaps`, `fetchGeoreferencedMaps`, `fetchMapRow`.
- `iiifManifest.ts` — `fetchIIIFManifest(url)`; handles IIIF v2 + v3.
- `georef.ts` — `fetchGeorefQueue`, `annotationStorageUrl`, `allmapsEditorUrl`.

`src/lib/map/types.ts` is **UI-only**: `ViewMode`, `DrawingMode`, `AnnotationSummary`, `SearchResult`, `AnnotationSet`. `src/lib/map/constants.ts` holds `BASEMAP_DEFS`, `DRAW_TYPE_MAP`, `DEFAULT_ANNOTATION_COLOR`.

Admin client functions: `src/lib/data/admin/adminApi.ts` (map CRUD, image upload, IIIF source mgmt, R2 mirror) with the payload shape in `mapEditPayload.ts`.

`MapListItem.bbox` is the DB column (`maps.bbox`); `MapListItem.bounds` is a runtime enrichment added by `useMapList.ts` once bounds are resolved. Same `[minLon, minLat, maxLon, maxLat]` shape.

`MapListItem.id` is `maps.id` (UUID). `allmaps_id` (16-char hex) is the canonical Allmaps image ID; `annotation_url` is an optional override (set by `mirror-r2` to the Supabase Storage URL of the rewritten annotation JSON). Either resolves via `annotationUrlForSource()`. Story `overlayMapId` may be UUID (new) or Allmaps ID (legacy) — resolve via `mapList.find(m => m.id === id || m.allmaps_id === id)`.

### Annotations (`src/lib/map/annotations/`)

`annotationState.ts` (list + selection), `annotationHistory.ts` (undo/redo with GeoJSON snapshots, 100-entry limit), `annotationContext.ts` (Svelte context), `olAnnotations.ts` (OL feature utils), `annotationCommands.ts` (draw/edit commands extracted from `DrawTool`). All features require `id`, `label`, `color`, `hidden` — use `ensureAnnotationDefaults(feature)`. Default colour `#2563eb`.

### Data access (`src/lib/data/supabase/`)

`client.ts` (browser client), `context.ts` (auth via Svelte context), `role.ts` (`fetchUserRole`), `annotations.ts`, `stories.ts`, `favorites.ts`, `mapOpens.ts`, `footprints.ts`, `types.ts` (generated). `footprints.ts` is both the footprint CRUD layer and the SAM2 review entry point: `fetchSubmittedFootprints()`, `fetchMapsWithSubmittedFootprints()`, plus `fetchLabelMaps()` — the map-selector source for `/scan?mode=triage` and `/scan?mode=trace`.

### IIIF utilities (`src/lib/core/iiif/`)

- `allmapsId.ts` — `deriveAllmapsId(iiifImageUrl)`.
- `annotationUrl.ts` — `annotationUrlForSource(source)`: bare ID or full URL → annotation URL.

### Map libraries

**The basemap is self-hosted.** `/explore`'s street basemap is one ~348 MB PMTiles archive spanning Hanoi to the Mekong (Protomaps' daily OpenStreetMap build, bbox `105.5,8.5,108.5,21.6`, z0–15) in the `vma-tiles` R2 bucket at key `basemap/vietnam.pmtiles`, served by `worker/` at `iiif.maparchive.vn/basemap/*` with byte-range support. No API key, no quota, no third-party usage policy. `src/lib/map/basemapStyle.ts` holds the source and a deliberately quiet OpenLayers style over the Protomaps v4 schema (`earth`, `landcover`, `landuse`, `water`, `roads`, `buildings`, `boundaries`, `places`); it carries the rebuild commands. Predecessors, both abandoned: CARTO's keyless raster endpoint began stamping "API KEY REQUIRED" over every tile, and the OSM Foundation's own tiles have a usage policy that does not cover a busy site. `PUBLIC_PROTOMAPS_KEY` is gone from `.env.example` too — nothing read it and nothing needs it. The Saigon-only extract it replaced (37 MB, bbox `106.3,10.3,107.1,11.2`) left 21 of 40 georeferenced maps — every Huế and Hanoi sheet — on bare `earth` fill; `basemap/saigon.pmtiles` is still in the bucket, unreferenced. Rebuild with `scripts/pmtiles_extract.sh vietnam 105.5,8.5,108.5,21.6 15 --upload`.

**OpenLayers is the only map engine** (MapShell + ImageShell); `@allmaps/openlayers` warps historical tiles. MapLibre GL was removed (Aug 2026) along with `@allmaps/maplibre`, `@protomaps/basemaps` and `ol-mapbox-style`.

## API routes (`src/routes/api/`)

Per-route reference: **`docs/api.md`**. The rules:

- Every handler is `requireRole → adminClient → query → json`, using the `$lib/server` helpers `requireRole`/`getRole` (`auth.ts`), `adminClient` (`supabaseAdmin.ts`) and `assertUuid`/`dbError` (`http.ts` — 400 on a malformed id, and no raw Postgres message ever reaches the client).
- Three auth classes: **admin/mod session** (`/api/admin/*`), **any signed-in user** (`/api/contribute/*`, `user_id` from the session, rate-limited by `assertUnderRateLimit`), and **worker token** (`/api/pipeline/*`, `Authorization: Bearer <worker_keys token>` via `$lib/server/workerAuth.ts`; mint with `scripts/mint-worker-key.mjs`). `/api/search`, `/api/context`, `/api/press`, `/api/maps/[id]/legend-points` are public and enforce `status IN ('public','featured')` server-side. `/api/search` takes `include=maps,scout,labels,places`; `places` searches the mig 067 gazetteer and is what the command palette turns into `/archive/place/<slug>` rows.
- Enqueue, never execute: routes that start pipeline work insert a `pipeline_jobs` row and return 202 (409 if one is in flight). Nothing runs until a worker claims it. `/api/pipeline/execute` is the one exception, for kinds that need the service key.
- Human pipeline stages (`reviewed`, `seg_reviewed`, `exported`, `idle`) are the only ones PATCHable; machine stages derive from jobs and are rejected with 400.

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce references.

## Database

Schema: `supabase/migrations/` (head **070**). Table-by-table reference and the rules behind each constraint: **`docs/db-guidelines.md`** §11. The rules in one breath:

- `maps.status` is `draft | public | featured` and is the **only** visibility model (mig 060). Draft maps are readable by any signed-in user, never anonymously (mig 063). A published map must carry `annotation_url` **or** `allmaps_id` (mig 062), and publishing enqueues `mirror_annotation` + `tile_to_r2` (mig 058).
- **Status transitions live in Postgres**, not the API: `set_extraction_status`, `revert_recent_validations`, `set_footprint_status`, `set_review_mark`, `claim_job`, `finish_job`. All `security definer`, `service_role` only. New write paths reuse them.
- `pipeline_jobs` is the queue (one live job per kind × map); `map_pipeline_status` is a **view**; `map_review_marks` holds the three human stages.
- Full-text search uses the `simple` tsvector config on purpose — the corpus is French/Vietnamese/English.

## Admin tooling

Map CRUD is inline in `/archive`, gated by `role === 'admin' | 'mod'`: `CatalogUnifiedSearch.svelte` dispatches `edit`, and the **route page** `src/routes/(editorial)/archive/+page.svelte` renders `MapEditModal`. Bulk upload, Scout and Status are tabs of `/admin`. Full reference in `docs/admin-tooling.md`.

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
