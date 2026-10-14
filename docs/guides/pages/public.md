# Public editorial pages — system spec

Scope: `(editorial)` non-catalog pages plus shared chrome. Source: code read 2026-10-14. Repo paths are relative to the repo root. "unverified" marks anything not confirmed in code.

---

### `/` — Home
Files: `src/routes/(editorial)/+page.svelte` (748), `+page.server.ts` (94), `+page.ts` (10, comment only), `src/styles/layouts/home.css` (733); components `features/catalog/FeaturedSheet.svelte` (532), `features/explore/HeroDemo.svelte` (390), `ui/PaletteSearchField.svelte` (61), `ui/Tabs.svelte` (113), helpers `features/catalog/homeCatalog`.
- **For / job:** first-time reader and search-engine landing; they come to see what the archive is, search it, and open the map.
- **Access:** public. Signed-out sees everything but the Favorites tab and the heart buttons. `/vi` is the Vietnamese address (in `LOCALIZED_PATHS`).
- **Data:** server load via `cached(platform, 'home-v1', …, { ttl: 300, ok })` → published map count, featured series (+ one thumbnail each), four place sets (Saigon, Hà Nội, Huế, Vietnam; 12 rows each) through `adminClient()`. `ok` refuses zero counts so an outage is not cached. Header `x-edge-cache`. SSR on. Favorites + thumbnails load client-side in `onMount` through the browser Supabase client.
- **Requirements:**
  - Server-render the masthead, sheet count, series and place lists so a crawler sees them.
  - Hero is two stills cross-faded by a range slider; a sweep animation runs until the first pointer/key, never under reduced motion.
  - One search entry at a time: the hero field hands the palette job to the nav while it is in view (`pageOwnsSearch`, IntersectionObserver).
  - Catalog block has 3 tabs (Maps / Surveys / Favorites if signed in) and place chips that switch with no round trip.
  - Favorite toggle is optimistic and rolls back on failure.
  - Emit title, description, OG/Twitter card and WebSite JSON-LD; canonical and hreflang come from the root layout.
- **Layout:** `header.hero` (stills, scrim, credit line, title, subtitle, search field, "Try" links, fade slider) → `main`: Catalog section (head + Tabs, place chips, `FeaturedSheet`, "See all N", footer links + "Open the map") → `HeroDemo` (live map/video "how it works") → 4-column band (Tools, Contribute, About, Where things stand) → CTA section with second search field.
- **Interaction:** `⌘K`/`Ctrl K` caption set in `onMount`; the "Try Hanoi, Khánh Hội or 1882" buttons call `openPaletteWith`. Slider is a native range with `aria-label`. States: loading (only Favorites: "Opening the archive…"), empty (Favorites: "No favorites yet."; other: "Nothing here yet."), error (favorites failure is `console.error` only, shows empty), signed-out (no Favorites tab), mobile (stack at 640/768; band rule only ≥720).
- **i18n · a11y · mobile:** Most copy goes through `$t`. Not translated: "Try" and its joiners, "Beta", "Studio", Tabs labels ("Maps", "Surveys", "Favorites"), `Hà Nội`/`Huế` (proper names, fine). Hero stills have `role="img"` + `aria-label`; chips use `aria-pressed`. Srcset gives phones the 800px cut.
- **Findings:**
  - `+page.svelte:539-541`: Tabs labels are raw English; `Tabs.svelte` does not call `$t` — so the tab strip stays English on `/vi`.
  - `+page.svelte:492` "Try …" is hardcoded English, and the `, ` / ` or ` joiners are English-only grammar.
  - `+page.svelte:699-722` "Where things stand" copy is a hand-kept snapshot ("this week", "a week ago", `STATS.snapshot = 'September 2026'`, `:229`) — stale now (Oct 2026) and not tied to data.
  - `+page.svelte:267` `MAP_COUNT_FALLBACK = 39` is a hardcoded number that drifts from real counts.
  - `+page.ts` exports nothing; its comment is wrong ("catalog loads in onMount … server-renders as 'Opening the archive…'") — the catalog is server data now. Dead file.
  - Page does not use `PageHero` nor `.editorial-main` (own `.hero`, `.main` in `home.css`) — deliberate exception, but design-system.md says PageHero "is not optional"; the doc should name `/` as the exception.
  - `home.css:529` uses `min-width: 720px`; the design system allows only 600/640/768/900. `home.css:652` uses 768 (ok).
  - `+page.svelte:726-727` hardcoded blog link `/blog/two-map-series-2026-09` and L7014 view address; both rot silently.
  - `+page.svelte:305` `displayedMaps = favoriteMaps` is a pointless alias.
  - Component size: 748 lines, well over the 500 guide (`SKILL.md` lists it at 571); half is comments and constants.

---

### `/about` — About
Files: `src/routes/(editorial)/about/+page.svelte` (198), `+page.server.ts` (118), `src/styles/pages/about.css` (93); `ui/PageHero.svelte`.
- **For / job:** a funder, researcher or volunteer who wants an honest account of what is done and what is not.
- **Access:** public; same for signed-in readers. In `LOCALIZED_PATHS` (`/vi/about`).
- **Data:** server load: `cached(platform, 'about-v1', loadStats)` with default ttl 300 s and an `ok` guard; nine queries through `adminClient()` (published `maps` rows for years and city split, drafts, `ocr_labels` total and validated, `footprints` total and approved, `series_cells` total and held, `map_series` with an index). Sets `cache-control: public, max-age=60` on the HTML. SSR on, no prerender.
- **Requirements:**
  - Show live counts (sheets, drafts, survey sheets held, OCR names and checked, shapes and approved), never typed numbers.
  - Say plainly that survey cells and catalogue sheets overlap and must not be added.
  - State what is not built (dataset, building histories, 3D, contributors, funding).
  - List five things a reader can do today, with deep links into `/explore`, `/scan`, `/catalog`.
  - End with a mailto contact button.
