# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

Vietnam Map Archive (VMA) — a SvelteKit 5 app for exploring georeferenced historical maps of
Saigon/Ho Chi Minh City. Integrates Allmaps with OpenLayers.

**This file is one of five, and the only one that loads every session.** The others load when you
open a file in their tree, which is why their content is not repeated here:

| File | Covers |
|------|--------|
| `src/lib/CLAUDE.md` | Svelte dialect · layering + feature isolation · the map runtime · data access · the component vocabulary |
| `src/routes/CLAUDE.md` | Route groups · the modes table · the API contract · admin tooling |
| `supabase/CLAUDE.md` | Schema rules · adding a migration · the local write-test stack |
| `work/CLAUDE.md` | The worker · OCR · MapSAM2 |

Working in one of those trees? Read its file first.

## Names

One thing, one name. These are the ones that have been confused before:

| Name | Is | Is not |
|------|-----|--------|
| **Vietnam Map Archive**, VMA | the product, and how to refer to it in prose | a hostname |
| `maparchive.vn` | the live site | the Pages project |
| `vmabeta` | the Cloudflare Pages project id, and nothing else | a name for the product — never use it in prose |
| `vietnam-map-archive` | the GitHub repo (renamed from `svelte-beta`, Sept 2026) | the local directory, which is still `svelte-beta` |
| **HACW** | the Hội An event PWA, a separate app that Walk forks | part of VMA |
| **Shapes · Search · Walk · Debt** | the four lines of work, in `docs/ROADMAP.md` | Tracks C/E/F/D, which is what they were called until 2026-09-22 |

Roadmap items are named for their subject — `l7014-rebuild`, `hand-triage`, `colour-blocks` — never
by a letter code. "Time machine" and "Time walk" are retired: they were two names for two different
things that nobody could tell apart, and they are now **Search** and **Walk**.

## Commands

```bash
npm run dev          # Dev server
npm run build        # Production build (wipes .svelte-kit/output first)
npm run check        # Type-check (primary verification) — currently 0 errors / 0 warnings
npm run lint         # prettier --check . && eslint .
npm run format       # prettier --write .
npm run test         # Playwright smoke suite, read-only (363 tests)
npm run db:test      # Start the local Supabase stack + seed the write-test fixtures
npm run db:test:reset  # Replay every migration from scratch, then reseed
npm run test:write   # Write-path smokes against that local stack (33 tests)
npm run deploy       # Build + deploy to Cloudflare Pages via wrangler
npx wrangler pages dev .svelte-kit/cloudflare  # Local CF preview
```

`npm run test` starts a dev server on 5173, or reuses one already running. It runs eighteen
read-only
browser checks — twelve in `tests/smoke.spec.ts`, six in `tests/catalog-series.spec.ts` (they hit
the real Supabase project but never write) — plus 340 browser-less pure checks riding the same
runner. **What each one pins, and why it exists, is `docs/testing.md`** — read it before changing a
check or adding one, because most of them exist to
catch a failure that looks like data rather than like a bug. Write paths are covered separately —
see `supabase/CLAUDE.md`.

`build` also runs `scripts/check-bundle.mjs`, which fails the build if an emitted chunk imports one
that wasn't written. That guards against a genuinely inconsistent bundle — it does **not** address
the propagation lag below, which no build-time check can see.

## Repo-wide rules

- **Svelte is legacy mode, not runes.** `$:`, `export let`, `createEventDispatcher`, `$store` —
  never `$state`/`$derived`/`$effect`. Load the `svelte-core-bestpractices` skill before any
  `.svelte` edit. Details: `src/lib/CLAUDE.md`.
- **Layering, lint-enforced:** `core → data → map → features → routes`; `ui` is leaf primitives with
  zero domain imports; `server` is `$lib/server` only. A directory imports only leftward. Routes
  stay thin. Details + feature isolation: `src/lib/CLAUDE.md`.
- **One OpenLayers map per page**, owned by `MapShell` (`ImageShell` for pixel work). Never
  `new Map()` in a child. Details: `src/lib/CLAUDE.md`; full reference `docs/architecture.md`.
- **Never import a Node builtin bare** (`import('path')`) — the CF Functions bundle errors with
  `Could not resolve "path"` and publishes nothing. Use the `node:` prefix.
- **A blank page right after a deploy is edge propagation, not a bug** — chunks 404 for a minute or
  two, and with `ssr = false` one missing chunk is a blank document. Wait and hard-reload first;
  the `curl` check is in `docs/deploy.md`.
- **Migration head is 091**, pushed 2026-09-16 (090) / local (091). Adding one, and regenerating
  types afterwards: `supabase/CLAUDE.md`.
- **A sheet's address is its name, not its uuid** — `maps.slug` (mig 088). `/catalog/<slug>` is
  canonical; a uuid and every retired slug 301 to it, so no published link dies. The rule and the
  reason a collision takes the *year* rather than a counter: the header of `088_map_slug.sql`.

## Deployment

Cloudflare Pages adapter, output `.svelte-kit/cloudflare`, deployed by `npm run deploy`
(`wrangler pages deploy .svelte-kit/cloudflare --project-name vmabeta`). The full story, including
the ten dead builds: **`docs/deploy.md`**. The rules:

- **No root `wrangler.toml`.** One that carries `pages_build_output_dir` replaces the dashboard's
  whole environment, secrets included. The R2 tile worker's `worker/wrangler.toml` is separate and
  fine.
- **Environment lives in the Cloudflare dashboard**, per environment (Production and Preview each
  hold their own copy; nothing inherits). `PUBLIC_*` are Text variables; `SUPABASE_SERVICE_KEY`,
  `IA_S3_*` are Secrets. Build command, output dir and `nodejs_compat` are dashboard settings too.
