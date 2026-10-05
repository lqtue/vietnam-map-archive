# Catalog — plan (2026-10-05)

**Status:** decided, not started · **Baseline:** VMA `main` @ fb2f7358 · **Measured:** production,
2026-10-05, public (anon) reader, 1,038 maps

Design detail for the five catalog items in `docs/ROADMAP.md` (the single tracker):
`catalog-list-speed`, `catalog-columns`, `catalog-local-search`, `map-region-from-bbox`,
`map-json-to-columns`. It leans on two items that already exist: `georef-flag-one-meaning` and
`series-identity`. This file is the engineering plan only; close an item in ROADMAP, not here.

**One sentence.** Make `/catalog` and `/explore`'s left rail fast and useful by showing only the
columns that vary, searching the list in the browser, and giving every map a real place and sheet
number to filter on.

## What we found

Three queries against production as the public (`PUBLIC_SUPABASE_ANON_KEY`, `status in
('public','featured')`), plus a headless-Chromium run against `https://maparchive.vn/catalog`.

### Which columns carry information

| Column                 | Filled | Distinct | Reading                                                                         |
| ---------------------- | -----: | -------: | ------------------------------------------------------------------------------- |
| `name`                 |   100% |    1,015 | 23 names repeat ("Huế", "Muong Cha", "Phnom Penh (W)")                          |
| `year`                 |   100% |       78 | 1950s + 1960s hold 680 of 1,038                                                 |
| `map_type`             |   100% |        5 | **1,000 of 1,036 are "topographic"**                                            |
| `is_georeferenced`     |   100% |    **1** | **all true** — the Map/Image status carries nothing for a public reader         |
| `collection`/`series_key` |  97% |        4 | the real structure of the archive                                               |
| `sheet_number`         |    97% |      732 | in no column, sort or filter of the catalog                                     |
| `location`             |     4% |       10 | 46 rows — **34 of the 36 maps with no series**, i.e. the city plans             |
| `holding_institution`  |    51% |       11 | 458 are Cartomundi                                                              |
| `creator`              |    48% |       20 | 480 are "Service Géographique de l'Indochine"                                   |
| `description`, `date_label`, `language`, `rights` | ~50% | – | drawer only                                                      |
| `original_title`, `shelfmark`, `physical_description` | 3–4% | – | drawer only                                                      |
| `printing_id`          |     0% |        0 | waits on migration 106's rollout                                                |

`location` looks 96% empty but is not broken: it is empty on the 1,002 survey sheets by design and
filled on the one-off plans (1791–1959), which are the maps people look for first. The catalog holds
**two kinds of row** — survey sheets, addressed by series and sheet number, and plans, addressed by
place and year — and one flat table with one set of facets suits neither.

`extra_metadata` also duplicates columns: `sheet_number` (1,002) and `sheet_half` (479) are real
columns _and_ JSON keys, and `api/search/+server.ts` still matches `extra_metadata->>sheet_number`.
`edition` (456) and `source_archive` (510) exist only in JSON.

### Where the time goes

| Step                                     | Measured                                                      |
| ---------------------------------------- | ------------------------------------------------------------- |
| `/api/search`, no query                  | 2.4–3.3 s                                                     |
| `/api/search?q=saigon&include=maps,labels` | 1.2–1.9 s, for a 13 kB body                                 |
| Body, no query                           | 153 kB gzipped (≈1.47 MB raw; ≈290 kB of it `extra_metadata`) |
| Edge cache                               | `cf-cache-status: DYNAMIC`                                    |
| Supabase, 2 sequential pages vs parallel | 2.2 s vs 1.4 s (laptop → Supabase)                            |
| Page load → first rows                   | ≈4.5 s                                                        |
| First render                             | one 1.3 s long task; 1,038 rows, 15,350 DOM nodes, 1,038 `<img>` |
| Type "saigon" → table settled            | 1.16 s (a network round trip)                                 |
| Clear the box / sort / switch to Grid    | 0.2 s / 0.2 s / 0.28 s (client cache and re-render)           |

The body is small once gzipped, so the cost is **server time and first paint**, not bandwidth.
The client caches per query string, which is why only a _repeat_ search is fast. Numbers come from a
laptop, so absolute values include its distance to Cloudflare and Supabase; the proportions hold.

## Decisions (2026-10-05)

1. A publish may take up to **5 minutes** to reach the public (edge cache TTL).
2. `maps.region` is **derived from `bbox`**, not filled by hand.
3. **Status and Type are hidden from the public**; staff keep them (drafts and image-only rows
   still exist for staff).
4. Maps are **searched in the browser**; the server keeps labels and places only.

## Principles

1. Show a column only if it varies. A single-valued column gets hidden or removed.
2. Filter and sort on real columns (`db-guidelines.md` §8). `extra_metadata` is for unknown keys.
3. One meaning per flag — `georef-flag-one-meaning`.
4. Additive migrations, no drops now. `created_by` stays (the RLS policies in 038/079/100/101/103
   read it); `triage_reviewed_by` is written by `set_triage_key` and read by nothing, harmless.