- **Layout:** `PageHero` (eyebrow, highlighted title, sub) → `.editorial-main` with five `.section-card`s: Where this stands (`<dl class="stats">`), What you can do today, What is not built, How it is kept, Get in touch.
- **Interaction:** links only; no controls, no URL params. States: no loading or empty state (server data); a failed query reads as 0 and the `ok` guard keeps it out of the cache but the page still renders zeros; mobile: one breakpoint at 600 px.
- **i18n · a11y · mobile:** Section headings and stat lines use `$t`; the hero title uses `splitHighlight($t(...))`. Not translated: `<title>`, meta description, hero eyebrow and sub, the whole "What you can do today" list, and the "Get in touch" paragraph. Uses `<dl>` for stats (good). No `aria` extras needed.
- **Findings:**
  - `+page.svelte:41-42` hero `eyebrow` and `sub` are passed raw to `PageHero`, so `/vi/about` shows English hero copy. Same on every page that passes props raw (see Patterns).
  - `+page.svelte:116-138` and `:189-195`: the "What you can do today" list items and the "Get in touch" paragraph are plain English, not `$t`.
  - `+page.server.ts:8` header says "cached at the edge for an hour"; the code uses the `cached` default of 300 s. The comment at `:52` says "six queries"; there are nine.
  - `+page.server.ts:54` sets `cache-control: public` on HTML whose payload also carries the root layout's session and locale (`+layout.server.ts`); no `Vary` is set. Whether a shared cache stores it is unverified; a private-by-default value would be safer.
  - Hardcoded deep links with a map view and a series key (`+page.svelte:121-127`) rot if the series is renamed.
  - Sibling inconsistency: the only editorial page with a page-level `max-age`; the stats card here duplicates figures that `/` (`STATS`) and `/contribute` type by hand.

### `/blog` — Blog index
Files: `src/routes/(editorial)/blog/+page.svelte` (89), `blog/posts.ts` (934, the posts as data), `src/styles/pages/blog.css` (269).
- **For / job:** reader following project news and research notes.
- **Access:** public. `/vi/blog` exists (in `LOCALIZED_PATHS`) but post bodies are English only.
- **Data:** none from the server; posts import from `posts.ts` (committed module, bundled into the page JS). SSR on. No cache headers set.
- **Requirements:**
  - List posts newest first: one featured (latest) card, the rest in a grid.
  - Show category chip (colour from `CATEGORY_COLORS`), date, title, excerpt.
  - Say there is no newsletter; point to a mailto for an announcement list.
  - Posts that turned out wrong carry a dated `note` (rendered on the post page).
- **Layout:** `PageHero` (eyebrow "Field notes", title) → `main.main`: featured post link → "Earlier posts" grid of `.section-card.is-sm.is-link.post-card` → subscribe card.
- **Interaction:** whole cards are links to `/blog/<slug>`. States: empty list is not handled (`latestPost` guarded by `{#if}`, no message); no loading or error (static data); mobile breakpoint 600 px.
- **i18n · a11y · mobile:** Some chrome via `$t` ("Latest", "Earlier posts", "No newsletter", hero title). Not translated: eyebrow, sub, subscribe paragraph, `<title>`, meta, category labels (`CATEGORY_LABELS`). Dates are always `en-US` format.
- **Findings:**
  - `+page.svelte:38` uses `<main class="main">`, not `.editorial-main`; the page template in `design-system.md` says every editorial route uses `.editorial-main`.
  - `+page.svelte:7` `formatDate` hardcodes `'en-US'` and is copy-pasted in `blog/[slug]/+page.svelte:10` and `changelog/+page.svelte:15` (three copies, three formats).
  - `+page.svelte:43,62` inline `style="background: …"` for the category chip instead of a class or `style:` directive.
  - `posts.ts` (934 lines) ships every post body in the JS of both blog routes; fine today, grows with each post.
  - `+page.svelte:83` mailto for an announcement list: contradicts the "No newsletter" heading right above it.

### `/blog/[slug]` — Blog post
Files: `blog/[slug]/+page.svelte` (118), `blog/[slug]/+page.ts` (11), `posts.ts`, `src/styles/pages/blog-post.css` (549).
- **For / job:** reader of one research note or update.
- **Access:** public. Unknown slug → `error(404, 'Post not found: <slug>')`. `/vi/blog/<slug>` resolves via reroute but is not a localized path (no hreflang twin).
- **Data:** universal `load` (`+page.ts`) looks the slug up in `posts.ts`; no DB, no cache headers. SSR on.
- **Requirements:**
  - Render the post HTML (`{@html post.content}`), after an optional dated note ("Since this was written").
  - Show category, date, title, excerpt; back link to `/blog`.
  - Sidebar: project blurb, the three newest other posts, contact.
  - Footer call to action to `/contribute` and `/about`.
