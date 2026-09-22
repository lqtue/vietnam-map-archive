# src/routes — surfaces and the API contract

Root context: `/CLAUDE.md`. Library-side rules (layering, the map runtime, the component
vocabulary): `src/lib/CLAUDE.md`. Per-route API reference: `docs/api.md`.

## Route groups

`(editorial)` = public pages with nav/footer. `(app)` = full-screen tools with `ssr = false`.
Modes are query params, not routes — `/explore` is the MapShell surface, `/scan` the ImageShell one,
each a ~10-line `{#if}` dispatcher. **`/scan` has no default mode** (Sept 2026): the public
read-only viewer merged into `/catalog/[id]`, so a request with no mode — or a mode that is not in
`$lib/core/scanModes.ts` — is redirected to `/catalog`, carrying `?map=` as `/catalog/<id>`.
`/vi/<path>` is the Vietnamese address of `<path>`
(`src/hooks.ts` reroute). Retired paths 301 from `src/hooks.server.ts`.

**The top bar is two tiers**: `Catalog · About · Blog` in the bar, every tool behind one `Tools ▾`
menu with the staff rows and `All pages → /directory`. Nav and footer come once from
`(editorial)/+layout.svelte`; a new page needs a row in `NavBar.svelte`, `EditorialFooter.svelte`
and `paletteDestinations.ts`.

| Route | Purpose | Source |
|-------|---------|--------|
| `/explore` | MapShell dispatcher | `src/routes/(app)/explore/` |
| `/explore?mode=browse` | Browse maps, play stories | `src/lib/features/explore/ExplorePage.svelte` |
| `/explore?mode=studio` | Free-form annotation + timeline animation. `?mode=annotate` is the name it shipped under and is aliased, not redirected (`MODE_ALIASES` in `(app)/explore/+page.svelte`) — the dispatcher only ever matches `studio` | `src/lib/features/annotate/` |
| `/explore?mode=story` | Author stories | `src/lib/features/stories/editor/` |
| `/scan` | ImageShell dispatcher | `src/routes/(app)/scan/` |
| `/scan?mode=inspect` | IIIF viewer, unlisted — the plain look at a **draft** scan | `src/lib/features/contribute/inspect/` |
| `/scan?mode=prepare` | Layout · neatline · tile grid · save · queue OCR | `src/lib/features/contribute/digitalize/` |
| `/scan?mode=text` | Check what came back: Names · Index · Numbers · Other | `src/lib/features/contribute/ocr/` |
| `/scan?mode=shapes` | Draw · Segment · Validate, `?tab=` | `src/lib/features/contribute/{trace,review}/` |
| `/trip/[id]` | Story playback | `src/lib/features/stories/play/` |
| `/catalog` | Faceted catalog + series band + inline admin | `src/lib/features/catalog/`, `src/routes/(editorial)/catalog/` |
| `/catalog/[id]` | One sheet: the record **and** its tiled scan (`SheetZoom`, full-screen). `[id]` is the **slug** (mig 088); a uuid or a retired slug 301s to it | `src/routes/(editorial)/catalog/[id]/` |
| `/catalog/place/[name]` | The gazetteer: one page per attested place name | `src/routes/(editorial)/catalog/place/[name]/` |
| `/catalog/series` | Every survey, and how much of each is held | `src/routes/(editorial)/catalog/series/` |
| `/catalog/series/[key]` | One survey: its coverage and every sheet it contains, held or not | `src/routes/(editorial)/catalog/series/[key]/` |
| `/catalog/series/[key]/[number]` | One sheet of a survey — including the ones the archive does not hold | `src/routes/(editorial)/catalog/series/[key]/[number]/` |
| `/contribute/georef` | Georeference via Allmaps Editor | `src/routes/(editorial)/contribute/georef/` |
| `/admin?tab=` | Bulk upload · Scout · Status | `src/lib/features/admin/` |

## API routes (`src/routes/api/`)

