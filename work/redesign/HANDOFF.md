# Handoff — the Sheet redesign

Branch `chore/frontend-cleanup`. Written 2026-09-07, end of the session that did
the work. Everything below is verified state, not intention.

## Where it stands

```
npm run check   1400 files, 0 errors, 0 warnings
npm run lint    0 errors · check-tokens: 164 files, no hex in any <style>
npm run build   62 client chunks, all imports resolve
npm run test    87 passed
```

**Nothing is committed.** 23 files staged by `git mv`, ~174 modified, ~32
untracked. A second Claude session on this machine has previously committed with
`add -A` and swept staged work — this is the first thing to deal with.

**Nobody has looked at it.** Four green gates prove it compiles, lints, bundles
and that 87 assertions hold. None of them prove the redesign *looks* right. No
browser has rendered a single page of it. Treat every visual claim below as
untested.

## What changed, in one screen

- **Six role tokens, two surfaces.** `--ground --ground-raised --ink --ink-soft
  --rule --accent` (+ `--on-accent`, `--status-*`, `--scrim`), redefined once
  under `.surface-paper` and once under `.surface-darkroom`. The route layout
  picks; the visitor never does. `scripts/check-tokens.mjs` fails the build on a
  hex literal inside any `<style>` block.
- **One layout primitive.** `Sheet.svelte` + `sheet.css` — neatline, margin,
  field. Both `+layout.svelte` files own it, so pages contribute content only.
- **One button.** `primitives.css`. The four old vocabularies are aliased onto
  it with `:is()`, not renamed.
- **Three self-hosted faces**, latin + latin-ext + vietnamese, 240 KB in
  `static/fonts`. No Google Fonts request survives anywhere.
- **Routes: 23 page routes → 15**, interactive surfaces 12 → 4. Grouped by
  *shell*, not verb: `/explore` is MapShell, `/scan` is ImageShell. Modes are
  `?mode=`, so the OL map stays warm across a switch.

Full reference: `docs/design-system.md`. Route map and the styling rules:
`CLAUDE.md`.

## Next, in order

### 1. Commit — now
Nothing else matters until this is safe. `git mv` history is preserved on 23
files; a stray `add -A` from another session loses that.

### 2. Look at it
`npm run dev`, then walk both surfaces:

| Check | Where | What would be wrong |
|---|---|---|
| paper surface | `/`, `/archive`, `/about`, `/blog` | neatline sits right, corner ticks visible, nav reads as a running head |
| darkroom surface | `/explore`, `/scan` | panels legible on dark, no white card anywhere |
| the hero | `/` | one sheet warping over Saigon, fading 0.12↔0.88 over 14s |
| mode strip | `/explore`, `/scan` | in the top-right margin, **not** floating over the map |
| every primitive | `/screens` | fastest way to see all of it at once |
| mobile | any tool at <600px | riskiest untested combination — see §4 |

### 3. Deploy is yours to run
`npm run deploy` and `supabase db push` are classifier-blocked for Claude here.
Run it yourself with `! npm run deploy`. Expect a blank page for a minute or two
after — that is edge propagation, not a bug (`docs/deploy.md`).

### 4. Mobile is the biggest untested risk
`ToolLayout`'s mobile drawer now lives *inside* a tool Sheet. Below 600px the
Sheet collapses its margin to `--s-2` and hides the corner ticks, and
`.sheet--tool` sets `height: 100dvh; overflow: hidden` with the field on
`minmax(0, 1fr)`. That combination has never been rendered on a phone. If
anything is broken, it is here.

### 5. The 6,255 lines of page CSS
Still under `components/`, `layouts/`, `pages/`. All of it reads role tokens
now; none of it was deleted. Ranked by size:

| File | Lines |
|---|---|
| `components/admin-modals.css` | 1,160 |
| `pages/about.css` | 663 |
| `components/search-panel.css` | 425 |
| `pages/blog-post.css` | 354 |
| `components/sidebar.css` | 371 |

A lot of these rules existed to restate the neo-brutalist border/shadow/radius
that tokens now handle in one place. Start with `admin-modals.css` and delete
rather than rewrite. This is a separate project; do not start it in a session
that is also doing something else.

### 6. The second token system
`components/sidebar.css` defines ~40 `--sb-*` variables. They all resolve to
role tokens now, so nothing is broken — but it is a namespace layered over a
namespace. Either fold it into the roles or write down why it stays.

## Open items inherited from the work

- **`ToolLayout` compact breakpoint** moved 1400 → 1280 to fit the three-
  breakpoint rule. Nobody has checked whether the 1280–1400 band actually needs
  the compact sidebar. `src/lib/map/shell/ToolLayout.svelte:99`.
- **67 eslint warnings, 0 errors.** 44 are `{#each}` without a key, all
  pre-existing. Worth a pass, none are bugs today.
- **`docs/ponytail-debt.md` is stale.** New `ponytail:` comments were added (the
  `:is()` alias block in `primitives.css`). Regenerate with `/ponytail-debt`.
- **`docs/system-guidelines.md` §11** has the live debt table. Its route
  references were rewritten, but no redesign debt was added to it. §5 above
  belongs in there.
- **`/scan` advertises four modes to everyone.** Gating is inside each component
  and unchanged, so a signed-out visitor clicking Triage hits that component's
  own gate. Correct, but the strip could hide staff modes if you want it to.

## Decisions made against the original proposal — don't silently undo these

1. **`driver.js` stays.** It was proposed for deletion on the belief the tour was
   three steps of native popover. It is 273 lines with a spotlight cutout and
   store-driven auto-advance. Restyled onto role tokens instead.
2. **Class names not renamed.** `.sb-btn` / `.tool-btn` / `.pill-btn` /
   `.sb-card` / `.tool-section` / `.sb-input` are aliased. Sixty files for zero
   visual change was not worth it. Write the new names in new markup; rename an
   old one when already editing that file.
3. **Google Translate restored, conditionally.** Deleted as dead, then found
   `/profile`'s Vietnamese toggle feeds it. `app.html` now loads it only when the
   `googtrans` cookie is set. Do not delete it again without removing that toggle.
4. **`/trip/[id]` was not merged.** Printed QR codes point at it.

## Two real bugs this surfaced (both fixed)

- The mode switcher floated at top-centre over the map and **swallowed clicks
  meant for the panels underneath**. Caught by `tests/smoke.spec.ts`, not by
  review. It now renders in the sheet margin, which is what the margin is for.
- `LayerControlsPanel` had `border: 1px solid var(--sb-border)` where
  `--sb-border` was itself a shorthand — invalid CSS, so the browser dropped the
  border entirely. It renders now.