## `catalog-list-speed`

Files: `src/routes/api/search/+server.ts`, `src/lib/data/supabase/paged.ts`,
`src/lib/features/shared/catalogSearch.ts`, `src/lib/features/catalog/CatalogTable.svelte`,
`src/lib/features/catalog/CatalogUnifiedSearch.svelte` (the grid).

1. **Edge cache, anonymous only.** `Cache-Control: public, s-maxage=300, stale-while-revalidate=600`
   when `role` is neither `admin` nor `mod`; `private, no-store` for staff. The response varies by
   role, so confirm an anonymous request carries no session cookie that makes the edge treat it as
   uncacheable. **Unverified:** whether Cloudflare Pages honours the header on a Function response.
   If `cf-cache-status` never reads `HIT`, fall back to a static JSON snapshot written on deploy and
   on admin edit.
2. **Parallel pages.** `readAll` is sequential and shared by other callers — leave it. Add a sibling
   that issues ranges `0–999` and `1000–1999` together and continues only if the second is full.
3. **Render in slices.** Show ~100 rows and extend with an `IntersectionObserver` sentinel, for the
   table _and_ the grid. Slice **after** grouping, so "Group by" still collapses whole groups. A
   virtual-list library only if windowing is wanted later; most of the win is not rendering 938 rows
   nobody has scrolled to.
4. **Stop sending `extra_metadata`** — only after confirming no reader. The drawer does not read it.
   Check `SeriesManage.svelte` and `MapEditModal.svelte`: the admin `edit` event hands them the list
   item, and `fetchMapRow` (the whole row) may need to be called when the modal opens instead.

Exit: cold load shows rows in about 1 s (was 4.5 s); the second anonymous request reads `HIT`; the
first render is under about 200 ms of blocking time.

## `catalog-columns`

Files: `catalogTableModel.ts`, `CatalogTable.svelte`, `ArchiveMapRows.svelte`, `ArchiveFilters.svelte`,
`catalogSearch.ts` (`passPeriod`, `passSeries`, `tally`, `PERIODS`), `MapCard.svelte`,
`CatalogDetailDrawer.svelte`, `SheetInfoPanel.svelte`. Depends on `georef-flag-one-meaning`.

| Surface                    | Now                                         | After                                                                  |
| -------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| Catalog table (public)     | thumb · title · year · area · type · collection · status | thumb · title + sheet no. · year · series · institution          |
| Catalog table (staff)      | same                                        | the public columns plus status and type                                |
| /explore rail              | pick · year · title · type                  | pick · year · title + sheet no. · series                               |
| Facets                     | area, type, series (catalog only), period — inside a collapsed disclosure | series (top level, rail too), year range + histogram, institution; area only on the plans view |
| Surveys / Plans & other    | –                                           | a segmented switch; Area applies to _Plans_ only                       |
| Drawer                     | every field arrives with the row            | long fields (description, rights, shelfmark, physical description) load on open |

- **Year range, not six buckets.** The six hand-written `PERIODS` lump two decades into one or two
  buckets. A two-handle range over `year` with a small histogram (78 distinct values; counts per
  decade) replaces `passPeriod`. Keep `PERIODS` only if the command palette or another caller reads
  it — grep before deleting.
- **Sheet number beside the name** disambiguates the 23 repeated titles. The list row needs the
  column, which `FULL_MAP_COLUMNS` lacks today (see `map-json-to-columns`). Add `sheet_number` and
  `sheet_half` to the list columns _first_, before `extra_metadata` is dropped.
- **The series facet already matches `series_key`** (`matchesSeriesFacet`), so it is ahead of the
  ROADMAP's wording; `seriesIndex.ts` still matches `maps.collection` — `series-identity` closes
  that, not this item.
- **Rail overlap.** `ArchiveBrowser.svelte` is edited by other work in flight; rebase before touching.

Tests: add pure checks for the year-range filter and the plans/surveys split; update
`docs/testing.md` and the test count in `CLAUDE.md` (it appears in `CLAUDE.md` more than once).

Exit: no public column in the table or the rail is a single value.

## `catalog-local-search`

New `src/lib/features/shared/localSearch.ts` (pure, with a check), wired into
`createCatalogSearch`.

- **Index.** One lowercased, accent-folded haystack per row from the fields `search_vector` covers:
  `name`, `original_title`, `creator`, `publisher`, `holding_institution`, `collection`, `location`,
  `shelfmark`, `date_label`, `year`, `sheet_number`.
- **Fold.** NFD, strip combining marks, and `đ → d`, on the query and the haystack alike — so `hue`
  finds `Huế`, which the server's `simple` config cannot.
- **Match.** Split the query into tokens; every token must be a word-prefix of the haystack
  (`192` finds 1920–1929, `hano` finds Hanoi, `1920s` folds to `192`). A query shaped `\d{4}-\d` is
  an exact sheet-number match — that rule moves here from the server.
- **Order.** Same as the empty-query table (year, then name). The server's "rank order" comment is
  not true today — the query orders by `id` — so nothing is lost.
