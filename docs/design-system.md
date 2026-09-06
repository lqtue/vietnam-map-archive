# The Sheet system

The design language of the Vietnam Map Archive. Written September 2026, replacing
the neo-brutalist tokens (cream `#faf6f0`, 3px black borders, `6px 6px 0` offset
shadows) that preceded it.

## The idea

A printed map sheet puts its content inside a **neatline** — a double rule, thin
outside and thick inside, with ticks breaking each corner where the plate was
registered. Inside the neatline is the **field**. Outside it is the **margin**,
and the margin is where the title cartouche, the scale bar and the legend have
always lived.

So: **chrome in the margin, content in the field.** An article is a field. A map
is a field. Both are one component.

The archive's own database already speaks this vocabulary — `LAYOUT_CATEGORIES`
in `src/lib/data/maps/triageTypes.ts` is `sheet · main_map · title · legend ·
name_list · inset · scale_bar · north_arrow · stamp`. The design is taken from
the subject rather than applied to it.

## Files

`src/styles/global.css` imports five files, in this order. Nothing else is
always-on.

| File | Lines | What |
|---|---|---|
| `fonts.css` | 249 | `@font-face` for three self-hosted families |
| `tokens.css` | 116 | six roles × two surfaces, type, space, line |
| `base.css` | 167 | reset and element defaults |
| `sheet.css` | 160 | the neatline / margin / field primitive |
| `primitives.css` | 394 | label · button · field · panel · chip · table |

Page-scoped sheets under `components/`, `layouts/` and `pages/` are imported by
the component that owns them, never globally.

## Colour: two surfaces, not two themes

Six role tokens, redefined once per surface. **The route layout picks the
surface; the visitor never does** — there is no theme toggle and no
`[data-theme]` attribute.

| Token | Paper | Darkroom | Role |
|---|---|---|---|
| `--ground` | `#eae7df` | `#14181a` | the sheet itself |
| `--ground-raised` | `#f6f4ef` | `#1d2325` | panels, cards, table heads |
| `--ink` | `#191c1a` | `#e6e4dc` | body text; the neatline |
| `--ink-soft` | `#5c625c` | `#8b9490` | captions, labels, secondary text |
| `--rule` | `#c6c2b6` | `#2e3739` | every hairline and border |
| `--accent` | `#0e7c86` | `#2aa5ae` | live, selected, primary |

Plus `--on-accent`, `--status-ok`, `--status-warn`, `--status-bad`, `--scrim`.

- `.surface-paper` — editorial pages. Cool grey-green laid stock, not warm cream.
- `.surface-darkroom` — the tools. Historical scans are light; a light interface
  around a light scan gives the eye nothing to separate them by, which is why
  every serious map tool puts a dark ground around imagery. `--ink` is paper
  white here, so text on this surface literally reads as paper.

Paper is also on bare `:root`, so a page that forgets its surface class is
legible rather than unstyled.

`--accent` is **survey cyan** — printed hydrography at full strength. It reads as
an instrument rather than a brand, and it sits far from the categorical hues the
footprint and layout palettes already use, so a "this is live" cue can never be
mistaken for data.

### The rule

**A component reads roles and never names a colour.** `npm run lint` runs
`scripts/check-tokens.mjs`, which fails the build on a hex literal inside any
`<style>` block. Two things stay literal, each marked
`/* token-exempt: why */`:

1. Colours handed to **OpenLayers** — OL builds styles in JS and cannot resolve a
   CSS custom property.
2. **Categorical data** colours, where the value encodes *which thing* rather
   than *what role*: footprint feature types, layout regions, tile priorities,
   story markers. A legend swatch that mirrors an OL canvas style counts too —
   tokenising it would make the legend stop matching the canvas.

## Type

Three families, self-hosted from `static/fonts`. Only latin, latin-ext and
vietnamese ship: the corpus is French, Vietnamese and English, and cyrillic plus
greek were 40% of the bytes and 0% of the corpus. 191 KB total, ~54 KB on the
usual path.

| Token | Family | Use |
|---|---|---|
| `--font-display` | Spectral 300 / 600 + italic | Engraved, high contrast. Used with restraint; italic for place names, the way hydronyms are set on a real sheet. |
| `--font-body` | Be Vietnam Pro 400 / 600 | Body. A Vietnamese face, by a Vietnamese foundry, for a Vietnamese archive. |
| `--font-mono` | IBM Plex Mono 400 / 500 | Coordinates, years, scales, tile ids. Tabular figures. |

