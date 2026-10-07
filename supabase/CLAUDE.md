# supabase — schema, migrations, the local test stack

Root context: `/CLAUDE.md`. Table-by-table reference and the rule behind each constraint:
`docs/db-guidelines.md` §11.

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

**118 (`118_georef_provenance.sql`) is written and applied to the local stack only — not pushed.**
It adds nullable `method`, `method_ref`, `datum`, `derived_from`, `allmaps_map_id`, `review` to
`georef_versions` and `series.dataset_doi`. `src/lib/data/supabase/types.ts` has these hand-added;
regenerate after the push (a full local regen rewrites unrelated hand-typed sections). Push it
before running `georef_write.mjs --apply` against production: the writer sends the new columns,
and the insert fails without them.

**The head is 116**, pushed 2026-10-06: seven canonical map genres, independent
subjects and depicted state, image content roles, legacy classification and review
evidence. Migration 116 alone was pushed from an isolated migration directory;
115 was pushed after 116 on 2026-10-06 with `--include-all`; local and remote history now match.
The source-backed audit changed three charts to hydrographic and one administrative
map to thematic; six ambiguous originals remain needs_review. No publication or
identity fields changed. Linked maps/map_images types were regenerated and reconciled.
`tests/sql/map-taxonomy.sql` checks constraints, old plan/regional inputs and review
invalidation in disposable local PostgreSQL. Migration 115, in production 2026-10-06: `context_at` returned `legend_entry`,
`legend_ref` and `title` rows as "labels" (no category filter); it now takes only the five
gazetteer categories, by effective category. Before it, **114**, pushed 2026-10-06: boxes from different OCR runs on the same
map can be grouped. Each original keeps its run; the combined label uses the first
selected box’s run for existing run filters. Migration 113, pushed the same day,
ensures the group envelope comparison tolerates
one millionth of a source pixel, so PostgreSQL → JSON → JavaScript rounding does
not reject an unchanged selection; actual movement still fails. Migration 112,
pushed the same day, adds text-box grouping that preserves original
labels and their oriented geometry under a separate combined OCR label, using
ordered self-FKs and atomic group/ungroup RPCs. Search, context and the gazetteer
expose root labels; review verdicts preserve member states. The app remains
compatible with pre-112 databases and enables grouping after detecting the columns.
Read-back verified the OCR handler returns 200 with grouping available. Linked types
were regenerated to a temporary file and the grouping columns, relationships and
RPC signatures reconciled; nullable geography arguments remain explicit because
the generator omits SQL argument nullability. The app changes are local, not deployed.
`tests/sql/text-groups.sql` verifies membership and reversibility in disposable local
PostgreSQL with spatial stand-ins.

Before it, **111** (pushed 2026-10-05: nullable `maps.regions` and `regions_2025` province arrays, derived from bbox; catalog Area facets match every listed province. Normal sheets use a 10% land-sample cutoff; sheets spanning over 2° on either axis use 2% and a finer grid, with no dominant region. Final read-back: 933 lists, 392 multi-province maps, 566 without lists, and no dominant province missing from its list). Before it, **110** (`maps.edition`, backfilled from `extra_metadata`; `holding_institution` filled from `source_archive = 'PCL'` on the 510 rows that had none — pushed 2026-10-05). Before it, **109** (pushed 2026-10-05: nullable `maps.region`, the 63-province name to June 2025, and `region_2025`, the 34 since, both derived from `bbox` by `scripts/oneoff/backfill_map_region.mjs` — a modern locator, not the historical place name). Through 108 it was pushed 2026-10-04 during the series-page recovery. The coordinated app/types work had deployed before migrations 105–108, causing 500 responses on missing tables/views. 105 creates stable `series` UUID identities; `maps.series_key` becomes a stored compatibility copy synced from `series_id`, so editing `collection` cannot change membership. `series_cells` retains its legacy composite key and gains an id/FK. 106 adds unresolved-capable `sheet_printings`, nullable printing/source-item links, image dimensions/version metadata and link-consistency triggers; it does not invent printing identities. `series_cell_coverage_detail` and `series_printing_availability` derive availability with explicit public/service-role gates. 107 adds staff-controlled archiving and a one-hop duplicate pointer; 108 corrects the `maps.status` default to `draft`.

An unknown `maps.collection` on insert keeps its legacy folded `series_key` for compatibility but has no `series_id`; it is not silently added to the curated `series` table. Resolve/create the stable series explicitly before linking it. An edit to `collection` on an already linked map never changes `series_id`.

