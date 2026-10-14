# supabase — schema, migrations, the local test stack

Root context: `/CLAUDE.md`. Table-by-table reference and the rule behind each constraint:
`docs/guides/db-guidelines.md` §11.

## The rules in one breath

- `maps.status` is `draft | public | featured | archived` and is the **only** visibility model (mig 060/107).
  Draft maps are readable by any signed-in user, never anonymously (mig 063). A published map must
  carry `annotation_url` **or** `allmaps_id` (mig 062) — `allmaps_id` alone is enough on purpose:
  a map may be published first and georeferenced by a volunteer afterwards (the sync-georef flip,
  mig 080; pinned in `tests/write.spec.ts`), so do not tighten this to "already georeferenced".
  Publishing enqueues `mirror_annotation` + `tile_to_r2` (mig 058).
- **Status transitions live in Postgres**, not the API: `set_extraction_status`,
  `revert_recent_validations`, `set_footprint_status`, `set_review_mark`, `claim_job`, `finish_job`.
  All `security definer`, `service_role` only. New write paths reuse them.
- `pipeline_jobs` is the queue (one live job per kind × map); `map_pipeline_status` is a **view**;
  `map_review_marks` holds the three human stages.
- Full-text search uses the `simple` tsvector config on purpose — the corpus is
  French/Vietnamese/English.
- **`maps.slug` is minted by Postgres, never by a caller** (mig 088): `map_slug_base` folds the
  name, `map_slug_mint` applies name → name-year → name-year-N, and two triggers keep it true. A
  rename does not re-address a sheet; clearing `slug` re-mints it and files the old one in
  `map_slug_aliases`. The `default ''` on the column is load-bearing — it is what keeps `slug`
  optional in the generated `Insert` type.
- The gazetteer key exists twice — `place_core_key()` here and `placeCoreKey` in
  `$lib/core/utils/placeKey.ts`. They must agree or a place page 404s.

## Adding a migration

**Production head is 119** (pushed 2026-10-08). Local files past it may be unpushed —
`supabase migration list` is the truth, not this line. Each migration's own header is its record:
what it does, why, and the deploy order it needs. Read the header, not a summary here.

Drop `supabase/migrations/NNN_*.sql` one past the head, `supabase db push`, then regenerate types:

```bash
supabase gen types typescript --linked 2>/dev/null > src/lib/data/supabase/types.ts
npm run check
```

Rules these migrations paid for:

- **Unpushed: 122 `review_events`** (PR 1 of `docs/plans/review-page-plan.md`) — `review_tasks`,
  `review_items`, and the insert-only `review_events` (no UPDATE/DELETE/TRUNCATE grant for anyone,
  `service_role` included; an item or task with events cannot be deleted, so write tests leave their
  events behind). anon/authenticated have no grant on tasks or items (the blind arm's proposal must
  not reach a client); a reviewer reads only their own events. Additive: push it before the app that
  has the two `/api/pipeline/review-*` endpoints. 120–121 belong to another unpushed branch.
- **Deploy order is part of the migration.** App code that reads a new column or table needs the
  push first (104: an app ahead of it answered 500 on every series page). A migration that removes a
  grant, column or name old code uses needs the app first, or both in one deploy (101, 095). Say
  which in the header.
- **A full type regen rewrites hand-typed sections.** Regenerate to a temp file and reconcile the
  new block by hand (112, 118). The generator also drops SQL argument nullability.
- **095 renamed eight tables** (`ocr_extractions`→`ocr_labels`, `footprint_submissions`→`footprints`,
  `series_sheets`→`series_cells`, `sheet_sources`→`cell_printings`,
  `map_iiif_sources`→`map_images`, `map_opens`→`map_views`, `user_favorites`→`favorites`,
  `annotation_sets`→`user_layers`) and left compat views under the old names (`drop-compat-views`
  in ROADMAP). `maps.georef_done` is now `is_georeferenced`.
- **RLS gates rows, not columns.** Hide a private column by revoking column SELECT (101).
- **`security definer` trigger functions need `revoke execute ... from public`** or they are
  callable by RPC (099, 102).
- Wrap `auth.uid()` in policies as `(select auth.uid())` so it runs once per query (100).
- **An unknown `maps.collection` gets no `series_id`** — it is not silently added to `series`.
  Resolve or create the series explicitly before linking. Editing `collection` never changes
  `series_id`.
- **Per-cell coverage trusts only non-archived `maps` rows and institution items**, not the legacy
  `series_cells.held_by`/`map_id` snapshot. A pre-tiled raster with no source-item or map link is
  not counted as held.

Project ref `trioykjhhwrruwjsklfo` (Sydney) is linked. `supabase db push` and
`supabase migration list` work without a password; `supabase db pull` asks for one, so use the
Dashboard SQL Editor instead. Repair with `supabase migration repair --status applied|reverted <id>`.

## The local write-test stack

`npm run db:test` runs `supabase start -x vector -x logflare` and seeds one staff user + one map via
`scripts/seed-test-db.mjs`. `npm run test:write` (`tests/write.spec.ts`, 41 tests) runs against it,
never production: the suite throws unless `PUBLIC_SUPABASE_URL` is a loopback address, and deletes
every row it writes. Credentials come from `.env.test` (the CLI's published demo keys, committed on
purpose) which Vite loads for the `--mode test` dev server on port 5199. Server-route auth is done
by letting `@supabase/ssr` mint the session cookies, so chunking and encoding match the app exactly.

CI runs the same two commands on every PR (`.github/workflows/ci.yml`, job `write`) — a
GitHub runner has Docker natively, so the suite is verified there even when the machine
writing the migration cannot start the stack at all.

Local ports are **54421** for the API and **54420** for the shadow DB, not the CLI defaults —
54321/54320 collide with another local project. `-x vector -x logflare` is needed under colima:
those containers bind-mount `/var/run/docker.sock`, which colima cannot provide.
