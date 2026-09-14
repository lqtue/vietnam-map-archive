# src/routes — surfaces and the API contract

Root context: `/CLAUDE.md`. Library-side rules (layering, the map runtime, the component
vocabulary): `src/lib/CLAUDE.md`. Per-route API reference: `docs/api.md`.

## Route groups

`(editorial)` = public pages with nav/footer. `(app)` = full-screen tools with `ssr = false`.
Modes are query params, not routes — `/explore` is the MapShell surface, `/scan` the ImageShell one,
each a ~10-line `{#if}` dispatcher. `/vi/<path>` is the Vietnamese address of `<path>`
(`src/hooks.ts` reroute). Retired paths 301 from `src/hooks.server.ts`.

**The top bar is two tiers**: `Catalog · About · Blog` in the bar, every tool behind one `Tools ▾`
menu with the staff rows and `All pages → /directory`. Nav and footer come once from
`(editorial)/+layout.svelte`; a new page needs a row in `NavBar.svelte`, `EditorialFooter.svelte`
and `paletteDestinations.ts`.

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

`/api/admin/upload-image` and `/api/admin/labels/*` were deleted (Aug 2026) — do not reintroduce
references.

## Admin tooling

Map CRUD is inline in `/catalog`, gated by `role === 'admin' | 'mod'`:
`CatalogUnifiedSearch.svelte` dispatches `edit`, and the **route page**
`src/routes/(editorial)/catalog/+page.svelte` renders `MapEditModal`. Plus the dedicated pages
`/admin?tab=bulk` and `/admin?tab=scout`. There is no general `/admin` route. Full reference in
`docs/admin-tooling.md`.
