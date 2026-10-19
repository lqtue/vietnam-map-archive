# Architecture

For anyone changing the app. Kind: guide. How the code is laid out, how a page is built, and why
each part is the way it is. The agent-facing short form is `src/lib/CLAUDE.md` and
`src/routes/CLAUDE.md`; the words for what the archive holds are [ontology.md](../ontology.md).

This page absorbed `system-guidelines.md` and `conventions.md` on 2026-10-17. Their text is kept
word for word below; only copies that had gone stale beside a newer one were dropped.

## Contents

1. [Layering](#1-layering)
2. [Routes and pages](#2-routes-and-pages)
3. [The map runtime](#3-the-map-runtime)
4. [Surfaces](#4-surfaces): /explore, the home page, the contribute tools
5. [Data](#5-data)
6. [Components and styling](#6-components-and-styling)
7. [Roles and known debt](#7-roles-and-known-debt)

## 1. Layering

The rule, the folder tree and the lint seams are in `src/lib/CLAUDE.md`. What they mean in practice:

- `data/maps/types.ts` is the **only** home for `MapRecord` / `MapListItem` / `MapStatus`.
  `map/types.ts` no longer re-exports them and holds UI-only types (`ViewMode`, `DrawingMode`,
  `AnnotationSummary`, `SearchResult`, `AnnotationSet`).
- `core/` must not import `@allmaps/openlayers` or `ol` — that is what keeps the OL bundle off
  `/explore`'s data path.
- `ui/` must not import from `features/`. When a primitive needs domain behaviour, the **route
  page** wires it: `/catalog` renders `MapEditModal` itself, `CatalogUnifiedSearch` only dispatches
  `edit`.
- Routes are thin — load, wire, render. Business logic belongs in a `features/` module so it stays
  importable and testable.
- Features are isolated from each other. Cross-feature imports go through `features/shared/`
  (cross-cutting UI) or `features/<x>/shared/` (a feature's public API); anything else under another
  feature is private. Lint-enforced by the regex rule in `eslint.config.js` — `catalog/` had been a
  shared layer by accident, imported by four features, before the seam was declared.
- One Svelte component per file. No barrel `index.ts` re-exports for components.

## 2. Routes and pages

### Every route

The group in parentheses is the SvelteKit layout group, not part of the URL. Both groups render
`NavBar`; only `(editorial)` adds `EditorialFooter` (`src/routes/(editorial)/+layout.svelte`).

| Route | Purpose | Source |
|-------|---------|--------|
| `/explore` | MapShell dispatcher | `src/routes/(app)/explore/` |
| `/explore?mode=browse` | Browse maps, play stories | `src/lib/features/explore/ExplorePage.svelte` |
| `/explore?mode=studio` | Free-form annotation + timeline animation. `?mode=annotate` is the name it shipped under and is aliased, not redirected (`EXPLORE_MODE_ALIASES` in `core/routeModes.ts`, read by `resolveExploreMode()` in `(app)/explore/+page.svelte`) — the dispatcher only ever matches `studio` | `src/lib/features/annotate/` |
| `/explore?mode=story` | Author stories | `src/lib/features/stories/editor/` |
| `/scan` | ImageShell dispatcher | `src/routes/(app)/scan/` |
| `/scan?mode=inspect` | IIIF viewer, unlisted — the plain look at a **draft** scan | `src/lib/features/contribute/inspect/` |
| `/scan?mode=prepare` | Layout · neatline · tile grid · save · queue OCR | `src/lib/features/contribute/digitalize/` |
| `/scan?mode=text` | Check what came back: Names · Index · Numbers · Other | `src/lib/features/contribute/ocr/` |
| `/scan?mode=shapes` | Draw · Segment · Validate, `?tab=` | `src/lib/features/contribute/{trace,review}/` |
| `/scan?mode=legend` | Staff: place the numbered legend on the scan in image pixels — select, click to place, accept a numeral, batch save | `src/lib/features/contribute/legend/` |
| `/trip/[id]` | Story playback | `src/lib/features/stories/play/` |
| `/catalog` | Faceted catalog + series band + inline admin | `src/lib/features/catalog/`, `src/routes/(editorial)/catalog/` |
| `/catalog/[id]` | One sheet: the record **and** its tiled scan (`SheetZoom`, full-screen). `[id]` is the **slug** (mig 088); a uuid or a retired slug 301s to it | `src/routes/(editorial)/catalog/[id]/` |
| `/catalog/place/[name]` | The gazetteer: one page per attested place name | `src/routes/(editorial)/catalog/place/[name]/` |
| `/catalog/area/[slug]` | Curated modern-province coverage pages, published maps only; links from catalog and sitemap | `src/routes/(editorial)/catalog/area/[slug]/` |
| `/catalog/series/[key]` | One survey: its coverage and every sheet it contains, held or not | `src/routes/(editorial)/catalog/series/[key]/` |
| `/catalog/series/[key]/[number]` | One sheet of a survey — including the ones the archive does not hold | `src/routes/(editorial)/catalog/series/[key]/[number]/` |
| `/catalog/institutions` | Holding institutions and source platforms, with published maps and external source records | `src/routes/(editorial)/catalog/institutions/` |
| `/catalog/institutions/cartomundi` | CartoMundi's Vietnam-related series and item-level Nakala rights evidence; `/catalog/cartomundi` redirects here | `src/routes/(editorial)/catalog/institutions/cartomundi/` |
| `/catalog/institutions/[slug]` | One holding institution: its series, published maps and external source records | `src/routes/(editorial)/catalog/institutions/[slug]/` |
| `/catalog/cartomundi/[id]` | One CartoMundi series: its sheets and item-level rights evidence | `src/routes/(editorial)/catalog/cartomundi/[id]/` |
| `/changelog` | Every release, from `releases.ts` | `src/routes/(editorial)/changelog/` |
| `/directory` | All pages, one list (the palette destinations) | `src/routes/(editorial)/directory/` |
| `/screens` | Every design-system component on one page; for whoever builds the UI | `src/routes/(editorial)/screens/` |
| `/login`, `/profile` | Sign in; the signed-in reader's own page (303 to `/login` without a session) | `src/routes/(editorial)/{login,profile}/` |
| `/contribute/georef` | Georeference via Allmaps Editor | `src/routes/(editorial)/contribute/georef/` |
| `/admin?tab=` | Bulk upload · Scout · Status · Stories | `src/lib/features/admin/` |

**Who can open what.** Every page is public except: `/profile` (303 to `/login`); `/explore?mode=studio`
and `?mode=story`, and every `/scan` mode, which need a session; the Validate tab of
`?mode=shapes` and `/admin?tab=scout|status|stories`, which need mod; `/admin?tab=bulk`, admin only.
**`/scan` has no default mode**: no mode, or one not in `$lib/core/scanModes.ts`, redirects to
`/catalog`, carrying `?map=` as `/catalog/<id>`.

**Redirects** are a table, not stub pages. `LEGACY_REDIRECTS` in `src/hooks.server.ts` issues a 301
with the query string preserved:

- `/view` → `/explore`
- `/annotate`, `/studio` → `/explore?mode=studio`
- `/create` → `/explore?mode=story`
- `/image`, `/catalog/series` → `/catalog`
- `/contribute/label`, `/contribute/digitalize` → `/scan?mode=prepare`
- `/contribute/trace` → `/scan?mode=shapes`
- `/contribute/review` → `/scan?mode=shapes&tab=validate`
- `/admin/bulk|scout|status` → `/admin?tab=…` (`/admin/status` included)

`LEGACY_PREFIXES` handles the two that carry an id rather than a fixed name:
`/map/<id>` → `/catalog/<id>` and `/place/<name>` → `/catalog/place/<name>`.
`withSearch()` joins an incoming query with `&`, since half the targets already
carry a `?mode=`.

There is no `/signup`, `/contribute/catalog`, `/hunt` or `/georef` route.

### Route groups

**Sept 2026 route merge: twenty-three pages became sixteen.** Modes are query
params, not routes. The grouping is **by shell**, not by verb — `/explore` is the
MapShell surface and `/scan` the ImageShell one — which is what lets the OL map,
the PMTiles source and the warped tiles stay warm across a mode change instead
of being torn down and rebuilt. **The tool is called Studio, and `?mode=annotate` is its live
alias.** `EXPLORE_MODE_ALIASES` in `core/routeModes.ts` (read by `resolveExploreMode()` in the dispatcher) maps it to `studio` rather than redirecting, because the
mode shipped under that name and it is still in share links and bookmarks; an unknown mode falls
through to browse, so an un-aliased old link would open the archive with no error anywhere —
`tests/smoke.spec.ts` asserts both spellings reach the Studio title. `/studio` and `/annotate` both
301 to `?mode=studio`. The directory is `features/annotate/` with `Annotate*` component names: the
rename to Studio is the URL and every visible label, not the files.

`src/hooks.server.ts` 301s every retired path
(`LEGACY_REDIRECTS` for the fixed ones, `LEGACY_PREFIXES` for `/map/<id>` and
`/place/<name>`); `withSearch()` joins with `&` because half the targets already
carry a `?mode=`.

**`/vi/<path>` is the Vietnamese address of `<path>`** (Sept 2026). The locale
came from a cookie and nothing else, which meant one URL served two languages —
and a crawler sends no cookie, so every request from Google resolved to English
and the whole Vietnamese side of the site had no address to index. `src/hooks.ts`
is the one line that fixes it: `reroute` strips the prefix so `/vi/about`
resolves to the `/about` route, and `hooks.server.ts` takes the path's locale
over the cookie's — an address has to mean the same thing to every reader. It is
universal, not server-only, or a client-side navigation would drop out of the
locale the reader arrived in. There are **no `[[lang]]` route directories**; the
route tree is untouched.

**Only `LOCALIZED_PATHS` (`$lib/core/i18n`) gets a `/vi` twin** — the eight
editorial pages, which is also exactly what `sitemap.xml` enumerates, so the two
read one list. Those carry an `hreflang` trio (`en`, `vi`, `x-default`) and two
sitemap entries each. Everything else — a map record, a place name, a blog post —
is a single document in its own language with only the chrome around it
translated, so a `/vi` twin would be the same page a second time: `/vi/catalog/<id>`
still renders, and **canonicalises back to the English URL**. That is the whole
duplicate-content story; do not add hreflang to a page with no real translation.

**Canonical and hreflang are the root layout's, once, for every page** —
`src/routes/+layout.svelte`, off `$page.url.pathname`. Only `/` had a canonical
before, so every other URL was its own duplicate across `?tab=`, `?map=` and
whatever a share appended. The origin is **pinned** (`SITE_ORIGIN` in
`$lib/core/site.ts`, the host `hooks.server.ts` 301s to, and what `sitemap.xml`
builds from too): taken from the request, a preview deploy at
`<hash>.vmabeta.pages.dev` declares itself canonical for production's content.
A page must not emit its own `<link rel="canonical">` — two is the same as none.

**Structured data** is `jsonLd()` (`$lib/core/utils/jsonLd.ts`) — `WebSite` on
`/`, `Map` on `/catalog/[id]`, `Place` on the gazetteer with the variant
spellings as `alternateName`. It escapes `<`, which `JSON.stringify` does not:
a map name containing `</script>` would otherwise close the tag and spill the
graph into the document as markup. That escaping is why the three `{@html}`
sites carry an eslint suppression rather than a rewrite. Null columns are
dropped, never sent as `""`. No `SearchAction`: `/catalog` takes no `?q=`, and
Google retired the sitelinks searchbox.

`/profile`, `/login` and `/admin` carry `<meta name="robots" content="noindex">`
— `robots.txt` allows everything, so a page that should not be indexed has to
say so itself.

- `(editorial)` — public pages with nav/footer: `/`, `/catalog`, `/catalog/[id]`,
  `/catalog/place/[name]`, `/about`, `/blog`, `/blog/[slug]`, `/directory`, `/screens`, `/profile`,
  `/login`, `/contribute`, `/contribute/georef`, `/admin`. There is no `/signup`.

**/catalog is one column, top down** (Sept 2026). It was a 260px `FacetRail` of counted chips beside
the results — a column that cost the table a third of the page and that nobody scrolled back up to
touch, which is why the table hid its Type and Collection columns under 800px while a third of the
width sat in a filter nobody had used. The rail is gone and **`FacetRail.svelte` is deleted**; the
three facets are the same `<details class="sb-more">` disclosure /explore wears (`ArchiveFilters`,
now with `showSearch` so the page's own `.sb-search.is-page` stays the only search box). The trade
is honest and worth knowing: the chips were multi-select and carried counts, the selects are one
value per facet and carry none — the three still combine.

**List or grid**, a `Tabs` strip in the results toolbar, remembered in `vma-catalog-view-v1`. The
grid is `MapCard` — the home page's card — which is why that component's `href` is now nullable:
**null makes it a `<button>` that dispatches `open`** instead of an anchor, so a grid card opens the
same detail drawer its table row does and a draft is not asked to link to a public page it does not
have. `<svelte:element>` picks the tag; the card is one component, not two.

`/directory` is the one page index: it renders `DESTINATIONS` from
`src/lib/features/shared/paletteDestinations.ts` — the same list the command palette offers, gated
by the same `destinationsFor(role, signedIn)` — grouped by each row's `group` field. Adding a page
means adding one row there, and it appears in the palette, on /directory and (if you want it there)
in the nav.

`/admin` is one console, tab chosen by `?tab=bulk|scout|status|stories` (bulk is the default); the pages live in `src/lib/features/admin/{BulkUploadPage,ScoutPage,StatusPage,StoryReviewPanel}.svelte` and each keeps its own role gate — bulk is admin-only, the others allow mod. Before the merge `/admin` itself was a 404, since only the three children existed.

`/contribute/georef` stays its own route on purpose: it is a public, server-rendered page with its
own title and meta description, listed in the sitemap's `STATIC_PATHS`, and it shares no runtime
with `/contribute`. Folding it in would cost an indexable page its identity to buy one fewer route.

`/catalog/place/[name]` is the **gazetteer page**: one server-rendered URL per attested place name
(the mig 067 view groups spellings), published maps only. `/screens` renders every design-system
component from fixtures — no database, use it to see what already exists before building a second
one. **Its claims are checked, not promised** (`tests/screens.spec.ts`): it said "everything in
`src/lib/ui/`" while rendering ten of seventeen, and counted "twenty … four … sixteen" cards over a
list of seven and seven. The test reads the source and fails when a `ui/` component is not named
there, when the card inventory names a selector its file no longer has, or when a retired element
class comes back. The counts are derived from the arrays now. A component that cannot be rendered
standalone (`AuthGate` starts a real sign-in, `SnapSheet` would cover the page) is listed with the
reason — being *named* is what the test asks for. `/admin?tab=status` is the archive's own review
queue: counts of maps, jobs and failures that used to need hand-run SQL, fed by
`GET /api/admin/status` (admin or mod).

`/catalog/[id]` is the **share page**: server-rendered from `+page.server.ts` so a crawler sees the
title, description and OG image without running JavaScript. Only `public`/`featured` maps resolve —
a draft id is a 404. Everything interactive is one click away at `/explore?map=<id>`. The OG image
is the map's `thumbnail` column, falling back to a derived `…/full/800,/0/default.jpg`; there is no
rendered preview, because the R2 worker is level0 behind a proxy and a IIIF size we know exists
beats one we hope for.
- `(app)` — full-screen tools with their own layout: `/explore`, `/scan`, `/trip/[id]`.

`/explore?mode=browse|studio|story` and `/scan?mode=prepare|text|shapes` are **dispatchers**: an `{#if}` chain of ~10 lines each, mounting one feature component. There is deliberately **no mode strip**: every mode's root fills the viewport from `position: fixed; inset: var(--nav-height) 0 0 0`, so a strip rendered as a sibling would sit *behind* the map, invisible and unclickable. NavBar is outside that fixed layer and does the switching. `?map=` is read from the URL by each mode rather than passed down, so it survives a mode change untouched.

`/trip/[id]` keeps its own URL on purpose: printed QR codes point at it.

Only the `(app)` tools set `ssr = false`; every `(editorial)` page server-renders, the home page
included — it stopped being an exception when its header stopped being a live map. **The home page's
data is server-rendered too** (`(editorial)/+page.server.ts`, Sept 2026): the featured sheets and
the published-map count come out of `adminClient()` with an explicit status filter, so the largest
thing on the page is in the HTML rather than arriving in `onMount` and shoving everything below it
down, and a crawler sees both the catalogue and a true count instead of the `39` fallback. What
stays on the client is what cannot be shared between readers — the signed-in reader's favorites
(`loadFavorites` fetches only the favourited rows, not the whole catalogue, which is what it used to
do to compute one number) and the thumbnails a map without a `thumbnail` column needs read out of
its annotation. One consequence, and the reason `src/routes/+layout.svelte` sets
`document.documentElement.dataset.hydrated` in `onMount`: a server-rendered nav is on screen and
looks clickable before any handler is attached, and a click in that window is dropped. A reader
rarely wins that race; a Playwright test under parallel load loses it every time, so
`tests/smoke.spec.ts` waits on `html[data-hydrated]` before it touches the nav or the hero field.

Code shared across the story lifecycle (markers, playback state, point ops) lives in
`src/lib/features/stories/shared/`. All app modes except the IIIF-canvas contribute tools share
MapShell + the map stores.

### Page registers

Four registers. The register decides the shell and the CSS.

#### Editorial

`/`, `/about`, `/blog`, `/blog/[slug]`, `/catalog`, `/contribute`, `/contribute/georef`, `/login`,
`/profile`, `/admin?tab=bulk`, `/admin?tab=scout`.

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

The shared classes (`.editorial-hero`, `.editorial-main`, `.section-card`, `.label-chip`,
`.text-highlight`, `.action-btn`, `.pill-btn`, `.badge-chip`, `.chip-*`) live in
`src/styles/components/editorial.css`, imported globally. **Do not redefine them per component** —
add a modifier class or extend the sheet. Page-specific CSS goes in `src/styles/pages/<page>.css`.

#### Geo-map tool

`/explore`, `/explore?mode=studio`, `/explore?mode=story`, `/trip/[id]`.

`src/lib/map/shell/MapWorkspace.svelte` is the shared base (§5). It composes `ToolLayout` +
`MapShell` + `LayerRenderer` + `MapModeOverlays`. Never create a second OL map outside `MapShell`.

#### IIIF-canvas tool

`/scan`, `/scan?mode=prepare`, `/scan?mode=text`, `/scan?mode=shapes`, plus `NeatlineEditor` inside
the admin modal.

These use `ImageShell` (static image extent, pixel coordinates) and the shared sidebar frame
`ToolSidebarShell` + `ToolMapPicker`. They do **not** use MapShell or the global map stores. CSS:
`src/styles/layouts/tool-page.css` + `src/styles/components/sidebar.css` — one sidebar vocabulary,
`.sb-*`. `components/tool-sidebar.css` held a second one (`.tool-*`) until Sept 2026; its last
speaker was `TriageSidebar` and the sheet is gone.

#### Admin

Admin work happens inside the editorial register. Map CRUD is a modal rendered by `/catalog`; bulk
and scout are ordinary editorial pages using `src/styles/pages/admin-bulk.css` and
`admin-scout.css`, with modal chrome in `src/styles/components/admin-modals.css`. The old
`layouts/admin.css` dashboard sheet was deleted — there is no `.dashboard` / `.top-bar` register any
more.

## 3. The map runtime

### MapShell — central map pattern

`src/lib/map/shell/MapShell.svelte` owns the single OpenLayers Map and is the entry point for all
geo-map pages. It mounts basemap tile layers (`basemapLayers.ts`) and exposes everything via Svelte
context (`src/lib/map/shell/context.ts`). Children call `getShellContext()` — never create a second
OL map. Basemap *visibility* is owned by `LayerRenderer`, not MapShell.

`src/lib/map/shell/LayerRenderer.svelte` is the single component that renders **all** map layers —
base (modern tile OR historical warped) and overlays — by subscribing to `layersStore`. In
side-by-side mode it hides overlays past index 0 so the left pane shows only the topmost;
`DualMapPane.svelte` independently renders overlays[1] in the right pane.

**One sync at a time, and only the newest one.** It holds two subscriptions, `layersStore` and
`layerStore`, and both fire synchronously on subscribe — so two passes started in the same tick and
both ran as far as the `await createWarpedLayer` inside, which is a dynamic import of 151 kB and
therefore a very long window. Neither saw the other's entry in `overlayInstances`, so both created a
layer, and the loser stayed attached to the OL map drawing forever. Measured on the 56-sheet
Indochine series restored from localStorage: **every annotation fetched four times, 276 requests and
712 kB** where 56 and 180 kB were wanted, plus three orphaned WebGL layers — and nothing in the
console to say so, because both passes succeeded. `queueSync` is the fix: one pass runs, everything
that arrives while it runs overwrites a single `pending` slot rather than queueing, so a slider
dragged through twenty values costs the first pass and one more with the value it stopped on. Any
new subscription that changes what is on the map goes through it, not straight to
`syncBase`/`syncOverlays`.

**Exception — `ImageShell.svelte`** (same dir): IIIF-canvas counterpart to MapShell for
pixel-coordinate work. Creates an OL map with a static image extent, exposes via
`getImageShellStore()` (`imageContext.ts`), binds `imgWidth`/`imgHeight`. Used by
`/scan?mode=prepare`, `?mode=text`, `?mode=shapes`, by `NeatlineEditor`, and by
`features/catalog/SheetZoom.svelte` on `/catalog/[id]` — none of them use MapShell or the global
stores. `SheetZoom` is the only one on an editorial page, so it **imports ImageShell dynamically on
the reader's click**: the record page is server-rendered for crawlers and most visits never zoom, so
OpenLayers stays out of its first paint. It is also the answer to "just link the full image" — a
level0 sheet 404s every size it did not mirror, `/full/max/` included, so the tiles are the only way
to see it whole.

**IIIF canvas coords:** OL uses `ol_y = -image_y` (y-flip). Tool components store bboxes image-space
(y-down) and flip when creating OL geometries. `src/lib/core/geo/rectUtils.ts` owns the flip helpers
(in `core` because `ImageShell` needs them too); `bboxHandles.ts` builds the shared handle features
and `createRectEditor` used by both `OcrBboxTool` and `TriageTool`. Polygon/line tools (`TraceTool`,
`ReviewTool`) flip inline.

### Map stores (`src/lib/map/stores/`)

- **layersStore** — single source of truth for what the map renders.
  `{ base: LayerRef, overlays: OverlayLayer[] }` where `base` is either `{ kind: 'basemap', key }`
  (`'g-streets' | 'g-archive' | 'g-satellite' | 'g-custom' | 'none'`) or
  `{ kind: 'historical', mapId, allmapsId, name?, thumbnail? }`. `overlays` is top-of-stack-first;
  each item has its own `opacity`, `visible`, and stable local `id`. There is no fixed overlay count limit. Hold and drag the three-dot layer menu to reorder, with a floating card and insertion marker; tapping opens actions and keyboard arrows also reorder. Order commits on release, and opacity sliders remain separate. Layer menus use the browser top layer and flip above cards near the viewport bottom.
  Persists to `localStorage` as `vma-layers-v1`. API: `setBase`, `addOverlay`, `removeOverlay`,
  `removeOverlayByMapId`, `setOpacity`, `setVisible`, `reorderOverlay`, `clearOverlays`,
  `isOverlay`; plus the free functions `toHistoricalRef(map)`, `toggleOverlayFor(map)`, `clamp01(n)`
  and the derived `topOverlay`.
- **mapStore** — `{ lng, lat, zoom, rotation, activeMapId, activeAllmapsId }`. Default: Saigon
  (106.70098, 10.77653) zoom 14. `activeMapId` is `maps.id` UUID and **is** mirrored from
  `layersStore.topOverlay` — the bridge is wired in `src/lib/map/shell/geoMapSetup.ts`
  (`topOverlay.subscribe → setActiveMap`). Kept for legacy callers: story playback, share links.
  `activeAllmapsId` holds the annotation source string — either a bare Allmaps image ID or a full
  annotation URL; `annotationUrlForSource()` (`src/lib/core/iiif/annotationUrl.ts`) accepts both.
- **layerStore** — per-shell view settings: `{ basemap, viewMode, lensRadius, customBaseUrl }`. View
  modes: `'overlay' | 'spy' | 'dual'` (UI labels: Stacked / Lens / Side-by-side). The side-by-side
  split is fixed at 50/50; `sideRatio` was removed.
- **urlStore** — bidirectional URL ↔ store sync. The hash carries **camera + basemap only**:
  `#@lat,lng,zoomz,rotationr&base=key`. The selected map lives in the **`?map=<id>` query param** —
  that is what /catalog, /scan?mode=prepare and every share link point at
  (`src/lib/features/explore/exploreUrl.ts`). A `map=` found in the hash is a legacy link and is
  migrated into `?map=` on init.

Other persisted keys (there is no `vma-viewer-state-v1`): `vma-scout-view-v1`, `vma-catalog-view-v1`
(list or grid), `vma-layers-v1`, `vma-story-player-v1`, `vma-story-library-v1`,
`vma-annotation-projects-v1`, `vma-bounds-cache-v2`, `vma-custom-base-url`, `vma-thumb-cache-v1`,
`vma-explore-{tour,welcome}-ack-v1`, `vma-create-saigon-seeded-v2`. Three are **gone** as of Sept
2026 and should not come back: `vma-explore-sidebar-ratios-v2` (the left rail is tabs, not a
splitter) and the two hero flags, `vma-hero-swept-v1` and `vma-hero-played-v1` — see the home-page
section. Debounced persistence lives in `src/lib/core/utils/persistence/createPersistedStore.ts`;
raw read/write in the sibling `storage.ts`.

### Command palette — the one search

`src/lib/features/shared/CommandPalette.svelte` is mounted once by the **root** layout, so it is on
every page in both route groups. ⌘K / Ctrl+K anywhere, `/` outside a form field, or the Search
button in `NavBar`. It searches four things through `/api/search`: **pages**
(`paletteDestinations.ts`, role-gated), **maps**, **places** (the gazetteer) and **labels** (which
open `/explore` at the spot).

Open state is `src/lib/core/utils/commandPalette.ts` — a bare boolean store in `core` rather than
beside the component, because `NavBar` is in `ui` and the layering rule bars `ui` from importing
`features`. `src/lib/core/utils/placeKey.ts` is the client-side twin of Postgres's `place_key()`
(mig 067), so a label on screen links straight to `/place/<slug>`; `tests/palette.spec.ts` guards
that the two agree.

### MapWorkspace contract

`src/lib/map/shell/MapWorkspace.svelte` is the unified base for geo-map modes. `/explore`,
`AnnotateMode` (the Studio) and `CreateMode` all build on it; new geo-map surfaces must use it rather than mounting
`MapShell` directly.

**Owns:** `ToolLayout` chrome (responsive workspace, sidebar resize, mobile drawer stack) ·
`MapShell` + `LayerRenderer` + `MapModeOverlays` · the map-list fetch and bounds backfill
(`useMapList`) · deriving `selectedMap` · forwarding view-mode changes to `layerStore` · the "Zoom
to Map" prompt.

**Does NOT own:** auth gates (the route page decides whether to render it) · mode-specific stores
(story player, annotation project, story library) · URL parameter parsing (the route page reads
params and seeds the stores).

**Props:** `mapStore` and `layerStore` (created by `createGeoMapStores()` in the route page — that
helper also wires the `topOverlay → mapStore.activeMapId` bridge), `supabase` (pass `null` to skip
auto-load), `dualPaneActive`, sidebar width/max props for both sidebars.

**Bind targets:** `shellMap`, `sidebarCollapsed`, `isMobile`, `isCompact`.

**Slots:** `sidebar`, `right-sidebar`, `map-children` (rendered inside MapShell's default slot —
GpsTracker, StoryMarkers, DrawTool, MapClickCapture, LegendPointsLayer), `dual-pane`, `map-overlay`,
`floating`, `mobile-layers`, `mobile-controls`, `mobile-browse`, `mobile-sidebar` (legacy
single-drawer fallback).

**Events:** `mapsloaded` only. Overlay load/error state is handled internally by `MapModeOverlays`;
there are no `overlayload*` events to wire.

**Z-index scale** (`src/styles/layouts/mode-shared.css`) — follow it:

| z | Element |
|---|---------|
| 0 | `.dual-container` |
| 5–30 | in-map elements; `.lens-overlay` is 30 |
| 50 | `.top-controls`, `.floating-controls` |
| 95 | `.explore-mode .resolving`, `.explore-mode .gps-error` |
| 100 | `.mobile-sidebar` |

### Map libraries

**Current default (2026-10-04): OpenStreetMap raster tiles**, using OpenLayers `OSM` with browser caching and visible attribution. The saved `g-streets` key now selects this global base, so existing readers also receive the coverage fix. The self-hosted regional extracts below remain available as `g-archive` (Archive). Series folders expose their individual sheets; info and legend can inspect any chosen sheet independently of stack order. Right-click coverage candidates use sheet bounds, rather than claiming an exact neatline hit. Layer-card Zoom to fits the viewport with a small margin and marks the selected boundary for three seconds; loaded Allmaps masks supply sheet edges, with bounds as the fallback.

**The optional Archive basemap is self-hosted.** `/explore`'s street basemap is one ~348 MB PMTiles archive spanning
Hanoi to the Mekong (Protomaps' daily OpenStreetMap build, bbox `105.0,8.5,108.5,22.0`, z0–15) in
the `vma-tiles` R2 bucket at key `basemap/vietnam-20260913.pmtiles`, served straight off the bucket
at `tiles.maparchive.vn/basemap/*` — an R2 custom domain, so byte-range reads are Cloudflare's to
cache and no longer invoke the worker (PMTiles is nothing but byte-range reads, and the worker could
not cache them: `cache.put()` rejects a 206). **The key carries the Protomaps build date on
purpose**: the domain sits behind a cache rule with a long edge TTL, so a rebuild written over the
same key would strand every reader on stale bytes. A new build is a new name and a new
`BASEMAP_PMTILES_URL`; delete the old object only after the new one is deployed and drawing. The
worker still answers `iiif.maparchive.vn/basemap/*` as a fallback. No API key, no quota, no
third-party usage policy. `src/lib/map/basemapStyle.ts` holds the source and a deliberately quiet
OpenLayers style over the Protomaps v4 schema (`earth`, `landcover`, `landuse`, `water`, `roads`,
`buildings`, `boundaries`, `places`); it carries the rebuild commands. Predecessors, both abandoned:
CARTO's keyless raster endpoint began stamping "API KEY REQUIRED" over every tile, and the OSM
Foundation's own tiles have a usage policy that does not cover a busy site. `PUBLIC_PROTOMAPS_KEY`
is gone from `.env.example` too — nothing read it and nothing needs it. The Saigon-only extract it
replaced (37 MB, bbox `106.3,10.3,107.1,11.2`) left 21 of 40 georeferenced maps — every Huế and
Hanoi sheet — on bare `earth` fill; `basemap/saigon.pmtiles` is still in the bucket, unreferenced.
Rebuild with `scripts/pmtiles_extract.sh vietnam 105.0,8.5,108.5,22.0 15 --upload`. **Two archives,
one style, one handoff at z8.** That extract stops at its own bbox, so zoomed out the neighbours
were simply missing and the tile edge around Vietnam read as a hole punched in the page.
`basemap/seasia-20260912.pmtiles` (28 MB, bbox `90,-13,132,32`, **z0–8**) is the same Protomaps
build clipped wide and shallow: 40° of neighbouring country costs gigabytes at z15 and nothing at
z8. `REGION_PMTILES_URL` draws for `zoom <= 8` and `BASEMAP_PMTILES_URL` for `zoom > 8` — OL's rule
is `minZoom < zoom <= maxZoom`, so exactly one is ever live; both drawing at once would declutter
Vietnam's labels twice and print them twice. Rebuild it with
`scripts/pmtiles_extract.sh seasia 90,-13,132,32 8 --upload`. Both layers also paint `C.water` as
their OL layer `background`, so anywhere past *either* bbox (west of 105.0° at z12, say) reads as
sea rather than as the page's own black.

**The 1960s topographic sheet (Series L7014) is no longer a second PMTiles archive.** The
pre-tiled mosaic, `map/rasterSeries.ts`, `L7014_PMTILES_URL` and the raster renderer were retired
2026-10-03 in `598fbe1b`. All 510 sheets are `maps` rows now and L7014 is an ordinary IIIF series,
offered and warped like any other (below). The mosaic's build and datum traps are recorded in
`scripts/l7014/README.md`.

**A series uses coverage at overview scales and live warping up close.** One `SeriesRef` owns
one renderer controller (`seriesRenderer.ts`), resolving its source identities and bounds through
`fetchSeriesSheets`. A dense overview draws sheet bounds in one vector feature and creates no
Allmaps renderer or image requests. The notice explains that scans appear on zoom-in; these
rectangles are index bounds, not warped neatlines. No pre-tiled mosaic or additional database
migration is required for this rendering change.

`seriesRenderPolicy.ts` shares an annotation-source admission budget among enabled series that
intersect the viewport: 24 for a map narrower than 900 CSS pixels, 64 otherwise. Every visible
source, including ones with unknown bounds, must fit its allocation before detail is admitted.
Otherwise the complete view stays in coverage mode; imagery is never silently truncated.
One size rule applies to every series, whatever its sheet count: when the median visible sheet
is narrower than 20% of the viewport (`MIN_SHEET_VIEW_SHARE`, about 200 px on a 1000 px map), the
series stays in coverage mode. A 44-sheet series and a 5,000-sheet one therefore both show
outlines at a whole-series view. Nearby padding fills only unused capacity. Hysteresis prevents repeated mode changes at the
boundary. Standalone explicitly selected sheets are separate from this series budget, and source
count is not an exact RAM-byte budget.

On detail pans, `retainSeriesSources` removes previous sources outside the current allocation,
including their GL resources, and rejects queued/late results no longer admitted. Annotation
requests share a six-request queue across series. Zooming back out, hiding, or removing a series
detaches its warped layer and clears loaded maps, tile caches and sprite caches immediately;
renderer disposal waits only for non-abortable annotation requests to settle. A new detail view
loads its nearby sheets again. `LayerRenderer` releases its map listeners on teardown, and the
secondary comparison pane creates a warped layer only while it has a visible selected sheet.
**Counting what arrived is the part that lies**: `addGeoreferenceAnnotationByUrl` resolves with
`(string | Error)[]`, one entry per map in the annotation, so a sheet that fails to parse comes back
*inside a fulfilled promise* and only a failed fetch rejects — count rejections alone and a
half-drawn series reports itself complete, which looks exactly like a survey with gaps in it.
`tests/series-load.spec.ts` pins both halves as well as admission, eviction and late disposal.
`tests/series-render-policy.spec.ts` pins density, shared allocations and hysteresis. The real
renderer browser fixture in `tests/browser/series-overview.spec.ts` uses 5,000 mocked sheets to
check that overview requests no scans and repeated detail/overview transitions release canvases.

**The series list is a database view, not a constant** (migration 082). `map_series` is one row per
`maps.collection` that is a survey, and `/explore` renders whatever it returns — so a new series is
a matter of ingesting sheets, not of editing a file and deploying. Three rules decide what
qualifies, all of them read off the data rather than declared: the sheets carry a
**`maps.sheet_number`** (which is what separates a survey from `Vietnam Map Archive`, the
archive's catch-all bucket of 36 unrelated sheets at every scale — stacking those on one another is
noise, and on the corpus the test draws the line exactly right: 62/62 Cartomundi rows and 15/15
L7014 rows carry a number, 0/36 in the bucket do); there is **more than one** of them georeferenced
with a `bbox`; and **this reader may see them**. `bounds` is the union of the sheets' own boxes and
`sheets` counts only the visible ones — **distinct cells, not rows** (migration 084): three of the
Indochine 1:25,000's cells are held in two editions each, so counting rows offered "56 sheets" over
53, and two printings of a single sheet could qualify as a series on their own. 084 also left-joins
`series_cells` (083) for `survey_sheets`, so the row reads "9 of 627 sheets" — what the survey
contains, which `maps` cannot say because it holds only successes. What the view deliberately does
**not** expose is how many cells reach a reader by *any* route (L7014's mosaic pixels counted
until they were retired): the /explore row is a control, and it must say what it draws, not what
the archive holds. The gate is spelled out in the view body rather than left to `security_invoker` — 081's
lesson repeated, since a service-client caller bypasses RLS. Two consequences worth knowing: a
wholly-draft survey has **no row at all** for an anonymous reader, which is why there is no `draft`
flag in the UI (that was a fact about the data kept in the code, and it went stale the moment a
sheet was published); and because the count is of rows *this* reader can see, a survey with one
published sheet is not offered publicly at all — it appears when a second is published.
`fetchMapSeries` reads it, `tests/write.spec.ts` asserts both halves of the gate against real
Postgres. Every series is a database series now: the L7014 mosaic that used
to be hardcoded beside them was retired on 2026-10-03 (`598fbe1b`). `buildSeriesRows`
(`features/explore/seriesRows.ts`, `tests/series-rows.spec.ts`) turns each `map_series` row into
**one row that is one layer** — a `SeriesRef` whose single part is the live-warped sheets — with one
name, one opacity slider, one eye, one × and one of the ten stack slots. A stack saved earlier
still holds the old rows: `readOverlayRef` drops a saved `raster` part, and `foldLegacyOverlays`
folds the rest back into one row per survey and renames the retired `l7014` key (both in
`map/stores/overlayKind.ts`, pinned by `tests/layer-stack.spec.ts`).

**OpenLayers is the only map engine** (MapShell + ImageShell); `@allmaps/openlayers` warps
historical tiles. MapLibre GL was removed (Aug 2026) along with `@allmaps/maplibre`,
`@protomaps/basemaps` and `ol-mapbox-style`.

**`@allmaps/openlayers` is loaded on demand, and `createWarpedLayer` is `async` for that reason
alone.** It has exactly one runtime importer in the tree — `createWarpedLayer` in
`src/lib/map/shell/warpedOverlay.ts`; every other mention (`LayerRenderer`, `DualMapPane`,
`HeroSequence`, `warp.ts`) takes the type, which erases. Behind that one import sit
`@allmaps/render`, `@allmaps/transform` and proj4: **151 kB gzipped, more than OpenLayers itself**,
which a static import put in front of /explore's basemap whether or not the visitor ever put a
historical sheet on the map. It is an `await import()` now, so it arrives with the first sheet and
/explore's first load is ~321 kB gzipped instead of ~472 kB. The cost is that every caller awaits,
and `DualMapPane`'s `onMount` had to become `async` and re-check `secondaryMap` after the await —
the pane can now be torn down inside a round trip that did not exist before. Keep any new importer
type-only, or the chunk goes back to being eager.

## 4. Surfaces

### /explore sidebar + mobile pattern

Same components drive both viewports. The reusable panels are in `src/lib/features/shared/` (moved
out of `catalog/` in Sept 2026, when four features turned out to import them):

- **`ArchiveBrowser.svelte`** + **`ArchiveMapRows.svelte`** — the archive browser (shared catalog
  engine + facets) and its rows. They were `explore/Explore{ArchiveBrowser,MapRows}` until Sept
  2026, when the /scan rail needed the same picker. **`ArchiveMapRows` *is* the catalog table with
  its columns reduced** — the same `DataTable`, header and row rules, minus the four a 380px rail
  cannot carry (thumbnail, Area, Collection, Status), and **the thumbnail is the pick control**: the
  picture of the sheet is the button that puts it on the map, with a check over it when it is on. A
  plus sign says a row can be added; the scan says which sheet is being added. Thumbnails go through
  `atWidth()` (`$lib/core/iiif/thumbUrl.ts`) — the stored `maps.thumbnail` column is 800px and the
  cell is 48, which over 39 rows is the same bill `FeaturedSheet` already pays 400 to avoid; that
  helper was private to `FeaturedSheet` until the third caller (this list and the /catalog table's
  own 96px cell) appeared. It was a hand-built `<ul>` of bordered buttons, beside a *second*
  hand-built `<ul>` (`CatalogTableCompact`) doing the same job in the catalog's own sidebar, with no
  two details alike — year 1rem extrabold against 0.82rem bold, the pick control a 32px circle
  against a `.btn.is-xs`. `CatalogTableCompact` is **deleted**; `CatalogTable`'s `compact` branch
  renders this. `rowAction` is the one thing the two callers disagree about: `toggle` (the default)
  means the row is a layer, `open` means it is a record and the layer toggle is the separate button
  in the pick column. `activeIds` switches `toggle` from `layersStore` to the caller's own
  selection, which makes it a radio — what a /scan tool (one open sheet, no layer stack) needs.
  `badges` puts caller-supplied text where the type chip goes — the pass progress on
  /scan?mode=prepare, the pending count on `?mode=shapes&tab=validate` — because the catalog rows
  carry neither. The three narrow columns are `width: 1%` + `nowrap` (shrink-to-fit), so the title
  keeps everything left over.
- **`LayerStackPanel.svelte`** — the layer stack. **Each row is two lines**: year + name + actions
  on top, a native `<input type="range">` for opacity underneath. It was one line with the whole row
  as a pointer-drag surface until Sept 2026 — which cost every sheet its name to an ellipsis and
  loaded the row with three gestures at once. The **name is the zoom-to-overlay button** now, so
  there is no press-vs-drag threshold to tune. Reorder via ▲/▼. Actions are an **eye toggle**
  (inline SVG, crossed out when hidden → `layersStore.setVisible`; the row dims but keeps its name,
  slider and %, since it is still the control — `◉`/`◌` said nothing and a `title` is no help on
  touch) and **Remove (×)**. In side-by-side the top 2 get **Top** / **Bottom** badges (mobile dual
  splits vertically).
- **`TopSheetActions.svelte`** — the way out of the viewer for the sheet on top of the stack:
  `⬡ Traced` (the footprints toggle, whose state `ExplorePage` owns), Scan, Annotate, and Share for
  a published map only. It lives **inside the right rail's Info tab**, under the sheet's name — it
  sat above the tab strip for one iteration, where it pushed the tabs down and belonged to no tab.
  It prints **no sheet name** of its own for the same reason the Info tab has **no "Catalogue page"
  link**: the name is the `<h3>` right above it, and that link is this strip's Share. It sat at the
  foot of the layer stack in the **left** rail until Sept 2026; it now sits above the tab strip in
  `ExploreRightSidebar`, which is already the panel titled *This sheet*. Mobile has no right rail,
  so `ExplorePage` renders it under `LayerStackPanel` in the `mobile-layers` drawer.
- **`LayerControlsPanel.svelte`** — Display mode (Stacked / Lens / Side-by-side) · Base map (Maps /
  Satellite / None) · "My location" GPS toggle, gated by `showGps` · place search, which is now
  **`PlaceSearchBar.svelte`** beside it and gated by `showSearch` (both default true). Single source
  of GPS on both viewports.
- **`PlaceSearchBar.svelte`** — the Nominatim place search: field, clear button and the
  `LocationSearch` results list. Inline in `LayerControlsPanel` until Sept 2026, when /explore's
  right rail wanted one at its crown; `.mo-search` has since been deleted from `components/modal.css`, so the
  component carries its own scoped CSS.
- **`CatalogSidebarPanel.svelte`** (`features/catalog/shared/`) — compact catalog browser used by
  tool pages other than /explore. It composes the whole catalog feature, so it is catalog's public
  entry point, not a shared primitive.
- **`CatalogTable.svelte`** (`features/catalog/`) — the full table; `compact` delegates to
  `ArchiveMapRows` (above), which is this table with four columns dropped. Year and Area row chips
  are **not** clickable filters.

**`/explore` is two rails, and the split is by subject** (Sept 2026 — it was one rail stacking
Browse → Layers → Controls at 40/40/20).

`src/lib/features/explore/ExploreSidebar.svelte` is the **left** rail, the archive: one filter bar
over a `.sb-pill` strip of **two tabs**, `All` and `Picked N`, with a single `SidebarCard` swapping
its body. It was two stacked cards with a draggable splitter and ratios in
`vma-explore-sidebar-ratios-v2` until Sept 2026 — the splitter, its handlers and the key are all
gone. Its All pane is `ExploreBrowsePanel.svelte` (which keeps both of its own modes: the "N maps
cover this spot" location list, and the expanded full-archive view), not `CatalogSidebarPanel`.

**The rail owns the search engine**, so both tabs answer to one query: All hands it to
`ArchiveBrowser`, and Picked narrows the layer stack to the sheets the query still matches, through
`LayerStackPanel`'s `filterIds`. With nothing typed and no facet chosen, `filterIds` is null and
Picked shows the whole stack. `ArchiveFilters.svelte` (`features/shared/`) is the bar itself —
search box, facets, reset — extracted so the rail and `ArchiveBrowser` render the same one;
`ArchiveBrowser` takes `search` (default null → it creates its own) and `showFilters` (default
true), so `ToolMapPicker` and every other caller are unchanged.

**The three facets are one native `<details class="sb-more">`**, its summary reading `FILTERS · 2`.
They stay independently combinable: a single `<select>` with `<optgroup>`s would be literally one
element but would allow only one facet at a time.

**Arriving with a stack selects Picked, once** — a share link's `?map=`, or the stack restored from
`layersStore`. It waits for the first non-empty reading rather than checking in `onMount`, because
the page resolves `?map=` asynchronously and the stack does not exist yet when the rail mounts.
Three things must not trigger it: the reader adding a sheet themselves (the rows are tap-to-add /
tap-again-to-remove, so switching away pulls the list out from under the second tap), the tour, and
anything after the first switch. **`tab` is bound by `ExplorePage`** because the tour opens the pane
each of its steps describes, and `tourActive` is what makes the tour win — without it the two
assignments raced and `tests/smoke.spec.ts:125` passed or failed on whichever landed last.

`src/lib/features/explore/ExploreRightSidebar.svelte` is the **right** rail, and it **mirrors
`ExploreSidebar` part for part, sharing the CSS rather than copying it**: crown, one search bar, a
`.sb-pill` tab strip, one `SidebarCard` that swaps its body. The frame is `.sb-rail` /
`.sb-rail-filters` / `.sb-rail-tabs` / `.sb-rail-body` in `components/sidebar.css`
(`.sb-rail.is-right` flips the border to the left edge) and the crown's bar is `.sb-search` there
too. Both rails carried four identical scoped rules each until Sept 2026 — which is how the right
one ended up with a modal's `.mo-search.is-compact` at a visibly different height from the left
one's own `.search`, and how the pills sat 2.4px off the search box's left edge in both. Neither
rail imports `layouts/tool-page.css`, so the frame lives in the always-on sheet instead of beside
`.panel`. It rides `ToolLayout`'s `right-sidebar` slot, so drag-resize and collapse come free. The
left rail is the archive; this one is the sheet on top of the stack.

Top is **`PlaceSearchBar`** (`features/shared/`) — the Nominatim field, its clear button and the
results list, extracted from `LayerControlsPanel` so both rails could hold one. It sits at the crown
because it is how a reader gets anywhere on the map, the same job the left rail's `ArchiveFilters`
does for the archive. Under it sits **My location** as a `.sb-more-btn` — the bare-toggle twin of
`.sb-more > summary`, so it wears the left rail's `FILTERS` face in the same slot under the same
bar; `.is-on` tracks GPS with the accent ink rather than a fill, since a filled pill there would
outweigh the search box. Both are crown controls because both are how a reader gets anywhere on the
map. `LayerControlsPanel` therefore takes **`showSearch={false}` and `showGps={false}`** here (both
default true, so the mobile Controls drawer keeps its own of each), or the Control tab would render
a second of each.

Three tabs: **Info** (default — the sheet's name, `TopSheetActions`, its catalogue metadata, and a
Holding-library link when `source_url` exists), **Legend** (the numbered-legend index off
`/api/maps/[id]/legend-points`, each row a place to fly to, plus the points toggle — the same GET
`LegendPointsLayer` makes, so an open tab fetches it twice) and **Control** (`LayerControlsPanel`,
with `legendPointsAvailable={false}` because Legend carries that toggle beside the list it switches
on). `padded={tab !== 'control'}` — the controls panel owns its own padding. `data-tour="controls"`
stays on the `<aside>` so the tour still lands on it.

Mobile is untouched — `ExplorePage` fills its own `mobile-*` drawers, so `splitRailsOnMobile` never
fires and Legend and Info are desktop-only.

Mobile (`< 900px`): `ToolLayout.svelte` shows a full-bleed map with a horizontal 3-tab bottom bar —
Layers · Controls · Browse — backed by `MobileDrawerStack.svelte`, one shared drawer body sliding
up. Slots: `mobile-layers`, `mobile-controls`, `mobile-browse`; `mobile-sidebar` is the legacy
single-drawer fallback other tool pages still use. A tool that fills only `sidebar` gets **that same
slot** in the mobile drawer, with `let:compact` true — one component instance, since the desktop
rail and the drawer are never mounted together. `?mode=prepare` and `?mode=shapes` did carry two
copies of their sidebar (39 and 20 lines of duplicated wiring) until Sept 2026. Desktop slots:
`sidebar`, `right-sidebar`, `floating`, default.

In dual mode, OL attribution + scale live on the **secondary** pane (right on desktop, bottom on
mobile) — hidden on the primary via CSS. Map-bounds resolution goes through `resolveBounds()` in
`src/lib/core/geo/mapBounds.ts` (`bounds → bbox → annotation_url → allmaps_id`) so R2-mirrored maps
and `?map=<id>` deep-links both zoom correctly.

`src/lib/features/explore/GpsDot.svelte` draws **where the reader is** — a headless OL point layer
(halo at `inkAlpha(INK.blue, 0.18)` under a hard dot ringed in `INK.paper`, `zIndex` 55, static
because a position is not an event). `GpsTracker` emitted fixes and `ExplorePage` moved the camera
to the first one and worked out which sheets covered it, but nothing drew the spot, so "My location"
answered *where am I* with a camera move and no marker. `FocusPulse` beside it (`zIndex` 60) now
also fires on a **place pick**: `handlePickLocation` sets `focusPoint`, so a Nominatim hit and a
legend row both get the ring instead of moving the camera and leaving the reader to guess which of
the hundred things under the crosshair they asked for.

### The home page

**The home page's header is two still images with a slider between them, and the live map is a
section further down** (Sept 2026). It used to be the header: every visitor paid for OpenLayers,
ol-pmtiles, Allmaps and ~390 kB of basemap to look at scenery they had not asked for. Measured on
the production build at 1440×900, the front page at rest is now **63 requests / ~0.9 MB**; scrolling
to the demo adds **71 requests and 1.36 MB** on top, which is exactly what a reader who never
scrolls no longer spends.

`static/images/hero-now.webp` and `hero-1882.webp` (159 kB and 165 kB, both 1600×900) are the
header: **Esri satellite imagery** underneath, the composed 1882 frame over it, and the Today/1882
slider in the masthead column driving the top one's opacity. Two `<img>`s and a `bind:value` — no
map, and the whole gesture the archive is about works with the page's first paint. The 1882 layer is
the LCP element and takes `fetchpriority="high"`; the imagery underneath takes `low` and an empty
`alt`, being the same picture in another state rather than a second picture. Because that imagery is
on screen whenever the slider is off the 1882 end, `.hero-credit` carries its attribution in the
corner — a still image has no OL attribution control to do it. Each still is served as a two-cut
`srcset` at `sizes="100vw"` — the `-800.webp` twin beside it (72 kB and 54 kB) is what a phone
takes, since the header is full-bleed and a 390px screen was being handed the whole 1600px frame for
a third of the page's weight at rest. Both cuts come out of `gen-hero-still.mjs`; regenerate them
together.

**The base is satellite, not the vector streets** — `BASEMAP` in `HeroMap.svelte`, which is also
what the live demo now draws. The streets style is deliberately quiet and at this zoom draws roads,
water and nothing else, so the "today" end of the fade was a pale diagram beside a hand-coloured
survey and the comparison the hero exists to make had one side missing. `HeroMap` mounts no
`LayerRenderer` (that one is driven by the persisted `layersStore`, which a decorative map must not
touch) and `createBasemapLayers` leaves visibility at its construction default, so the choice is
applied by hand with `setVisibleBasemap` — moved out of `LayerRenderer` into `basemapLayers.ts` when
the second caller appeared.

**The header keeps showing what it does until someone takes the control.** `sweepHeroSlider()` on
the page waits 1.1 s, then cycles `heroSheet` on rAF: 1.4 s down to 0.12, a 900 ms dwell on the
imagery, 1.4 s back up, a 900 ms dwell on the sheet, repeat. The easing is `easeInOutCubic`, the
curve the annotate-mode timeline already uses, so neither turn is a corner; `SWEEP_HOLD_MS` is the
dwell, and without it the thing is a metronome and the two states it exists to compare never sit
still long enough to be read.

A slider nobody drags is a slider nobody knows is there, and this one is the archive's whole idea.
It ran **once a tab** behind `vma-hero-swept-v1`, then **once per load**; both are gone (Sept 2026).
The flag meant anyone who had already opened the front page in that tab never saw the gesture again
— which is everyone testing it — and once-per-load meant anyone who looked away for four seconds
missed it with no way to ask again. **Looping was requested explicitly, twice**, against the note
that used to sit here saying not to; do not restore a single pass on the strength of a comment.

Three parts are not up for simplification: it stops dead on the reader's first `pointerdown` or
`keydown` on the slider and never restarts (a control that animates under a finger is fighting the
person using it, and that first touch is the whole reason the loop exists); it never runs under
`prefers-reduced-motion`; and `onMount(sweepHeroSlider)` returns the teardown that clears both the
timer and the rAF, which matters more now the loop is unbounded. On WCAG 2.2.2 — moving content past
five seconds needs a way to stop it — the slider *is* that mechanism: visible, obviously grabbable,
and touching it ends the motion for good.

Neither is a hand-made crop — `scripts/gen/gen-hero-still.mjs` drives the real demo section in
Playwright and photographs it twice, so the two ends of the slider line up to the pixel (the 1882
one doubles as the section's own poster while OL loads). They no longer match the live map below:
the section was refitted to frame the whole sheet and **the header was deliberately left on the
earlier pinned close-up**, so re-running the script replaces it with the wide view — a decision, not
a repair. The two passes are separate page loads, and the `hero-now` one **aborts the annotation
request on purpose**: `HeroSequence.start()` catches a failed overlay by parking at stage 0 and
returning, so the sheet, footprints and labels never arrive and there is no 1.5-second window to
race between "the basemap painted" and "the sheet starts fading in". **Re-run it whenever
`HERO_SHEET` changes or the fabric is regenerated**, or the header advertises a frame the demo no
longer opens on. Each shot is written twice, at 1600 and 800, and `HeroDemo` is handed the same
`srcset` so a phone reuses the small cut rather than fetching the large one for the poster. It needs
`vips` and `cwebp`, a dev server (or `HERO_BASE_URL`), and it hides the sticky `.top-nav` and OL's
controls before shooting — the nav is sticky, so Playwright photographs it along with the map
otherwise.

`src/lib/features/explore/HeroDemo.svelte` is the section (`#how-it-works`, between the catalog and
the band). **What plays by default is a clip, not the map** (Sept 2026).
`scripts/gen/gen-hero-video.mjs` records the real section, so the clip is the same four beats — 699 kB
at 1200px, 298 kB at 800px, against ~179 kB of JavaScript plus ~390 kB of basemap before OL draws a
tile. It is cheaper than the thing it stands in for **and** it moves, which the frozen still did
not: a reader who never got OpenLayers used to see one frame of the end state and none of the sheet
arriving, which is the one thing the section exists to show. The live map is the **upgrade**, behind
a *Try it yourself* button, because the clip cannot do the two things the copy promises — the
Today/1882 slider and ⌘-scroll zoom. That button waits for the clip's `ended`, for the same reason
the slider waits for `settled`: the clip burns its own captions along the bottom of the frame and
the button sits in that slot, so offering it mid-clip put it on top of “46 plots and waterways,
traced by hand”. A reader who never gets a clip at all — reduced motion, or metered — is offered it
immediately instead, or the readers most likely to want a lighter page would lose the only route to
the map. `tests/smoke.spec.ts` pins both: no canvas before the click, and the button hidden while
the clip runs. Four gates now: the poster is the section's own content; `prefers-reduced-motion` or
`isMeteredConnection()` (`$lib/core/utils/connection.ts`) stops there; otherwise an
`IntersectionObserver` fetches the clip **400px** early; and `HeroMap.svelte` is dynamically
imported only on the click. The clip is held at frame 0 until a second observer at the real viewport
edge fires, and `play()` lives in a `$:` block rather than in that observer — both can fire in the
same tick, and then `bind:this` has not run and the call reached `undefined`.

The poster is **frame 0 of the clip**, written by the same script, so the still and the moving
picture cannot disagree. It used to be `hero-1882.webp`, which is the header's pinned close-up while
this section frames the whole sheet — and nothing ever took it down, so an enlarged 1882 sheet sat
behind the live map, showing through every patch whose basemap tile had not landed. It now comes
down on either `rolling` (the clip's own `playing` event) or `HeroMap`'s `painted` prop, which it
sets from OpenLayers' `rendercomplete` — the first frame with every tile actually drawn.
`rendercomplete` rather than a timer: a slow connection keeps its poster exactly as long as it needs
one, and if neither event comes — no WebGL, tiles refused, a metered reader — the poster stays,
which is right in all three cases. **Not a GIF:** the same nine seconds at 800px and 10 fps is 12.1
MB as a GIF, 33× the H.264 of the same width. That margin is a fixed distance, not `100%` of the
viewport: at one viewport of lead the section already intersected on load on a laptop, which is the
entire cost the component exists to avoid. The stage is `aspect-ratio: 16/9` so nothing shifts when
either the image or the map arrives.

`HeroMap.svelte` mounts its own `MapShell` on an idle callback and plays four beats — the modern
city, the 1882 Plan Cadastral warping over it, its traced footprints, its validated OCR labels. It
creates **its own** map and layer stores rather than the persisted globals; one that wrote to
`layersStore` would rearrange the reader's /explore layer stack. `HeroSequence.svelte` beside it
drives the cues on `setTimeout` and the fades on rAF (they shared one rAF loop until a throttled tab
delayed the last cue). `HERO_SHEET` on the page carries `id` and a `view` of `{ bbox, rotation }`,
and `HeroMap.fitSheet` derives the zoom from the stage's own size — one number cannot be right on a
phone and a 27-inch screen at once. The `bbox` is **not** `maps.bbox`: that column is the
georeferenced *mask*, while the layer draws the whole scan (paper edges, shelfmark, legend), which
for this sheet runs 830 m further east — fit the column and the bottom is cropped. These are the
scan's corners `(0,0)…(width,height)` through the annotation's transform. `rotation` holds the sheet
square: this scan's x-axis runs north, so it is essentially a quarter turn, and /explore is where to
find it for another sheet (⌘/ctrl-drag, then read `r` off `#@<lat>,<lng>,<zoom>z,<rotation>r`).
`FIT_PAD` leaves 6% of the sheet's own size as margin on each side. The annotation URL is derived
from `id` inside `HeroMap`, so changing which sheet plays is one uuid; the sheet has to be
georeferenced **and** mirrored, since the demo plays our own copy. The sheet is hardcoded because it
is the only one carrying all three layers. The Today/1882 opacity slider is `HeroDemo`'s, which is
why `overlayOpacity` and `settled` are bindable props of `HeroMap` rather than its own state;
⌘/ctrl-wheel zooms, there are no zoom buttons.

Three more things keep the live map cheap once it does load. `MapShell` takes a `pixelRatio` prop
and the demo pins it to **1** (at a Retina screen's own ratio OL asks for about four times the
tiles). **The four beats play on every visit** — a `vma-hero-played-v1` session flag used to compose
the final frame at once on a reload, and it is gone (Sept 2026) for the same reason as the sweep's
flag: it handed a returning reader the conclusion with the reasoning cut out. Removing it left
`HeroMap`'s `immediate` dead, so that and the `HeroSequence` prop it fed are deleted too, their
branches folded into the `reduced` check that was always the real one — `prefers-reduced-motion`
still composes the frame at once, and `HeroSequence` owns that check itself. And **the fabric is
frozen**: `heroFabric.ts` is generated by `scripts/gen/gen-hero-fabric.mjs` and carries the sheet's
footprints and labels as a module (5.9 kB gzipped) instead of a `/api/export/footprints` call and a
Supabase query on every visit — `FootprintsLayer` takes it through a `featureCollection` prop and
skips both the fetch and the un-warped filter the generator already applied, and the third and
fourth captions quote `HERO_FOOTPRINT_COUNT` / `HERO_LABEL_COUNT` so the copy cannot drift from what
is drawn. `tests/hero-fabric.spec.ts` is what fails if a regeneration comes back empty or in pixel
coordinates.

`FeaturedSheet` asks IIIF for the picker tiles at `/full/400,/`, not the stored `thumbnail` column's
800 — the tiles are 132px wide, and five 800s were 715 kB of front page for five thumbnails.
`atWidth()` there is the one place a IIIF size is rewritten; the plate still takes 1200.

### Contribute tools

**Shared (`src/lib/features/contribute/shared/`):** `ScanLeftRail.svelte` — **the left rail every
`/scan` mode carries**: which sheet, what is drawn over it, and how far to dim the paper. All four
modes mount it, so a mode change swaps the right-hand panel instead of rebuilding the page. It
composes `ToolSidebarShell.svelte` (the `<aside class="panel">` frame, whose crown is `.sb-bar` —
the same one `ExploreSidebar` wears;
`.panel-header`/`.panel-mode-label`/`.collapse-btn`/`.home-link` were a second copy of it and are
gone from `tool-page.css`) over two `SidebarCard`s titled **Browse the archive** and **My layers**,
the same as /explore's rail. The picker is `ToolMapPicker.svelte`, which renders `ArchiveBrowser` —
search box, three facet dropdowns, count, rows. It rendered `SearchMapsTab` until Sept 2026 — that
whole `features/shared/search/` cluster (`MapSearchBar` → `SearchPanel` → two tabs) plus its
412-line `search-panel.css` is **deleted**: its callers were ViewMode, CreateMode and the studio's
floating bar, the first two merged away in the route consolidation, and nothing outside the cluster
ever imported it. `ToolMapPicker` loads every georeferenced sheet by default; a `maps` prop
overrides that list, which is how `?mode=shapes&tab=validate` shows its queue (badged with its
pending count) and `?mode=inspect` keeps the *un*georeferenced scans `fetchLabelMaps` filters out.
The rail also carries the **mode switcher** in its footer, gated by its `mode` prop: unset — which
is how `?mode=inspect` mounts it — there is no switcher, because inspect is unlisted (its public job
moved to `/catalog/[id]` in Sept 2026; what is left is the plain look at a *draft* scan) and the
other three want a session. The tab strip every `/scan` rail wears is `$lib/ui/Tabs.svelte`
(`tone="rail"`), links or buttons depending on whether a row carries an `href`. Also
`ToolPanelHeader.svelte`, `EmptyPanel.svelte`,
`CliCommandBlock.svelte` (copy-paste CLI block), `bboxHandles.ts` (flip helpers live in
`$lib/core/geo/rectUtils.ts`), `iiifSource.ts` (`resolveMapIiifInfoUrl`). Data clients:
`src/lib/features/contribute/shared/ocrApi.ts` and `src/lib/features/contribute/pipelineApi.ts`.
Category/colour/status constants have one home: `src/lib/features/contribute/shared/constants.ts`
(with `types.ts` beside it — all three moved from `ocr/` because `MapEditPipelineTab` and
`LabelHits` import them). Footprint geometry types live in `src/lib/data/maps/footprintTypes.ts`.

**Prepare (`/scan?mode=prepare`) and Text (`?mode=text`)** — the two halves of getting words off a
sheet, **one component** (`DigitalizePage.svelte`) mounted for both: the dispatcher's `{#if}` covers
the pair, so moving between them is a prop change and the OL map, the IIIF tile source and the open
sheet all stay warm. Two page components would rebuild the canvas every time an operator checked
their crop. The switcher is the **left rail's footer** (`Tabs` in `ScanLeftRail`, three
links), which is where it belongs — beside the sheet list, which also does not change with the mode.

- **Prepare**: `TriageTool.svelte` (neatline rect + tile priority grid; click cycles normal → low-res amber → skip gray), `RegionsTool.svelte` (the layout regions — one labelled rect per part of the sheet, click to select, drag to correct; a dashed edge is the model's proposal and a solid one a person's) and `TriageSidebar.svelte`, whose five steps are **Layout · Neatline · Tiles · Save triage · Run OCR** — now a *check* rather than a build: the `layout` job adopts its own `main_map` region as `triage.neatline` (stamping `neatline_src`), tile priorities come from `--auto-priority` at run time, and **Save triage is the acceptance** (`triage.validated_at`), which is the only thing `enqueue_ocr_all.mjs` will queue on. `triageState()` in `src/lib/data/maps/triageTypes.ts` is the one predicate — `ready | proposed | needs_crop | needs_layout` — and the fleet script carries a hand copy because it is `.mjs`; `tests/triage-state.spec.ts` is the contract. The gate used to be `triage.neatline`, which **no sheet in the corpus had**, so the script's default mode queued nothing and reported success. **Detect** on step 1 enqueues a `layout` job: one low-resolution look at the whole sheet asking the model where the main map, title block, legend, name list, inset and furniture are. It is a job and not a route because the Gemini key lives on the worker and deliberately not in the web app. The answer lands in `maps.triage.regions` and the page polls for it. **Save triage** writes the neatline, tile grid and per-tile priorities to `maps.triage` (mig 069) — localStorage stays the working draft, but only a saved triage is visible to `scripts/queue/enqueue_ocr_all.mjs`, which by default queues **only** triaged sheets (`--untriaged` includes the rest in auto mode) and crops to the `main_map` region when the layout pass found one, falling back to the neatline. "Run OCR" **enqueues a `pipeline_jobs` row** and returns 202; nothing runs until a worker claims it. Same behaviour in dev and on Cloudflare — the old `child_process` spawn and its `{ cli_only, cli_command }` fallback are gone. `CliCommandBlock` now only serves the segmentation panel.
- **Text**: `OcrBboxTool.svelte` renders + edits `ocr_labels` bboxes and supports `drawMode`
  for manual bboxes (POSTs with `model: 'manual'`). `OcrSidebar.svelte` is a filterable table with
  inline text/category edit and auto-save on blur, split into `OcrRunBar.svelte` +
  `OcrRow.svelte` (the row, 145 lines of the sidebar's old 928), with state in
  `ocrReviewController.ts`. `BboxPanel.svelte` is the floating selected-bbox editor.

  **The axis is the job, not the OCR category** (`ocr/jobs.ts`, the panel's footer tabs): **Names**
  (names on the terrain) · **Index** (the sheet's own printed legend and name list) · **Numbers**
  (numerals on the map, against the index that explains them) · **Other** (title block, furniture,
  off-sheet, and anything on the map that is none of the above). A category cuts across all four —
  the 1942 sheet's printed index alone contributed 719 `street` and 630 `institution` rows, none of
  them marks on the map, all of them in the same chip as the street names a reviewer was trying to
  check. The four **partition** the loaded rows, which is what makes the tab counts a promise that
  clearing all four clears the sheet; `tests/ocr-jobs.spec.ts` holds exactly that. Picking a job
  reframes the canvas on the part it reads, starts the table in that job's order, and resets the
  category chips to the job's set — the chips are a refinement *inside* a job. The region pills this
  replaced are gone; `regionFilter.ts` stays as what `jobs.ts` is built on.

  **Search, filter and group are one system, not a per-table one** (Oct 2026). The panel's search,
  status, category, confidence, run and group-by are `features/shared/FacetFilters.svelte` — the
  same `FilterBar` /catalog and the legend rail wear — driven by `core/utils/facets.ts`, which
  holds the rules: an empty choice is no constraint (so **Pending + Validated together** is two chips
  on, and a reviewer can see what is already done instead of re-reading it); a facet's counts ignore
  its own choice; reset goes to the caller's `defaults` (the open job's categories), not to empty.
  A table declares `facets` and a group list and applies `filterRows` / `groupRows`; the shapes
  tables and the map lists are the next callers, and `GroupRow` (`lib/ui`) is the group heading.
  Status and run are also server queries (`?status=pending,validated`, a 2000-row cap), so
  those two facets reload; their chip counts are the sheet-wide totals the server returns.

The layout job — enqueue, poll, adopt the regions once it closes — lives in
`digitalize/layoutJob.ts` (`createLayoutJob`), beside `ocrRunApi.ts` and `triagePrefs.ts`, so the
route keeps only layout.

Pipeline stage (idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed →
exported) is polled via `GET /api/admin/maps/[id]/pipeline`. Four of those stages are **derived**
from the map's latest `ocr`/`seg` job; PATCH accepts only `reviewed`, `seg_reviewed`, `exported` and
`idle` — anything else is a 400.

**Shapes (`/scan?mode=shapes`)** — everything that is a shape rather than a word, three tabs over
one sheet and one `ImageShell`, chosen by `?tab=`. `trace/ShapesPage.svelte` is the shell; the tabs
are **links on the same route**, so a tab change keeps the instance, the canvas and the open sheet.

- **Draw** — `TraceTool.svelte` (OL Draw + Select + Modify) + `TraceSidebar.svelte`. Polygon for
  closed footprints, line for roads/waterways. Writes live in `trace/traceData.ts` (`createTrace`),
  through `POST /api/contribute/footprints` (rate-limited, author stamped server-side).
- **Segment** — `SegSidebar.svelte` + `segCommand.ts` (which also owns the `digitalize-seg-<mapId>`
  localStorage, moved off `triagePrefs`): pipeline stage, the gate to the next one, and the MapSAM2
  command to run in Colab. It never starts anything — the GPU is elsewhere.
- **Validate** — HITL for SAM2 `submitted` / `needs_review` polygons: `ReviewTool.svelte` +
  `ReviewSidebar.svelte` (approve/reject, "Mark seg reviewed"), state in `review/reviewQueue.ts`
  (`createReviewQueue`). Geometry and type edits are **held until the verdict** and sent with it — a
  reviewer nudging a corner has not decided yet. The rail shows the queue here rather than the
  archive: `fetchMapsWithSubmittedFootprints()`, one row per sheet badged with its pending count.
  API `GET/PATCH /api/admin/footprints`; "Mark seg reviewed" PATCHes `/api/admin/maps/[id]/pipeline`
  → `seg_reviewed`.

They were three places — `?mode=trace`, the Segmentation phase of `?mode=triage`, and `?mode=review`
— which is one sheet opened three times and the same canvas built three times. It is one loop: draw
a few by hand, let the model do the rest, check what it did. `TracePage.svelte` and
`ReviewPage.svelte` are gone.

**Story review left `/scan` entirely** — it is `/admin?tab=stories`
(`features/admin/StoryReviewPanel.svelte`). A story has no sheet and no canvas; it had been riding
inside a pixel-coordinate tool it shared nothing with. `?mode=review&kind=stories` redirects there.

## 5. Data

### Maps domain

Canonical types live in **`src/lib/data/maps/`**:

- `types.ts` — `MapRecord`, `MapListItem`, `MapSourceType`, `MapStatus`, `IIIFManifestMeta`. **This
  is the only home** — `src/lib/map/types.ts` no longer re-exports them.
- `footprintTypes.ts` — `FeatureType`, `FootprintSubmission`, `PixelCoord`, `LegendItem`,
  `geometryKind`, plus `FEATURE_TYPE_LABELS` / `FEATURE_TYPE_COLORS` / `featureTypeFill()`. The
  colours are the **one** palette for footprints: `FootprintsLayer`, `TraceSidebar` and
  `ReviewSidebar` each had their own until Sept 2026, so a building was green on /explore, gold in
  the trace list and blue in the review list.
- `triageTypes.ts` — the saved triage and the layout vocabulary: `LAYOUT_CATEGORIES` (sheet ·
  main_map · title · legend · name_list · inset · scale_bar · north_arrow · stamp), `LayoutRegion`,
  `SavedTriage`, `parseRegion` (untrusted model output in, valid region or null out) and
  `tilingCrop` (**`main_map` beats the neatline**, because the neatline is the printed border and a
  legend inside it is inside the neatline too). Lives in `data` so `$lib/server` and the digitalize
  UI share one vocabulary.
- `service.ts` — `fetchMaps`, `fetchFeaturedMaps`, `fetchGeoreferencedMaps`, `fetchMapRow`.
- `iiifManifest.ts` — `fetchIIIFManifest(url)`; handles IIIF v2 + v3.
- `georef.ts` — `fetchGeorefQueue`, `annotationStorageUrl`, `allmapsEditorUrl`.

`src/lib/map/types.ts` is **UI-only**: `ViewMode`, `DrawingMode`, `AnnotationSummary`,
`SearchResult`, `AnnotationSet`. `src/lib/map/constants.ts` holds `BASEMAP_DEFS`, `DRAW_TYPE_MAP`,
`DEFAULT_ANNOTATION_COLOR`.

Admin client functions: `src/lib/data/admin/adminApi.ts` (map CRUD, image upload, IIIF source mgmt,
R2 mirror) with the payload shape in `mapEditPayload.ts`.

`MapListItem.bbox` is the DB column (`maps.bbox`); `MapListItem.bounds` is a runtime enrichment
added by `useMapList.ts` once bounds are resolved. Same `[minLon, minLat, maxLon, maxLat]` shape.

`MapListItem.id` is `maps.id` (UUID). `allmaps_id` (16-char hex) is the canonical Allmaps image ID;
`annotation_url` is an optional override (set by `mirror-r2` to the Supabase Storage URL of the
rewritten annotation JSON). Either resolves via `annotationUrlForSource()`. Story `overlayMapId` may
be UUID (new) or Allmaps ID (legacy) — resolve via
`mapList.find(m => m.id === id || m.allmaps_id === id)`.

### Annotations (`src/lib/map/annotations/`)

`annotationState.ts` (list + selection), `annotationHistory.ts` (undo/redo with GeoJSON snapshots,
100-entry limit), `annotationContext.ts` (Svelte context), `olAnnotations.ts` (OL feature utils),
`annotationCommands.ts` (draw/edit commands extracted from `DrawTool`). All features require `id`,
`label`, `color`, `hidden` — use `ensureAnnotationDefaults(feature)`. Default colour `#2563eb`.

### Data access (`src/lib/data/supabase/`)

`client.ts` (browser client), `context.ts` (auth via Svelte context), `role.ts` (`fetchUserRole`),
`annotations.ts`, `stories.ts`, `favorites.ts`, `mapOpens.ts`, `footprints.ts`, `types.ts`
(generated). `footprints.ts` is both the footprint CRUD layer and the SAM2 review entry point:
`fetchSubmittedFootprints()`, `fetchMapsWithSubmittedFootprints()`, plus `fetchLabelMaps()` — the
map-selector source for `/scan?mode=prepare` and `?mode=shapes`.

### IIIF utilities (`src/lib/core/iiif/`)

- `allmapsId.ts` — `deriveAllmapsId(iiifImageUrl)`.
- `annotationUrl.ts` — `annotationUrlForSource(source)`: bare ID or full URL → annotation URL.

### API route conventions

All API routes live under `src/routes/api/`. Every handler is
`requireRole → adminClient → query → json`, built from `$lib/server`:

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

Rules: accept JSON, return JSON — no form data. Admin routes re-check `profiles.role` in the
handler; do not rely on RLS alone. The service key is `$env/static/private` and must never reach a
component. The current route inventory is in `src/routes/CLAUDE.md`.

---

### Data layer conventions

**Map identity.** `maps.id` (UUID) is the canonical identifier everywhere — FK columns, URL params,
component props. `maps.allmaps_id` is used only when calling Allmaps (annotation URLs, warped tile
layers) and is never a join key. `mapStore.activeMapId` now holds the UUID and is mirrored from
`layersStore.topOverlay`; the old `&map=` hash writer is gone and the deep-link param is
`?map=<slug>` (the readable address since mig 088; a uuid or alias still resolves via `resolveMapRef`).

**Client usage.** Browser: `getSupabaseContext()` → `{ supabase, session }`. Server: `adminClient()`
from `$lib/server/supabaseAdmin`. Always pass the generic — `createClient<Database>(...)`. A bare
`createClient(...)` is what forces `as any` casts downstream; about 25 remain.

### Supabase types

- `src/lib/data/supabase/types.ts` is current against migration head **116**, plus 122's three review tables (spliced from `--local` generator output, 2026-10-14; nothing else of that output was taken) (verified 2026-10-06: every 116 `maps`/`map_images` column is present; 115 only replaces a function body, so it changes no type. `edition` and `region` / `region_2025` added by hand 2026-10-05; the generator emits a different, older shape for this file, so a raw regenerate is not a zero-line diff; verified 2026-10-05:
  106's `printing_id` and 107's `duplicate_of_map_id` / `archive_reason` are present; 108 changes
  only a column default, which the types do not carry). Regenerate from the linked project after
  every push; a zero-line diff after a hand edit is the cheapest confirmation it was right.
  One trap if you reach for `--local` instead: the local stack image emits an older template and
  churns ~30 unrelated lines of scaffolding that have nothing to do with the schema. Nothing
  regenerates the file automatically — before 075 it still declared four tables long dropped.
  Prefer the real types over `as any`; ~25 casts remain, mostly in Svelte components.
- The generic belongs on the client: `createClient<Database>(...)`. A bare `createClient(...)` is
  what forces most `as any` casts downstream.
- Insert/Update payloads use `?:` optional fields, not `Partial<{...}>` (which resolves as `never`).
- **Realtime is stubbed out of the browser bundle.** Nothing in `src/` calls `.channel()` or
  `.subscribe()`, but `SupabaseClient`'s constructor builds a `RealtimeClient` regardless, and the
  root layout builds a client on every route — so the phoenix + websocket stack was riding along on
  the front page, the catalogue and the blog. `vite.config.ts` aliases `@supabase/realtime-js` to
  `src/lib/data/supabase/realtimeStub.ts`, which satisfies the constructor and throws on anything
  else. The root layout chunk went 65.3 kB → 48.4 kB gzipped (238 kB → 181 kB raw) on **every**
  page. The alias needs an absolute path (`fileURLToPath`): a `/src/...` string builds fine but the
  dev server's esbuild dep-optimiser reads it off the filesystem and dies with `Cannot read file`.
  The day a real `.channel()` appears, the alias and the stub both come out.

### The gazetteer key

**One place, not one spelling.** The gazetteer (`place_names`) groups by **`core_key`** — the proper
name with the generic word in front of it stripped (migration 081). `Rue Catinat` / `R. Catinat` /
`Catinat` are one place, and so are `Khánh Hội` / `Village de Khanh-Hoi` / `Vge de Khánh Hồi`, which
the command palette offered as three. Measured on the corpus: **2554 entries → 1796**, and since
`press.ts` bills Gallica and the NLV **once per place** (every attested spelling becomes an OR
clause in one CQL query, capped at 8), that is the same 30% off the outside-lookup bill. `name_key`
stays the most-attested *spelling's* key, so the URL is still `/catalog/place/boulevard-charner`
rather than `/charner`, and the loader resolves any variant's slug through `core_key` and 301s to
the canonical one — every link minted before 081 still lands. The rule exists twice, in
`place_core_key()` and in `placeCoreKey` (`$lib/core/utils/placeKey.ts`), because a label on screen
links to its place page without a round trip; `tests/palette.spec.ts` reads the migration to pin the
word list and `tests/write.spec.ts` asks the database itself, which is what caught Postgres's
`unaccent` expanding `œ`→`oe` where NFD does not (`Rue Schrœder` keyed two ways, and its place page
404'd). Two guards are corpus-learned, not reasoned: a stripped core under four characters is
rejected (`Chợ Lớn` would become `lon`), and `Grand`/`Ancienne`/`Ngã` are deliberately **not**
generic. Known ceiling: 47 groups merge across categories, so `Rạch Lò Gốm`, `Quai de Lò Gốm` and
`Đường Bến Lò Gốm` share one page — usually right in Saigon, where the quay is named for the canal.
081 also makes the view's published-only gate explicit
(`m.status in (...) or auth.uid() is not null`): `security_invoker` is no gate at all for
`/catalog/place/[name]` and `/api/search`, which read it on the service client, so a draft sheet was
moving a public page's `mentions` and `years`.

## 6. Components and styling

### Component rules

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
- Deep sharing: `setContext`/`getContext` — `getShellContext()`, `getImageShellStore()`,
  `getSupabaseContext()`, `getAnnotationContext()`. Never prop-drill more than two levels.
- `$:` for derived values only, and keep it under ~3 lines — extract a function past that. Never use
  `$:` for async side effects; use `onMount` or an explicit call.
- Always return a cleanup function from `onMount` when you add listeners.
- Any component past ~400 lines is a smell. The Aug-2026 pass split every file over that line; the
  largest survivor is 575.

### Styling

Everything shared lives in `src/styles/`, reached via the `$styles` alias. `global.css` imports
`tokens.css` plus the always-on component sheets; layout and page sheets are imported by whoever
needs them. The full file map and the token list are in `docs/guides/design-system.md`.

**Token rule.** Never hardcode a colour, border or shadow in a component `<style>` block. Component
CSS carries layout and positioning; everything visual goes through `var(--token)`.

```css
/* wrong */ border: 3px solid #111;
/* right */ border: var(--border-thick);
```

The Aug-2026 sweep took component hex literals from ~900 to 116. The Sept-2026 plate-tone pass took
the rest: canvas colours moved to `INK` in `src/lib/core/ink.ts` (an OpenLayers style is a draw call
and cannot read a CSS variable), stale `var(--token, #old-value)` fallbacks became
`var(--token, var(--other-token))`, and ink-at-alpha scrims became `color-mix`. Four literals
survive in the tree and each says why where it sits: `ink.ts` itself, the offscreen analysis canvas
in `suggestTriage.ts`, the Google logo paths, and `ReviewSidebar`'s cadastral class swatches.

**One button system.** Every button is in `components/buttons.css` except `.sb-btn` (token-scoped).
A component that needs a near-`.chip` adds the class and overrides `--btn-*`; it never rebuilds the
shape, and it never redefines a global button class in its own `<style>` block — Svelte scoping
makes that win silently.

**Scoping.** `<style>` is component-scoped by default — use it freely for layout. Never redefine a
shared global class per component. Use `:global()` only for third-party DOM (OL controls). Inline
`style=` is for dynamic values only (`style="--sidebar-width: {w}px"`).

### Component vocabulary

**Two button names, two card sizes, one modifier vocabulary.** `.btn` is an action and `.chip` is a
choice (a tab, a facet, a filter; `.is-on` when picked); both are the same pill and differ only in
their `--btn-*` values. The modifiers are the ones `.sb-btn` / `.sb-pill` already used, so the
editorial and sidebar scopes are one thing to learn: sizes `.is-xs` `.is-sm` `.is-lg`, tones
`.is-primary` `.is-danger` `.is-success` `.is-ghost`, states `.is-on` `.is-block` `.is-icon`
`.is-disabled`. `.is-icon` is one round shape at three sizes (48px map control · `.is-sm` card
corner · `.is-xs` row toggle). **Twenty-seven selectors across nine families became eleven** in Sept
2026: four tones were each spelled three ways (`.btn-primary` · `.chip.primary` ·
`.action-btn.primary-btn`), `.action-btn` was a size, `.pill-btn` was lighter chrome and nothing
else, `.btn-outline` was already the default, `.tool-btn` was `.sb-btn.is-sm` in a bar running on
`--sb-*` anyway, and `.ctrl-btn` / `.btn-icon-*` / `.cmp-btn` were one shape at three sizes. Three
private badges in `admin-modals.css` were `.badge-chip.is-sm` plus a tint. **`.section-card`** is
the one card, padded by `--card-pad`, with `.is-sm` (a column of them) and `.is-link` (the whole
card is a link, so it lifts); `.post-card`, `.subscribe-card`, `.sidebar-card` and `.profile-card`
were it re-typed in four files. The ledgers are the headers of `buttons.css` and `Tabs.svelte`, and
`tests/screens.spec.ts` fails if a retired name reappears.

**One tab strip, two tones.** `$lib/ui/Tabs.svelte`. There were **five** — `ChunkyTabs` (`.chip` at
page scale), `.admin-tabs` (the same `.chip` as links), `.tabs` in `MapEditModal` (the same `.chip`
again, hand-written per tab), `.sb-rail-tabs` (`.sb-pill`, hand-written in both /explore rails) and
`.phase-tabs` (a private face invented for the /scan sidebars, which is the slot `.sb-rail-tabs`
already owned). Only one of the five said anything to a screen reader. `tone` picks the design
system — `page` is the editorial `.chip`, `rail` the sidebar `.sb-pill` — because those are two
palettes on purpose; what is shared is the markup, the API and the semantics, which had no reason to
differ. **A row with an `href` makes the whole strip links** (`aria-current`, no `tablist`, since a
tab that changes the URL is a link); without one it is a real `role="tablist"` with `aria-selected`.
`tests/screens.spec.ts` fails if any of the three retired class names reappears.

**One search field, three sizes.** `.sb-search` in `components/sidebar.css`, worn by both /explore
rails, both /scan rails, the two table toolbars and **/catalog**; `.is-compact` is the toolbar size,
where the field shares its row with a status select and a count, and `.is-page` the full width of an
editorial page — same border, radius, parts and palette, only the padding, the type and the drop
grow (to `--shadow-solid-xs`, which is what the `.data-table.is-card` under it casts). It was four
designs until Sept 2026: `.shapes-search` in `shapes-table.css`, `.mo-search` in `modal.css` (a
modal class that outlived its modal — its last wearer was `CatalogSidebarPanel`, and both it and
`.shapes-search` are **deleted**), and /catalog's own 2.5px pill in the route's `<style>`, which was
styled twice and lost every conflicting property to the scoped copy, so what reached the screen was
a box-shadow *inside* the box. Named like `.sb-pill.is-compact`, which is the same relationship.

**One table, one sort.** Every table is `$lib/ui/DataTable.svelte` — the scroll container, the
`<table>` and its density (`table.css`), the `<thead>` built from a column list, and the `<tbody>`.
**Rows are the caller's**, through the default slot, because the rows are the only part that ever
differed; anything under the table (an empty state, a paging button) is the `after` slot. A blank
column — a status dot, a thumbnail, an actions cell — is a column with `sortable: false` and an
`srLabel`, not a hand-written `<th>` beside the loop, so a table's header is one list read in one
place, order included. A sortable column is `$lib/ui/SortHeader.svelte` and the state behind it
`$lib/core/utils/tableSort.ts`; `bind:sort` lets DataTable toggle it, and a table sorted by the
**server** (`ScoutTable`, whose page holds 60 of 1037 rows) passes `sort` unbound and listens to the
`sort` event instead. One catch: a caller's scoped CSS reaches its own `<tr>`/`<td>` but **not** the
`<table>`/`<thead>`/`<th>` — those are DataTable's, so a rule keyed on one needs `:global()` inside
a wrapper the caller owns (`.ct` in `CatalogTable`) or, better, a class on the cells. There were
four hand-rolled versions of this until Sept 2026 — /catalog wrote five lines of caret markup per
column, the scout queue and the two contribute sidebars concatenated a text arrow into the header
string, and the state came in three shapes (`{key, asc}`, `{key, dir}`, two loose props). The header
became `SortHeader` first; the fifteen lines of scaffolding around it stayed copied four times until
`DataTable` took them. **None of the four was reachable from a keyboard and none set `aria-sort`**:
a `<th>` with `on:click` is a label someone attached a handler to. The header is a real `<button>`
now, and the indicator draws both carets with one lit, so a header does not change width when the
direction flips. `tableSort.ts` is in `core` because the four tables are in four different features
and a feature may not import another; it sorts decorate-sort-undecorate (the value function runs
once per row, not once per comparison — `OcrSidebar`'s parses a regex), keeps blanks last in
**both** directions, and collates `numeric` so `Rue 100` follows `Rue 11`.

The numbered legend is one too: `features/shared/LegendTable.svelte` is `DataTable` with the legend's
columns (№ · Name · Grid, and State in the staff tool), used by `SheetLegendPanel` on /explore and
`LegendSidebar` on `/scan?mode=legend`. It sorts itself; the caller filters and searches. Until
Oct 2026 both were hand-built `<ul>`s, so the two rails of the legend tool looked unrelated. A
`<table class="data-table">` written by hand (SeriesManage, NeatlineEditor, BulkUploadPage did)
is the same mistake the four sort headers were: use `DataTable`.

**Styling:** all CSS in `src/styles/`, imported via the `$styles` alias. **One sidebar design
system.** `src/styles/components/sidebar.css` owns it (`.sb-card`, `.sb-btn`, `.sb-pill`,
`.sb-input`, …) and its `--sb-*` block is now nothing but views onto `tokens.css` — it used to be a
second palette (`#fafaf7` ground, `#111` ink, `#2563eb` blue) set before the plate-tone pass, which
is why the map-shell sidebars read cool and bright against a warm app. `layouts/tool-page.css`
(`.panel`, `.panel-header`, `.bottom-bar` — position and size only) defers to the same `--sb-*`
scale, so a panel on `/scan` and one on `/explore` share one border weight, one radius, one hover
colour and one type scale. Canvas colours that OL paints come from `INK` / `inkAlpha` in
`src/lib/core/ink.ts`, never a literal. Root entry is `src/styles/global.css`, which imports
`tokens.css` plus the always-on component sheets; layout and page sheets are imported by the
component or route that needs them. **Two themes, one value each.** `tokens.css` writes every ink as
`light-dark(light, dark)` and picks by the used `color-scheme` — there is no second `[data-theme]`
palette to drift out of step. `:root` carries `color-scheme: light dark` (follow the OS);
`:root[data-theme='light'|'dark']` pins it, and that attribute is the only thing the toggle writes.
`src/lib/core/utils/theme.ts` owns the choice (`light | dark` — two states, not three; the button in
`NavBar` flips between them, stored raw under `vma-theme`) and exports `isDarkTheme`, derived from
that choice alone. The OS is read once, by `matchMedia`, for a reader who has never chosen; after
that the choice is pinned and an OS flip mid-session no longer moves the page. `src/app.html`
replays the stored value before first paint, so a reader on dark never sees a light flash. A new
colour needs both faces; `tests/theme.spec.ts` asserts the contrast of each.

Four things do not simply flip:

- **`--color-text-on-yellow`** never changes. `--color-yellow` is the one surface that stays light
  in both themes, so its ink is always the dark one.
- **`--color-on-accent`** flips the *other way* from the page: blue, green, red and purple are dark
  inks carrying paper-coloured text in light, and the dark theme lifts all four into light surfaces
  that need dark text. `color: var(--color-white)` on an accent fill is the bug this replaces.
- **`.on-ink-plate`** (`editorial.css`) is the mirror: the footers, the About CTA and the contact
  card are painted with the text ink and carry paper type, and *both* halves of that pair flip — so
  at night the slab inverted into a bright band and its ochre links sat on paper at 1.8:1. Pinned,
  they keep the appearance they were designed with. A filled *state* (`.chip.active`,
  `.sb-pill.is-on`, a hovered row) is the opposite case and should keep flipping: it only has to
  read as filled.
- **`.on-light-plate`** (`editorial.css`) pins the whole palette to its light face for a subtree,
  and the yellow heroes use it. Without it a `.hero-sub` card inside a hero takes the dark card
  stock while inheriting the plate's dark ink — a dark box on a bright yellow field. The light faces
  are named `--light-ink` / `--light-paper` / … in `tokens.css` so pinning needs no hex.

The OpenLayers basemap is painted, not styled, so `basemapStyle.ts` carries its own `LIGHT` and
`DARK` palettes and subscribes to `isDarkTheme`; the same reason `core/ink.ts` exists for annotation
colours. Warped historical sheets keep their own ink in both themes — they are photographs of paper.
`.mirror-cmd`'s console and `--is-canvas-*` in `mode-shared.css` are pinned dark on purpose.
Component `<style>` blocks carry layout/positioning; every colour, border and shadow goes through a
`var(--token)`. New pages use the template in `docs/guides/design-system.md`; nav and footer come once from
`src/routes/(editorial)/+layout.svelte`, so a new editorial page only needs the links added in
`src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`.

**The top bar is two tiers.** `Catalog · About · Blog` sit in the bar itself; every tool is behind
one `Tools ▾` menu, which also carries the staff rows (`/scan?mode=shapes&tab=validate` and
`/admin?tab=status` for mod, `/screens` for admin) and ends with `All pages → /directory`. The staff
rows need a role, and `ui` may not import `data`, so `(editorial)/+layout.svelte` resolves it once
with `fetchUserRole` and passes `role` to `NavBar` — the same reason `CommandPalette` gets it from
the root layout.

### Fonts

**The fonts are self-hosted.** `src/styles/fonts.css` carries the `@font-face` rules and
`static/fonts/` the twelve woff2 files (212 kB on disk; a page fetches the three or four subsets it
actually uses). They came from `fonts.googleapis.com` until Sept 2026: a render-blocking stylesheet
on one third-party origin pointing at files on another, so two DNS lookups, two TLS handshakes and
an extra round trip stood between the HTML and the first painted word — which is what the two
`preconnect` hints in `app.html` were paying for, and both are gone with them. Only **latin,
latin-ext and vietnamese** are kept; Google served cyrillic and greek too, and no page has ever
asked for them. `unicode-range` is verbatim from Google's CSS, so a browser still fetches only what
a page needs, and `app.html` preloads the two that are on every page above the fold
(`inter-400-800-latin`, `be-vietnam-pro-800-latin`). Regenerate by re-fetching that CSS with a
modern user agent, keeping the three subsets and rewriting the URLs. Inter is still **a variable
axis** (`wght@400..800`) — one file per subset rather than four static cuts; Be Vietnam Pro has no
variable build, so it stays static at 600/700/800. The Google Translate widget that used to sit
there is **gone**: ~100 kB of third-party script on every page for a control that never rendered
(`autoDisplay: false`, hidden mount point). Do not reintroduce it without a visible language switch
to justify it.

### Navigation and page state

Nav and footer render once from the group layout. To add a public page: create the route under
`(editorial)/`, add the link to `src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`,
add a row to `paletteDestinations.ts`, and add it to the route table in §2.

Editorial pages use a mount fade-in:

```svelte
<script lang="ts">
  let mounted = false;
  onMount(() => { mounted = true; });
</script>
<div class="page" class:mounted>…</div>
```

Async data shows a skeleton or spinner **inside** the content area — the hero and nav are visible
immediately.

## 7. Roles and known debt

### Roles and access

| Role | Access |
|------|--------|
| logged out | public read: explore, catalog, blog, about, trip playback |
| `user` | contribute: georeference, trace footprints, digitalize, author stories |
| `mod` | + review/approve footprints, OCR review, map metadata, scout |
| `admin` | + create/delete maps, publish, bulk upload, pipeline control |

Role lives in `profiles.role`, read on the client via `fetchUserRole` (`data/supabase/role.ts`) and
enforced server-side by `requireRole`. `/contribute` shows the review and admin cards only to `mod`
/ `admin`.

---

### Known debt

| Item | Location | Fix |
|------|----------|-----|
| 32 `as any` casts (counted 2026-10-06) | the export route, `map/shell` and the catalog components | pass `<Database>` to `createClient` at each call site |
| `footprints.ts` mixes two concerns | `data/supabase/footprints.ts` holds both map-selector queries and footprint CRUD | split into `maps/labelMaps.ts` + a contribute-scoped module |
| Mixed error conventions | throw vs `console` → `[]` vs `console` → `false` across `data/` | pick one |
| Mobile gaps in contribute | `OcrSidebar` bind/`on:filter` and the Segmentation tab are desktop-only (carried from the Aug 2026 cleanup, not re-verified since) | decide whether these tools are desktop-only by design, then either say so or fix |
| `/scan?mode=inspect` may be dead weight | `features/contribute/inspect/` duplicates what `/catalog/[id]` does since 7.3, drafts included | check whether the tool map picker is the only thing it still offers, then delete it and drop the mode from `core/scanModes.ts` — roadmap, *Open after 7.3* |
| Fat page components | `ExplorePage.svelte` (**431** script lines, up from 336) and `DigitalizePage.svelte` (**434**, up from the 263 it was cut to when the layout job left in Sept 2026) are controllers, not wiring. Both grew back past the point the extraction bought, which is the argument for doing it as a controller module rather than as a one-off trim (recounted 2026-10-06 at HEAD, `<script>` block including its tags). The Sept 2026 route merge moved them out of `src/routes` into `features/`, which fixed where they live, not how big they are | pull into `features/<x>/<x>Controller.ts` when next touching them — the `ocrReviewController.ts` / `layoutJob.ts` pattern |
