# VMA System Guidelines

Canonical reference for code organisation, page structure, and component patterns. All new routes and components follow these rules; deviations need a comment saying why.

Companion docs: `db-guidelines.md` (schema), `design-system.md` (tokens + CSS), `admin-tooling.md`, `pipelines.md`, `theory.md` (the intellectual framing), `cleanup-2026-08.md` (what the Aug-2026 restructure changed).

---

## 0. Mission and product layers

Build the spatial memory of colonial Saigon: ingest historical maps → process into geometry → enrich with knowledge → serve to users and researchers.

```
6. PLATFORM        auth, nav, about, blog, profile
5. RESEARCH SUITE  user publications combining maps + annotations + stories   [future]
4. USAGE           explore, studio, stories, walking tours
3. ENRICHMENT      knowledge graph, photos, 3D                                [future]
2. PROCESSING      pixel (triage / OCR / SAM2 / review) | georef (Allmaps)
1. INGEST          upload map → IA / BnF / R2 / own server
```

Layers 1, 2, 4 and 6 are built. Layer 3 and 5 are aspirations — no schema and no code. See `docs/theory.md` for the underlying data-stack model and `docs/strategy.md` for what is funded or planned.

---

## 1. The layering rule

> **`core → data → map → features → routes`; `ui` is leaf primitives with zero domain imports; `server` is `$lib/server` only.**

A directory may import only from directories to its **left**. This is the single organising rule for `src/lib`; it replaced 19 ad-hoc top-level directories in August 2026.

```
src/lib/
├─ core/      pure — no OpenLayers, no Supabase
│             geo/ (geo, bearing, geolocation, mapBounds, types)
│             iiif/ (allmapsId, annotationUrl, iiifImageInfo)
│             utils/ (debounce, id, pwa, persistence/)
├─ data/      DB + HTTP access and the canonical domain types
│             supabase/ maps/ admin/ blog/ about/
├─ server/    $lib/server — SvelteKit makes a client import a build error
│             auth · supabaseAdmin · http · storage · ia · mapFields
│             facets · transformer · allmaps · ocrReview
├─ map/       the OpenLayers runtime, one home
│             shell/ (MapShell, ImageShell, LayerRenderer, ToolLayout, …)
│             stores/ (mapStore, layerStore, layersStore, urlStore)
│             annotations/ · types.ts · constants.ts
├─ features/  one directory per product surface
│             explore/ catalog/ stories/{shared,editor,play} studio/
│             contribute/{ocr,digitalize,trace,review,shared} admin/
└─ ui/        generic primitives only — no domain imports
              NavBar EditorialFooter PageHero MapCard LocationSearch AuthGate …
```

**Consequences to respect:**

