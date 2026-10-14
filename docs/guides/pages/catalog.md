# Catalog pages — system spec

Scope: `src/routes/(editorial)/catalog/**` and `src/lib/features/catalog/`. Read-only audit, 2026-10-14, against `main` @ 727bec39. All line numbers are from that tree. Sibling-wide facts first, so each page can stay short.

**Facts that hold for every page below**
- No `+error.svelte` exists anywhere under `src/routes` and there is no `src/error.html`. Every `error(404, …)` and every `dbError` 500 from these loaders renders SvelteKit's built-in error page. The nav and footer are not guaranteed to appear. (Unverified how the default page looks in production; the absence of the file is verified.)
- Locale: only `/catalog` and `/catalog/area/<slug>` have a `/vi` twin (`LOCALIZED_PATHS` and `isLocalizedPath` in `core/i18n/index.ts`). Every other page here is "one document, one language" with a cookie-chosen chrome. So `/vi` prefixes missing from sheet links are deliberate, not bugs.
- `$t('English string')` is keyed by the English text. Every `$t` key used in these files exists in `vi.ts` (checked with a read-only script in the scratchpad). The gap is strings that never pass through `$t`.
- Only `/catalog` (`catalog-v1`, 5 min, via `$lib/server/edgeCache.ts`) uses the edge cache. No loader here sets `Cache-Control`. No page sets `prerender`, `ssr` or `csr`, so all are SSR plus hydrate.

---

