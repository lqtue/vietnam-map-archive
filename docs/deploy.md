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

## Ownership — considered 2026-09-22, mostly declined

Nothing here is broken, and nothing below has been done. This section exists so the question is not
re-opened from scratch: it records what consolidating the accounts would actually cost.

Today the three platforms sit under two identities — GitHub and Cloudflare under `lqtue`, Supabase
under a second identity the same person controls. A `VietnamMapArchive` GitHub org exists but holds
nothing.

| Platform | Can it move between accounts? | What moving costs |
|---|---|---|
| GitHub | **Yes, cheaply.** Transfer to the org; issues, PRs and stars come along and both old URLs keep redirecting, git included | Actions secrets and the Cloudflare Pages build integration do **not** travel. Re-add the secrets, and re-authorize the GitHub App for the org — a Pages source left pointing at the old owner builds nothing, which presents as the blank page this file's last section describes, with no obvious cause |
| Supabase | **Org-scoped only.** A project moves between orgs you own and keeps its ref; there is no account-to-account move | Nothing, if the ref is preserved. If the ref ever changes it is `PUBLIC_SUPABASE_URL` in both Cloudflare environments, and a wrong value there fails the **build** at the first `$env/static/private` import rather than at runtime |
| Cloudflare | **No.** Pages projects, R2 buckets and zones are all account-bound | Recreate the Pages project (new `.pages.dev` host), re-enter every variable and secret by hand in both environments, redeploy `vma-iiif-worker`, copy 119,616 tile objects to a new R2 bucket, and cut `maparchive.vn` DNS over. Hours of work and real downtime on tiles, to change a name that appears only in a dashboard |

**The verdict:** the GitHub transfer is worth doing on any day it is wanted, and needs the two
follow-ups in its row. The Cloudflare move is not worth making, now or later — `vmabeta` is an
internal project id and no reader ever sees it. The one thing worth five minutes regardless is
adding a second **Owner** to the Supabase org: of everything here, that project is the only piece
that cannot be recreated from this repo.

`vmabeta` and `svelte-beta` therefore survive on purpose — the first is the Pages project id, the
second the local directory. Neither is a name for the product; see the Names table in `CLAUDE.md`.
