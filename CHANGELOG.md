# Changelog

Vietnam Map Archive. The app deploys continuously to Cloudflare Pages, so a
version here is a marker rather than a build: the number goes up when something
structural changed — a rewrite, a new data layer, a re-cut of the routes — not
on a schedule.

**The numbering is not invented.** The first app labelled itself `v1`, `v2
stable` and `v2.1` in its commits; this repository's early commits label
themselves `v1` through `v3.3`, and there is a `VMA_v3.2` snapshot repo to
match. So the hand-drawn HTML app keeps **1.x–2.x**, the SvelteKit rewrite keeps
**3.x**, and everything after that continues from `v3.3` — the last number
anyone wrote down.

Versions 6.0, 7.0, 7.1 and 7.2 are written out in full, because that is the
architecture that exists today. Everything earlier is summarised; the detail is in `git log`,
and most of it has been replaced.

The plain-language version of this file is published at
[maparchive.vn/changelog](https://maparchive.vn/changelog); its source is
`src/routes/(editorial)/changelog/releases.ts`. Add a release to both.

Raw history: `git log --reverse --format='%ad %s' --date=short`.

| Version | Date | In one line |
|---|---|---|
| [7.2](#72--september-2026) | Sept 2026 | A survey is one thing: 514 sheets on the map as two layers, and a page for every sheet a survey contains, held or not |
| [7.1](#71--september-2026) | Sept 2026 | The scan tools renamed after what they do, and split by the job in front of you |
| [7.0](#70--september-2026) | Sept 2026 | Sixteen pages instead of twenty-three, one design system with dark mode, a front page that costs nothing, and OCR that can measure itself |
| [6.0](#60--august-2026) | Aug 2026 | A job queue and a worker, layered source, status transitions inside Postgres |
| [5.2](#52--june-2026) | Jun 2026 | `/explore` and `/trip` |
| [5.1](#51--may-2026) | May 2026 | One layer stack, a mobile viewer, bulk upload and scout |
| [5.0](#50--april-2026) | Apr 2026 | Route groups, `MapShell`, a unified catalogue, the OCR pipeline |
| [4.1](#41--march-2026) | Mar 2026 | Admin pipeline, blog, the first vectorization |
| [4.0](#40--february-2026) | Feb 2026 | Supabase, accounts, stories — the map became a platform |
| [3.4](#34--january-2026) | Jan 2026 | View modes, core modules pulled apart |
| [3.3](#33--december-2025) | Dec 2025 | Undo/redo, shareable links, the trip page |
| [3.0](#30--october-2025) | Oct 2025 | Rewritten in SvelteKit |
| [2.1](#21--june-2025) | Jun 2025 | A time slider |
| [2.0](#20--april-2025) | Apr 2025 | First stable public site |
| [1.0](#10--april-2025) | Apr 2025 | One `index.html` and a folder of scanned maps |

---

## 7.2 — September 2026

**Current.** The archive learned the difference between what it **holds** and
what a survey **contains**, and the gap turned out to be most of the corpus.
Two migrations, three routes, no new dependency.

### A survey is a thing now

- **`series_sheets` (mig 083)** — one row per sheet a survey contains, held or not. Status is derived from `held_by`/`source` and never stored: `held_by` set is held, `source` alone is a scan somebody has located, neither is a gap. 706 rows: L7014 627 cells (461 / 123 / 43), Indochine 79 (59 held).
- **`map_series` counts cells, not rows (084)**, and gains `survey_sheets` as the denominator. The Indochine survey holds three cells in two printings each, so /explore had been saying "56 sheets" over 53. **085** rebuilds 083's check constraint, which was null-blind and had never once fired — `held_by = 'map'` against a NULL `held_by` evaluates to NULL, and a CHECK rejects only false.
- **L7014 is one row in /explore, not two.** The pre-tiled mosaic and the nine hand-placed city sheets are complementary, not alternative: the mosaic's hole over Saigon *is* what the city sheets cover. `buildSeriesRows` folds a raster archive together with the database series it declares itself `halfOf`, so one tap adds both layers and the row reads *461 of 627 sheets*.
- **`?series=<key>`** — the counterpart of `?map=<id>`. The layer stack lives in localStorage and had no address, so a survey was not something you could send anyone. Takes either half of a folded row's key, carries no camera of its own, and is consumed once applied.

### Every sheet a survey contains has a URL

- **`/catalog/series/<key>`** and **`/catalog/series/<key>/<number>`** — 452 mosaic cells were drawable on the map and invisible in every list and every search, because they have no `maps` row. Unheld sheets get a page too, carrying `noindex`: useful to a researcher, not something to compete in search with the sheets that exist.
- **`/catalog/series`** is the index. The coverage pages had one way in — a `›` inside a full-screen tool behind `ssr = false` — so no address a crawler could follow and nothing for the command palette. It reads `map_series` rather than a hand-kept list, so a survey appears by being ingested. In `sitemap.xml` with one entry per survey, and in `paletteDestinations.ts`, which is what also puts it on /directory.
- A survey with no imported index appears in neither, because its coverage page 404s deliberately. `ams-l909` was in the sitemap for one revision, which is a crawl invitation to a 404.
- The per-sheet pages are deliberately **not** in the sitemap: the series page links all 706, and the ~200 unheld ones are `noindex`.
- Palette ties break by position in `DESTINATIONS` instead of alphabetically. "Map series" had taken the query `map` off "Map viewer" on the strength of an s preceding a v.

### IIIF derivatives that were never written

- **62 Indochine sheets 404'd every width-addressed derivative**, `?force_proxy=1` included, because the R2 worker renders nothing and they were mirrored before `tile_map.sh` grew its `full/800,` step. `MapCard` hid a failed image outright, so 56 published sheets drew nothing in /catalog's grid while the same rows drew fine in list view, which has always stepped down. Both ends fixed; 0/62 → 62/62.
- **Six L7014 drafts** were missing 400 and 200 while 800 served. 12 objects written from the tile pyramid; 31 sheets × 3 widths all serve.
- **`backfill_iiif_widths.py` could not tell "missing" from "refused".** Its probe used urllib's default User-Agent, which the edge answers with **403**, and it reads anything that is not a 200 as missing — so it reported 31 of 31 L7014 and 62 of 62 Indochine sheets as missing all three widths. Curl, same URLs, same second: 6 and 0. A real run would have rewritten 93 objects that already served, then failed its own verification pass through the same probe, so a wholly successful run and a total failure printed the same thing. One User-Agent header.
- **The status column on a coverage page had no colour to say it with**: `is-{status}` spelled a modifier that does not exist in `editorial.css`, whose tints are `.chip-green` / `.chip-yellow` / `.chip-gray`, so all 627 badges rendered as one bare pill.

### An index nobody maintains

`series_sheets.held_by` and `map_id` have no trigger and no function behind them
— the one-off importers are the only writers. The index is correct today and
goes wrong silently the first time anyone publishes a draft or georeferences one
of the obtainable sheets: the coverage page keeps drawing that cell as missing,
and its percentage is wrong by a plausible amount. `scripts/check_series_index.mjs`
joins the index to `maps` and exits 1 on a cell the index calls a gap that a
`maps` row claims, or a `map_id` pointing at a row that is gone. **It is the
detector, not the fix** — deriving those columns in a view or a trigger is still
open. Clean on production: 0 adrift, 0 dangling over 706 sheets.

Known limit, recorded rather than fixed: `series_sheets` is keyed
`(series_key, sheet_number)`, one row per cell, and the archive holds **10 cells
in more than one edition** — three with two published printings each, fourteen
years apart. The coverage page can name exactly one of them.

### Around the edges

- The front page's "Where things stand" band announces both surveys. It had said *"The last written update was in May"* four posts later, and the page said **"1791 to 1968"** twice when published sheets run to 1984.
- /about gains a count read from `series_sheets` — 520 of 706 sheets across two complete surveys — with copy saying why it must not be added to the 103 catalogued maps. Its city line is capped at four places plus a count; it had grown to thirteen.
- `maps.location` had two spellings each of Saigon and Huế, typed from an ASCII sheet title during this week's L7014 ingest. Merged, 29 distinct → 27. Data only.
- `vi.ts` is **generated** from `work/copy/translate-vi.md`; a hand edit to it survives exactly until the next regeneration, which is how `'All sheets in this survey'` went missing. Restored at source, 283 entries.

### Tests

`tests/series-sheets.spec.ts` pins what a coverage page claims — that `source` is
provenance and not possession, that the three statuses partition the survey, the
cell camera including a zero-area bbox, and the paging loop, since PostgREST caps
an unbounded select at 1000 rows silently and Cochinchine's three series are 826.
Mutation-checked: three deliberate breaks fail five of the nine. Suite 263 → 273.

### The deploy

Two `npm run build` runs in one shared worktree, a minute apart, published a
deployment missing a blog post and two images while serving every other new page
— same commit, different bytes. `build` wipes `.svelte-kit/output` before writing
it, so the loser's output is half-overwritten and the deploy that runs last
publishes whatever is on disk. Neither build log said anything; it was found by
diffing the two deployment URLs against the custom domain, and fixed by one clean
build alone.

---

## 7.1 — September 2026

`/scan` re-cut around the work rather than around the machinery
that does it. No migration, no new dependency; the whole change is which
component a URL mounts and what the panels are called.

### Modes named after the work

- `?mode=triage` → **`?mode=prepare`**: the layout pass, the neatline, the tile grid, save, queue.
- The OCR review left it and became **`?mode=text`** in its own right.
- `?mode=trace` and `?mode=review` → **`?mode=shapes`**, with `?tab=draw|segment|validate`.
- Old spellings are **aliases in the dispatcher**, not redirects — `triage`, `ocr`, `trace` and `review` all still land where they now live. An unknown mode falls through to `inspect`, which is public, so an un-aliased old link would have looked like it worked; `tests/smoke.spec.ts` asserts all six spellings.
- The switcher is the left rail's footer, beside the sheet list — the one part of the page that does not change with the mode. `digitalize/PhaseTabs.svelte` became `shared/SidebarTabs.svelte`, links or buttons depending on the row.

### Prepare and Text are one component

`DigitalizePage.svelte` is mounted for both, from one `{#if}` covering the pair,
so moving between them is a prop change rather than a remount: the OL map, the
IIIF tile source and the open sheet stay warm. Two page components would have
rebuilt the canvas every time an operator checked their crop.

### The text review is four jobs, not ten categories

- **Names · Index · Numbers · Other** (`ocr/jobs.ts`), tabs at the foot of the panel, each badged with its row count.
- The OCR category cuts across all four: the 1942 sheet's printed index alone contributed 719 `street` and 630 `institution` rows, none of them marks on the map, all in the same chip as the street names being checked. The category chips survive as a refinement *inside* a job.
- The four **partition** the loaded rows, which is what makes the counts a promise that clearing all four clears the sheet. `tests/ocr-jobs.spec.ts` holds the partition, not the four rules — a row matching two jobs is reviewed twice and one matching none is never seen, and neither looks like an error anywhere.
- Picking a job reframes the canvas on the part it reads and, over a printed block, takes the boxes down: there one rectangle covers fifty rows, so the boxes hide the table the reviewer is there to read.

### Shapes is one loop instead of three pages

Draw by hand, hand the rest to MapSAM2, check what it drew — one sheet, one
canvas, three tabs. `TracePage.svelte` and `ReviewPage.svelte` are gone;
`trace/traceData.ts` and `review/reviewQueue.ts` hold the writes. Geometry and
type edits in Validate are held until the verdict and sent with it.

### One table module instead of four

- Every sortable column header is `$lib/ui/SortHeader.svelte` — a real `<button>` in the `<th>`, with `aria-sort` on the cell. None of the four hand-rolled versions was reachable from a keyboard and none said anything to a screen reader.
- One indicator: both carets drawn, one lit, so a header keeps its width when the direction flips. /catalog had written five lines of that markup per column; the other three concatenated a text arrow into the header string.
- `tableSort.ts` moved to `core` (four tables, four features, and a feature may not import another) and absorbed /catalog's second copy. It is decorate-sort-undecorate now: the value function runs **once per row** rather than once per comparison, which mattered because `OcrSidebar`'s parses a regex and ran ~22,000 times per keystroke on a 2000-row sheet.
- Blanks sort last in **both** directions, and collation is `numeric` everywhere — `Rue 100` follows `Rue 11`. The contribute tables used to stringify a missing value, so an uncategorised row filed under "undefined", between `t` and `v`.
- `tests/table-sort.spec.ts` caught the direction bug in the first version of the blank rule.
- And then the **table itself**: `$lib/ui/DataTable.svelte`. Four tables each wrote the same fifteen lines — the scroll container, the `<table>` and its density, a `<thead><tr>` looping `SortHeader` with plain `<th>`s hand-written around it for the dot / thumbnail / actions columns, the `<tbody>`, an empty-state paragraph after it. Only the rows differed, and the rows are the point of each one, so they stay with their table and arrive through the default slot.
- A blank column is a **column** now (`{ key: 'dot', label: '', srLabel: 'Status', sortable: false }`), not a `<th>` beside the loop, so a table's header is one list read in one place, order included. Anything under the table — an empty state, a "show 500 more" button — is the `after` slot, because the four disagreed about what belongs there.
- The one catch, and it is documented in the component: a caller's scoped CSS reaches its own `<tr>`/`<td>` but not the `<table>`/`<thead>`/`<th>`, which are now `DataTable`'s. `CatalogTable` keeps a `.ct` wrapper it owns and six rules became `:global()` inside it.

### One tab strip instead of five

- `$lib/ui/Tabs.svelte`. It replaced `ChunkyTabs`, `.admin-tabs`, `MapEditModal`'s `.tabs`, both rails' hand-written `.sb-rail-tabs`, and the `.phase-tabs` the /scan sidebars had invented for a slot the rails already owned.
- Three of the five were already the same `.chip` in a flex row with a different gap. **Only one of the five said anything to a screen reader.**
- Two tones, because `.chip` and `.sb-pill` are two design systems on purpose — what is shared is the markup, the API and the semantics. A row with an `href` makes the whole strip links with `aria-current`; without one it is a real `role="tablist"`.
- `.shapes-search` folded into `.sb-search.is-compact` the same way: the same flex row, the same hairline, the same borderless input, a quarter-rem of padding apart, in the same design system. `.mo-search` — a modal class that had outlived its modal, worn last by `CatalogSidebarPanel` — went the same way, and `.sb-search` grew a third size, `.is-page`, for the full width of an editorial page. Four field designs, one left.

### The element vocabulary cut in half

- **Buttons: twenty-seven selectors across nine families → eleven.** `.btn` is an action, `.chip` is a choice, and they share one modifier vocabulary with the sidebar's `.sb-btn` / `.sb-pill`: `.is-xs/.is-sm/.is-lg`, `.is-primary/.is-danger/.is-success/.is-ghost`, `.is-on/.is-block/.is-icon/.is-disabled`.
- Four tones had been spelled three ways each — `.btn-primary` · `.chip.primary` · `.action-btn.primary-btn` — which is what made "check every button" a job nobody could finish.
- None of what went was a design: `.action-btn` was a size, `.pill-btn` was lighter chrome and nothing else, `.btn-outline` was already the default, `.tool-btn` was `.sb-btn.is-sm` in a bar already running on `--sb-*`, and `.ctrl-btn` / `.btn-icon-edit` / `.btn-icon-delete` / `.cmp-btn` were one round shape at three sizes.
- **Badges:** `.source-type-chip`, `.ocr-cat-chip` and `.essentials-pill` were each a one-file copy of `.badge-chip.is-sm` plus a tint.
- **Cards: fourteen patterns → nine.** `.post-card`, `.subscribe-card`, `.sidebar-card` and `.profile-card` were `.section-card` re-typed in four files with a different padding. It takes `--card-pad` now, plus `.is-sm` for a column of them and `.is-link` when the whole card is a link.
- `components/buttons.css` 335 → 228 lines; the stylesheets 7,429 → 7,208. The ledger of every retired name is in the header of `buttons.css`, and `tests/screens.spec.ts` fails if one comes back.

### The catalog page, top down

- **The 260px facet rail is gone and `FacetRail.svelte` is deleted.** It was a column of counted chips that cost the table a third of the page — which is why the table hid its Type and Collection columns under 800px while a filter nobody scrolled back up to touch sat in the space. All seven columns fit now.
- The three facets are the `<details class="sb-more">` disclosure `/explore` already wore (`ArchiveFilters`, given a `showSearch` prop so the page's own field stays the only search box). Honest trade: the chips were multi-select and carried counts, the selects take one value per facet and carry none. The three still combine.
- **List or grid**, a `Tabs` strip in the results toolbar, remembered in `vma-catalog-view-v1`. The grid is `MapCard` — the home page's card — so there is no second card component. Its `href` is nullable now: **null makes it a `<button>` that dispatches `open`** rather than an anchor, so a grid card opens the same detail drawer its table row does and a draft is not asked to link to a public page it has not got. `<svelte:element>` picks the tag.
- The page's search field had been styled **twice** — a 2.5px pill in the route's `<style>` over `.catalog-page .chunky-input` in the layout sheet — and the scoped copy won every conflicting property, so what actually reached the screen from the second was a box-shadow *inside* the box. It is `.sb-search.is-page` now.
- The dot-grid ground and the bordered `.state-panel` went with it: the same chrome the home page dropped in 7.0, still running on the one page that had not had the pass. A second, dead copy of the dot field sat in `components/catalog.css`, which `/catalog` does not even load.
- Filtering from the field and then pressing **Reset** used to leave the page's own box showing a query the results had stopped answering to — the store is two-way now, guarded.

### One archive list instead of three

- `ArchiveMapRows` **is the catalog table with its columns reduced**: the same `DataTable`, header and row rules, minus the four a 380px rail cannot carry, and the thumbnail in place of the pick control. /explore, the /scan rail and the catalog's own sidebar all render it.
- It had been a hand-built `<ul>` of bordered buttons, beside a *second* hand-built `<ul>` — `CatalogTableCompact`, **deleted** — doing the same job in the catalog sidebar with no two details alike: year 1rem extrabold against 0.82rem bold, title semibold-muted against regular-ink, the pick control a 32px circle against a `.btn.is-xs`. One knob is left, `rowAction`, for the one real difference: a tap means *add a layer* on /explore and /scan, *open the record* in the catalog.
- **The picture of the sheet is the button.** A plus sign says a row can be added; the scan says which sheet is being added. Still a real `<button>` with `aria-pressed`.
- Which meant a third caller for `atWidth()`, so it left `FeaturedSheet` for `$lib/core/iiif/thumbUrl.ts`. The stored `maps.thumbnail` is 800px wide; the rail draws it at 48 and the /catalog table at 96, and both had been fetching the full 800 for every row.

### /screens now has to be telling the truth

- It claimed "everything in `src/lib/ui/`" while rendering **ten of seventeen**, and its card blurb counted "twenty … four … sixteen" over a list of seven and seven. A reference nobody can trust is worse than none, because it is consulted and then believed — and while it was wrong, five tab strips were built.
- `tests/screens.spec.ts` reads the source and fails when a `ui/` component is not named on the page, when the card inventory names a selector its file no longer has, or when a retired element class comes back.
- The counts derive from the arrays. `Tabs` (both tones), `SortHeader`, `PaletteSearchField`, `CatalogGrid` and `.sb-search` (both sizes) are on the page; `NavBar` and `EditorialFooter` are named separately rather than sharing one row.

### Two files came apart

- `OcrSidebar.svelte` 928 → 673: the row is `OcrRow.svelte`, and the column geometry moved to `shapes-table.css` where the `<th>`s can reach it too.
- Story review left `/scan` for `/admin?tab=stories`. A story has no sheet and no canvas; it had been riding inside a pixel-coordinate tool it shared nothing with.

---

## 7.0 — September 2026

The month the surfaces were consolidated and the reading pipeline
got a way to measure itself. 157 commits.

### The route merge — twenty-three pages became sixteen

- The archive is one subtree (`/catalog`, `/catalog/[id]`, `/catalog/place/[name]`) instead of three sibling routes.
- `/admin` is one console with `?tab=bulk|scout|status`. Before this, `/admin` itself was a 404 — only its three children existed.
- `/explore` is the map surface, mode chosen by `?mode=browse|studio|story`.
- `/scan` is the scanned-image surface, mode chosen by `?mode=inspect|triage|trace|review`.
- Grouping by shell rather than by verb is what lets the map, the basemap and the warped sheet stay loaded across a mode change instead of being rebuilt.
- Every retired path 301s to its replacement, so old links and printed QR codes still work.
- `/directory` renders the one page index, from the same list the command palette offers.

### One design system

- A plate-tone palette taken off the sheets themselves, replacing a second cooler palette the map sidebars had been using.
- Dark mode, with four things pinned on purpose because they must not flip: yellow's ink, accent-fill text, the ink-slab footers, and the light-pinned heroes.
- The theme toggle is two states, light ⇄ dark, not three.
- One button system: emoji iconography and the blobs around it are gone; the offset shadow came off every button.
- The app is set in Google Sans with a pairing chosen to stay readable for older eyes; every label is set the way the sheet it came from set it.
- A two-tier top bar: three public links in the bar, every tool behind one `Tools ▾` menu.
- Type, colour, border and shadow all route through tokens; fifteen undefined CSS variables were repaired and the sheets deduped.

### The home page got cheap

- The header is two still images with a slider between them, and the live map moved to a section further down. Every visitor used to pay for the whole map engine to look at scenery they had not asked for.
- At rest the front page is now ~63 requests / ~0.9 MB; the live demo costs its 71 requests and 1.36 MB only if a reader scrolls to it.
- The demo's four beats — modern city, 1882 sheet warping over it, traced footprints, validated labels — play on every visit, with the sheet's footprints and labels frozen into the bundle instead of fetched.
- The header's slider sweeps by itself until the reader touches it, then stops for good. It never runs under `prefers-reduced-motion`.
- The page's data is server-rendered, so a crawler sees the catalogue and a true published count instead of a fallback number.
- Fixed: a phone could not scroll past the hero (OpenLayers' non-passive wheel listener), and the hero quoted a label count it was simultaneously capping below.

### /explore

- Split into two rails: the archive on the left, the sheet on top of the stack on the right. Both wear the same frame and share the CSS rather than copying it.
- The left rail is two tabs — All and Picked — answering to one search box, so a query narrows the layer stack as well as the archive.
- The right rail is Info / Legend / Control, with place search and My location at its crown.
- Each layer-stack row is two lines now: name and actions on top, opacity slider underneath. The name is the zoom-to button, so no press-vs-drag threshold.
- A lit legend row and the map's pulse are one thing — picking a place, or a legend entry, rings the spot instead of just moving the camera.
- "My location" finally draws where the reader is; it used to move the camera and leave no marker.
- Fixed: a share link keeps the camera it was sent with.

### /scan

- One left rail for every mode — which sheet, what is drawn over it, how far to dim the paper — so a mode change swaps the right-hand panel instead of rebuilding the page.
- Triage now proposes the whole thing and leaves a person only to agree: the layout pass adopts its own main-map region as the crop, tile priorities come from the density pre-pass, and saving is the acceptance.
- Regions survive a remount; the neatline and the regions follow the pointer.
- A sheet can be reviewed from the keyboard, one hand on the map.

### Reading the sheets (OCR)

- **A measured gate.** Runs can be scored without writing to production, with columns for diacritic retention, category, detection and the label's baseline rotation.
- **seq-v1 is the default prompt** — it passes the gate; v8 on the sequence path failed it (recall −14, char_acc −2.7) and was rejected on the numbers.
- **A sheet's printed street index is now read**, and a body pass is scored against it — free ground truth, no hand labelling.
- Two passes by default: a grid, a half-tile-shifted grid, then a vote. `passes: 3` adds a 1200 px pass for small type.
- A label is stored as its own rectangle, not just the box around it.
- Tiles are sized by ground distance rather than by pixels, so one setting means the same thing on sheets at different scales.
- A run reports what it cost.
- Fixed: the twelve faults the automated path was hiding; the row-sequence call never received the prompt the run asked for; letter-spaced street names left residue; a jittered small box was being counted as a second word; the dedupe was deleting distinct streets; a partial write looked like a finished run; a sheet with over 1000 extractions lost its tail and its counts.

### Infrastructure

- **The basemap is self-hosted** — one PMTiles archive covering Hanoi to the Mekong in R2, served off a custom domain with the build date in the key, so a rebuild cannot strand readers on stale bytes. It replaced a Saigon-only extract that left 21 of 40 sheets on bare fill.
- The fonts are self-hosted too; three render-blocking Google Fonts requests are gone, along with the Google Translate widget (~100 kB on every page for a control that never rendered).
- `info.json` is cached at the edge, and the two hosts every page needs are warmed early.
- Fixed: the mirrored tile pyramid was falling through to archive.org; thumbnails asked R2 for a size it did not have; `tile_map.sh` was dying silently on every map; the warped canvas was not cleared between frames.
- Security: the browser was being handed an unvalidated session; draft maps stopped being anonymously readable.
- Cross-feature seams are declared and lint-enforced, so one feature can only reach another through a stated public entry point.
- The dead search cluster (four components and 412 lines of CSS) and a duplicate location layer were deleted.

### Elsewhere

- Search inside the maps, a place-time index, and the period press.
- Two pages that make the system visible to its owner: `/admin?tab=status` and `/screens`.
- A published map's georeference can be reopened and corrected in one click.
- Scout gained the AGS Library, a usable image on every row, and a recorded reason instead of a score.
- Five sheets carrying NAC2 scholarship are featured.
- Copy: say what the archive is and has, rather than what it will have; the archive is of Vietnam and now says so consistently.

---

## 6.0 — August 2026

The cleanup and the queue. 74 commits, after seven quiet weeks (13 Jun → 2 Aug).

- **`src/lib` was restructured into layers** — `core → data → map → features → routes`, with `ui` as leaf primitives and `server` import-guarded — and the rule is enforced by lint rather than by review.
- ~3.1k lines of grep-verified dead code deleted; every oversized component split; server boilerplate consolidated into `$lib/server`.
- **A job queue and a worker replaced the copy-paste CLI.** Publishing enqueues work; a worker claims it. Worker keys mean pipeline machines hold no database credentials.
- **Status transitions moved into Postgres** as `security definer` RPCs, and `map_pipeline_status` became a view over the queue.
- One visibility model: `draft | public | featured`. A published map must be georeferenceable.
- Stories got a review queue; contributions got a rate limit.
- Server-rendered share page with link previews.
- OCR: level-aware label ↔ footprint join, an auto-priority tile grid from a density pre-pass, legend extraction, numbered legend points on the georeferenced map, and **the eval harness that gates core-pipeline changes on measured quality**.
- The SAM2 seed module that never existed, plus a colour pre-pass.
- Fixed: node builtins now carry the `node:` prefix, or the Cloudflare bundle publishes nothing; the build runs from a clean output dir and gates on bundle integrity; the basemap came off CARTO's keyless endpoint after it began stamping "API KEY REQUIRED" over every tile.
- Deployment: several rounds of it. The conclusion is that there is no root `wrangler.toml` — one displaces the dashboard's whole environment — and secrets resolve through `$env/static/private`, because the dynamic form does not bind on Pages.

---

## 5.2 — June 2026

`/explore` arrived with its welcome chooser, coverage lookup and guided tour, and
`/trip` with it. Catalogue search was consolidated into one shared engine.
Coverage lookup became role-aware so staff see draft maps; the admin map-edit UI
was restored in the catalogue; the "Looking up maps…" spinner stopped hanging.

## 5.1 — May 2026

The viewer was rebuilt around a single concept — one layer stack — and mobile
got a three-tab bottom bar backed by one shared drawer, after which desktop and
mobile shared components. Bulk R2 upload, one `MapEditModal` for admin edits,
holding institutions, the scout discovery pipeline, unified catalogue search with
full-text search, and a codebase cleanup pass. The basemap moved to Protomaps
with Esri satellite. `/annotate` became `/studio` and gained a keyframe
animation panel.

## 5.0 — April 2026

Six numbered phases of structural work: the trace tool, a rewritten label tool
replacing a monolith, a unified `/catalog` with admin features, `MapShell`
composability, a profile page, and route groups with the editorial UI. The OCR
pipeline and R2 mirroring landed, along with the digitalize tools, the pipeline
status API and the footprints API.

## 4.1 — March 2026

The admin pipeline, the about and blog routes, the export API, and the first
SAM-based vectorization pipeline (later superseded by MapSAM2). MGRS support for
4–10 digit references. Google login. The VWAI and CDEC experiments, cleaned out
again by the end of the month.

## 4.0 — February 2026

Supabase, accounts, migrations, PWA and mobile fixes, story publishing, the
annotation store, and the first Label Studio. This is where the map stopped
being a document and became a platform with users.

## 3.4 — January 2026

View mode controls, and the core modules pulled apart for the first time.

## 3.3 — December 2025

Annotation history with undo/redo, shareable map URLs, a responsive layout,
rotation, and the trip page. Commit `v3.3` on 16 Dec 2025 is the last version
number anyone wrote by hand; the [`VMA_v3.2`](https://github.com/lqtue/VMA_v3.2) snapshot repo was pushed the day
before it.

## 3.0 — October 2025

**Rewritten in SvelteKit**, in four days: the commits read `v1`, `v2`, `v3`,
`v3.1`, `v3.2` between 27 and 30 October 2025. Same project, second
implementation — this is the repository you are reading.

---

## Before this repository

The first two years live in separate repositories on GitHub, now read-only.
They were left where they are rather than folded in — most of their weight is
scanned images, and the history is one click away. They are where the numbering
comes from.

The 2025 site is still published at
[lqtue.github.io/VMA](https://lqtue.github.io/VMA/), with a notice pointing
here.

### 2.1 — June 2025

A time slider, so the maps could be moved through rather than picked from a
list (`v2.1 with time slider`, 17 Jun 2025). A README followed on the 21st,
setting out the vision, the phases and the volunteer roles. Last push to that
repository: 30 Jun 2025.

### 2.0 — April 2025

`v2 stable` (20 Apr 2025): a welcome screen, an instruction popup after it fades,
and a narrative track in `narrative.csv`.

### 1.0 — April 2025

[`lqtue/VMA`](https://github.com/lqtue/VMA), created 3 Apr 2025, first upload on the 12th: one `index.html`,
hand-written CSS and JS, a folder of scanned sheets as `.webp`, and web fonts.
Served from GitHub Pages at `lqtue.github.io/VMA`. 73 commits, most of them
`Add files via upload` — the maps were the content and the site was the wrapper.

[`lqtue/historical_maps`](https://github.com/lqtue/historical_maps) (25 Jun 2025) is a single `index.html` and one commit —
an experiment, not a version.