### `/catalog` — The Archive (faceted catalog)
Files: `catalog/+page.server.ts` (67), `catalog/+page.svelte` (280); `features/catalog/CatalogUnifiedSearch.svelte` (491), `CatalogTable.svelte` (331), `CatalogDetailDrawer.svelte` (367), `SeriesList.svelte` (87), `SeriesDetailDrawer.svelte` (368), `SheetStatus/WorkPips/OpenInMenu`; shared engine `features/shared/catalogSearch.ts` (417) and `ArchiveFilters.svelte` (375).
- **For / job:** reader or researcher finding a sheet by title, year, series, place or institution; staff editing records in place.
- **Access:** public. Signed-out reader sees public and featured maps only (API decides). `role` is read in `onMount` (`fetchUserRole`), so staff controls appear after hydrate. Admin/mod get: Include scout queue toggle, Work filter select, Type facet, Status/Open-in columns, Edit button in the drawer, `MapEditModal`, draft count in the toolbar.
- **Data:** server load `cached('catalog-v1')` over `fetchSeriesIndex`, `fetchCoverageIndex`, `fetchInstitutionCatalog` (service client; `ok` guard refuses an empty degraded result). `?area=` and `?region=` are read after the cache. The map list is client-side: one `GET /api/search?include=maps&limit=5000` on mount, filtered in the browser (`localSearch`); labels and scout rows come from per-query debounced calls. Staff also hit `/api/admin/maps/work-state`. The drawer lazy-loads long fields (`fetchMapLongFields`). Favorites via Supabase.
- **Requirements:** (1) search title, creator, year, description in the browser without waiting on the network; (2) facets: Kind (All/Surveys/Plans), series or type, place (region or province), institution, year range with histogram; (3) list or grid view (remembered in `vma-catalog-view-v1`), group by year, area, series or institution; (4) render in slices (100 table rows, 60 grid cards) with an `inView` sentinel; (5) series, area, region and institution bands as crawlable links, only while nothing narrows the list; (6) row opens a drawer with metadata, Map, Studio, Sheet page and Edit actions; (7) admins edit a map without leaving the page.
- **Layout:** `PageHero` (Submit a map mailto) → `.sb-search.is-page` field → `<details>` "Browse collections" with four bands (series, area, region, institution; `atRest` only) → `ArchiveFilters` (Kind tabs, `+ Filter` menu, active chips, Clear all, year timeline) → toolbar (count, scout toggle, Group by select, List/Grid tabs) → `LabelHits` → table or grid or empty state → `CatalogDetailDrawer`, `SeriesDetailDrawer`, `MapEditModal`.
- **Interaction:** table header click sorts (default year asc); group rows and group headers collapse; row click opens the drawer; cmd/ctrl-click on the title goes to the link; Esc closes the drawer; series row: plain click opens `SeriesDetailDrawer`, modified click goes to the coverage page. URL carries only `?area=` and `?region=` (read on load; a change remounts the search via `{#key}`). Query, other facets and view are not in the URL. States: loading shows "…" in the toolbar count; empty shows `.empty-state.is-block` "Nothing matches."; fetch failure only `console.error`s and retries on the next keystroke (no visible error); editor load failure shows `.edit-error` with `role="alert"`. Mobile: table hides columns 5 and 6 below 800px; drawer goes full width below 600px; grid is `auto-fill minmax(240px,1fr)`.
- **i18n · a11y · mobile:** Hero, search placeholder, facets, toolbar, empty state and drawer chrome use `$t`. Not translated: hero eyebrow "Collection" (`+page.svelte:100`), "Browse by area" (`:157`), `editError` text (`:57`), `aria-label="Filter by work"` (`CatalogUnifiedSearch:267`), drawer `aria-label="Map details"` and every drawer field label (`CatalogDetailDrawer:114,78-107`). a11y: group headers in the grid are real buttons with `aria-expanded`; table group rows are not (see findings).
- **Findings:**
  - `CatalogTable.svelte:115-118` links every public row to `/map/<uuid>`, not to the slug. That is a 301 to `/catalog/<uuid>` and then a second 301 to the slug (`hooks.server.ts:34`). The row already carries `slug`; the drawer uses `mapHref(item)` correctly (`CatalogDetailDrawer:186`). Contradicts the `src/routes/CLAUDE.md` rule "slug is the address". The comment at `:140-146` still says `/map/<id>`.
  - `CatalogTable.svelte:102` group `<tr on:click>` has no key handler, no `tabindex`, no `aria-expanded`; the grid twin (`CatalogUnifiedSearch:329-334`) has all three.
  - `CatalogUnifiedSearch.svelte:108` (`$: query.set(searchQuery)`), `:200` (`$: writeJson`), `:205` (`$: resetSlice`), `:81` (`$: if … loadWork()`) are `$:` blocks that write or call out. Breaks "`$:` computes, it does not write" in the house rules; line 108 plus the mirror at `:165` is a two-way loop held by a guard.
  - `CatalogDetailDrawer.svelte:61-62` and `SeriesDetailDrawer.svelte:36-37` hand-roll a `window` keydown listener in `onMount`/`onDestroy`; rules say `<svelte:window>`. Both drawers are the same furniture written twice (backdrop, slide-in, sticky head, actions) with no shared component, and neither has `aria-modal`, a focus move or a focus trap (`:113-114`).
  - Emoji in chrome: `✨` (`CatalogDetailDrawer:71`), `✏️` (`:179`), `✎` (`:171`), `↗` (`:193`). The design system bans emoji and pictorial glyphs in chrome.
  - `CatalogTable.svelte:321` uses an `800px` breakpoint, which is not one of the four (600/640/768/900). Hard-coded `1.5px` borders and `rem` sizes in component CSS (`CatalogTable:247,283`, `CatalogUnifiedSearch:457`); the drawer shadow is drawn in the border ink with a `2.5px` border (`CatalogDetailDrawer:227-228`).
  - `CatalogUnifiedSearch` carries seven props for other callers (`pickMode`, `compact`, `activeId`, `requireGeoref`, `showLayerActions`) and stays 491 lines; the catalog page uses none of them.
  - `+page.svelte:82-83` hard-codes the submission mailto address and an English-only body; the button label is translated, the email is not. Same for `✎ Edit` (`CatalogDetailDrawer:171`).
  - Search failure has no UI (`catalogSearch.ts:194-198`): the reader sees "Nothing matches." for an outage.
  - Filters do not survive reload or share (no `?q=`, no `?series=`).

