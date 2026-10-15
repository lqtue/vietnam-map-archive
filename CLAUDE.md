# CLAUDE.md

Vietnam Map Archive (VMA): Vietnam's places, kept through time. It ties maps, documents, photos and
writings to the place and time they describe (link, the core), saves what could be lost (keep) and
lets anyone see a place as its sources show it (show) — a research tool whose records anyone can
search, cite and download. A SvelteKit app over Allmaps and OpenLayers.

**`docs/CONCEPT.md` is what VMA is, and the words for it.** Read it before writing app copy or
describing VMA anywhere, and use its words.

**Start with `docs/NOW.md`** (imported below): the bets, the idea gate, who is on what. A new idea
goes through that gate before it gets a branch.

@docs/NOW.md

Every other doc is found from `docs/README.md` (the one index). Five more instruction files load
when you open a file in their tree:

| File | Covers |
|------|--------|
| `src/lib/CLAUDE.md` | Svelte dialect · layering + feature isolation · map runtime · data access · components |
| `src/routes/CLAUDE.md` | Route groups · modes table · API contract · admin tooling |
| `supabase/CLAUDE.md` | Schema rules · migrations and what each does · local write-test stack |
| `work/CLAUDE.md` | The worker · OCR · MapSAM2 |
| `docs/paper/CLAUDE.md` | The manuscript: source of truth, number ledger, claim discipline |

## Names

| Name | Is | Is not |
|------|-----|--------|
| **Vietnam Map Archive**, VMA | the product; use it in prose | a hostname |
| `maparchive.vn` | the live site | the Pages project |
| `vmabeta` | the Cloudflare Pages project id, nothing else | a product name — never in prose |
| `lqtue/vietnam-map-archive` | the GitHub repo (was `svelte-beta`) | the `VietnamMapArchive` org |
| **HACW** | the Hội An event PWA that Walk forks | part of VMA |
| **Shapes · Search · Walk · Debt** | the four lines of work in `docs/ROADMAP.md` | Tracks C/E/F/D, "Time machine", "Time walk" (retired) |

Roadmap items are named for their subject (`l7014-rebuild`), never a letter code.

## Commands

```bash
npm run build          # Production build; also runs scripts/check-bundle.mjs
npm run check          # Type-check — the primary verification; keep it at 0 errors / 0 warnings
npm run test           # Playwright, read-only (hits real Supabase, never writes)
npm run db:test        # Local Supabase stack + write-test fixtures
npm run db:test:reset  # Replay every migration, then reseed
npm run test:write     # Write-path tests against that local stack
npm run deploy         # Build + wrangler deploy to Cloudflare Pages
```

Read `docs/guides/testing.md` before changing or adding a check: most catch a failure that looks
like data rather than a bug.

## Rules

- **Branch from `main`, open a PR, merge — never commit straight to `main`.**
- **Svelte is legacy mode, not runes.** `$:`, `export let`, `createEventDispatcher`, `$store` —
  never `$state`/`$derived`/`$effect`. Load the `svelte-core-bestpractices` skill before any
  `.svelte` edit.
- **Layering, lint-enforced:** `core → data → map → features → routes`; `ui` has no domain imports;
  `server` is `$lib/server` only. Import only leftward. Routes stay thin.
- **One OpenLayers map per page**, owned by `MapShell` (`ImageShell` for pixel work). Never
  `new Map()` in a child.
- **Never import a Node builtin bare** — use `node:path`, not `path`; the CF Functions bundle fails.
- **Migrations:** run `supabase migration list` before assuming the production head; local files
  past it may be unpushed. How to add one: `supabase/CLAUDE.md`.
- **A sheet's address is its slug** (`maps.slug`), not its uuid; old addresses 301 to it
  (`088_map_slug.sql`).
- **Before a migration or any number-producing run**, read `docs/guides/db-guidelines.md` and
  `docs/guides/lessons.md`.
- **`docs/private/` is gitignored — never publish.** The repo is public.
- **`.claude/handoff*.md`** — gitignored, one per stream, written by `/handoff <stream>`.

## Deployment

Only `main` reaches production. Read `docs/guides/deploy.md` first.

- **No root `wrangler.toml`** — it would replace the dashboard environment, secrets included.
  (`worker/wrangler.toml` is separate and fine.)
- **Environment and secrets live in the Cloudflare dashboard**, per environment, nothing inherited.
  Secrets resolve at build time (`$env/static/private`), so every building environment needs them.
- **A blank page right after deploy is edge propagation**, not a bug. Wait, hard-reload, then use
  the `curl` check in the deploy guide.