- **Secrets resolve at build time** via `$env/static/private`. `$env/dynamic/private` returns
  undefined in Pages Functions. So every environment that builds needs all three present, or the
  build fails on the first import. CI copies `.env.test` to `.env` before `check` and `build`.
- **The repo is `lqtue/vietnam-map-archive`** (renamed from `svelte-beta`, Sept 2026; GitHub
  redirects the old URL and the local directory is still called `svelte-beta`). The Pages project is
  still `vmabeta`, because renaming it would change the deploy target and the `.pages.dev` host for
  nothing.
- **`vmabeta.pages.dev` 301s to `maparchive.vn`** — `hooks.server.ts`, exact host match, so preview
  deploys at `<hash>.vmabeta.pages.dev` stay reachable. Two indexable addresses for one site, one of
  them saying `beta`, was the reason.

## Docs

- `docs/architecture.md` — **the map runtime**, unabridged: MapShell/ImageShell, the stores, route
  groups, the /explore rails, the contribute tools, the PMTiles basemap, the series layers
- `docs/db-guidelines.md` — schema conventions; all migrations must follow these
- `docs/conventions.md` — the reasoning behind the one-line rules: fonts, the gazetteer key, the
  generated types, the realtime stub, the component/theme vocabulary
- `docs/testing.md` — what each of the 363 tests pins, and the failure it exists to catch
- `docs/system-guidelines.md` — layering rule, page structure, component patterns, route map, and
  §11 the live debt table
- `docs/design-system.md` — tokens, the CSS file map, the page template
- `docs/api.md` — every server route, its auth class and its contract
- `docs/deploy.md` — Cloudflare Pages: env in the dashboard, no root `wrangler.toml`, the
  blank-page-after-deploy effect
- `docs/pipelines.md` — OCR + MapSAM2 command reference and design rationale
- `docs/allmaps-series-note.md` — how a survey is carried as one Allmaps layer, and what the
  annotation format does and does not allow
- `docs/admin-tooling.md` — MapEditModal, Bulk Upload, Scout, R2 worker, holding-institution model
- `docs/digitalize-guide.md` — **operator guide** for `/scan?mode=prepare`: propose-then-accept, the
  layout categories, the ground-per-call target, and the failure modes that return plausible output
  while dropping data
- `docs/image-processing-record.md` — **the image-processing work collected in one place**:
  chronology, the method at each stage, every measured number with its source file, the nine
  rejected approaches, the four things not yet established, and the anchors for comparing against
  the field
- `docs/field-comparison.md` — **the same work held against the field**: MapSAM2 / SODUCO /
  mapKurator / ICDAR MapText / the two automatic georeferencing routes, what our numbers cannot be
  compared to and why, and the verdict per axis
- `docs/worked-example-1882.md` — **one sheet all the way through**, with the number each stage
  produced: the georeference checked by hand (11.3 m RMSE), the three OCR runs and why only one
  counts, the first `join` and the first `approved` footprints in the archive's history, and the
  four defects that only surfaced by running the chain
- `docs/ROADMAP.md` — **the one tracker, open work only**: the foundations pass, the OCR drain,
  evidence, survey layer, Shapes · Search · Walk · Debt. Items are named for what they act on
  (`l7014-rebuild`, not `N1`); the old letter codes map to those names at the bottom of that file.
  Close an item by moving it out, not by ticking it
- `docs/roadmap-record.md` — **frozen 2026-09-22**: every closed pass with its measurements and the
  defects it turned up. Not maintained; read it for what something cost, never for what is open
- `docs/lessons.md` — **the rules this project has paid for more than once**, each with the failure
  that taught it and a date. Read before any unattended run, any database write, or any pass that
  produces a number
- `docs/search-plan.md` — label search · temporal fabric · period sources (**Search** detail)
- `docs/walk-plan.md` — the walk-through surface (**Walk**): HACW forked for a District 4 route,
  warped sheets as a year slider, and the frozen-JSON seam between the two apps
- `docs/platform-design.md` — one workspace for VMA + HACW: what is shared and what stays per-app
- `docs/strategy.md` (funder-facing), `docs/theory.md`, `docs/user-guide.md` — vision and
  outward-facing prose, not engineering reference. `docs/journals/` holds dated research notes
  (`YYMMDD-slug.md`)
- `docs/private/` — **gitignored, never publish**: the outreach ledger (`network.md` — who is out
  there, §4 verified against institutional pages 19 Sep 2026), the Allmaps relationship file with
  its contact addresses (`allmaps.md`), and the personal application material moved out of
  `docs/archive/` on 19 Sep 2026. The repo is public; this directory is the reason nothing in it is
- `docs/ponytail-debt.md` — ledger of `ponytail:` shortcut comments. The plugin that generated it is
  gone (Sept 2026); maintain it by hand with the grep at the top of that file (scope:
  `src/ work/ scripts/ tests/ supabase/ eslint.config.js playwright.config.ts`)
- `docs/archive/` — frozen: historical plans and the August 2026 cleanup record (the personal
  application material moved to `docs/private/`). Do not cite as current; the live debt table is
  `docs/system-guidelines.md` §11
- `contracts/` — JSON Schemas for the shapes VMA shares with other apps (`context`, `label-hit`,
  `footprint-feature`); checked by `tests/schemaCheck.ts`
- `CHANGELOG.md` — version history, 1.0 (Apr 2025, one `index.html`) to **7.4** (current). The
  numbers continue the ones the commits already used, so the SvelteKit rewrite is 3.x; the number
  moves on a structural change, not a build. **Its public twin is `/changelog`**, whose source is
  `src/routes/(editorial)/changelog/releases.ts` — plain language, shorter, a different audience.
  Nothing generates one from the other: add a release to both