- Every handler is `requireRole → adminClient → query → json`, using the `$lib/server` helpers
  `requireRole`/`getRole` (`auth.ts`), `adminClient` (`supabaseAdmin.ts`) and `assertUuid`/`dbError`
  (`http.ts` — 400 on a malformed id, and no raw Postgres message ever reaches the client).
- Three auth classes: **admin/mod session** (`/api/admin/*`), **any signed-in user**
  (`/api/contribute/*`, `user_id` from the session, rate-limited by `assertUnderRateLimit`), and
  **worker token** (`/api/pipeline/*`, `Authorization: Bearer <worker_keys token>` via
  `$lib/server/workerAuth.ts`; mint with `scripts/mint-worker-key.mjs`). `/api/search`,
  `/api/context`, `/api/press`, `/api/maps/[id]/legend-points` are public and enforce
  `status IN ('public','featured')` server-side. `/api/search` takes
  `include=maps,scout,labels,places`; `places` searches the mig 067 gazetteer and is what the
  command palette turns into `/place/<slug>` rows.
- Enqueue, never execute: routes that start pipeline work insert a `pipeline_jobs` row and return
  202 (409 if one is in flight). Nothing runs until a worker claims it. `/api/pipeline/execute` is
  the one exception, for kinds that need the service key.
- Human pipeline stages (`reviewed`, `seg_reviewed`, `exported`, `idle`) are the only ones
  PATCHable; machine stages derive from jobs and are rejected with 400.

## Addressing a sheet

`/catalog/<slug>` and `/explore?map=<slug>` are the readable addresses (migration 088). Three rules
hold the seam together, and the second is the one that is easy to drop:

- **The slug is minted in Postgres and travels with the row.** Nothing in `src/` slugifies a name —
  `LIST_COLUMNS`, `/api/search`'s two column sets and the share loader all carry `slug`, and
  `$lib/core/utils/mapSlug.ts` only picks between what a row already has. A new list query that
  forgets the column produces uuid links that still work, which is why it would go unnoticed.
- **Every old address still lands.** `/catalog/[id]` resolves slug → alias → uuid and 301s the last
  two; `resolveMapRef` (`$lib/data/maps/resolveRef.ts`) accepts all three for `?map=`. Do not
  "tidy away" the uuid branches: a label hit and a footprint submission reach the UI carrying only
  `map_id`, and those links are 301s rather than dead ends.
- **`/api/*` stays on uuids.** The slug is an address, not an identity — it can be re-minted, and
  `maps.id` cannot.

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce
references.

## Series on /catalog

`/catalog` has a `+page.server.ts` for one reason: the surveys. The catalogue itself stays a
client-side search against `/api/search`, but `fetchSeriesIndex` (`$lib/data/maps/seriesIndex.ts`,
shared with `/catalog/series`) is the same for every anonymous reader and belongs in the HTML a
crawler gets. It feeds three things:

- the **band** above the results — `SeriesList`, the same rows `/catalog/series` renders, shown only
  while `atRest` (no query, no facet) is bound back out of `CatalogUnifiedSearch`;
- the **drawer** a row opens (`SeriesDetailDrawer`) — the row keeps its real `href`, so cmd-click
  and crawlers still reach the coverage page and only an unmodified left click is taken;
- the **series facet**, whose choices are passed down to `ArchiveFilters`. Nothing else passes any,
  so /explore and the /scan picker draw no such control. The filter matches `maps.collection`;
  which collections count as surveys is `map_series`' decision (mig 082/084) and is never
  re-derived client-side.

## Admin tooling

Map CRUD is inline in `/catalog`, gated by `role === 'admin' | 'mod'`:
`CatalogUnifiedSearch.svelte` dispatches `edit`, and the **route page**
`src/routes/(editorial)/catalog/+page.svelte` renders `MapEditModal`. Plus the dedicated pages
`/admin?tab=bulk` and `/admin?tab=scout`. There is no general `/admin` route. Full reference in
`docs/admin-tooling.md`.