- **Layout:** `.layout` two columns: `article` (header, optional note, body, CTA footer) and `aside.sidebar` (three cards). No `PageHero`.
- **Interaction:** links only. States: 404 for a bad slug; no loading state; mobile: breakpoints at 900 and 600 px in `blog-post.css`.
- **i18n · a11y · mobile:** Chrome strings use `$t`; post text is English only. `<time>` has no `datetime` attribute. Single `<h1>`.
- **Findings:**
  - No `PageHero` and no `.editorial-main`; root is `.page.blog-post-page` — a second shell next to the design-system one (reasonable for an article, but undocumented).
  - `+page.svelte:40` `<time class="post-date">` lacks `datetime=`; `changelog` does set it.
  - `+page.svelte:10` third copy of `formatDate`.
  - `+page.svelte:25-28` no OG/Twitter tags and no per-post canonical beyond the root layout's; `/` has a full card block, so shared post links unfurl bare.
  - `{@html post.content}` and `{@html post.note}` (`:52,61`) rely on `posts.ts` being committed code; lint-disabled with a comment saying so. Fine today; a hard stop if posts ever come from the DB.
  - `blog-post.css` is 549 lines for one page.

### `/changelog` — Version history
Files: `src/routes/(editorial)/changelog/+page.svelte` (142), `changelog/releases.ts` (246), `src/styles/pages/changelog.css` (167).
- **For / job:** reader who wants a plain-language list of what changed, version by version.
- **Access:** public; `/vi/changelog` exists.
- **Data:** none from the server; `releases` array is a committed module. SSR on, no cache headers.
- **Requirements:**
  - List releases newest first; mark the current one "Running now".
  - Show an optional screenshot (two versions have one) with a 600/1200 srcset.
  - Put the three legacy versions in their own card with a link to the old repository.
  - Say why most versions carry no screenshot.
- **Layout:** `PageHero` → `.editorial-main`: `<ol class="releases">` (mark column: version, date, "Running now"; body column: headline, change list, figure) → note paragraph → legacy `.section-card` with a second `<ol>`.
- **Interaction:** read-only; the external link opens in a new tab with `rel="noopener"`. States: none needed; mobile: one breakpoint at 700 px.
- **i18n · a11y · mobile:** Chrome via `$t`; hero eyebrow/sub, the legacy paragraph, and all release text are English only. `<time datetime>` set; `<img>` has `alt`, width/height and lazy loading.
- **Findings:**
  - `+page.svelte:10-13,32` and `<style>` at `:133`: the page still uses the old `mounted` + `onMount` fade (`.page { opacity: 0 }` until JS runs). `design-system.md` says this was removed; `.page` in `editorial.css:208` already fades by CSS. Here the local rule hides the server-rendered page until hydration and double-animates.
  - `changelog.css:111` breakpoint 700 px is not one of the four allowed.
  - The `<li>` markup for a release is duplicated between the main and legacy lists (`+page.svelte:46-83` vs `:97-125`); one `ReleaseItem` would remove ~30 lines.
  - `formatDate` uses `{year, month}` while blog uses a full date (see `/blog`).

### `/contribute` — Contribute hub
Files: `src/routes/(editorial)/contribute/+page.svelte` (172, with a local `<style>`); no stylesheet in `src/styles/pages/`.
- **For / job:** a would-be volunteer picking a task: prepare, trace, georeference; staff see extra tools.
- **Access:** public page, no redirect and no gate. Signed-out readers see the three public cards; the targets (`/scan?mode=…`) gate themselves (unverified, not read here). Staff cards appear for `role` `admin` or `mod`. In `LOCALIZED_PATHS` (with `/contribute/georef`).
- **Data:** no server load. Client `onMount` reads the role from `profiles` through the browser Supabase client (`fetchUserRole`). SSR on; no cache headers.
- **Requirements:**
  - Offer three entry cards: Prepare a sheet, Trace buildings, Georeference a map.
  - Show three extra cards to staff only: Place the legend, Review footprints, Catalog metadata.
  - Say what the work is worth: counts of names waiting and shapes traced.
  - Keep the whole card a link with a call-to-action label.
- **Layout:** `PageHero` (eyebrow, highlighted title, sub) → `.editorial-main` → `section.contribute-grid` (auto-fill, 340 px min) of `a.section-card.card-link`.
- **Interaction:** cards are links; hover lifts the card. States: staff cards pop in after the role fetch (flash on load); no loading, empty or error state; mobile: grid collapses by `minmax(340px,…)`, no media query.
- **i18n · a11y · mobile:** Card text through `$t`; hero eyebrow and sub raw English; `<title>`/meta raw. Cards are anchors with visible headings (good). A 340 px minimum can overflow a 320 px phone minus gutters (unverified).
- **Findings:**
  - `+page.svelte:46,60`: "Around 950 distinct names … 43 checked" and "46 shapes" are typed into `$t` keys and drift from `/about` (live) and `/` (`STATS`: 958/43/46); a change in count orphans the Vietnamese key.
  - `+page.svelte:130-136` `:global(body) { … }` re-declares the body reset on a single page; it leaks to every page after client navigation. Same block in `contribute/georef/+page.svelte:193`.
  - `+page.svelte:154-157,167` hand-rolls the `.section-card.is-link` hover lift and a raw `font-size: 0.875rem`; `design-system.md` says to use `.is-link` and tokens.
  - `+page.svelte:12-15` a third role fetch (root layout, editorial layout, page) for the same user; no shared store.
  - `.mod-card` / `.catalog-card` hover borders pick green and purple for no stated meaning.
  - Hero says "Anyone with an account can contribute" but the page has no sign-in prompt for a signed-out reader.