### `/catalog/[id]` — One sheet (record + zoomable scan)
Files: `catalog/[id]/+page.server.ts` (153), `catalog/[id]/+page.svelte` (474); `features/catalog/SheetZoom.svelte` (241), `SupersededSheet.svelte` (134), `SheetWork.svelte` (27), `FavoriteButton`.
- **For / job:** the page people paste into chat and search; a reader checking one sheet's scan, date, holder and places; staff reopening its georeference.
- **Access:** public for `public` and `featured`. A draft resolves only for a signed-in reader (banner plus `noindex, nofollow`); anonymous gets 404, never a sign-in redirect. `[id]` accepts slug, retired slug (`map_slug_aliases`) or uuid; the last two 301 to the slug (`/vi` kept). An `archived` row 301s to its settled duplicate or 404s. Staff (admin/mod, read in `onMount`) also see the Contribute block (`SheetWork`), Allmaps fix link and two warnings.
- **Data:** server load with the service client: `maps` by slug, then alias or uuid fallback; `place_names` (`contains map_ids`, top 40); `maps` whose `extra_metadata->>mirrors_original_for` is this id; `verifiedEditorSourceId`. Four queries on a cold path, no `cached()`, no cache header. Staff block calls `/api/admin/maps/work-state` for this id. Schema.org `Map` JSON-LD plus OG and Twitter tags in `<svelte:head>`.
- **Requirements:** (1) serve the record SSR so crawlers see title, description and image; (2) show the still, and on click load `ImageShell` on demand (dynamic import) with pan, zoom and full screen; (3) list the facts the row has, hide empty ones; (4) link places named on the sheet to `/catalog/place/<slug>`; (5) for a third-party join of IGN half-sheets, say so and link the originals; (6) for a georeferenced sheet offer "Open on the map", OpenHistoricalMap trace link and the warped-tile URL.
- **Layout:** `PageHero` (eyebrow "Archive", title = name, sub = year · creator · holder) → `main.editorial-main.share-page` (56rem): draft banner → `SheetZoom` → description paragraphs → action row (Open on the map, Browse the archive, favourite, View original) → staff "Contribute" → OHM trace section → `SupersededSheet` → places pills → facts `<dl>` grid.
- **Interaction:** click the still to start the viewer; "Full screen" toggles a CSS `position: fixed` state (z-index 400) and refits the view; Esc leaves full screen only; "Close the viewer" returns to the still. Copy tile URL button (clipboard, "Copied" for 1.5 s). States: no `iiif_image` → still is a disabled button without the zoom hint; no still and no iiif → nothing in the figure; viewer import failure → "The viewer failed to load."; loading → "Loading the viewer…". Mobile: frame `min(70vh, 34rem)`; full screen covers the viewport.
- **i18n · a11y · mobile:** Banner, buttons, section heads use `$t`. Not translated: hero eyebrow (`:235`), every facts label (`:170-195`), "Copied / Copy tile URL" (`:298`, shown to the public whenever a tile URL exists), "Fix georeference in Allmaps" and both staff warnings (`:302` on), the schema `inLanguage: 'en'` (`:103`). a11y: still is a real `<button>` with `alt`; `figcaption` links; no focus handling on full screen.
- **Findings:**
  - `+page.server.ts:71-84` and `:99-114` repeat the same archived-redirect block; one path is the uuid branch, the other the slug branch.
  - `+page.svelte:2-5` header comment says "Everything interactive lives one click away in /explore?map=<id>"; the scan viewer has been on this page since Sept 2026.
  - `SheetZoom.svelte:197` hard-codes `z-index: 400` ("there is no z-index token"); full screen has no `role="dialog"`, no focus move, no page scroll lock, so keyboard users can tab to page content behind it.
  - OHM trace section is public but reuses the `.share-trace` class named for staff; its buttons mix `$t` and bare English.
  - Page hits Supabase on every request (4 queries) with no edge cache, unlike `/catalog`; the most-shared page is the least cached. Unverified whether crawlers hammer it.
  - `export let data;` is untyped here while sibling pages write `PageData` (works via svelte-check auto-typing; style only).

