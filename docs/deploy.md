# Deployment (Cloudflare Pages)

How the app is built and deployed, and the two expensive lessons behind the rules. Moved out of
`CLAUDE.md` in September 2026; the rules stay there, the story lives here.

Cloudflare Pages adapter. Build output: `.svelte-kit/cloudflare`. There is **no** root
`wrangler.toml` — see below for why. The R2 tile worker has its own `worker/wrangler.toml`.

**Environment lives in the Cloudflare dashboard, and `wrangler.toml` must not exist.**
A root `wrangler.toml` carrying `pages_build_output_dir` makes the Wrangler file the
source of truth for the Pages project, and Cloudflare then replaces the dashboard's
entire environment with what that file declares — build variables *and* runtime
secrets. Secrets cannot live in a committed file, so the file cannot be used here.

Both halves of that were learned the expensive way:

- With the file present and no `[vars]`, the build logged `Build environment variables:
  (none found)` and rollup failed on the first `$env/static/public` import
  (`"PUBLIC_SUPABASE_URL" is not exported by "virtual:env/static/public"`). Ten
  consecutive preview builds died this way while `npm run build` stayed green locally.
- Adding `[vars]` fixed the build, and the deploy then failed at runtime instead:
  `Error: supabaseKey is required.` — `wrangler pages secret put` had reported success,
  but the config file had displaced the secret store too.

So: `PUBLIC_SUPABASE_URL` and `PUBLIC_SUPABASE_ANON_KEY` are
plain **Text** variables in Settings → Variables and Secrets; `SUPABASE_SERVICE_KEY`,
`IA_S3_ACCESS_KEY` and `IA_S3_SECRET_KEY` are **Secret** there. Build command, output
directory (`.svelte-kit/cloudflare`) and `nodejs_compat` are dashboard settings too.
Each environment (Production, Preview) holds its own copy — a preview deployment with
no secrets returns 500 from every route that needs one, and nothing inherits.

`npm run deploy` therefore passes the directory explicitly:
`wrangler pages deploy .svelte-kit/cloudflare --project-name vmabeta`.

Secrets are read through `$env/static/private`, which resolves them at **build** time.
`$env/dynamic/private` was tried and does not work here — the three secrets came back
undefined in Pages Functions (`Error: supabaseKey is required.` on every route using
`adminClient()`), both with and without a Wrangler config. Consequence: every environment
that builds needs all three present, Preview included, or the build fails on the first
import. CI has no dashboard, so
`.github/workflows` does `cp .env.test .env` before `check` and `build` — which is why CI
stayed green through all ten build failures.

## Blank page right after a deploy

Expected, and self-heals. Pages serves the new HTML and `entry/app.<hash>.js` before every
`_app/immutable/` chunk is reachable at the edge; individual chunks 404 for a minute or two. Because
every `(app)` route sets `ssr = false`, one unreachable chunk is a fully blank document whose only
symptom is `Failed to fetch dynamically imported module` (WebKit:
`Importing a module script failed`). Wait and hard-reload before debugging;
`curl -o /dev/null -w "%{http_code}"` against the chunk the console names will flip to 200.
`scripts/check-bundle.mjs` guards against a genuinely inconsistent bundle at build time, which is a
different failure.

## One address

Pages publishes the project at `vmabeta.pages.dev` as well as at the custom
domain. That is two indexable URLs for one site, and one of them says `beta` in
front of a public archive, so `src/hooks.server.ts` 301s the bare
`vmabeta.pages.dev` to `maparchive.vn`, path and query kept.

The match is the exact host, not a suffix: a preview deploy is
`<hash>.vmabeta.pages.dev` and has to stay reachable to be worth anything.
Static assets are served by Pages itself rather than by the Function, so they
do not pass through the hook — only documents redirect, which is what a
crawler and a reader follow.

Turning the `.pages.dev` host off entirely is a dashboard setting and would
work too; this keeps it in the repo, where it is visible.
