# VMA Design System

The visual language for Vietnam Map Archive. Applies to every public page and to the chrome of the
map tools.

---

## Philosophy

**Ink on an aged sheet.** The palette, the type and the chrome are taken off the maps themselves: a
grey-buff ground, a warm lithographic black, and accents pulled from candy saturation down to a
printable ink. Flat fills, a hard border, and an offset shadow that reads as a second plate a hair
out of register. Not a playful toy, not a generic SaaS dashboard, and — since Sept 2026 — not the
neo-brutalist poster it started as either.

**There is no icon set.** No emoji in the chrome, no illustrative blobs. Where a glyph survives it
is because the glyph *is* the content: the favourite heart, the GPS toggle, the placeholder for a
map with no thumbnail. Everywhere else the label already says the word.

Two registers coexist:

- **Editorial** (`/`, `/about`, `/blog`, `/catalog`, `/contribute`, `/login`, `/profile`,
  `/admin?tab=`) — clean, left-aligned, information-dense.
- **Tool** (`/explore?mode=`, `/scan?mode=`, `/trip/[id]`) — full-bleed map or canvas under the nav,
  sidebar chrome, compact controls.

New public pages default to the **editorial** register.

**There are two themes, one value each.** `tokens.css` writes every ink as `light-dark(light, dark)`
and lets the used `color-scheme` pick — there is no second `[data-theme]` palette to drift out of
step. `:root[data-theme='light'|'dark']` pins the scheme, and that attribute is the only thing the
toggle in `NavBar` writes; `src/lib/core/utils/theme.ts` owns the choice (`light | dark`, stored
under `vma-theme`, seeded once from the OS for a reader who has never chosen) and `src/app.html`
replays it before first paint. Write both faces of any colour you add, and never hardcode one.

---

## Tokens

Defined in `src/styles/tokens.css`, imported first by `src/styles/global.css`. **Never hardcode a
colour, border, shadow or radius in a component `<style>` block.**

### Colours

The plate-tone palette (Sept 2026), taken off the sheets rather than from a UI kit. Every value was
checked against both surfaces before it went in; the ratios below are quoted where they are the
reason for the value. White on each accent: red 6.4, blue 7.1, green 6.2, orange 4.8, purple 7.6 —
all clear AA for normal text.

| Variable | Value | Role |
|---|---|---|
| `--color-bg` | `#eae7e0` | Page background — the sheet. Cooler and darker than a cream, which is what stops the page reading as a wellness brand |
| `--color-white` | `#f7f5f0` | Card stock, a shade lighter than the page — a mounted sheet on a backing board |
| `--color-text` | `#1a1a17` | Lithographic black, warm, never `#000`. 14.1 on the page |
| `--color-border` | `#1a1a17` | Every border. **Not** the shadow — that is `--shadow-ink` |
| `--rule` | `#7d7869` | Hairlines, for a rule that reads as printed rather than as a UI divider. 3.6 on the page |
| `--shadow-ink` | `#63615a` | Every offset shadow. The ink thinned to ~65% over the page |
| `--color-primary` | `#a63a2b` | The administrative overprint — CTAs, danger, errors. Use it once per screen |
| `--color-blue` | `#2f5d78` | Ink blue — active, selected, info |
| `--color-yellow` | `#e0b544` | Ochre — hover fills, highlights. A **light** surface: pair with `--color-text-on-yellow` |
| `--color-green` | `#3d6b4a` | Plate green — done / complete |
| `--color-orange` | `#a85f2b` | Burnt sienna — community, warning |
| `--color-purple` | `#5a4b80` | Indigo — the fifth thing |
| `--color-text-on-yellow` | `#1a1a17` | Text on a yellow surface. 9.0 |

Legacy aliases also exist and are still referenced, all warmed into the same paper family:
`--color-primary-600/700`, `--color-gray-50/100/300/400/500/900`, `--color-success-600`,
`--color-warning-600`, `--color-error-600`. `--color-gray-500` (`#66614f`) is the meta-text grey —
5.0 on the page, 5.7 on a card.

**Canvas colours are a separate file.** An OpenLayers style is a canvas draw call and cannot read a
CSS variable, so `src/lib/core/ink.ts` holds the same inks as TypeScript constants — ten mirroring
the tokens above, plus `teal`, `plum`, `olive` and `slate` for the categorical maps (ten OCR
categories, nine layout regions, seven footprint types) that need more hues than six page accents
can give. Everything OL paints reads `INK`; nothing else does.