Vietnamese coverage was a hard constraint, not a taste call — it is what ruled
out Instrument Serif, Fraunces and Martian Mono.

Scale: `--t-2xs` `--t-xs` `--t-sm` `--t-md` `--t-lg` `--t-xl` `--t-2xl` `--t-3xl`
(0.6875 → 4rem). Tight at reading sizes, loose at display sizes — how a specimen
sheet steps, rather than one ratio applied past where it reads.

Weights: `--w-light` 300 · `--w-regular` 400 · `--w-medium` 500 · `--w-semi` 600.
There is no bold. The old design shouted.

## Line, radius, elevation

**Paper is square; instruments are eased.** The neatline and every rule sit at 0
radius, and only what you press or type into gets the 2px.

- `--rule-hair` 1px · `--rule-thick` 2px
- `--radius` 2px · `--radius-pill` 999px
- `--shadow-overlay` — the *only* shadow, for modals and popovers. Elevation on
  paper is `--ground-raised` plus a rule. Nothing lifts on hover; rules darken.
- `--ease` — one duration, 120ms. Zeroed under `prefers-reduced-motion`.

## Space and breakpoints

`--s-1` 0.25 · `--s-2` 0.5 · `--s-3` 0.75 · `--s-4` 1.25 · `--s-5` 2 ·
`--s-6` 3.5rem.

**Breakpoints are 600 / 900 / 1280.** Three. There were nineteen.
`ToolLayout`'s mobile split at 900 is the one other components pair with.

## Layout

`src/lib/ui/Sheet.svelte` is the only layout primitive. Both `+layout.svelte`
files own it, so a page contributes content and nothing else — no header
scaffold, no max-width, no footer.

```
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   margin: nav, mode strip
   ╔══════════════════════════════════╗
│  ║                                  ║   │
   ║              FIELD               ║       map, article, table
│  ║                                  ║   │
   ╚══════════════════════════════════╝
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   margin: scale, meta
```

- `variant="page"` — the field pads and scrolls, content sits on `--measure`.
- `variant="tool"` — the field goes edge to edge and belongs to the map.
- Slots: `cartouche` (top-left, the nav), `margin-top-right` (the mode strip),
  default (the field), `margin-bottom-left`, `scale`.
- `graticule` — a faint coordinate grid behind the margin, home page only, off
  below 900px where there is no margin to draw it in.

A block that must break the measure marks itself `.is-wide`.

**Chrome never floats over the field.** The first mode switcher was fixed at
top-centre over the map and swallowed clicks meant for the panels underneath —
caught by `tests/smoke.spec.ts`. That is the failure the margin exists to
prevent.

## Primitives

`.label` · `.btn` · `.field` · `.panel` · `.chip` · `.data-table`, plus `.row`,
`.stack`, `.divider`, `.state-msg`, `.spinner`, `.visually-hidden`.

There were four parallel button vocabularies before this: `.btn`, `.sb-btn`,
`.tool-btn`, `.pill-btn`, plus `.action-btn` / `.ctrl-btn` / `.primary-btn` /
`.secondary-btn`. One survives. The rest are aliased onto the primitives with
`:is()` at the bottom of `primitives.css` rather than renamed across sixty files
for no visual change — **write the new names in new markup**, and rename an old
one when you are already editing the file for another reason.

Modifiers: `.btn--primary` `.btn--ghost` `.btn--danger` `.btn--sm` `.btn--xs`
`.btn--icon` `.btn--block`, and `aria-pressed="true"` / `.is-on` for a selected
tool.

## Page template

```svelte
<script lang="ts">
  // The layout owns the Sheet, the nav and the footer. Contribute content.
</script>

<svelte:head>
  <title>Thing — Vietnam Map Archive</title>
  <meta name="description" content="One sentence." />
</svelte:head>

<h1>Thing</h1>
<p>A standfirst, on the measure.</p>

<section class="is-wide">
  <span class="label">Section</span>
  <table class="data-table">…</table>
</section>

<style>
  /* Layout and position only. Every colour is a role token. */
  section {
    margin-bottom: var(--s-6);
    padding-top: var(--s-4);
    border-top: var(--rule-hair) solid var(--rule);
  }
</style>
```

## See it

`/screens` renders the whole system from fixtures — tokens, type, space, line,
and every component in `src/lib/ui/`. No database, so it cannot break on data.
Look there before building a second version of something that already exists.