### `/catalog/area/[slug]` — Maps covering one province
Files: `area/[slug]/+page.server.ts` (18), `area/[slug]/+page.svelte` (101).
- **For / job:** reader or crawler landing on "maps of <province>" from the catalog band, search, or the sitemap.
- **Access:** public. Unknown slug or an area with no published maps: 404. Has a `/vi` twin (in `LOCALIZED_PATHS` and the sitemap).
- **Data:** load runs `fetchAreaMaps` (all public maps, 9 columns, parallel pages) then filters in JS by `coverageAreas(map)`; no `cached()`, no cache header. The catalog index of the same data is cached; this loader is not.
- **Requirements:** (1) show intro copy and a fixed provincial-boundaries caveat in English or Vietnamese; (2) list maps oldest first with thumbnail, date, series, holder; (3) link back to `/catalog?area=<name>` and to the archive; (4) set title, description and OG tags from the area copy.
- **Layout:** `PageHero` (no eyebrow) → `main.editorial-main`: two paragraphs, a search link, `<h2>`, `ul#area-maps` of rows (thumbnail link + name/date/series/holder), browse link.
- **Interaction:** plain links only; no controls. States: no thumbnail → row without image; no name → "Untitled"; no date → "Undated"; empty and unknown are both 404.
- **i18n · a11y · mobile:** Hand-written inline `vietnamese ? … : …` strings, no `$t`; area labels come from `CATALOG_AREAS[locale]`. Thumb link has `aria-label`; image has fixed 120x90. Rows wrap (`flex: 1 1 16rem`).
- **Findings:**
  - Uses its own bare `ul/li` list and no `.section-card`, `MapCard` or `DataTable`; this is the one page of its family that does not reuse a catalog row or card.
  - Inline `vietnamese ? … : …` copy (`:12-14,31-33,36,38,46,60-63,72`) duplicates the dictionary mechanism and will not show in `npm run i18n:check`.
  - Links to sheets use `/catalog/${map.slug}` without a locale prefix (`:45,59`); deliberate (sheet pages have no `/vi` twin) but the reader's language falls back to the cookie.
  - `fetchAreaMaps` reads the whole public catalog per request to show one province.

### `/catalog/place/[name]` — Gazetteer place
Files: `place/[name]/+page.server.ts` (66), `place/[name]/+page.svelte` (311); `features/explore/PressPanel.svelte` (imported from another feature; routes may).
- **For / job:** someone arriving from search or the palette to see everything the archive holds about one attested place name; a way into `/explore` at the spot.
- **Access:** public. 404 if the name is under 2 characters, has no `place_names` row, or no published map names it. A variant spelling 301s to the canonical slug (without the `/vi` prefix; the page has no twin).
- **Data:** load: `place_names` by `core_key` (`placeCoreKey`), then `maps` filtered to `public`/`featured` by the row's `map_ids`. Service client, no cache. `PressPanel` fetches press hits client-side after render. Needs `place_core_key()` (SQL) and `placeCoreKey` (TS) to agree or the page 404s.
- **Requirements:** (1) one URL per place however it is spelled; (2) facts: span of years, map count, mentions, category; (3) other spellings plus an honest note about OCR errors; (4) sheets that name it, oldest first, each opening `/explore?map=…&at=lng,lat`; (5) positional caveat from `geom_rmse`; (6) JSON-LD `Place` with `alternateName` and geo.
- **Layout:** `PageHero` (title wrapped in the lettering class for the place category, sub = generated sentence) → `main.editorial-main.place` (60rem): facts row → spellings → press panel → `<h2>` "On these maps" → caveat → card grid (`auto-fill minmax(15rem)`), each with a second small "Sheet details" link.
- **Interaction:** links only; the press panel has its own states (unverified). States: no thumbnail → card without image; no name → "Untitled"; no coordinates → no `&at=`; mobile = grid collapses to one column naturally.
- **i18n · a11y · mobile:** Mostly English-only: "map(s)", "mention(s)", "Also written…", the caveat, the generated description and "Untitled" are not in `$t`; only "attested", "On these maps" and "Sheet details" are. The details link has a good per-sheet `aria-label` (English).
- **Findings:**
  - Sheet links use uuids: `+page.svelte:192` (`/explore?map={m.id}`) and `:204` (`/catalog/${m.id}`). The loader does not select `slug` (`+page.server.ts:56-58`), so each link costs a 301. Breaks the slug-as-address rule.
  - Own card CSS (`.maps .card`) rather than `MapCard` or `.section-card.is-link`; thumbnails are raw `m.thumbnail` (`:193`) while other pages use `atWidth` + `stepDown`, so large images load and a missing size never steps down.
  - Mixed-language page: partial `$t` use makes a Vietnamese reader see a half-translated page.
  - No cache on a page crawlers reach through `/catalog/[id]`'s places list.