### Typography

| Variable | Value | Use |
|---|---|---|
| `--font-family-display` | `'Google Sans Display', 'Google Sans', 'Be Vietnam Pro', system-ui, sans-serif` | Headings, nav, badges, labels, buttons |
| `--font-family-base` | `'Google Sans Text', 'Google Sans', 'Inter', 'Be Vietnam Pro', system-ui, sans-serif` | Body text, descriptions, captions |

**Google Sans is named but never loaded.** It is Google's own licence and Google Fonts does not
serve it, so it resolves only where the reader already has it (Android, ChromeOS). The two faces the
app actually ships are the pairing: **Inter** for reading and **Be Vietnam Pro** for headings and
chrome. Both cover Vietnamese, which is why the old third face is gone. The pair was chosen for
older eyes — Inter has the tallest x-height and the most open apertures of the Google Fonts
grotesks, and a straight `l` that will not be read as `1`; body copy sits at 17px with 1.6 leading
for the same reason.

Sizes: `--text-xs` `.75rem` · `--text-sm` `.875rem` · `--text-base` `1.0625rem` (17px) · `--text-lg`
`1.125rem` · `--text-xl` `1.25rem` · `--text-2xl` `1.5rem` · `--text-3xl` `2rem`.
Weights: `--font-normal` 400 · `--font-medium` 500 · `--font-semibold` 600 · `--font-bold` 700 ·
`--font-extrabold` 800.

Use `800` for page and section titles, `700` for nav and sub-headings, `500` for body copy, `400`
for long-form blog reading. Hero titles use `clamp(2.5rem, 6vw, 4rem)` — always fluid.

**The Google Fonts link lives once in `src/app.html`**, and asks for exactly the two faces
`tokens.css` can load — Inter, Be Vietnam Pro. Do not add a `<link>` to a page or component: three
tool pages each carried a second render-blocking stylesheet (for Spectral and Noto Serif, which
appear in no font stack) until Sept 2026.

**Map labels set themselves.** `components/lettering.css` with `core/utils/mapLettering.ts` gives a
label the role its own sheet would have given it — `.lettering-hydronym` italic for rivers and
canals, `.lettering-area` letterspaced capitals for quarters and districts, roman for everything
else. Use them wherever a transcribed name is shown, not a generic italic.

### Borders, shadows, radii, spacing

| Variable | Value | Use |
|---|---|---|
| `--border-thick` | `3px solid var(--color-border)` | Cards, nav, hero, structural elements |
| `--border-thin` | `2px solid var(--color-border)` | Inline labels, progress tracks, dividers |
| `--shadow-solid` | `6px 6px 0 var(--shadow-ink)` | Feature cards, primary CTAs |
| `--shadow-solid-sm` | `4px 4px 0` | Smaller cards, badges |
| `--shadow-solid-xs` | `2px 2px 0` | Chips, dense controls |
| `--shadow-solid-hover` | `8px 8px 0` | Hover lift only — never on a static element |

**Buttons carry no shadow** (Sept 2026). `.btn` and `.chip` (and so every tab, every icon button and
everything that used to be `.action-btn` or `.pill-btn`), `.back-link` and the catalog's tag chips
are flat; `--btn-shadow` is the opt-in for a caller that wants one back. Two things had been leaning
on it and were replaced rather than deleted: **hover** was a 2px lift, which only read as a lift
against the shadow it uncovered, and is now `filter: brightness(0.95)` — it works on every colour
variant without an override fight over `background`; and **`:focus-visible`** *was* the hover
shadow, so it had to become a real `outline`, or keyboard focus would have gone invisible. Cards,
plates and non-interactive chips (`.section-card`, `.hero-sub`, `.label-chip`, `.badge-chip`) keep
theirs — the offset plate is still the house gesture, just not on things you press.
| `--radius-sm / md / lg / pill` | `8px / 16px / 24px / 999px` | Tags · cards, inputs · feature cards · buttons, chips |

Aliases `--shadow-sm/md/lg` map onto the solid set.

**The shadow is never blurred and never the border ink.** A hard offset in `--shadow-ink` sits
behind a border in `--color-border`; that separation is what keeps 190 shadows from shouting. Some
component sheets write the offset out by hand at 1, 1.5, 3 or 5px because the four sizes above do
not cover dense chrome — those are fine, but they must end in `var(--shadow-ink)`, so the whole
system re-weights from one line. The exceptions, all deliberate: `0 0 0` (the pressed state),
`inset` row markers, and single-axis edge rules like `0 -4px 0` which are borders drawn as shadows
and want `--color-border`. Spacing scale: `--space-1…16` (`0.25rem` → `4rem`). Layout:
`--nav-height: 56px` — tool pages inset from the top by this. Breakpoints: `--bp-tablet 768px`,
`--bp-desktop 1024px` (the tool shells use a hard `900px` mobile cut-off).

