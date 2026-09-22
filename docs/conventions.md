# Conventions — the long form

The reasoning behind the one-line rules in `CLAUDE.md` and `src/lib/CLAUDE.md`. Moved out of the
root file (Sept 2026).
Verbatim: fonts, the gazetteer key, the generated Supabase types, the realtime stub, and the whole
component/theme vocabulary.

## Fonts

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

## The gazetteer key

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

## Supabase types

- `src/lib/data/supabase/types.ts` is current against migration head 086
  (`series_sheets.year`/`.edition` from 086 — regenerated from the linked project after the push, a
  clean six-line diff across Row/Insert/Update and nothing else). Was current against 085
  (`map_series.survey_sheets` from 084; 085 changes only a check constraint, which the types do not
  carry). The column was hand-typed before the push — `check` fails without it — and regenerating
  after the push produced a **zero-line diff**, which is the cheapest confirmation that a hand edit
  matched the generator. Was current against 082 (`map_series` plus `series_key`, regenerated from
  the linked project after the push — the view and the function and nothing else, so nothing
  drifted). Was current against 081 (`place_names.core_key` plus
  `place_core_key`/`place_generic_words`). One trap if you reach for `--local` instead: the local
  stack image emits an older template and churns ~30 unrelated lines of scaffolding that have
  nothing to do with the schema. Was current against 078 (`label_w`/`label_h` from 076;
  `global_xi`/`global_yi`, non-null `global_x`/`global_y` and `set_triage_key` from 077;
  `scout_candidates.review_note` from 078). 076, 077 and 078 are all pushed, and the file was
  regenerated from the linked project — the earlier note that 076/077 were unpushed and 077
  hand-applied is stale. It had drifted: the file still declared `legend_submissions`,
  `map_help_requests`, `metadata_submissions` and `story_progress` long after 075 dropped them,
  because nothing regenerates it automatically — do it after every push. Prefer the real types over
  `as any`; ~25 casts remain, mostly in Svelte components.
- The generic belongs on the client: `createClient<Database>(...)`. A bare `createClient(...)` is
  what forces most `as any` casts downstream.
- **Realtime is stubbed out of the browser bundle.** Nothing in `src/` calls `.channel()` or
  `.subscribe()`, but `SupabaseClient`'s constructor builds a `RealtimeClient` regardless, and the
  root layout builds a client on every route — so the phoenix + websocket stack was riding along on
  the front page, the catalogue and the blog. `vite.config.ts` aliases `@supabase/realtime-js` to
  `src/lib/data/supabase/realtimeStub.ts`, which satisfies the constructor and throws on anything
  else. The root layout chunk went 65.3 kB → 48.4 kB gzipped (238 kB → 181 kB raw) on **every**
  page. The alias needs an absolute path (`fileURLToPath`): a `/src/...` string builds fine but the
  dev server's esbuild dep-optimiser reads it off the filesystem and dies with `Cannot read file`.
  The day a real `.channel()` appears, the alias and the stub both come out.

## Component vocabulary

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
replays the stored value before first paint, so a reader on dark never sees a light flash.

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
`var(--token)`. New pages use the template in `docs/design-system.md`; nav and footer come once from
`src/routes/(editorial)/+layout.svelte`, so a new editorial page only needs the links added in
`src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`.

**The top bar is two tiers.** `Catalog · About · Blog` sit in the bar itself; every tool is behind
one `Tools ▾` menu, which also carries the staff rows (`/scan?mode=shapes&tab=validate` and
`/admin?tab=status` for mod, `/screens` for admin) and ends with `All pages → /directory`. The staff
rows need a role, and `ui` may not import `data`, so `(editorial)/+layout.svelte` resolves it once
with `fetchUserRole` and passes `role` to `NavBar` — the same reason `CommandPalette` gets it from
the root layout.
