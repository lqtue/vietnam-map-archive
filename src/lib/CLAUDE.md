# src/lib — the rules for this tree

Root context: `/CLAUDE.md`. Full map-runtime reference: `docs/architecture.md` — read it
before touching the OpenLayers layer; what follows is only the shape.

## Svelte dialect

**Legacy, NOT runes.** Use `$:`, `export let`, `createEventDispatcher`, `$store`.
Do not use `$state`, `$derived`, `$effect`.

**House rules live in one place**: the `svelte-core-bestpractices` skill (`.agents/skills/`,
symlinked into `.claude/skills/`) — a project fork of the upstream `sveltejs/ai-tools` skill,
rewritten for this dialect and merged with <https://github.com/spiegelgraphics/svelte-best-practices>.
**Load it before creating, editing or reviewing any `.svelte` file.** It covers the dialect, the
HTML→CSS→template→JS ladder, `$:` discipline, reassign-don't-mutate, keyed `{#each}`, scoped CSS,
component size and teardown. `skills-lock.json` still carries the upstream hash, so `npx skills add`
would revert the fork.

**Svelte MCP server** (plugin `svelte`, from `sveltejs/ai-tools`): `list-sections` first, then
`get-documentation`, then `svelte-autofixer` on any code before showing it (re-run until clean);
`playground-link` only for standalone components. Delegate more-than-small `.svelte` / `.svelte.ts`
work to the `svelte-file-editor` agent — it iterates with the autofixer in its own context.

**Caveat:** the autofixer and the Svelte skills assume runes, and their "avoid legacy features" list
is exactly this repo's house style — `$:`, `export let`, `on:click`, `<slot>`/`<svelte:fragment>`,
`<svelte:component>`, `<svelte:self>`, `createEventDispatcher`, stores, `use:action`, `class:`.
Ignore every suggestion to modernise those; act only on the rest (missing `{#each}` keys, effect
cleanup, scoped-CSS and a11y findings, real bugs).

## Layering (enforced by `@typescript-eslint/no-restricted-imports` in `eslint.config.js`; type-only imports are exempt)

> `core → data → map → features → routes`; `ui` is leaf primitives with zero domain imports;
> `server` is `$lib/server` only.

A directory may import only from directories to its **left**. Routes stay thin: load + wire, no
business logic.

**Feature isolation (also lint-enforced):** a feature may import another feature only through a
declared seam — `src/lib/features/shared/` (cross-cutting UI: the layer panels, `SidebarCard`,
`MapViewerSidebar`, `LabelHits`, and the `catalogSearch` client) or `src/lib/features/<x>/shared/`
(that feature's public API — `stories/shared`, `contribute/shared`, `catalog/shared`). Everything
else under another feature is private. Routes may import anything under `features/`.

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

`$lib/server/*` is import-guarded by SvelteKit — a client-side import of the service key is a build
error, not a code-review catch.

## The map runtime

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
- **Canonical types** live in `src/lib/data/maps/` (`types.ts`, `footprintTypes.ts`,
  `triageTypes.ts`, `service.ts`, `iiifManifest.ts`, `georef.ts`). `src/lib/map/types.ts` is UI-only.
- **Basemap and overlays are self-hosted PMTiles** on `tiles.maparchive.vn` — see
  `docs/architecture.md` §Map libraries before changing a URL, a zoom range or a build key.
- **`@allmaps/openlayers` is loaded on demand** — one runtime importer, `createWarpedLayer` in
  `map/shell/warpedOverlay.ts`, which is why it is `async`. Keep any new importer type-only or
  151 kB goes back in front of /explore's first paint.
- **Command palette** is mounted once by the root layout: `features/shared/CommandPalette.svelte`,
  ⌘K, searching pages · maps · places · labels through `/api/search`.

Code shared across the story lifecycle (markers, playback state, point ops) lives in
`src/lib/features/stories/shared/`. All app modes except the IIIF-canvas contribute tools share
MapShell + the map stores.

## Data access

List reads go through `LIST_COLUMNS` in `src/lib/data/maps/service.ts` — exactly the columns
`toMapListItem` projects. `select('*')` was 120 kB of row for the catalog (37 kB over the wire),
most of it `extra_metadata` and the long source fields no list renders; the named list is 9 kB.
`fetchMapRow` still takes the whole row, because the admin editor writes back columns no list carries.

**Supabase types:**

- Insert/Update types: use `?:` optional fields — **not** `Partial<{...}>` (resolves as `never`).
- `src/lib/data/supabase/types.ts` is generated and current against migration head **086**. Nothing
  regenerates it automatically — do it after every push. Prefer real types over `as any`. Drift
  history and the `--local` trap: `docs/conventions.md` §Supabase types.
- The generic belongs on the client: `createClient<Database>(...)`. A bare `createClient(...)` is
  what forces most `as any` casts downstream.
- **Realtime is stubbed out of the browser bundle** (`vite.config.ts` aliases `@supabase/realtime-js`).
  The day a real `.channel()` appears, the alias and the stub both come out.

**Environment variables:**

```
PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY   # anon key = the sb_publishable_… key
SUPABASE_SERVICE_KEY            # admin API routes only; the sb_secret_… key
IA_S3_ACCESS_KEY, IA_S3_SECRET_KEY   # Internet Archive upload
VMA_API_URL, VMA_WORKER_KEY     # worker machines only — never the web app
```

## The component vocabulary is one of each

`.btn` is an action and `.chip` a choice; `.section-card` is the one card; `$lib/ui/Tabs.svelte` the
one tab strip; `.sb-search` the one search field; `$lib/ui/DataTable.svelte` + `SortHeader` +
`core/utils/tableSort.ts` the one table and one sort. All CSS in `src/styles/` via `$styles`;
colours are `var(--token)`, canvas ink is `INK`/`inkAlpha` in `core/ink.ts`. Two themes, one value
each — `light-dark()` in `tokens.css`, and four things deliberately do not flip. **Before adding any
of these, read `docs/conventions.md` §Component vocabulary** — it lists the twenty-seven selectors
these eleven replaced, so a second one is a regression, not a new component. `tests/screens.spec.ts`
fails if a retired name reappears.

**The fonts are self-hosted** (`src/styles/fonts.css` + `static/fonts/`, latin · latin-ext ·
vietnamese only, Inter variable). Do not reintroduce the Google Fonts link or the Translate widget —
`docs/conventions.md` §Fonts.

**One place, not one spelling.** The gazetteer (`place_names`) groups by `core_key`, and the rule
exists twice — `place_core_key()` in Postgres and `placeCoreKey` in `$lib/core/utils/placeKey.ts`.
The two must agree or a place page 404s. `docs/conventions.md` §The gazetteer key.
