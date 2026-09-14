# supabase — schema, migrations, the local test stack

Root context: `/CLAUDE.md`. Table-by-table reference and the rule behind each constraint:
`docs/db-guidelines.md` §11.

## The rules in one breath

- `maps.status` is `draft | public | featured` and is the **only** visibility model (mig 060).
  Draft maps are readable by any signed-in user, never anonymously (mig 063). A published map must
  carry `annotation_url` **or** `allmaps_id` (mig 062), and publishing enqueues `mirror_annotation`
  + `tile_to_r2` (mig 058).
- **Status transitions live in Postgres**, not the API: `set_extraction_status`,
  `revert_recent_validations`, `set_footprint_status`, `set_review_mark`, `claim_job`, `finish_job`.
  All `security definer`, `service_role` only. New write paths reuse them.
- `pipeline_jobs` is the queue (one live job per kind × map); `map_pipeline_status` is a **view**;
  `map_review_marks` holds the three human stages.
- Full-text search uses the `simple` tsvector config on purpose — the corpus is
  French/Vietnamese/English.
- The gazetteer key exists twice — `place_core_key()` here and `placeCoreKey` in
  `$lib/core/utils/placeKey.ts`. They must agree or a place page 404s.

## Adding a migration

Head is **086**, pushed 2026-09-13. Drop a new `supabase/migrations/NNN_*.sql` incrementing from it,
`supabase db push`, then regenerate types:

```bash
supabase gen types typescript --linked 2>/dev/null > src/lib/data/supabase/types.ts
npm run check
```

Project ref `trioykjhhwrruwjsklfo` (Sydney) is already linked. `supabase db push` and
`supabase migration list` both work directly (verified 2026-09-10 — `migration list` prints the
local/remote table without a password prompt). `supabase db pull` still asks for a direct DB
password; use the Dashboard SQL Editor or `db push` instead of pulling. Repair migrations with
`supabase migration repair --status applied|reverted <id>`.

## The local write-test stack

`npm run db:test` runs `supabase start -x vector -x logflare` and seeds one staff user + one map via
`scripts/seed-test-db.mjs`. `npm run test:write` (`tests/write.spec.ts`, 25 tests) runs against it,
never production: the suite throws unless `PUBLIC_SUPABASE_URL` is a loopback address, and deletes
every row it writes. Credentials come from `.env.test` (the CLI's published demo keys, committed on
purpose) which Vite loads for the `--mode test` dev server on port 5199. Server-route auth is done
by letting `@supabase/ssr` mint the session cookies, so chunking and encoding match the app exactly.

Local ports are **54421** for the API and **54420** for the shadow DB, not the CLI defaults —
54321/54320 collide with another local project. `-x vector -x logflare` is needed under colima:
those containers bind-mount `/var/run/docker.sock`, which colima cannot provide.
