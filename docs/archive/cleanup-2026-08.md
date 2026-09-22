# The August 2026 cleanup

A whole-repo pass over `src/`, `scripts/`, `docs/` and the build config, run as ~40 commits on
`chore/cleanup`. Nothing about the product changed: every route URL, every API path and every CSS
token name is the same.

## What changed

**A layering rule where there was none.** `src/lib` had 19 top-level directories organised by
accident of history — `map/` and `maps/` one letter apart, map state in `stores/` but the map
runtime in `shell/`, feature stores in three places, no server-only home. It is now five buckets
with a dependency direction:

> `core → data → map → features → routes`; `ui` is leaf primitives; `server` is `$lib/server` only.

164 files were `git mv`'d and 342 import paths rewritten. `MapListItem` no longer has a re-export
shim; `$lib/server` makes a client import of the service key a build error instead of a code-review
catch.

**Numbers.**

| | before | after |
|---|---|---|
| `src` LOC | 45,316 | 43,584 (~9k duplicated lines removed, ~3k shared modules added) |
| `src` files | 208 | 277 (splits) |
| files over 400 lines | 22 | 9 (largest 575) |
| `as any` | 109 | ~25 |
| `svelte-check` | 0 errors / 34 warnings | 0 / 0 |
| eslint | not configured | 0 errors (71 baseline warnings) |
| hex literals in component styles | ~900 | 116 (OpenLayers JS palettes, brand SVG) |
| tracked binaries | 13 MB PNG + 4.9 MB `work/vectorize/` | 748 KB JPEG |
| docs in `docs/` | 28 files / 3.2 MB | 8 living docs + `archive/` |

**Also landed:** eslint + prettier + `.editorconfig` and a whole-repo format; a root
`wrangler.toml`; redirect stub pages replaced by a `LEGACY_REDIRECTS` table in
`src/hooks.server.ts`; `/contribute/review` moved into the `(app)` route group; `ReviewCanvas`
replaced by `ImageShell` + `ReviewTool`; server helpers (`requireRole`, `adminClient`, `assertUuid`,
`dbError`, `pickMapFields`, `facets`) collapsing 19 hand-rolled auth gates and 21 `createClient`
copies; a `topOverlay → mapStore.activeMapId` bridge that made the "mirror" the code had documented
but never wired actually exist; a security fix removing the service key from the public
`/api/maps/[id]/legend-points` route; and 11 dead scripts pruned.

## Where the review reports live

`work/cleanup/` held the working material — a per-module tracker, a current-versus-proposed layout
doc, and six scope reviews. It was deleted on 2026-09-02 once the follow-ups closed; git history has
it.

## Open follow-ups

Carried over unticked from that tracker:

- **`data/supabase/footprints.ts` mixes two concerns** — map-selector queries (`fetchLabelMaps`) and
  footprint CRUD. Split into `data/maps/labelMaps.ts` + a contribute-scoped module.
- **`CatalogUnifiedSearch` still queries Supabase directly.** Move the read into
  `data/maps/service.ts` so the component is presentational. (The `ui → features/admin` half of this
  is done: `/catalog`'s page owns `MapEditModal` now.)
- **`features/contribute/shared` geometry types** — already lifted to `data/maps/footprintTypes.ts`;
  the remaining `ImageShell` coupling wants one more look.
- **One error convention.** `data/` still mixes throw, `console` → `[]` and `console` → `false`.
- **a11y stragglers** — `CatalogDetailDrawer:56`, `ReviewSidebar:104`, `login/+page.svelte:45`
  (`onclick=` instead of `on:click`), two `line-clamp` cases.
- **Mobile gaps in contribute** — `OcrSidebar` bind/`on:filter` and the Segmentation tab are
  desktop-only.

See also the debt tables in `docs/system-guidelines.md` §11 and `docs/db-guidelines.md`, and the
shortcut ledger in `docs/ponytail-debt.md`.