### `/contribute/georef` — Georeference a map
Files: `src/routes/(editorial)/contribute/georef/+page.svelte` (308, with ~110 lines of local CSS); data helper `src/lib/data/maps/georef.ts`.
- **For / job:** a volunteer who picks an unplaced scan and opens it in the Allmaps Editor; staff re-open an existing georeference to fix it.
- **Access:** public page, no gate. Signed-out readers can see the queue if RLS allows draft reads for anon (unverified). The fix list loads only for `admin`/`mod`. Localized (`/vi/contribute/georef`).
- **Data:** no server load. Client `onMount`: `fetchGeorefQueue` (`maps` where `status='draft'`, ordered by priority then name) and the role from `profiles`; staff also `fetchGeorefFixList`. All through the browser Supabase client. SSR renders the loading card only.
- **Requirements:**
  - Explain the three steps (open in Allmaps, 3+ control points, save).
  - List draft maps that still need georeferencing, with a count and a button to the Allmaps Editor (new tab).
  - For staff: list georeferenced maps with a name/year filter and a "Fix in Allmaps" link; mark pipeline-made and source-less maps instead of offering a link.
  - Not need a submit step: the archive reads finished maps back from Allmaps.
- **Layout:** `PageHero` (eyebrow slot is a back link "← Contribute") → `.editorial-main`: How-it-works card, then loading card or Needs-georeferencing card, then (staff) Fix card with search input and list.
- **Interaction:** one text filter (`fixSearch`, case-insensitive name or year). States: loading (custom `.state-card` with `.spinner` and "Loading maps…"), empty ("Every map is georeferenced…"), no results ("No georeferenced map matches."), signed-out (as public), mobile (names truncate with ellipsis; no media query).
- **i18n · a11y · mobile:** Mostly `$t`. Raw English: hero sub and back link, step 1 text, fix-help paragraph, `aria-label="Find a georeferenced map"`, the `title` on "no source", the "draft" badge, `<title>`/meta. Search input is `type="search"` with an aria-label. Rows are `<li>`; no focus styling beyond defaults.
- **Findings:**
  - `+page.svelte:20-32` + `data/maps/georef.ts:84-87`: a failed query returns `[]` after a `console.error`, so the page says "Every map is georeferenced." on an outage. No error state.
  - `+page.svelte:90-93` hand-rolled `.state-card` loader instead of `.empty-state` / `.spinner` from `feedback.css`.
  - `+page.svelte:193-198` `:global(body)` reset (see `/contribute`).
  - `+page.svelte:178-181,209-222,297` colour/opacity and font sizes written by hand (`font-size: 0.9rem`, `opacity: 0.5/0.6/0.75`) instead of tokens; ~110 lines of local CSS where `src/styles/pages/` is the house place.
  - `+page.svelte:75` step 1 mixes untranslated words with a translated label, which cannot be translated as a sentence.
  - `+page.svelte:59` `.chip-back` is a one-off back link; `PageHero` has no `back` prop, and `blog/[slug]` uses `.back-link` instead.

### `/directory` — All pages
Files: `src/routes/(editorial)/directory/+page.svelte` (146, local CSS); list from `src/lib/features/shared/paletteDestinations.ts` (266).
- **For / job:** reader who wants every page in one list instead of the two-tier menu.
- **Access:** public page. The list is gated by role (`destinationsFor(role, signedIn)`): `anyone`, `member`, `mod`, `admin`. Hidden rows are counted in a footnote.
- **Data:** no server load. `fetchUserRole` runs in `onMount` through the browser client; the destinations are a static array shared with the command palette. SSR on, no cache headers.
- **Requirements:**
  - Show the same destinations the palette offers, in six groups (Browse, Make, Contribute, Read, Account, Staff), minus `/directory` itself.
  - Hide what the reader cannot open; say how many are hidden and, if signed out, link to sign in.
  - Each row: label, hint, and (desktop) the path.
- **Layout:** `PageHero` → `.editorial-main` → one `.section-card` per non-empty group → `ul.dir-list` of grid rows (label | hint | path) → optional note.
- **Interaction:** rows are links; hover fills ochre. States: signed-out (public rows + note with sign-in link), staff (extra rows after the role fetch), loading (none shown), empty (cannot happen), mobile (<= 640 px rows stack, path hidden).
- **i18n · a11y · mobile:** Hero title via `$t`; eyebrow, sub, group names, every label and hint, and the footnote are raw English. Rows are plain anchors; one `<h2>` per group.
- **Findings:**
  - `+page.svelte:18,32,74-80`: `role` starts `null` and resolves in `onMount`, so a signed-in admin first sees the member list and a footnote "N pages are not listed because this account cannot open them", which then vanishes. The layout already holds the role; this page re-fetches it.
  - `+page.svelte:58,64-65` and `paletteDestinations.ts`: group names, labels and hints never pass through `$t`, so `/vi/directory` and the Vietnamese palette show English page names. Keys such as "Version history" exist in `vi.ts` because NavBar/footer translate them separately.
  - `+page.svelte:76-78` plural/pronoun grammar built from English ternaries; cannot be translated.
  - `paletteDestinations.ts` lists `/contribute/georef` as `member`, but that page has no gate and works for anyone; the list and the page disagree.
  - Not listed anywhere: `/login`, `/catalog/*` below `/catalog/institutions`, `/blog/<slug>`; `/screens` and `/admin?tab=stories` appear only for staff.
  - `+page.svelte:88` `:global(.section-card-header)` scoped under `.directory-page` — fine, but a `.section-card` without header would need no override.

### `/login` — Sign in
Files: `src/routes/(editorial)/login/+page.svelte` (146), `+page.server.ts` (17); `src/routes/auth/callback/+server.ts` (return path).
- **For / job:** a reader who wants to save favorites or contribute; one button, Google only.
- **Access:** public. A signed-in user gets a 303 to `/` (server load). Page is `noindex`. Not in the palette or directory; reached from NavBar ("Sign in"), `AuthGate`, `FavoriteButton`, `/trip/[id]`.
- **Data:** server load only checks `safeGetSession()`. Sign-in is client-side `signInWithOAuth({ provider: 'google', redirectTo: <origin>/auth/callback })`. SSR on.
- **Requirements:**
  - One Google button, disabled while the redirect starts.
  - Show the provider error message if the call fails.
  - State what signing in is for and that contributions are released as CC-BY open data.
  - Admins and mods without MFA level 2 are sent to `/profile` by the callback.