---

## CSS files

All stylesheets live in `src/styles/` and are reached via the `$styles` alias. `global.css` imports
`tokens.css` plus the eight always-on component sheets — `buttons`, `feedback`, `table`,
`nav-buttons`, `editorial`, `lettering`, `sidebar`, `modal`; everything else is imported by the
component or route that needs it, so a page only pays for what it uses.

| File | Loaded by | Scope |
|---|---|---|
| `tokens.css` | `global.css` | every custom property |
| `global.css` | root layout | entry point |
| **components/** | | shared widgets |
| `buttons.css` | `global.css` | **every button**: `.btn` and `.chip`, plus the one `is-*` modifier vocabulary they share with `.sb-btn` |
| `feedback.css` | `global.css` | `.spinner` (the only one) and `.empty-state` (+ `.is-block`, `.error`) — one placeholder line for loading, empty and failed |
| `table.css` | `global.css` | `.data-table`, its three densities, and the sortable header (`.th-sort` + `.sort-ind`) that `$lib/ui/SortHeader.svelte` renders |
| `nav-buttons.css` | `global.css` | nav-bar button chrome |
| `editorial.css` | `global.css` | `.page`, `.editorial-main`, hero, `.section-card` (+ `.is-sm` / `.is-link`), `.stat-tile`, the badges, footer, nav |
| `lettering.css` | `global.css` | `.lettering-hydronym` / `.lettering-area` — how a printed sheet sets its own names, paired with `core/utils/mapLettering.ts` |
| `modal.css` | `global.css` | generic modal scaffolding |
| `sidebar.css` | `global.css` + `SidebarCard` | sidebar card frame |
| `admin-modals.css` | `MapEditModal`, `NeatlineEditor` | admin modal chrome only — the `.btn` family moved to `buttons.css` in Sept 2026, and so did its three private badges and its `.close-btn` |
| `catalog.css` | `CatalogGrid`, `CatalogCard`, `/catalog` | map card grid |
| `shapes-table.css` | `OcrSidebar`, `OcrRunBar`, `TraceSidebar` | the toolbar and cell editors around that table |
| `auth-gate.css` | `AuthGate`, `StudioMode`, `CreateMode` | signed-out gate — the card only; its button is a `.chip` |
| `library.css` | `LibraryGrid`, `StudioMode`, `CreateMode` | project/story library grid |
| **layouts/** | | page shells |
| `tool-page.css` | every IIIF-canvas tool + `/scan` | tool page frame, panels, toolbars |
| `mode-shared.css` | `ToolLayout`, `ImageShell`, `MapModeOverlays`, `/explore` | map-mode chrome + the z-index scale |
| `catalog.css` | `/catalog` | catalog page layout |
| `home.css` | `/` | home page layout |
| `create-mode.css` | `CreateMode`, `StudioMode` | story/annotation editor layout |
| **pages/** | | one per editorial page |
| `about.css`, `blog.css`, `blog-post.css`, `profile.css`, `admin-scout.css`, `admin-bulk.css`, `admin-status.css`, `screens.css` | their route (`admin-bulk.css` also by `GeorefSyncPanel`) | page-specific |

**Breakpoints.** Four, and no others — a fifth value invented for one page is how the set got to
seventeen before Sept 2026:

| Width | Meaning |
|---|---|
| `600px` | small phone — editorial pages drop to one column |
| `640px` | dense chrome (nav, modals, admin tables) gets its compact form |
| `768px` | tablet — `global.css` shrinks body type and pins inputs to 16px so iOS stops zooming |
| `900px` | the tool split: `ToolLayout` swaps the desktop rail for the mobile drawer stack, matched by `mode-shared.css` and `tool-page.css` |

`ToolLayout` also reads `1400px` in JS for `isCompact`. CSS custom properties do not work inside
`@media`, so these are literals on purpose — `--bp-*` tokens existed until Sept 2026, matched
nothing and were deleted.

**Two button names, because there are two things.**

- **`.btn`** — an action. "Save", "Open the map viewer", "Delete".
- **`.chip`** — a choice. A tab, a facet, a filter; `.is-on` when picked.

Both are the same pill and differ only in the six `--btn-*` properties each sets.

**One modifier vocabulary, and it is the sidebar's**: sizes `.is-xs` `.is-sm` `.is-lg`, tones
`.is-primary` `.is-danger` `.is-success` `.is-ghost`, states `.is-on` `.is-block` `.is-icon`
`.is-disabled`. `.sb-btn` and `.sb-pill` (`sidebar.css`, because they run on the `--sb-*` token
scope) use the same words, so the two scopes are one thing to learn. `.is-icon` is round at three
sizes — 48px the floating map control, `.is-sm` a card's action corner, `.is-xs` a row toggle in a
table.

This was **twenty-seven selectors across nine families** until Sept 2026, with four tones each
spelled three ways (`.btn-primary` · `.chip.primary` · `.action-btn.primary-btn`), which is what
made "check every button" a job nobody could finish. What went, and why none of it was a design
rather than a context: `.action-btn` was a size, `.pill-btn` was lighter chrome and nothing else,
`.btn-outline` was already the default, `.tool-btn` was `.sb-btn.is-sm` in a bar that runs on
`--sb-*` anyway, and `.ctrl-btn` / `.btn-icon-edit` / `.btn-icon-delete` / `.cmp-btn` were one round
shape at three sizes. The full ledger is the header of `buttons.css`; `tests/screens.spec.ts` fails
if a retired name reappears.

**Everything else is in `buttons.css`.** If a component needs a button that is nearly a `.btn`, add
the class and override the `--btn-*` properties in the component — do not rebuild the shape.

**One card.** `.section-card` (`editorial.css`), padded by `--card-pad`, with `.is-sm` for a column
of them (smaller radius, lighter shadow) and `.is-link` when the whole card is a link and should
lift. Four page-locked cards — `.post-card`, `.subscribe-card`, `.sidebar-card`, `.profile-card` —
were this rule re-typed in four files with a different padding until Sept 2026; what is left in
those pages is only what is genuinely theirs, a gap, a dashed edge, a tighter `--card-pad`. /screens
lists the whole card inventory and `tests/screens.spec.ts` checks that every row in it still exists.

**Never redefine a global button class in a component `<style>` block.** Svelte's scoping means the
local rule silently wins, so nothing looks broken while `.btn primary` means two different things in
two files. `ExploreSheet`, `TripComplete` and `TripPlayback` each did this until Sept 2026.

**One table.** Every `<table>` wears `.data-table` and picks a density: `.is-dense` (sidebar) or
`.is-card` (a table that is its own card, on /catalog). Nine custom properties define a density, so
a new one is a short block and never a second copy of the base. Before Sept 2026 there were four
unrelated implementations across three stylesheets.

**One spinner.** `.spinner` in `feedback.css` is the whole system: size and colour tune through
`--spinner-size`, `--spinner-thickness`, `--spinner-track` and `--spinner-ink`, and
`.spinner.on-ink` covers a spinner on a solid coloured button. There is exactly one
`@keyframes spin` in the tree — it replaced nine near-identical definitions in Sept 2026. Never
write a second one.

`layouts/admin.css` and `components/label.css` were deleted in Aug 2026 — the three surviving
`label.css` classes moved into `tool-page.css`. Do not reintroduce either name.

**Import form:**

```svelte
<script lang="ts">
  import '$styles/layouts/tool-page.css';
</script>
```

---

## Components

**Reach for one of these before writing markup.** Every one already exists in `src/lib/ui/`;
re-implementing what they do is how the codebase grew twenty different card patterns.
See them all rendered together at **`/screens`**.

| Component | Use it for |
|---|---|
| `PageHero` | **The hero on every editorial page.** Props `eyebrow` · `title` · `sub` · `badges`; slots `title` (wins over the prop, for `.text-highlight` markup), `sub`, `actions`, `eyebrow`. Do not hand-roll `.editorial-hero`. |
| `NavBar` · `EditorialFooter` | Mounted once by `(editorial)/+layout.svelte`. A page never renders either. |
| `AuthGate` | The signed-out "sign in to continue" card. |
| `CatalogGrid` · `CatalogCard` · `MapCard` | Map listings. |
| `LibraryGrid` | Project / story library grids. |
| `ChunkyTabs` | The tab strip. Use it instead of a row of buttons that toggle a variable. |
| `FacetRail` | Faceted filter column. |
| `LocationSearch` | Nominatim place lookup with results dropdown. |
| `SnapSheet` | Mobile bottom sheet. |
| `NameDialog` · `InlineRename` | Naming and renaming flows. |
| `NavDropdown` | Nav menu disclosure. |

`ui/` is leaf-level by the layering rule: these import nothing from `features/`, `map/` or `data/`,
so any page or feature may use them.

The shared editorial **classes** live in `src/styles/components/editorial.css` and are global. Use
them without redefining the CSS.

`.top-nav` `.nav-logo` `.nav-links` `.nav-link` `.nav-auth` · `.editorial-hero` `.hero-inner`
`.label-chip` `.text-highlight` · `.editorial-main` `.section-card` `.section-card-header`
`.section-title` `.section-title-sm` `.section-desc` · `.badge-chip` (`.is-sm` for a table row) with
`.chip-blue` / `.chip-green` / `.chip-yellow` / `.chip-gray` · `.btn` `.chip` · `.editorial-footer`.

`.icon-blob` and its five `color-*` fills were **deleted** in Sept 2026 — a 72–80px organic blob
holding a pictorial emoji, and the single most templated thing on the site. Do not reintroduce it or
anything shaped like it.

### Hero

Use the component. The classes below are what it renders — you should not be typing them.

```svelte
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
</script>

<PageHero
  eyebrow="Page context"
  sub="Supporting paragraph. Max ~500px wide."
  badges={[{ label: 'Fact one' }, { label: 'Fact two' }]}
>
  <svelte:fragment slot="title">
    Bold headline<br /><span class="text-highlight">highlighted word.</span>
  </svelte:fragment>
</PageHero>
```

Plain-text title and no highlight? Then the prop is enough: `<PageHero title="Bold headline" />`.

`.text-highlight` (white fill, black stroke, offset shadow) belongs on one or two words of a hero
title — never in body text. Only `.chip-blue`, `.chip-green` and `.chip-yellow` exist; the
orange/purple/red chip classes were removed.

### Page shell

Every `(editorial)` route roots at `<div class="page x-page">`, then `PageHero`, then
`<main class="editorial-main">`. `.page` carries the mount fade as a CSS animation with `both`
fill and a `prefers-reduced-motion` guard — it was a `mounted` boolean flipped in `onMount` and
read as `class:mounted` on six routes, which is a round trip through JS on a page that
server-renders, and four of those routes carried an identical copy of the CSS.

`.editorial-main` caps the measure at 1100px. `.editorial-main.is-wide` opens it to 1400 for a
dense table; `/admin?tab=scout` is the only caller and prose never takes it.

### Stat tile

`.stat-tile` with `<span class="value">` and `<span class="label">` children. `.is-sm` is the
compact face — three across in a narrow panel. `/about` states its numbers as a `<dl>` of wide
rows instead; that is a different object and stays in `about.css`.

### Badges

`.badge-chip` plus one tone: `.chip-blue`, `.chip-green`, `.chip-yellow`, `.chip-orange`,
`.chip-red`, `.chip-gray`, `.chip-white`. There is no purple. `.chip-yellow` is a filled yellow
and keeps dark ink in both themes, because yellow is the one surface that stays light;
`.chip-white` is the paper face — `.chip-yellow` painted white until Sept 2026, which is why four
components each carried a private yellow tint rather than use it.

`.badge-chip.is-sm` is the dense face for a badge inside a table row or a list line: base font, no
offset shadow. A display-size chip with a 2px shadow reaches into the row below. Four components
had a private near-identical copy of it.

### Section card

```html
<div class="section-card">
  <div class="section-card-header">
    <div>
      <h2 class="section-title-sm">Section heading</h2>
      <p class="section-desc">One or two sentences.</p>
    </div>
  </div>
  <!-- content -->
</div>
```

The header carries no icon. The heading is the identifier.

### Buttons

`.action-btn.primary-btn` (the overprint red, white text) and `.action-btn.secondary-btn` (card
stock, dark text) for CTAs — both lift on hover with `translate(-3px,-3px)` plus the larger shadow.
`.pill-btn` for small utility actions (sign out, toggles). `.chip` hovers to the ochre; that is the
system's hover fill, not a per-page choice.

---

## Page template

Nav and footer come once from `src/routes/(editorial)/+layout.svelte`. A new editorial page renders
only its own body:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import PageHero from '$lib/ui/PageHero.svelte';
  import '$styles/pages/my-page.css';

  let mounted = false;
  onMount(() => {
    mounted = true;
  });
</script>

<svelte:head>
  <title>Page Title — Vietnam Map Archive</title>
  <meta name="description" content="…" />
</svelte:head>

<div class="page my-page" class:mounted>
  <PageHero eyebrow="Section label" sub="Supporting sentence.">
    <svelte:fragment slot="title">
      Page headline<br /><span class="text-highlight">key phrase.</span>
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <!-- .section-card blocks -->
  </main>
</div>

<style>
  .page {
    min-height: 100vh;
    opacity: 0;
    transition: opacity 0.4s ease;
  }
  .page.mounted {
    opacity: 1;
  }
</style>
```

`.editorial-main` constrains to `1100px` with `4rem 1.5rem` padding and a `3.5rem` gap between
sections.

---

## Rules

**Always**

- Use `var(--color-*)`, `var(--border-*)`, `var(--shadow-*)`, `var(--radius-*)` — a hex literal in a
  component `<style>` block is a bug. For a tint,
  `color-mix(in srgb, var(--token) N%, var(--color-white))`; never a new literal.
- A canvas colour comes from `INK` in `src/lib/core/ink.ts`, never from a literal in the component.
  The whole list of remaining literals in the tree, each documented where it sits: `ink.ts` itself,
  the offscreen analysis canvas in `suggestTriage.ts`, the Google logo paths, and `ReviewSidebar`'s
  cadastral class swatches, which name what the sheet itself printed and so are data rather than
  theme.
- `border: var(--border-thick)` on every card and structural container.
- `--font-family-display` for headings and labels; `--font-family-base` for body.
- Left-align editorial hero content.
- Add `class:mounted` with the `opacity: 0 → 1` fade-in on the root `.page`.
- `aria-expanded` on any toggle or disclosure; collapsible regions use `{#if}`, not `display: none`.
- **Check `/screens` before writing a component or a card style.** If something close already
  exists, extend it. Twenty distinct card patterns exist — four reusable, sixteen locked to a single
  page — because this step kept getting skipped.
- **Keep controls few.** A surface needing more than ~6 buttons, selects and inputs is a design
  question, not a layout one — decide what matters most and put the rest behind a disclosure.
  `MapEditPipelineTab` (23 controls) is the example not to follow.

**Never**

- `transform: rotate()` on an editorial page.
- Emoji or a pictorial icon anywhere in the chrome. The only glyphs that stay are the ones that
  *are* the content — the favourite heart, the GPS toggle, the no-thumbnail placeholder.
- Hardcoded font sizes — `clamp()` for headlines, tokens for everything else.
- A per-page Google Fonts `<link>` — it is in `app.html`.
- `--shadow-solid-hover` on a static element; it is a hover state.
- Redefining `.btn`, `.chip`, `.action-btn` or `.pill-btn` in a component `<style>` block.
- A new page without nav + footer links.

**Adding a new public page**

1. Copy the template above into `src/routes/(editorial)/<page>/+page.svelte` — including its
   `PageHero`, which is not optional.
2. Add its stylesheet at `src/styles/pages/<page>.css` and import it in the page.
3. Add the link to `src/lib/ui/NavBar.svelte` and `src/lib/ui/EditorialFooter.svelte`.
4. Add a row to the route map in `docs/system-guidelines.md` §2.
5. Build content from `.editorial-main` + `.section-card`; don't invent new layout patterns.

---

## Colour × state reference

| State | Token | `INK` twin | Example |
|---|---|---|---|
| Complete / done | `--color-green` | `INK.green` | finished pipeline stage, approved footprint |
| Active / in progress | `--color-blue` | `INK.blue` | current phase, selected region, hydrology |
| Community / people | `--color-orange` | `INK.orange` | contributor cards, institutions, pending review |
| Future | `--color-purple` | `INK.purple` | roadmap items, legend regions |
| Hero / highlight | `--color-yellow` | `INK.yellow` | hero background, hover fill, the neatline |
| CTA / danger | `--color-primary` | `INK.red` | primary buttons, error messages, streets |
| Neutral | `--color-text` / `--color-bg` | `INK.ink` / `INK.paper` | body, cards, footer |
| Hairline | `--rule` | `INK.rule` | printed rules, the tile grid |

The four inks with no token — `INK.teal`, `INK.plum`, `INK.olive`, `INK.slate` — exist only on
canvas, where ten OCR categories need more hues than seven roles provide. Do not invent a CSS token
for one; if a page needs a seventh colour, the answer is usually that it needs fewer things on it.
