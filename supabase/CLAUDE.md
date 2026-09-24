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
- **`maps.slug` is minted by Postgres, never by a caller** (mig 088): `map_slug_base` folds the
  name, `map_slug_mint` applies name → name-year → name-year-N, and two triggers keep it true. A
  rename does not re-address a sheet; clearing `slug` re-mints it and files the old one in
  `map_slug_aliases`. The `default ''` on the column is load-bearing — it is what keeps `slug`
  optional in the generated `Insert` type.
- The gazetteer key exists twice — `place_core_key()` here and `placeCoreKey` in
  `$lib/core/utils/placeKey.ts`. They must agree or a place page 404s.

## Adding a migration

Head is **096**, local (094 pushed 2026-09-23; 095/096 not yet pushed). 092 nulls out the
`'Vietnam Map Archive'` placeholder in `maps.collection` (it meant "no series," not a series —
collapsed a live bug in `annotationMirror.ts` that was stomping real series membership on every
re-mirror); 093 collapses spelling/language duplicates in `language`/`dc_publisher`/`rights`; 094
adds the CHECK constraint `map_type` never had. 095 is the schema half of one review vocabulary:
renames `ocr_extractions`→`ocr_labels`, `footprint_submissions`→`footprints`,
`series_sheets`→`series_cells`, `sheet_sources`→`cell_printings`, `map_iiif_sources`→`map_images`,
`map_opens`→`map_views`, `user_favorites`→`favorites`, `annotation_sets`→`user_layers` (compat views
under the old names bridge `db push` to deploy — drop them in a later migration, not yet written);
renames the `status`/`validated_*`/`reviewer_id` columns onto one vocabulary
(`review_status`/`reviewed_by`/`reviewed_at`) across `ocr_labels`, `footprints`, `scout_candidates`,
`stories`; drops `maps.iiif_manifest`/`ia_identifier`/`dc_coverage`/`dc_subject`/`legend_done`/
`help_needed`; renames `maps.georef_done`→`is_georeferenced`, `dc_publisher`→`publisher`,
`dc_description`→`description`, `year_label`→`date_label`; adds `maps.sheet_number`/`sheet_half`
and `triage_reviewed_at`/`triage_reviewed_by` as typed columns backfilled from the
`extra_metadata`/`triage` JSON (the JSON keys stay, for old deployed code — see the migration
header); sets `created_by default auth.uid()`; sets `status`/`created_at`/`updated_at`/`source_type`
`NOT NULL` (`source_type` also gets `default 'other'`) — `iiif_image`/`thumbnail` deliberately do
NOT get `NOT NULL`, because BulkUpload's create-then-tile flow and several `write.spec.ts` fixtures
insert without them; recreates every function whose body referenced a renamed/dropped name.
**Unrenamed table, column renamed, no compat view: `maps` (`georef_done` etc.), `stories.status`,
`scout_candidates.status`/`.reviewer_id`.** A view can't share a table's name, so these four have no
bridge — any code still using the old column name breaks the moment 095 is pushed, which is why 095
has to ship in the same deploy as the app-code update, not ahead of it. 096 is the data half: the
series-sheet name cleanup (Indochine 1:100,000 "Est/Ouest" suffixes, Tonkin transcription fixes,
L7014/L909 sheet-code suffixes, hyphen spacing — `collection is not null` only, 303 rows on the
production corpus, 0 slug moves), nulls `maps.location` where it only duplicated the series, and
collapses rights/language spelling variants on `scout_candidates` and `cell_printings` the way 093
did for `maps`. Drop a new
`supabase/migrations/NNN_*.sql`
incrementing from head, `supabase db push`, then regenerate types:

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
`scripts/seed-test-db.mjs`. `npm run test:write` (`tests/write.spec.ts`, 33 tests) runs against it,
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