### `/catalog/series/[key]` — One survey (coverage + every sheet)
Files: `series/[key]/+page.server.ts` (327), `+page.svelte` (757), `notes.ts` (218); `features/catalog/SeriesCoverageMap.svelte` (110), `SeriesManage.svelte` (185), `coverageBackdrops.json`.
- **For / job:** researcher asking "how much of survey X does the archive hold, and which printings exist elsewhere"; also the crawl entry for 627-sheet surveys.
- **Access:** public. 404 when `map_series` has no row or no published sheet, or when the series has no imported index (`series_sheets` empty). `/catalog/series` (no key) 301s to `/catalog`. Admin/mod additionally see the "Manage" card, which fetches every `maps` row of the survey under the reader's own session (RLS decides) and offers "Publish" (`PATCH /api/admin/maps/<id>` with `status: public`).
- **Data:** service-client load, uncached: `map_series`, `fetchSeriesSheetIndex`, `fetchCanonicalSheetPrintings`, a paged `maps` read, `fetchSheetSources`. Merges printings, editions, coverage boxes and `SERIES_NOTES[key]`. All 627 rows ship in the HTML on purpose (crawl).
- **Requirements:** (1) say first what the survey is (note, optional) then how much is held; (2) show a coverage count that distinguishes held, scan identified elsewhere, and no known scan; (3) draw cell footprints on a static SVG map; (4) list every sheet with search, status chips and sort; (5) open per-cell printings (held, elsewhere, verified but unlinked) in a `<details>`; (6) link to `/explore?series=<key>&solo=1` with a camera fitted to held cells.
- **Layout:** `PageHero` (title, sheet count and span, "Open in map") → `.page-wrap` (60rem): About card → Coverage card (lead, SVG map, credit, bar, legend) → Manage card (staff) → search field + 3 status chips + count → `DataTable` (Sheet, Name, Version, Status, Source).
- **Interaction:** search is accent-insensitive across number, name, source (`matchesAllTerms`); chips toggle with `aria-pressed`; columns sort via `SortHeader`. States: nothing matches → `.table-empty` "No sheet in this survey matches."; no `bbox` → no map; no denominator → "full sheet list is not imported yet" text, no bar; staff fetch error → `role="alert"` with the HTTP status. No loading state (all SSR). Mobile: facets wrap; `.facts` goes 2 columns at 40rem; table is the shared `DataTable`.
- **i18n · a11y · mobile:** English only, except "Open in map". Bar has `role="img"` and a label; map has `role="img"` with label; the `<details>` is the Version cell.
- **Findings:**
  - Component is 757 lines; the 150-line printings block is inline in a table cell (`:384-500`). House limit says extract; this adds to the over-500 list.
  - Local `interface SheetPrinting` (`+page.svelte:164`) re-declares the type the server file imports from `$lib/data/maps/sheetSources`; its comment says that module "is still being written". Server file has the same stale note (`+page.server.ts:240-245`) and an orphaned JSDoc block (`:31-44`).
  - Sheet links use uuids: `+page.server.ts:184,196` (`/catalog/${row.id}`), no `slug` in the select (`:160`).
  - No `.page` root or `.editorial-main`; uses private `.page-wrap` (60rem) that `[number]` copies at 46rem. Bar, legend, dot and segment CSS is duplicated with `SeriesDetailDrawer` (the drawer's header says "tint for tint").
  - `SeriesManage.svelte:182` falls back to a hex `#b00020` for a token (`--color-danger`) that does not exist; use `--color-error-600`.
  - Staff "Publish" in `SeriesManage` acts at once with no confirm and no undo; its error text is the bare HTTP status (`:114`).

### `/catalog/series/[key]/[number]` — One sheet of a survey
Files: `[number]/+page.server.ts` (72), `[number]/+page.svelte` (193).
- **For / job:** someone following a sheet number (including one the archive does not hold) to learn if a scan exists and where.
- **Access:** public. 404 for unknown series or unknown cell. Sheets not held are `noindex`.
- **Data:** uncached load: `map_series`, `fetchSeriesSheet`, then published `maps` rows for that cell (id, name, year, half).
- **Requirements:** (1) say plainly: in the archive, scan identified elsewhere, or none known; (2) link every held record of the cell (two printings or two halves), not one; (3) name where a copy is recorded; (4) show the cell box as a non-georeference; (5) link to `/explore` by map or by camera hash.
- **Layout:** `PageHero` (title, series name) → `.page-wrap` (46rem): back link → Status card → Cell card (`<dl>`) → primary CTA.
- **Interaction:** links only. States: held 1 → one link; held >1 → list with half/year; not held → source line; no bbox → no CTA.
- **i18n · a11y · mobile:** English only; no `$t`. Uses `.status.is-*` colour plus text. Narrow single column.
- **Findings:**
  - Uses uuids: `+page.svelte:37,76,90` (`/explore?map=`, `/catalog/<id>`); the select omits `slug` (`+page.server.ts:50`).
  - Server comment (`:4-5`) still says 452 L7014 cells have no `maps` row; `series/[key]/+page.server.ts:5` says every sheet is a row since 2026-10-03.
  - No eyebrow, no breadcrumb component; the back link is a plain `<a>` (`.back-link` exists in the design vocabulary and `cartomundi/[id]` uses it).
  - Duplicates `.page-wrap`, `.muted`, `.crumb` styling with the series page.

### `/catalog/institutions` — Institution catalog
Files: `institutions/+page.server.ts` (9), `institutions/+page.svelte` (175); data `lib/data/maps/institutions.ts` (280), `cartomundi.ts` + `cartomundiIndex.json`.
- **For / job:** researcher asking who holds what, and which platforms gave us scans.
- **Access:** public, no redirects, no staff extras. Linked from the nav Catalog menu ("Institutions") and the /catalog band ("All institutions").
- **Data:** service-client load, uncached: `fetchInstitutionCatalog` (public `maps`, `cell_printings`, `series`) plus the bundled CartoMundi snapshot summary. The same function is cached on `/catalog` but not here, although this page returns the full map list of every institution.
- **Requirements:** (1) list institutions with counts of published maps, external source items and series; (2) list source platforms separately from holders; (3) filter both lists with one search box over names and member titles; (4) each institution opens inline to maps, source series and CartoMundi series; (5) CartoMundi and Nakala rows link to the rights evidence page.
- **Layout:** `PageHero` → `main.editorial-main` (turned into a grid): label + `.sb-search` input → card "Holding institutions" (one `<details>` each) → card "Source platforms".
- **Interaction:** typing filters live; `<details>` open/close; the institution name is a link inside `<summary>`. States: no match → "No institutions match this search." (institutions only; the platforms card shows nothing). No loading state (SSR). Long lists scroll in a `max-height: 24rem` box.
- **i18n · a11y · mobile:** Body uses `$t` throughout; not translated: eyebrow "Sources" (`:35`), `<title>` and meta description (`:26,29`). Search has a real `<label for>`.
- **Findings:**
  - A link inside `<summary>` (`:55-56`) is interactive content in an interactive parent: a click on the name navigates instead of opening, and the disclosure needs the surrounding area; keyboard order is two stops in one control.
  - `ul { max-height: 24rem; overflow: auto }` (`:162-165`) makes nested scroll regions that keyboards cannot focus.
  - Search is a bare `<input class="sb-search">` (`:41`); `/catalog` uses `label.sb-search.is-page`. The scoped `a { color: var(--color-blue) }` (`:172`) restyles every link on the page.
  - Search result handling is uneven: no empty state for the platform card.
  - Page-level `main { display: grid }` overrides `.editorial-main` in a scoped block (`:138`).

### `/catalog/institutions/[slug]` — One holding institution
Files: `institutions/[slug]/+page.server.ts` (10), `+page.svelte` (192).
- **For / job:** researcher or curator checking one holder's sheets, source records and other holdings.
- **Access:** public. Unknown slug: 404.
- **Data:** uncached `fetchInstitution(db, slug)`: public `maps` for the holder, `cell_printings` rows grouped by series, CartoMundi series (static JSON) and "outside" holdings (a bundled USGS list with a checked date).
- **Requirements:** (1) summary line: published maps, external items, other holdings, website, back link; (2) filter the item tables by sheet, title, year; (3) list published maps as links to the sheet page by slug; (4) per series, a table of source items with a link out and the archive sheets that match; (5) list holdings outside indexed series with a "checked on" date and PDF or GeoPDF link.
- **Layout:** `PageHero` (eyebrow "Institution catalog", title = name, sub = `about`) → `main.editorial-main`: summary → filter → cards: Published maps (plain `<ul>`), CartoMundi series, one card per series with a `DataTable.is-dense`, Other holdings (one `<h3>` + `DataTable` per source series).
- **Interaction:** one filter input narrows series items and outside holdings (not the Published maps list). States: nothing matches → `.table-empty`; institution with only maps shows no filter; mobile rely on `DataTable` scroll.
- **i18n · a11y · mobile:** Body uses `$t`; table column labels (`:27-38`), the `<title>`/description and "GeoPDF/PDF" are English only. Filter has a `<label for>`.
- **Findings:**
  - Filter does not touch the "Published maps" list, so typing a title leaves the whole list in place while the tables below shrink (`:71-80`).
  - Uses `.chip` for a non-interactive "served" tag (`:122`); the design system says `.chip` is a choice, `.badge-chip` a label.
  - Published maps appear as a text list with no thumbnail, unlike every other map list (grid, area, place).
  - `outsideSeries` and `shownSeries` recompute twice per keystroke; fine at this size (unverified at larger).

### `/catalog/institutions/cartomundi` — CartoMundi series index
Files: `institutions/cartomundi/+page.server.ts` (7), `+page.svelte` (241); old address `/catalog/cartomundi` redirects 301 here (`cartomundi/+page.server.ts`, keeps the query).
- **For / job:** rights-minded researcher checking which CartoMundi series may cover Vietnam and which scans have a license check.
- **Access:** public. Static JSON only; no database.
- **Data:** `cartomundiSeries()` and `cartomundiSummary()` from `cartomundiIndex.json` (a snapshot built by a script; 5,367 sheet records, 870 items). No cache needed, and none set.
- **Requirements:** (1) explain what the index is and is not, and the rights caveat; (2) list series with zone, scope, scale, date, holder, counts; (3) filter by text and by catalogue region; (4) announce result count (`aria-live`); (5) link each series to its detail page and to the source.
- **Layout:** `PageHero` → back link → "What this index shows" card → "Series" card: controls (search, region select), count, `ul.series-list` rows (title/meta left, counts right).
- **Interaction:** text and select filters; empty → `<p class="empty">`. Mobile: row grid collapses at 600px.
- **i18n · a11y · mobile:** No `$t` anywhere; `Intl.NumberFormat('en')` and `'en'` date format are fixed (`:24,35`). Real labels, polite live region.
- **Findings:**
  - Hand-styled input and select (`:169-179`, `min-height: 2.75rem`) instead of `.sb-search`; the same block is pasted into `cartomundi/[id]`.
  - Whole page English-only while its sibling `/catalog/institutions` is translated.
  - `.empty` is a local class; the shared one is `.empty-state` (`feedback.css`).
  - `class="page cartomundi-page"` has no matching CSS.

### `/catalog/cartomundi/[id]` — One CartoMundi series
Files: `cartomundi/[id]/+page.server.ts` (26), `+page.svelte` (378).
- **For / job:** same reader, one series deep: sheet records and Nakala license evidence per item.
- **Access:** public. Unknown id: 404. Not in the nav or the palette; reached from the institution pages.
- **Data:** static snapshot only (`cartomundiSeriesById`, `ItemsBySeries`, `SheetsBySeries`). The loader hard-codes a map of four series ids to survey keys (`+page.server.ts:9-14`) to offer "View this survey in Vietnam Map Archive".
- **Requirements:** (1) facts card for the series; (2) a plain statement of what a posted license does and does not establish; (3) searchable table of every catalogue sheet record with its rights evidence or "Rights not checked here"; (4) searchable table of linked Nakala items with license link and checked date; (5) link to the DOI and CartoMundi source.
- **Layout:** `PageHero` (eyebrow "CartoMundi series") → back link → About `<dl>` card → "How to read the rights information" → sheets card (search, count, table) → linked items card (search, count, table).
- **Interaction:** two independent search boxes; empty states differ for "nothing indexed", "no match" and "no Nakala items" (the last explains that zero does not mean no scans). Mobile: `table { min-width: 42rem }` inside `.table-scroll` under 600px.
- **i18n · a11y · mobile:** English only; headers are `th scope="col"`, search inputs labelled, counts `aria-live`.
- **Findings:**
  - Two raw `<table>`s with local CSS (`:314-340`) instead of `DataTable` / `.data-table`; the design rule is one table. No sort.
  - Hard-coded series-to-survey ids in a route file (`+page.server.ts:9-14`) will drift when a survey is added; it sits beside data that already has a registry.
  - Search input/label CSS duplicated from the index page.
  - The unfiltered table renders every sheet record of a series with no slicing; the largest series has 926 (series 201), so one table can reach about 900 rows.

---

## Patterns across these pages

- **Page shell: three dialects.** Seven pages follow `div.page` > `PageHero` > `main.editorial-main` (`/catalog` swaps in its own `.content`). The two series pages put `PageHero` outside any `.page` and use private `.page-wrap` (60rem and 46rem). Eyebrow use is random: set on `/catalog` ("Collection"), `[id]` ("Archive"), the institutions pages and CartoMundi; absent on area, place and both series pages. A system needs one shell with a fixed eyebrow rule.
- **Tables: four implementations.** `DataTable` is used on both series pages, `[slug]` institution and Manage; `CatalogTable` is a `DataTable.is-card` with its own group rows; `cartomundi/[id]` has two raw `<table>`s; area, place and institutions use `ul`/`li` lists. Only the catalog table has slicing; the 627-row survey table and 926-row CartoMundi table render whole.
- **Facets and search: three controls.** `/catalog` uses the shared `FilterBar` plus `ArchiveFilters`; series and institution pages use a bare `.sb-search` (sometimes in a `<label>`, sometimes not); CartoMundi pages hand-style `input` and `select`. State is never in the URL except `?area=` and `?region=` on `/catalog`.
- **Empty and error states: no shared pattern.** `.empty-state.is-block` (catalog), `.table-empty` (series, institution tables), plain `<p>` (institutions), local `.empty` (CartoMundi). A fetch failure on `/catalog` looks like "Nothing matches." and nothing else says "failed".
- **404 handling: every loader throws `error(404, msg)` and no `+error.svelte` exists.** The message strings (for example "No such series", "No published map at that address") are never shown in a branded page. Series 404 on "no index" is deliberate and matches `SeriesList` (button instead of link).
- **Sheet addresses: slug rule broken in 5 places.** `CatalogTable:117`, `place/[name]/+page.svelte:192,204`, `series/[key]/+page.server.ts:184,196`, `[number]/+page.svelte:37,76,90` link by uuid or `/map/<uuid>`; `institutions`, `area`, `SeriesManage` and the drawer use the slug. Each uuid link costs one or two 301s. The slug column is absent from three selects, which `src/routes/CLAUDE.md` warns will go unnoticed.
- **Map thumbnails: no shared component off `/catalog`.** The catalog grid uses `MapCard` with `atWidth(thumbnail, 400)`; table uses `atWidth(…, 200)`; area uses `atWidth` at 200 with fixed 120x90; place uses the raw column with no `stepDown`; institution pages show none. Coverage maps are plain SVG with an optional baked backdrop (no OpenLayers on this subtree; the only live map is `ImageShell` inside `SheetZoom`).
- **Admin inline edits: two mechanisms.** `/catalog` dispatches `edit` and the route renders `MapEditModal` (fetches the full row, saves, refreshes the engine); the series page has its own `SeriesManage` card that PATCHes status directly. Both gate on `role` read in `onMount` (UI hidden until hydrate), then the API/RLS decides. No admin affordance on the sheet page except a Work block and an Allmaps link.
- **i18n: three levels.** (a) `$t` throughout (`/catalog`, institutions, partly `[id]`); (b) inline `locale ? a : b` copy (area only); (c) none (series, `[number]`, CartoMundi, most of place). Only `/catalog` and area have `/vi` twins and hreflang/sitemap entries; the others are single-language documents with a cookie chrome. Field labels (`Original title`, `Creator`, …) are duplicated in `[id]` `facts()` and `CatalogDetailDrawer` `fields`, English-only in both.
- **Duplication worth a component.** Drawer furniture (two copies), coverage bar/legend CSS (series page and drawer), `.page-wrap`, the facts `<dl>`, and the search/label CSS pasted between the two CartoMundi pages. Caching is inconsistent: `/catalog`'s index is edge-cached 5 min while the same data (`fetchInstitutionCatalog`, `fetchAreaMaps`) is re-read on every institution and area request, and the most-shared page (`[id]`) is uncached.