- **Layout:** `.page.auth-page` centered `main.auth-card`: `h1` "Sign in", optional error box, button with Google logo, notice. No `PageHero` (deliberate, commented).
- **Interaction:** one button. States: idle, loading (button disabled, no spinner), error (raw `authError.message` in `.auth-error`, English from the provider), signed-in (redirected), mobile (card is `width: 100%`, max 400 px; no media query).
- **i18n · a11y · mobile:** Title, button and notice via `$t`; `<title>` raw; provider error raw. Error box has no `role="alert"`, so a screen reader does not hear it. The Google logo SVG has hardcoded brand fills (documented exception in the design system).
- **Findings:**
  - `+page.svelte:14-19` ignores `?next=`. `routes/(app)/trip/[id]/+page.svelte:121` sends `/login?next=/trip/<id>` and `auth/callback/+server.ts:8` reads `next`, but the login page never passes it in `redirectTo`. A reader sent here from a trip lands on `/` after sign-in. Also, `/profile` redirects here with no `next`.
  - `+page.svelte:5` `session` is destructured and never used.
  - `+page.svelte:40` error box has no `role="alert"`/`aria-live`.
  - `+page.svelte:100,136-144` font sizes and `opacity: 0.6` on `.auth-notice` written by hand (`0.75rem`, `2.25rem`) instead of tokens.
  - `AuthGate.svelte:15` repeats the same `signInWithOAuth` call; two copies of the OAuth redirect logic.

### `/profile` — Your profile
Files: `src/routes/(editorial)/profile/+page.svelte` (158), `+page.server.ts` (26), `src/styles/pages/profile.css` (175); `features/account/MfaPanel.svelte`.
- **For / job:** a signed-in reader checks their account, counts, language; staff reach their tools and set up MFA.
- **Access:** signed-in. No session → 303 to `/login`. `noindex`. Staff block (MFA panel, staff links) only when `role` is `admin` or `mod` (role read server-side).
- **Data:** server load: `safeGetSession`, then `profiles.role` through `adminClient()` (no cache). Client `onMount`: two head counts (`label_pins`, `footprints` by `user_id`) through the browser client. SSR on.
- **Requirements:**
  - Show avatar (or initials), name, email, role badge, and a Sign out button.
  - Show contribution counts: pins placed and buildings traced.
  - For staff: MFA panel and five links to staff pages.
  - Toggle language between English and Tiếng Việt (cookie, no reload).
- **Layout:** `PageHero` → `.editorial-main` → one `.section-card.profile-card` holding header row, stats, (staff tools), preferences.
- **Interaction:** Sign out (`signOut()` then hard navigate to `/`), language chip. States: loading ("Counting…" pulse), error (stat failure is `console.error`; counts stay 0 with no message), signed-out (redirect), mobile (no media query in `profile.css`).
- **i18n · a11y · mobile:** Most strings via `$t`. Raw: hero eyebrow and sub, "System status", "Scout review", "Bulk upload". The only language switch in the whole app lives here, behind sign-in. Avatar `alt` is the display name. Role badge shows `role.toUpperCase()`.
- **Findings:**
  - `+page.svelte:151` flag emoji in the language chip; `design-system.md` bans emoji in chrome.
  - `+page.svelte:17-28,34` `user`, `role`, `avatarUrl` are `const` from `data`, so they do not update if the load re-runs (`invalidate('supabase:auth')` runs on token refresh); should be `$:`.
  - `+page.svelte:30,55` `reviews` is tracked and always 0; never shown. Dead field.
  - `+page.svelte:57-59` count failure shows zeros as if real.
  - `+page.svelte:131-135` staff link labels hardcoded English; the list differs from `paletteDestinations.ts` (no Story queue; there Bulk upload, Scout and Design system need `admin`, here `mod` sees them too) and from NavBar's staff rows.
  - No way to switch language for a signed-out reader except typing `/vi` (see Shared chrome).
  - `profile.css` has no `@media`; header row (avatar + info + button) wrapping on a phone is unverified.

### `/screens` — Design system gallery
Files: `src/routes/(editorial)/screens/+page.svelte` (911), `src/styles/pages/screens.css` (238); also pulls `pages/admin-status.css`; checked by `tests/screens.spec.ts`.
- **For / job:** whoever builds UI; shows every token and `src/lib/ui` component from fixtures.
- **Access:** public URL with no gate (no server load, no redirect); `noindex`. Linked only for admins (NavBar "Design system", palette role `admin`, profile staff links, which also show it to mods).
- **Data:** none. Fixtures in the file; swatch values read with `getComputedStyle` in `onMount`. SSR on.
- **Requirements:**
  - Show colours (live values), type, shadows, radii and borders.
  - Show every component in `src/lib/ui` (a test fails if one is missing).
  - Keep a card inventory (global vs page-locked), and the status tones.
  - Never touch the database.
