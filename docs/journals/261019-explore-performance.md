# Explore scale checks — 19 October 2026

**Question:** Can Explore stay bounded as the archive and individual series grow?
**Answer:** Browsing and inspection now retain one page, and annotations share a request budget
and evict offscreen sources. SQL fixtures preserve full counts at 100k records.
**So what:** Large series can grow without making initial Explore load fetch the full catalog;
full-summary query cost and overview rendering still need measurement as the corpus grows.

Implemented bounded Explore pages (60 rows by default, maximum 100), stable year/name/ID cursors, full-query counts/facets/choices, accent-folded indexed search, and source-only paging that respects visible replacement halves. Full map metadata is read only for the selected page. Filtering and summaries use a narrow projection.

Deploy migrations **125 and 126 before the application**. Migration 126 adds a stored search vector and GIN index, which rewrite/index existing maps during deployment. Applied to production on 19 October 2026.

## Reproduce

Create a disposable local database named `vma_explore_performance`, then run:

```sh
VMA_EXPLORE_TEST_DATABASE_URL=postgresql://127.0.0.1:55439/vma_explore_performance \
VMA_EXPLORE_BENCHMARK=1 npm run test:explore-sql
PURE_ONLY=1 npx playwright test tests/explore-api.spec.ts
```

The SQL runner refuses a different database name or non-loopback server. Fixtures reset the public schema inside a transaction and roll back their changes. Use this database only for these fixtures.

## Measured SQL results

Local PostgreSQL, synthetic rows, three immediately repeated unfiltered calls. Each series contains approximately 100 sheets; geography has three provinces, names/years repeat, and every row is public and georeferenced. Query `hue:*` matches one third of the archive. Times include complete counts, facet choices, decade bins and the first page. Byte counts are the raw RPC JSON, before API shaping or HTTP compression.

| Archive rows | Unfiltered RPC ms, three calls | Search RPC ms | Unfiltered bytes | Search bytes | Page rows |
| --- | --- | --- | --- | --- | --- |
| 10,000 | 109 / 106 / 105 | 39 | 42,132 | 41,432 | 60 |
| 100,000 | 1,070 / 1,047 / 1,060 | 429 | 119,400 | 117,231 | 60 |

Point and ID restrictions run before JSON materialization. The migration adds a partial GiST index on PostgreSQL's built-in bounding boxes. A second synthetic layout distributes footprints among 256 clusters: point lookups matched 31/10,000 rows in 8 ms and 371/100,000 rows in 68 ms; one-ID lookups took 3 ms and 20 ms respectively. Optional-parameter OR predicates can prevent generic RPC plans from choosing available indexes; actual production plans remain to be measured. These timings establish bounded matching JSON work, not guaranteed index selection.

Location discovery uses persisted `maps.bbox`. A read-only audit on 19 October 2026 found zero public/featured georeferenced maps with missing bbox. `georef_write` persists these bounds. Future imports must persist/index bbox for location discovery; missing-bbox maps remain accessible through text search and exact lookup. No browser-wide annotation scan or restrictive database constraint was added.

Page map data stays bounded; facet choices and series counts grow with the number of distinct series/institutions/places. Full-query summary work remains proportional to matching data. Anonymous first-page results now use the existing deployment-versioned edge cache for 300 seconds. Staff, signed-in users, cursor pages, ID/point requests and oversized cache keys bypass it. Browser responses remain private/no-store; public catalog changes may take five minutes to appear on a warm edge. At 100,000 rows, the roughly one-second cold unfiltered SQL cost makes separate summary requests or pre-aggregated summaries the next optimization to measure. These synthetic timings do not establish production latency or a before/after browser speedup.

## Regression coverage and limits

The SQL fixture uses 1,201 tied records plus role/undated/source cases. It verifies complete counts and rare choices beyond 1,000 records, disjunctive facets, accent folding, geographic/year/point filters, draft visibility, no public RPC execution, all cursor pages without duplicates/omissions, exact final-page detection, and replacement visibility. Pure API tests verify input bounds/malformed values, server-controlled staff access, accent/token handling, the returned field allowlist, normalized anonymous cache keys and role/spatial cache bypass. An injected Supabase fetch test checks actual neighbor-request role gates, both retained OR groups, quoted names and chronological ordering.

Browser LCP/INP/CLS, memory, GPU resource cleanup, map-ready timing and production query plans have not been measured by this fixture.

The complete pure suite passes (499 tests). Mocked browser checks pass for desktop
10k/100k catalogs and a mobile 100k catalog, with 60 result rows, next/back and search,
shared desktop/mobile requests, sparse timeline alignment, and no full-catalog query.
The series loader's 23 checks include 250 distant pans, eviction/reload and late disposal.
The retention limit was soft (every visible sheet stayed drawable), so a whole-series view
could still load hundreds of scans. It is now hard: when a series has more sheets in view
than its share of the budget (64, or 24 under 900 px, split across the series in view), or
when its sheets are under 20% of the viewport wide (so a 44-sheet series and a 5,000-sheet one
both show outlines when zoomed out),
`seriesRenderer.ts` draws sheet footprints as vectors, makes no scan requests and destroys
the Allmaps renderer; zooming in brings it back (`seriesRenderPolicy.ts`). Three browser
checks (`tests/browser/series-overview.spec.ts`: a 5,000-sheet series, four series, mobile)
pass. These are regression checks, not a measured browser heap or GPU benchmark. Type checking reports zero errors/warnings; the production build and
changed-file ESLint/Prettier checks pass. Both local SQL regression suites pass.
