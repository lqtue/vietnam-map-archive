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
| `lqtue/vietnam-map-archive` | the GitHub repo (renamed from `svelte-beta`, Sept 2026) | the local directory, which is still `svelte-beta` |
| `VietnamMapArchive` | a GitHub org that exists; the repo has **not** been transferred into it | where the repo lives today |
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
npm run test         # Playwright smoke suite, read-only (377 tests)
npm run db:test      # Start the local Supabase stack + seed the write-test fixtures
npm run db:test:reset  # Replay every migration from scratch, then reseed
npm run test:write   # Write-path smokes against that local stack (37 tests)
npm run deploy       # Build + deploy to Cloudflare Pages via wrangler
npx wrangler pages dev .svelte-kit/cloudflare  # Local CF preview
```

`npm run test` starts a dev server on 5173, or reuses one already running. It runs nineteen
read-only
browser checks — twelve in `tests/smoke.spec.ts`, seven in `tests/catalog-series.spec.ts` (they hit
the real Supabase project but never write) — plus 358 browser-less pure checks riding the same
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
- **Migration head is 104**; 095–104 are in production (verified 2026-10-01 via
  `supabase migration list`) — see `supabase/CLAUDE.md` for what each one does. Adding one, and
  regenerating types afterwards: `supabase/CLAUDE.md`.
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
  redirects the old URL and the local directory is still called `svelte-beta`). A
  `VietnamMapArchive` GitHub org exists and the repo **has not been transferred into it** — that
  move is cheap and available whenever it is wanted; `docs/deploy.md` §Ownership has the cost of
  each platform's move, including the two not worth making. The Pages project is
  still `vmabeta`, because renaming it would change the deploy target and the `.pages.dev` host for
  nothing.
- **`vmabeta.pages.dev` 301s to `maparchive.vn`** — `hooks.server.ts`, exact host match, so preview
  deploys at `<hash>.vmabeta.pages.dev` stay reachable. Two indexable addresses for one site, one of
  them saying `beta`, was the reason.

## Docs

`docs/README.md` is the reader index; `docs/model-layout.md` maps docs and work to the system model.
Each file's opening paragraph says what it covers. Read before acting:

- **Before code:** `architecture.md` (map runtime) · `conventions.md` · `design-system.md` ·
  `system-guidelines.md` (layering, §11 live debt table) · `api.md` · `testing.md` (what each of the
  377 tests pins)
- **Before a migration or DB write:** `db-guidelines.md` · `lessons.md` (rules this project paid for
  more than once — also before any unattended run or any pass that produces a number)
- **Before deploying:** `deploy.md`
- **Pipelines:** `pipelines.md` (OCR + MapSAM2) · `digitalize-guide.md` (`/scan?mode=prepare`) ·
  `admin-tooling.md` · `allmaps-series-note.md`
- **Open work:** `ROADMAP.md` is the one tracker, open items only, named for what they act on.
  Close an item by moving it out, not by ticking it. Plans: `search-plan.md`, `walk-plan.md`,
  `knowledge-system-plan.md`, `evidence-chain-plan.md`, `platform-design.md`
- **Research records:** `research/README.md` indexes `image-processing-record.md`, `field-comparison.md`,
  `worked-example-1882.md` and `river-reconstruction.md` (exploratory, 1882 + 1898; no river layer approved), `journals/` (dated
  `YYMMDD-slug.md`), `paper/` (the manuscript, outline and claim audit — LaTeX and Markdown sources)
- **The object model:** `knowledge-system-plan.md` — every object, its link fill rates, the ranked
  gaps, and §9, the index of every open ROADMAP item by layer. When an item is added to or closed in
  ROADMAP, move its name in §9 in the same commit. `system-graph.md` draws it twice: a plain-language
  five-step picture for non-engineers and an engineer view with tools, research and branches
- **Outward-facing prose, not engineering reference:** `strategy.md`, `theory.md`, `user-guide.md`

Special rules:

- `docs/private/` — **gitignored, never publish.** Outreach ledger, the Allmaps relationship file
  with contact addresses, personal application material. The repo is public.
- `docs/roadmap-record.md` — **frozen 2026-09-22**; read it for what something cost, never for what
  is open. `docs/archive/` is frozen too — do not cite it as current.
- `docs/ponytail-debt.md` — ledger of `ponytail:` comments; the generating plugin is gone, so
  maintain it by hand with the grep at the top of that file.
- `.claude/handoff.md` — gitignored; the last session's state, written by `/handoff`. Read it first
  when resuming; it lists which dirty files are another session's.
- `contracts/` — JSON Schemas for shapes shared with other apps, checked by `tests/schemaCheck.ts`.
- `CHANGELOG.md` — 1.0 (Apr 2025) to **7.4** (current); the number moves on a structural change,
  not a build. Its public twin is `/changelog` (`src/routes/(editorial)/changelog/releases.ts`) —
  plain language, shorter, a different audience. Nothing generates one from the other: add a
  release to both.