- **Layout:** `PageHero` → `.editorial-main` → `Tabs` (Tokens, Parts, Components, Cards) → one `{#if tab === …}` block per tab of `.sc-section`s.
- **Interaction:** four tabs held in a local `tab` variable (not in the URL); demos for rename, dialog, sort header, tab tones, location search. States: signed-out and signed-in render identically; mobile breakpoint 640 px.
- **i18n · a11y · mobile:** English only (no `$t`), acceptable for a staff page. `Tabs` has a label. Many demo buttons are unlabeled by design.
- **Findings:**
  - `+page.svelte:92` the type table says `--text-base` is `1rem`; `tokens.css:110` makes it `1.0625rem`. The reference page is wrong about its own system.
  - `+page.svelte:50` the active tab is not in the URL (`?tab=`), unlike `/admin`; a link to "Cards" is impossible.
  - 911 lines, the largest editorial page; the Components tab alone is `:444-815`. Could split per tab.
  - `docs/guides/design-system.md:268` names `ChunkyTabs`, which is now `Tabs`; and `design-system.md` "Page template" still shows the `mounted` boolean that `/screens` (`:245-255`) says was removed. The doc contradicts the page.
  - `/screens` is publicly reachable but described as staff-only in nav; harmless (no data) but the gate and the link disagree.

---

## Shared chrome

### `(editorial)/+layout.svelte` — editorial shell
Files: `src/routes/(editorial)/+layout.svelte` (25); root `src/routes/+layout.svelte` (248), `src/routes/+layout.server.ts` (20).
- **For / job:** puts `NavBar`, the page slot and `EditorialFooter` around every `(editorial)` route (catalog pages included).
- **Access:** all visitors. The root layout server load returns `{ session, user, locale }` from `safeGetSession()` for every route.
- **Data:** root: validated session built field by field; locale from `locals.locale`. Editorial layout: `fetchUserRole` in `onMount` once, to feed `NavBar`.
- **Requirements:**
  - Mount nav and footer once; a page never renders them.
  - Pass `session` and `role` to `NavBar` (`ui/` may not import `data/`).
  - Root layout adds canonical and hreflang for every page, the command palette, the consent banner, the `/` and `⌘K` shortcut, the service worker, and measurement.
- **Layout:** `NavBar` → `<slot />` → `EditorialFooter`; palette and consent banner are mounted by the root layout after the slot.
- **Interaction:** `/` opens the palette unless the target is an input; `⌘K`/`Ctrl K` always. `data-hydrated` is set on `<html>` after mount for tests.
- **i18n · a11y · mobile:** locale is set synchronously from `data.locale` (`$: locale.set`); `<html lang>` is filled by `hooks.server.ts`. No skip-to-content link anywhere in the shell.
- **Findings:**
  - `+layout.svelte:15-18` role is read once in `onMount`, so it is never refreshed after an auth change. The root layout runs its own `loadRole` (`routes/+layout.svelte`), and `/contribute`, `/contribute/georef`, `/directory` run a third. One role, three queries; share it through the existing context or `$page.data`.
  - Role is `null` until it lands, so staff rows pop in late on every full page load (by design, "safe direction").
  - No skip link and no `<main>` in the shell; each page supplies its own `<main>` (some use `<div class="main">`).
  - Root `+layout.svelte` is dense (consent, measurement, auth sync, canonical); fine for a root but over the size guide.

### `NavBar.svelte` — top bar
Files: `src/lib/ui/NavBar.svelte` (631), `ui/NavDropdown.svelte` (125), `src/styles/components/editorial.css`, `nav-buttons.css`.
- **For / job:** site-wide navigation: read pages in the bar, every tool behind `Tools ▾`.
- **Access:** all; staff rows (legend, review queue, admin console) for `admin`/`mod`; "Design system" for `admin` only. Signed out: "Sign in" ghost button; signed in: avatar pill → `/profile`.
- **Data:** none; props `session`, `role`. Theme from `$lib/core/utils/theme`.
- **Requirements:**
  - Bar: logo, `Catalog ▾` (All maps, Institutions), About, Blog, `Tools ▾`, search opener, theme toggle, "Open the map", sign-in or avatar.
  - One page lights one item (`startsWith` on the path).
  - Search opener hides (opacity 0, `tabindex -1`) while the home hero field is in view.
  - "Open the map" goes quiet on `/` so the hero stays the loudest thing.
  - At <= 640 px the hamburger opens a drawer with a flat list.
- **Layout:** left logo, centre links, right utilities (search, theme, CTA, auth); mobile: logo + hamburger, drawer slides in with overlay.
- **Interaction:** Escape closes dropdown and drawer; click outside closes the dropdown; `title="Search (⌘K)"` on the opener; theme toggle cycles light/dark and stores `vma-theme`. States: signed-out, staff, drawer open; `aria-expanded` on hamburger and dropdown trigger.
- **i18n · a11y · mobile:** Mostly `$t`. Raw English: dropdown label "Tools" (`:132`), "Studio" (`:137`, `:316`), "All pages →" (`:174`), `title="Search (...)"` (`:185`). Drawer has `role="dialog" aria-modal`. Breakpoints used: 640 and 900 (both in the allowed set).
- **Findings:**
  - `:70,96-99` `isHome` and the active-item tests read `$page.url.pathname`, which keeps the `/vi` prefix (reroute does not rewrite `url`). On `/vi` the quiet CTA does not apply, and on `/vi/about` or `/vi/blog` no nav item lights up. `stripLocale` is not used here.
  - All hrefs are unprefixed (`/about`, `/catalog`…); nothing in the nav, footer or palette calls `withLocale`. A reader on `/vi/about` clicks Blog and lands on English unless the `vma-lang` cookie is set; only `/profile`'s toggle sets it. See Patterns.
  - `NavDropdown.svelte:75` `role="menu"` on a panel of plain `<a>` items without `role="menuitem"` and with no arrow-key handling; an ARIA menu promises both. Also a link click inside the panel does not close it (`closeDrawer` only closes the drawer), so after an editorial-to-editorial navigation the panel likely stays open (unverified in a browser).
  - `:545` `rgba(0, 0, 0, 0.4)` overlay and `z-index: 299/300` written as literals; the design system forbids hardcoded colours, and the z-index scale lives in `mode-shared.css`. Same class of literal in `CommandPalette.svelte:425`.
  - Drawer has no focus trap or focus return (Escape only); `aria-modal="true"` promises one.
  - 631 lines, over the 500 guide; the desktop menu and drawer repeat the same link list twice (`:119-175` vs the drawer from about `:293`), so a new page needs three edits (menu, drawer, footer) plus `paletteDestinations.ts`.
  - No `/changelog` entry in the nav; reachable only via footer, palette and directory.