- `data/maps/types.ts` is the **only** home for `MapRecord` / `MapListItem` / `MapStatus`. `map/types.ts` no longer re-exports them and holds UI-only types (`ViewMode`, `DrawingMode`, `AnnotationSummary`, `SearchResult`, `AnnotationSet`).
- `core/` must not import `@allmaps/openlayers` or `ol` — that is what keeps the OL bundle off `/explore`'s data path.
- `ui/` must not import from `features/`. When a primitive needs domain behaviour, the **route page** wires it: `/catalog` renders `MapEditModal` itself, `CatalogUnifiedSearch` only dispatches `edit`.
- Routes are thin — load, wire, render. Business logic belongs in a `features/` module so it stays importable and testable.
- Features are isolated from each other. Cross-feature imports go through `features/shared/` (cross-cutting UI) or `features/<x>/shared/` (a feature's public API); anything else under another feature is private. Lint-enforced by the regex rule in `eslint.config.js` — `catalog/` had been a shared layer by accident, imported by four features, before the seam was declared.
- One Svelte component per file. No barrel `index.ts` re-exports for components.

---

## 2. Route map

The group in parentheses is the SvelteKit layout group, not part of the URL. Both groups render `NavBar`; only `(editorial)` adds `EditorialFooter` (`src/routes/(editorial)/+layout.svelte`).

| Route | Group | Entry component | Auth |
|-------|-------|-----------------|------|
| `/` | (editorial) | `+page.svelte` | none |
| `/about` | (editorial) | `+page.svelte` + `content.ts` beside it | none |
| `/blog`, `/blog/[slug]` | (editorial) | `+page.svelte` + `posts.ts` beside it | none |
| `/catalog` | (editorial) | `+page.svelte` → `CatalogUnifiedSearch` (+ `MapEditModal` for admin/mod) | none |
| `/contribute` | (editorial) | `+page.svelte` | none (mod cards gated) |
| `/contribute/georef` | (editorial) | `+page.svelte` → Allmaps Editor | none |
| `/login` | (editorial) | `+page.svelte` | none |
| `/profile` | (editorial) | `+page.svelte` + `+page.server.ts` | auth (303 → `/login`) |
| `/admin?tab=bulk` | (editorial) | `+page.svelte` | admin |
| `/admin?tab=scout` | (editorial) | `+page.svelte` + `ScoutCard` | admin/mod |
| `/explore` | (app) | `+page.svelte` + `MapWorkspace` + `ExploreSidebar` (left rail) + `ExploreRightSidebar` (right rail) | none |
| `/explore?mode=annotate` | (app) | `StudioMode.svelte` | auth |
| `/explore?mode=story` | (app) | `CreateMode.svelte` | auth |
| `/trip/[id]` | (app) | `+page.svelte` + `TripPlayback` | none |
| `/scan` | (app) | `+page.svelte` + `ImageShell` | none |
| `/scan?mode=prepare` | (app) | `+page.svelte` + `DigitalizePage` + `TriageTool` | auth |
| `/scan?mode=text` | (app) | `+page.svelte` + `DigitalizePage` + `OcrBboxTool` | auth |
| `/scan?mode=shapes` | (app) | `+page.svelte` + `ShapesPage` + `TraceTool` / `SegSidebar` / `ReviewTool` | auth; Validate is mod/admin |

Every route is in one of the two groups — the footprint review moved into `(app)` in Aug 2026, and became `?mode=shapes&tab=validate` in Sept.

**Redirects** are a table, not stub pages. `LEGACY_REDIRECTS` in `src/hooks.server.ts` issues a 301 with the query string preserved:

- `/view` → `/explore`
- `/annotate`, `/studio` → `/explore?mode=annotate`
- `/create` → `/explore?mode=story`
- `/image` → `/scan`
- `/contribute/label`, `/contribute/digitalize` → `/scan?mode=prepare`
- `/contribute/trace` → `/scan?mode=shapes`
- `/contribute/review` → `/scan?mode=shapes&tab=validate`
- `/admin/bulk|scout|status` → `/admin?tab=…`

`LEGACY_PREFIXES` handles the two that carry an id rather than a fixed name:
`/map/<id>` → `/catalog/<id>` and `/place/<name>` → `/catalog/place/<name>`.
`withSearch()` joins an incoming query with `&`, since half the targets already
carry a `?mode=`.

There is no `/signup`, `/contribute/catalog`, `/hunt` or `/georef` route.

---

## 3. Page registers

Four registers. The register decides the shell and the CSS.

### Editorial

`/`, `/about`, `/blog`, `/blog/[slug]`, `/catalog`, `/contribute`, `/contribute/georef`, `/login`, `/profile`, `/admin?tab=bulk`, `/admin?tab=scout`.

Nav and footer come from the group layout, so a page renders only its own body:

```svelte
<div class="page my-page" class:mounted>
  <header class="editorial-hero">
    <div class="hero-inner">
      <div class="label-chip">Context label</div>
      <h1 class="hero-title">Headline<br /><span class="text-highlight">key word.</span></h1>
      <p class="hero-sub">Supporting sentence.</p>
    </div>
  </header>
  <main class="editorial-main"><!-- .section-card blocks --></main>
</div>
```

The shared classes (`.editorial-hero`, `.editorial-main`, `.section-card`, `.label-chip`, `.text-highlight`, `.action-btn`, `.pill-btn`, `.badge-chip`, `.chip-*`) live in `src/styles/components/editorial.css`, imported globally. **Do not redefine them per component** — add a modifier class or extend the sheet. Page-specific CSS goes in `src/styles/pages/<page>.css`.

### Geo-map tool

`/explore`, `/explore?mode=annotate`, `/explore?mode=story`, `/trip/[id]`.

`src/lib/map/shell/MapWorkspace.svelte` is the shared base (§5). It composes `ToolLayout` + `MapShell` + `LayerRenderer` + `MapModeOverlays`. Never create a second OL map outside `MapShell`.

### IIIF-canvas tool

`/scan`, `/scan?mode=prepare`, `/scan?mode=text`, `/scan?mode=shapes`, plus `NeatlineEditor` inside the admin modal.

These use `ImageShell` (static image extent, pixel coordinates) and the shared sidebar frame `ToolSidebarShell` + `ToolMapPicker`. They do **not** use MapShell or the global map stores. CSS: `src/styles/layouts/tool-page.css` + `src/styles/components/sidebar.css` — one sidebar vocabulary, `.sb-*`. `components/tool-sidebar.css` held a second one (`.tool-*`) until Sept 2026; its last speaker was `TriageSidebar` and the sheet is gone.

### Admin

Admin work happens inside the editorial register. Map CRUD is a modal rendered by `/catalog`; bulk and scout are ordinary editorial pages using `src/styles/pages/admin-bulk.css` and `admin-scout.css`, with modal chrome in `src/styles/components/admin-modals.css`. The old `layouts/admin.css` dashboard sheet was deleted — there is no `.dashboard` / `.top-bar` register any more.

---

## 4. Component rules

**Legacy Svelte syntax. Do not use runes.**

```svelte
<!-- correct -->
export let value: string;
$: derived = value.toUpperCase();
const dispatch = createEventDispatcher();

<!-- forbidden -->
let value = $state('');
let derived = $derived(value.toUpperCase());
```

- Parent → child: props. Child → parent: `createEventDispatcher`. Never two-way bind complex data.
- Deep sharing: `setContext`/`getContext` — `getShellContext()`, `getImageShellStore()`, `getSupabaseContext()`, `getAnnotationContext()`. Never prop-drill more than two levels.
- `$:` for derived values only, and keep it under ~3 lines — extract a function past that. Never use `$:` for async side effects; use `onMount` or an explicit call.
- Always return a cleanup function from `onMount` when you add listeners.
- Any component past ~400 lines is a smell. The Aug-2026 pass split every file over that line; the largest survivor is 575.

---

## 5. MapWorkspace contract

`src/lib/map/shell/MapWorkspace.svelte` is the unified base for geo-map modes. `/explore`, `StudioMode` and `CreateMode` all build on it; new geo-map surfaces must use it rather than mounting `MapShell` directly.

**Owns:** `ToolLayout` chrome (responsive workspace, sidebar resize, mobile drawer stack) · `MapShell` + `LayerRenderer` + `MapModeOverlays` · the map-list fetch and bounds backfill (`useMapList`) · deriving `selectedMap` · forwarding view-mode changes to `layerStore` · the "Zoom to Map" prompt.

**Does NOT own:** auth gates (the route page decides whether to render it) · mode-specific stores (story player, annotation project, story library) · URL parameter parsing (the route page reads params and seeds the stores).

**Props:** `mapStore` and `layerStore` (created by `createGeoMapStores()` in the route page — that helper also wires the `topOverlay → mapStore.activeMapId` bridge), `supabase` (pass `null` to skip auto-load), `dualPaneActive`, sidebar width/max props for both sidebars.

**Bind targets:** `shellMap`, `sidebarCollapsed`, `isMobile`, `isCompact`.

**Slots:** `sidebar`, `right-sidebar`, `map-children` (rendered inside MapShell's default slot — GpsTracker, StoryMarkers, DrawTool, MapClickCapture, LegendPointsLayer), `dual-pane`, `map-overlay`, `floating`, `mobile-layers`, `mobile-controls`, `mobile-browse`, `mobile-sidebar` (legacy single-drawer fallback).

**Events:** `mapsloaded` only. Overlay load/error state is handled internally by `MapModeOverlays`; there are no `overlayload*` events to wire.

**Z-index scale** (`src/styles/layouts/mode-shared.css`) — follow it:

| z | Element |
|---|---------|
| 0 | `.dual-container` |
| 5–30 | in-map elements; `.lens-overlay` is 30 |
| 50 | `.top-controls`, `.floating-controls` |
| 95 | `.explore-mode .resolving`, `.explore-mode .gps-error` |
| 100 | `.mobile-sidebar` |

---

## 6. API route conventions

All API routes live under `src/routes/api/`. Every handler is `requireRole → adminClient → query → json`, built from `$lib/server`:

| Helper | File | Purpose |
|---|---|---|
| `requireRole`, `getRole` | `server/auth.ts` | role gate; never trust a client-supplied role |
| `adminClient` | `server/supabaseAdmin.ts` | service-key client (bypasses RLS) |
| `assertUuid`, `dbError` | `server/http.ts` | 400 on a malformed id; no raw Postgres message reaches the client |
| `pickMapFields` | `server/mapFields.ts` | the one allow-list of writable `maps` columns |
| `uploadJson`, `uploadToIA` | `server/storage.ts`, `server/ia.ts` | Supabase Storage / Internet Archive |
| `tally` | `server/facets.ts` | declarative facet counting for `/api/search` |
| `getTransformer`, `allmapsAnnotationUrl` | `server/transformer.ts` | Allmaps warping server-side |
| `probeAllmapsAnnotation`, `lookupAllmapsId` | `server/allmaps.ts` | georef probe + id derivation |
| `bulkSetStatus`, `revertRecentValidations` | `server/ocrReview.ts` | OCR review write paths |

Rules: accept JSON, return JSON — no form data. Admin routes re-check `profiles.role` in the handler; do not rely on RLS alone. The service key is `$env/static/private` and must never reach a component. The current route inventory is in `src/routes/CLAUDE.md`.

---

## 7. Data layer conventions

**Map identity.** `maps.id` (UUID) is the canonical identifier everywhere — FK columns, URL params, component props. `maps.allmaps_id` is used only when calling Allmaps (annotation URLs, warped tile layers) and is never a join key. `mapStore.activeMapId` now holds the UUID and is mirrored from `layersStore.topOverlay`; the old `&map=` hash writer is gone and the deep-link param is `?map=<uuid>`.

**Client usage.** Browser: `getSupabaseContext()` → `{ supabase, session }`. Server: `adminClient()` from `$lib/server/supabaseAdmin`. Always pass the generic — `createClient<Database>(...)`. A bare `createClient(...)` is what forces `as any` casts downstream; about 25 remain.

**Generated types.** `src/lib/data/supabase/types.ts` is generated — never hand-edit:

```bash
supabase gen types typescript --linked 2>/dev/null > src/lib/data/supabase/types.ts
```

It is current against migration head 051. Insert/Update payloads use `?:` optional fields, not `Partial<{...}>` (which resolves as `never`).

---

## 8. Styling

Everything shared lives in `src/styles/`, reached via the `$styles` alias. `global.css` imports `tokens.css` plus the always-on component sheets; layout and page sheets are imported by whoever needs them. The full file map and the token list are in `docs/design-system.md`.

**Token rule.** Never hardcode a colour, border or shadow in a component `<style>` block. Component CSS carries layout and positioning; everything visual goes through `var(--token)`.

```css
/* wrong */ border: 3px solid #111;
/* right */ border: var(--border-thick);
```

The Aug-2026 sweep took component hex literals from ~900 to 116. The Sept-2026 plate-tone pass took the rest: canvas colours moved to `INK` in `src/lib/core/ink.ts` (an OpenLayers style is a draw call and cannot read a CSS variable), stale `var(--token, #old-value)` fallbacks became `var(--token, var(--other-token))`, and ink-at-alpha scrims became `color-mix`. Four literals survive in the tree and each says why where it sits: `ink.ts` itself, the offscreen analysis canvas in `suggestTriage.ts`, the Google logo paths, and `ReviewSidebar`'s cadastral class swatches.

**One button system.** Every button is in `components/buttons.css` except `.sb-btn` (token-scoped). A component that needs a near-`.chip` adds the class and overrides `--btn-*`; it never rebuilds the shape, and it never redefines a global button class in its own `<style>` block — Svelte scoping makes that win silently.

**Scoping.** `<style>` is component-scoped by default — use it freely for layout. Never redefine a shared global class per component. Use `:global()` only for third-party DOM (OL controls). Inline `style=` is for dynamic values only (`style="--sidebar-width: {w}px"`).

**Two themes.** `tokens.css` writes each ink as `light-dark(light, dark)`; `:root[data-theme='light'|'dark']` pins which face is used, and the `vma-theme` boot script in `src/app.html` replays the reader's choice before first paint. A new colour needs both faces — `tests/theme.spec.ts` asserts the contrast of each. Anything that paints to a canvas rather than reading CSS (the OL basemap, annotation ink) subscribes to `isDarkTheme` instead.

---

## 9. Navigation and page state

Nav and footer render once from the group layout. To add a public page: create the route under `(editorial)/`, add the link to `src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`, and add a row to §2 above.

Editorial pages use a mount fade-in:

```svelte
<script lang="ts">
  let mounted = false;
  onMount(() => { mounted = true; });
</script>
<div class="page" class:mounted>…</div>
```

Async data shows a skeleton or spinner **inside** the content area — the hero and nav are visible immediately.

---

## 10. Roles and access

| Role | Access |
|------|--------|
| logged out | public read: explore, catalog, blog, about, trip playback |
| `user` | contribute: georeference, trace footprints, digitalize, author stories |
| `mod` | + review/approve footprints, OCR review, map metadata, scout |
| `admin` | + create/delete maps, publish, bulk upload, pipeline control |

Role lives in `profiles.role`, read on the client via `fetchUserRole` (`data/supabase/role.ts`) and enforced server-side by `requireRole`. `/contribute` shows the review and admin cards only to `mod` / `admin`.

---

## 11. Known debt

| Item | Location | Fix |
|------|----------|-----|
| ~30 `as any` casts | mostly Svelte components | pass `<Database>` to `createClient` at each call site |
| `footprints.ts` mixes two concerns | `data/supabase/footprints.ts` holds both map-selector queries and footprint CRUD | split into `maps/labelMaps.ts` + a contribute-scoped module |
| `CatalogUnifiedSearch` still queries Supabase directly | `features/catalog/CatalogUnifiedSearch.svelte` | move the read into `data/maps/service.ts` |
| Mixed error conventions | throw vs `console` → `[]` vs `console` → `false` across `data/` | pick one |
| Mobile gaps in contribute | `OcrSidebar` bind/`on:filter` and the Segmentation tab are desktop-only (carried from the Aug 2026 cleanup, not re-verified since) | decide whether these tools are desktop-only by design, then either say so or fix |
| Fat page components | `ExplorePage.svelte` (336 script lines) and `DigitalizePage.svelte` (263, down from 322 — the layout job left in Sept 2026) are controllers, not wiring. The Sept 2026 route merge moved them out of `src/routes` into `features/`, which fixed where they live, not how big they are | pull into `features/<x>/<x>Controller.ts` when next touching them — the `ocrReviewController.ts` / `layoutJob.ts` pattern |