- **Labels and places stay on the server**, as a separate debounced call that fills `labels` without
  holding up the maps list. The command palette's `fields=slim` path is unchanged.
- **Library.** None at 1,038 rows. MiniSearch only if typo tolerance is asked for.

Exit: typing never waits on the network for the maps list.

## `map-region-from-bbox` — done 2026-10-05

Built as below with three changes: two columns (`region`, 63 provinces; `region_2025`, 34), the province is the one under most of a 7×7 grid over the `bbox` rather than the centroid, and a sheet with more neighbouring-country land (Cambodia, Laos, China) than Vietnamese is left null. 928 of 1,499 rows labelled, 816 of 1,038 public.

Migration `109_map_region.sql` (the head is 108; re-check when this starts) adds nullable
`maps.region text`, plus a script in `scripts/` that fills it from the `bbox` centroid using province
boundaries. Rules:

- **Confirm `bbox` is lng/lat first** — it is `number[]` and the type does not say.
- The label is a **modern province name**, a locator, not the historical name; a 1791 plan of
  Gia Định is still labelled by today's province. Say so on the page.
- Leave `region` null when one province cannot describe the map (the 4 "regional" maps, a
  country-sized `bbox`). Set the width threshold after looking at the distribution.
- The script writes through the service role and takes the repo's apply-flag convention
  (`scripts-apply-flag`); dry-run by default.
- After the migration: regenerate `src/lib/data/supabase/types.ts`, bump the head note in
  `CLAUDE.md` and `supabase/CLAUDE.md`, add `region` to the list columns.

Exit: every public map with a bounded `bbox` has a `region`, and the Area facet reads it.

## `map-json-to-columns`

**Built 2026-10-05.** `source_archive` was not `holding_institution`'s twin but its complement: 'PCL' on exactly the 510 rows with none (the L7014 scripts also write 'TTU'), so it stays a JSON tag and the PCL value is copied across. `edition` became a column (mig 110). `mirrors_original_for` was not in the plan and is still a JSON filter.

- Read `sheet_number` from the column in `api/search/+server.ts` (or drop the branch once local
  search owns it) and stop writing the JSON copy; same for `sheet_half`. Writers: `mapFields.ts`,
  `MapEditModal.svelte`, `mapEditPayload.ts`, the ingest scripts.
- Promote `edition` and `source_archive` to columns. **Check `source_archive` against
  `holding_institution` first** — 510 rows have one and 510 lack the other, which may be the same
  set; if so it is a rename, not a new column.
- Collapse `LIST_COLUMNS` (`data/maps/service.ts`), `FULL_MAP_COLUMNS` and `SLIM_MAP_COLUMNS`
  (`api/search/+server.ts`) into one shared constant. A `catalog_list` view only if that drifts again.
- Do not touch `created_by` or `printing_id`.

Exit: no filter or sort in `src/` reads `extra_metadata`.

## Order

1. `georef-flag-one-meaning` (existing) — and `catalog-list-speed` steps 1–3, which share no files.
2. Add `sheet_number`/`sheet_half` to the shared list columns (first slice of `map-json-to-columns`).
3. `catalog-list-speed` step 4, once the readers are checked.
4. `catalog-columns`.
5. `catalog-local-search`.
6. `map-region-from-bbox`, then wire the Area facet to it.
7. Rest of `map-json-to-columns`.

## How to check it

Every item is judged against the same probe, re-run before and after:

- `curl -s -o /dev/null -w '%{time_starttransfer} %{size_download}' -H 'Accept-Encoding: gzip'
  'https://maparchive.vn/api/search?include=maps&limit=5000'`, twice, plus
  `curl -sI` for `cf-cache-status`;
- a Playwright run of `/catalog` that records: time to the first and last row, DOM node count,
  long-task durations, time for a typed query to settle, and the sort/grid switch times;
- the public-column fill and distinct counts above, from the anon key.

The probe scripts were written in a session scratchpad and are not in the repo; if the numbers are
to be tracked over time, add them as `scripts/catalog_probe.mjs`.

## Risks

- **The cache hides a publish for up to 5 minutes.** Accepted; staff responses stay uncached, so
  editors see their own change at once.
- **Local search sees only the rows the API returned.** For a reader that is every public map; for
  staff it includes drafts. If the archive passes the 5,000-row fetch limit, this stops working —
  `FETCH_LIMIT` in `catalogSearch.ts` is the ceiling to watch.
- **Region labels are modern.** A historical map filed under a modern province can mislead if the
  page does not say so.
- **The Cloudflare caching assumption held (2026-10-05, live).** `cf-cache-status` still reads
  DYNAMIC, because the Cache API sits inside the Function, but a repeat request carries a rising `age`
  and answers in 0.3–0.4 s (was 2.4–3.3 s), 112 kB gzipped. The `X-VMA-Cache: HIT` label does not
  survive the hit path, so read `age`; a URL not seen before shows `MISS`. The snapshot fallback was
  not needed. `/catalog` after the change: 100 rows and ~1,430 DOM nodes (was 1,038 rows, 15,350
  nodes); typing "hue" settles in under 100 ms and finds `Huế`.