### `EditorialFooter.svelte` — footer
Files: `src/lib/ui/EditorialFooter.svelte` (33); styles in `editorial.css:449-490`.
- **For / job:** secondary links, credits, contact.
- **Access:** all.
- **Data:** none, static.
- **Requirements:** ten links (Home, Catalog, Institution catalog, Map viewer, Contribute, About, Blog, Version history, All pages, GitHub), credits line (Allmaps, OpenLayers, SvelteKit), a mailto.
- **Layout:** one dark slab (pinned light-on-ink in both themes), links row, credits row, contact row.
- **Interaction:** links only. External links use `target="_blank" rel="noopener"`.
- **i18n · a11y · mobile:** Link labels via `$t` (GitHub/product names are not). No landmark label; `<footer>` is the implicit contentinfo. Mobile rules at `editorial.css:425` (600 px).
- **Findings:**
  - `:14` label "Institution catalog" vs NavBar "Institutions" for the same page.
  - Footer has no Tools, Sign in or language link; combined with the nav, there is no public language switch at all.
  - `editorial.css:449-454` still lists `.about-page .footer`, `.blog-page .footer`, `.blog-post-page .footer`, `.home-page .footer`; no markup in `src/` uses a `.footer` class (grep of `routes` and `lib`), so these selectors are dead.

### Command palette
Files: `src/lib/features/shared/CommandPalette.svelte` (619), `paletteDestinations.ts` (266), `src/lib/core/utils/commandPalette.ts` (62), `ui/PaletteSearchField.svelte` (61); API `/api/search`.
- **For / job:** find a page, map, place or label from anywhere without a menu.
- **Access:** public; staff pages gated by role, hidden rather than refused. Mounted in the root layout, so it also runs on the `(app)` tool routes.
- **Data:** `fetch('/api/search?q=…&include=maps,places,labels&limit=6&fields=slim')` with a 180 ms debounce, an `AbortController`, and a 30-entry per-tab answer cache. Page rows are local (`matchDestinations`).
- **Requirements:**
  - Open with `⌘K`/`Ctrl K`, `/` outside form fields, the nav button, or the home search fields (which seed the first keystrokes).
  - Rank pages by label prefix, word, path, keyword, hint.
  - Arrow keys move, Enter opens, Escape closes and returns focus.
  - Keep page results alive when the API fails.
- **Layout:** scrim → centered dialog: input row (icon, input, spinner, esc), result list with group headings (Go to, Maps, Places, Named on a map), footer with key hints.
- **Interaction:** `role=combobox` input with `aria-activedescendant`; options are anchors. States: loading (spinner, "Searching…"), empty ("Type to search." or `Nothing matches “q”.`), error ("Couldn't reach the archive. Page results still work."), signed-out (public pages only), mobile (breakpoint 600 px).
- **i18n · a11y · mobile:** placeholder, dialog and list `aria-label`, empty and footer hints use `$t`. Raw English: group headings (`:58-62`), page labels and hints, "Undated", `aria-label="Search maps, places and pages"` (`:334`), `aria-label="Close search"` (`:311`), the live-region text, the error text (`:199`), "anywhere" (`:415`), "mention(s)".
- **Findings:**
  - `:233` `$: if ($paletteOpen) open();` runs an async function that writes state from a reactive statement; the house rule says `$:` computes only. A `paletteOpen.subscribe` or a `use:` action would be clearer.
  - `:396` `on:click|preventDefault={() => choose(row)}` always calls `goto`, so cmd/ctrl-click or middle-click on a real `href` still navigates in the same tab.
  - `:274-277` Tab is swallowed to "trap" focus; the scrim `<button>` is unreachable by keyboard and there is no inert background.
  - `:425` hardcoded `rgba(17, 17, 17, 0.35)` scrim.
  - Hits are unprefixed paths (`exploreHref`, `placeHref`, destinations), so choosing a result on `/vi/…` leaves the Vietnamese address.
  - `/` as a global shortcut also fires on `(app)` tool pages; whether any tool uses `/` itself is unverified.
  - 619 lines; the data-fetching, ranking and view could split (the destination list already did).

### `/vi/` reroute — `src/hooks.ts`
Files: `src/hooks.ts` (12), `src/lib/core/i18n/index.ts` (stripLocale, withLocale, localeFromPath, LOCALIZED_PATHS), `vi.ts` (~340 keys).
- **For / job:** gives each translated page a Vietnamese address a crawler can index.
- **Access:** all. `/vi/<path>` resolves to the route `<path>` (universal `reroute`, so client navigation agrees).
- **Data:** none. `hooks.server.ts` reads the path first, then the `vma-lang` cookie, into `locals.locale`; the root layout sets the `locale` store and `<html lang>`.
- **Requirements:**
  - `LOCALIZED_PATHS` (`/`, `/catalog`, `/about`, `/blog`, `/changelog`, `/contribute`, `/contribute/georef`, `/directory`) plus populated `/catalog/area/*` get hreflang pairs and sitemap entries.
  - Every other path is one document with translated chrome only; its canonical is the English path.
  - The path wins over the cookie.
