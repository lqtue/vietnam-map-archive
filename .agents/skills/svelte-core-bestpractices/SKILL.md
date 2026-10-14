---
name: svelte-core-bestpractices
description: How Svelte is written in this repo. Load before creating, editing or reviewing any .svelte file or .svelte.ts module. Legacy-mode dialect — overrides the upstream runes guidance.
---

# Svelte in VMA

**Project fork.** Installed from `sveltejs/ai-tools`, then rewritten: upstream
assumes runes, this repo is Svelte 5.39 in **legacy mode**. `skills-lock.json`
still holds the upstream hash, so a reinstall would revert this file.

Sources merged here: the framework-agnostic half of
<https://svelte.dev/docs/svelte/best-practices> and
<https://github.com/spiegelgraphics/svelte-best-practices> (Svelte-4 era, so it
translates directly).

## The dialect

Use `$:`, `export let`, `on:click`, `<slot>` / `<svelte:fragment>`,
`<svelte:component>`, `<svelte:self>`, `createEventDispatcher`, `$store`,
`use:action`, `class:`. Never `$state`, `$derived`, `$effect`, `$props`,
`{#snippet}`, `{@render}`, `{@attach}`.

The Svelte MCP autofixer and every upstream skill will tell you to modernise
those. Ignore that half; act on the rest — missing `{#each}` keys, cleanup,
scoped-CSS and a11y findings, real bugs.

## Reach for the lowest tier first

1. **HTML** — a `<details>`, a `<dialog>`, `<input type=range>`.
2. **CSS** — `:hover`, `@media`, a transition, `position: sticky`.
3. **The template** — `{#if}`, `{#each}`, `class:`, `style:`.
4. **JavaScript** — only when the three above cannot.

Never reach into the DOM to do what the template can do. `bind:this` +
`onMount` to touch an element is the JS tier pretending to be tier 3; a
`use:action` is the reusable shape and gets a teardown for free.

## Reactivity

- **`$:` computes, it does not write.** A reactive statement that assigns to
  other component state or calls `.set()` is the legacy shape of the
  effect-writing-state bug. Derive the value instead.
- **Keep `$:` blocks small.** One block, one derived value. A block with
  side-effects at the bottom is two things wearing one coat.
- **Reassign, never mutate.** `arr = [...arr, x]`, not `arr.push(x)`;
  `obj = { ...obj, k }`, not `obj.k = v`. Legacy reactivity fires on the
  assignment, so mutation is both a stale render and a shared-reference bug.
  (`<svelte:options immutable>` is a no-op in Svelte 5 — do not add it.)
- **Plan store dependencies.** No cycles, no store that derives from a store
  that derives from it. `src/lib/map/stores/` is the one dense cluster; add to
  it deliberately.
- **Context, not a module-level `let`,** for anything request-scoped. Module
  state is shared across requests on the server. The three that exist
  (`supabaseAdmin`'s client cache, `basemapStyle`'s `C`/`S`) are server-only or
  browser-only on purpose.

## Template

- **Every `{#each}` is keyed** by a stable id, never the index. All 90 in the
  tree are; keep it that way.
- **`bind:` over an event handler** when it is plain two-way state — less
  boilerplate and one fewer place to forget. Use a handler when the write needs
  validation, ordering, or must not fire on every keystroke.
- **`class:` and `style:` over string interpolation** in the attribute.
- **`<svelte:window>` / `<svelte:document>` over a hand-rolled listener** for
  anything that lives as long as the component. The exception is a drag:
  `pointermove`/`pointerup` attached on pointerdown and torn down on up is the
  right shape, and `ExploreSidebar`, `ToolLayout` and `MapModeOverlays` do it
  deliberately.
- **Nothing hard-coded** — no pixel dimension, no row count, no date that the
  data or the container can supply.

## CSS

- **Scoped to the component.** 11 files reach for `:global`; each new one needs
  a reason in a comment.
- **JS values reach CSS as custom properties** — `style:--foo={x}`, then
  `var(--foo)` in the `<style>` block. Style a child through a custom property
  first; `:global` only when there is no other way in.
- Colour, border and shadow always go through a `var(--token)`; the component's
  own `<style>` carries layout and position only. See `docs/guides/design-system.md`.

## Size and cleanup

- **A component should fit on one screen.** Average here is ~210 lines (146
  components, 30.5k lines); **nine** are over 500: `screens/+page.svelte` 647,
  `DigitalizePage` 629, `CreateMode` 591, `OcrSidebar` 588,
  `MapEditHostingTab` 574, `(editorial)/+page.svelte` 571, `ExplorePage` 560,
  `CommandPalette` 554, `NavBar` 536. Do not add to that list — extract the
  panel, the table, the controller. (`TriageSidebar` was the worst at 833 and
  came off the list in Sept 2026: five files, 221 + four steps. It is the
  worked example of the cut this bullet is asking for.)
- **Every subscription, listener, timer and observer is torn down** in
  `onDestroy` or by the action's return. The tree currently has **zero**
  unpaired `addEventListener` and **zero** uncleared `setInterval`; that is a
  property worth keeping, not a coincidence.
- **Descriptive English names.** `mapsAwaitingReview`, not `data2`.

## Before you show the code

Run the Svelte MCP autofixer, apply everything except the modernise-to-runes
findings, then `npm run check` (0 errors / 0 warnings is the standing state).