The per-cell coverage view derives holding only from non-archived `maps` rows and institution items; it intentionally stops trusting legacy `series_cells.held_by`/`map_id` snapshots. A pre-tiled raster layer with no normalized source-item or map link therefore is not counted as held. Add an explicit raster asset/source relation before relying on derived coverage for those holdings.

104 adds
`maps.series_key`, a generated column (`series_key(collection)`, mig 082's function), and rebuilds
`map_series` on it. The series coverage page and `fetchSheetEditions` now filter on it, so an app
deployed ahead of the push would have answered 500 on every `/catalog/series/<key>` — and the read-only suite,
which reads production, fails the same way until it lands. 104 also copies `extra_metadata.sheet_number`
/ `sheet_half` into their typed columns for the 188 first-edition rows 095's one-off backfill missed;
`ingest_indochine_100k_nakala.mjs` now writes the columns itself. `collection` is still the only
input: the key is not independent of the label until a `series` table exists (`series-identity`).
Regenerate types after the push (104's `series_key` was hand-typed, Row only).

103 (pushed; its routes record a
row after writing each history file and answer 500 if the table is missing, so an app deployed
ahead of the migration fails every publish, sync and neatline save *after* its history file is
already written — the reverse of 101's order). 102 is live in production (verified 2026-10-01 via
`supabase migration list`). 103 adds `georef_versions` (anon/authenticated lose `user_id`, as 101 did for footprints), one row per stored georeference version
(`annotations/<map>/<stamp>.json`), and the `map_georef_current` view (newest stamp per map). Every
writer records its row right after the history file and before the live file moves:
`mirrorAnnotation`, the neatline `PATCH`, `sync_district4_annotations.mjs`. `geom_src` comes from
`$lib/core/georef/version.ts`, the one hash implementation, which the scripts import by path. After
the push, run `node --env-file=.env scripts/backfill_georef_versions.mjs --apply` to record what
Storage already holds, and regenerate the types (103's were hand-typed). 102 revokes PUBLIC execute on `maps_guard_contributor_slug()`, the
trigger function 097 added and 099 missed. 101 narrows `map_images` and `map_slug_aliases`'s read policies from
"published or any signed-in user" to "published, the map's creator, or staff" — the two
draft-visibility gates copying 063's wording that nothing non-staff actually reads that broadly —
and revokes anon's SELECT on `footprints.review_note`/`.review_tags`/`.reviewed_by`/`.user_id` (and
the matching columns on the `footprint_submissions` compat view), since RLS gates rows, not columns,
and a public map's `footprints` rows were handing the anon key a reviewer's private notes and both
parties' user ids. `maps` and `ocr_labels` keep the wider "published or any signed-in user" read
policy on purpose — `/scan?mode=inspect` (no role gate) and `fetchGeorefQueue`/`fetchLabelMaps`
(`src/lib/data/maps/georef.ts`, `src/lib/data/supabase/footprints.ts`) depend on any signed-in
volunteer being able to read *any* draft, not only their own, which is what the open-contribution
model in 063/079 means. **Deploy the app before pushing 101**: the old export route selects
`footprints.*` on the anon key and would 42501 against the new grants. 101's own header has the full per-table audit trail.
092 nulls out the
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
did for `maps`. 097 closes the moderation, worker-claim, map visibility, slug, and direct-write
security gaps; it must ship alongside the API changes and its generated types must be refreshed
from the linked project after `db push`. 098 sets `security_invoker = true` on the
`map_pipeline_status` view, making explicit that it runs as the querying role now that 097 has
already revoked `select` from anon/authenticated. 099 revokes `PUBLIC`'s default `EXECUTE` grant
on the four `security definer` trigger-only functions (`handle_new_user`,
`maps_assign_slug`, `maps_demote_bare_slug`, `enqueue_publish_jobs`), so they can no longer be
called directly via RPC — trigger execution itself is unaffected, since a trigger always runs as
its owner. 100 wraps every bare `auth.uid()`/`auth.role()` call inside an RLS policy's
`USING`/`WITH CHECK` in `(select auth.uid())`, so Postgres evaluates it once per query (an
InitPlan) instead of once per row; access rules are unchanged. Drop a new
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
`scripts/seed-test-db.mjs`. `npm run test:write` (`tests/write.spec.ts`, 38 tests) runs against it,
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