- **Layout:** n/a.
- **Interaction:** no UI to enter `/vi`; the only switch is the toggle on `/profile` (sets the cookie, no URL change).
- **i18n · a11y · mobile:** n/a.
- **Findings:**
  - Dictionary has about 340 keys, but hero `eyebrow`/`sub` props, `<title>`/meta and several page bodies are never passed through `$t` (see page sections). `/vi/about`, `/vi/blog`, `/vi/changelog`, `/vi/contribute`, `/vi/directory` therefore mix languages even though they are in `LOCALIZED_PATHS` and advertised with hreflang.
  - A `/vi` reader who follows any internal link falls back to English unless the cookie is set; the server never sets it from a `/vi` visit.
  - Blog post pages and the catalog's per-sheet pages are English documents under a `/vi` twin only by accident of the reroute; they have no hreflang (correct) but no redirect either.

### Redirects — `src/hooks.server.ts`
Files: `src/hooks.server.ts` (300).
- **For / job:** keeps retired addresses alive, canonicalises the host, repairs bad mode params, sends link-preview bots to the sheet page, writes security headers.
- **Access:** all requests.
- **Data:** none; static maps `LEGACY_REDIRECTS` (13 exact paths), `LEGACY_PREFIXES` (`/map/`→`/catalog/`, `/place/`→`/catalog/place/`).
- **Requirements:**
  - 301: `vmabeta.pages.dev` → canonical host; legacy exact paths and prefixes (query kept via `withSearch`).
  - 302: bad `?mode=` on `/explore`, bad `?tab=` on `/admin`, a `/scan` request with no valid mode (to `/catalog/<ref>` or `/catalog`), preview bots on `/explore?map=` (to the sheet page).
  - Refuse cross-origin or wrongly-typed writes on `/api/*` (403/415).
  - Add the security header set to every response.
- **Layout:** n/a.
- **Interaction:** order is host, legacy, dispatcher, scan, preview bot, locale, Supabase client, resolve, headers.
- **i18n · a11y · mobile:** n/a.
- **Findings:**
  - `legacyTarget(event.url.pathname)` (`:129`, called at `:207`) runs on the raw path while `normalizedDispatcherTarget` and `retiredScanTarget` use `stripLocale`. So `/vi/view`, `/vi/map/<id>` and `/vi/place/<name>` do not redirect (they reroute to a path with no route and 404), but `/vi/scan` does. Unverified at runtime.
  - The scan and preview-bot redirects re-add `/vi` by hand (`:74`, `:125`); the legacy ones never do.
  - `PREVIEW_BOT_RE` is a hand-kept user-agent list; new unfurlers will get the bare site card.

---

## Patterns across these pages

- **Page shell is two shells.** Most pages use `.page` → `PageHero` → `.editorial-main`. Divergent: `/` (own `.hero` + `.main`), `/blog` (`.main`), `/blog/[slug]` (no hero, own `.layout`), `/login` (card, no hero). `/changelog` still carries the old JS `mounted` fade the design system retired.
- **Data loading splits three ways.** Server `+page.server.ts` with edge cache (`/`, `/about`); static module imports (`/blog`, `/changelog`); client `onMount` reads through the browser Supabase client (`/contribute*`, `/directory`, `/profile` counts). Only `/` and `/about` use `cached()`; only `/about` sets a page `cache-control`.
- **Role is fetched four times.** Root layout, editorial layout, and again in `/contribute`, `/contribute/georef`, `/directory` (plus the server load on `/profile`). Each starts `null` and pops in late. One shared source would fix the flash on `/directory` and the staff cards on `/contribute`.
- **Loading, empty, error are not one pattern.** `feedback.css` has `.spinner` and `.empty-state`; `/` and `/contribute/georef` use them partly, `/georef` hand-rolls `.state-card`, `/profile` uses `.loading-pulse`. Fetch failures mostly end in `console.error` and an empty state that reads as success (`/contribute/georef`, `/profile`, home Favorites).
- **i18n coverage is partial and uneven.** `$t` covers body copy but not hero `eyebrow`/`sub` (passed raw to `PageHero`), `<title>`/meta, tab labels (`Tabs` does not translate), palette headings and page labels, directory rows. Seven pages are in `LOCALIZED_PATHS`, yet each mixes languages. Dates are always `en-US`.
- **No public way to switch language, and no locale-aware links.** The only toggle is on `/profile`; nav, footer, palette and in-page links are unprefixed, and `NavBar` tests `$page.url.pathname` with the `/vi` prefix still on it.
- **Hand-typed numbers repeat.** Counts appear in `/` (`STATS`, fallback 39), `/contribute` (950/43/46 in `$t` keys) and `/about` (live). Only `/about` reads the database.
- **Key handling lives in three places.** Global `⌘K` and `/` in the root layout; Escape in `NavBar` and `NavDropdown` via two separate `document` listeners, and in the palette via its input's keydown; the home slider stops its sweep on `pointerdown`/`keydown`. No shared keyboard layer, no skip link.
- **Local CSS and literals leak past the token rule.** `:global(body)` resets in `/contribute` and `/contribute/georef`; `rgba()` overlays in `NavBar` and the palette; hand-written font sizes and opacities in `/login`, `/contribute*`; breakpoints 700 (`/changelog`) and 720 (`/`) outside the allowed four.
- **Docs drift from code.** `design-system.md` still names `ChunkyTabs` and `.action-btn`/`.pill-btn`, shows the `mounted` template, and says fonts load from Google Fonts; `app.html` self-hosts them; `/screens` states the type scale wrongly (`--text-base`).
