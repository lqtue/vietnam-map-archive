# VMA Database Design Guidelines

This document is the canonical reference for schema decisions. All migrations must follow these
rules. Deviations require a comment in the migration explaining why.

---

## 1. Identifiers

### Primary key
Every table has exactly one PK:
```sql
id uuid primary key default gen_random_uuid()
```

### Canonical map identifier
`maps.id` (UUID) is the single canonical reference to a map. Use it everywhere.

`maps.slug` (mig 088) is an **address, not an identity**: it is what `/catalog/<slug>` and
`?map=<slug>` carry so a shared link says what is on the other end. It can be re-minted and a
collision can move it, which is exactly why it is never a foreign key, never a join key, and never
what `/api/*` takes. Old addresses are kept in `map_slug_aliases` rather than dropped.

`maps.allmaps_id` is a **service credential** — the Allmaps API key for this map's annotation. It is
only used when calling Allmaps endpoints (building annotation URLs, loading warped tile layers). It
is never a join key or URL parameter.

Resolved (Aug 2026): `mapStore.activeMapId` now holds the `maps.id` UUID, mirrored from
`layersStore.topOverlay`; the map deep-link is the `?map=<uuid>` query param, and the `&map=` hash
writer is gone. The old `supabase/maps.ts` shim was deleted — read through
`src/lib/data/maps/service.ts`.

### Foreign keys
All FK columns reference the PK (`id uuid`). Text pseudo-FKs are not permitted.

```sql
-- correct
map_id uuid not null references public.maps(id) on delete cascade

-- forbidden
map_id text   -- no FK, no integrity
allmaps_id text  -- service credential used as join key
```

---

## 2. Naming

| Concept | Column name | Example |
|---------|------------|---------|
| Primary key | `id` | `id uuid primary key` |
| Foreign key | `{table_singular}_id` | `map_id`, `story_id`, `run_id` |
| User identity | `user_id` | `user_id uuid references auth.users` |
| Boolean flag | `is_{state}` | `is_featured`, `is_public`, `is_primary` |
| Creation time | `created_at` | `created_at timestamptz default now()` |
| Mutation time | `updated_at` | see § 4 |
| Status lifecycle | `status` | `status text check (...)` |

Never use `submitted_by`, `author_id`, `owner_id` — always `user_id`.

Table names are plural snake_case matching the domain, not the feature that happens to use them
(`maps`, `footprints`, `story_points` — not `hunts`, which was dropped in migration 034
when the feature was renamed).

---

## 3. Required columns

Every table must have:
```sql
id         uuid primary key default gen_random_uuid()
created_at timestamptz default now()
```

Tables where rows are mutated after insert (status changes, edits) must also have:
```sql
updated_at timestamptz default now()
```
…with an auto-update trigger (see § 4).

---

## 4. Auto-update trigger pattern

Use a shared trigger function per table. Name it `{table}_set_updated_at`:

```sql
create or replace function public.{table}_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger {table}_updated_at
  before update on public.{table}
  for each row execute function public.{table}_set_updated_at();
```

---

## 5. Status fields

Use `text` with a `CHECK` constraint. Never use Postgres enums (hard to add values).

```sql
status text not null default 'open'
  check (status in ('open', 'in_progress', 'approved', 'rejected'))
```

Always add a comment documenting valid transitions:
```sql
comment on column public.{table}.status is
  'Lifecycle: open → in_progress → approved | rejected';
```

---

## 6. User roles

Valid values for `profiles.role`: `'admin'`, `'mod'`, `null` (default).

- `admin` — full write access, publish maps, manage users
- `mod` — approve/reject footprints, enrich catalog metadata
- `null` — default for any authenticated user; can label, georeference, submit footprints

The CHECK constraint on `profiles.role` must reflect all valid values. (`cataloger` was renamed to
`mod` in migration 038.)

---

## 7. Denormalization policy

Denormalized columns are only permitted when:
1. The source of truth is in another table
2. A trigger keeps the copy in sync
3. Both the column and the trigger have SQL comments documenting the relationship

Example: `maps.iiif_image` is a cache of the primary `map_images` row, synced by
`sync_primary_iiif_to_map` trigger.

Never denormalize FKs. If you need `maps.allmaps_id` in a child table, join through
`map_id → maps.allmaps_id` at read time.

---

## 8. JSONB columns

Use JSONB for:
- Flexible metadata where keys are user-defined (`extra_metadata jsonb default '{}'`)
- GeoJSON geometry (`pixel_polygon`, `features`)
- Configuration objects with fixed structure (`challenge`, `camera`)

Do not use JSONB for data that needs to be filtered, sorted, or indexed — give those fields their
own columns.

Always default to `'{}'` (objects) or `'[]'` (arrays), never `null`.

---

## 9. RLS patterns

All tables must have `alter table ... enable row level security`.

| Access | Policy pattern |
|--------|---------------|
| Public read | `using (true)` |
| Own rows | `using (auth.uid() = user_id)` |
| Admin write | `using (exists (select 1 from profiles where id = auth.uid() and role = 'admin'))` |
| Automated pipeline (service key, no auth.uid) | `with check (user_id is null)` |

---

## 10. Migration hygiene

- One concern per file. Schema change + its data backfill belong together; unrelated changes go in
  separate files.
- Always use `if not exists` / `if exists` / `or replace` on all DDL.
- Never amend a pushed migration. Add a new one.
- Number files as `NNN_short_description.sql`. Gaps in numbering are fine.
- After dropping a column or table, delete or stub the corresponding TypeScript types in the same
  PR.
- **Never change schema in the Dashboard SQL Editor.** An object edited there is invisible to
  `supabase/migrations/`, and the cost lands on whoever writes the next migration that rebuilds it,
  not on whoever made the edit. Learned on 070: production's `pipeline_jobs_kind_check` had been
  widened by hand to allow `warp`, no migration recorded it, and 070 rebuilt the list from the
  migrations — dropping a kind that was in use and failing on existing rows
  (`check constraint "pipeline_jobs_kind_check" ... is violated by some row`). It rolled back
  cleanly, but only because a check constraint is the *gentle* version of this: the same mistake on
  a policy or a trigger silently removes protection instead of refusing. If a hotfix in the
  Dashboard is genuinely unavoidable, write the matching migration the same day.
- A migration that rebuilds an enumerated constraint should therefore assert against reality first,
  not against the previous migration: `select distinct kind from pipeline_jobs` costs nothing and
  would have caught this.

---

## 11. Current schema (production head 104; additive model migrations 105–108 pending rollout)

Table/column names below were renamed in mig 095 (`ocr_extractions`→`ocr_labels`,
`footprint_submissions`→`footprints`, `series_sheets`→`series_cells`, `sheet_sources`→
`cell_printings`, `map_iiif_sources`→`map_images`, `map_opens`→`map_views`, `user_favorites`→
`favorites`, `annotation_sets`→`user_layers`; `status`/`validated_*`/`reviewer_id` columns onto
`review_status`/`reviewed_by`/`reviewed_at`; `maps.georef_done`→`is_georeferenced`,
`dc_publisher`→`publisher`, `dc_description`→`description`, `year_label`→`date_label`). Compat
views under the old table names exist until the deploy carrying this rename has shipped —
`supabase/CLAUDE.md` has the full list and what has no such bridge.

Moved here from `CLAUDE.md` in September 2026. The table lists what exists; the paragraphs after it
are the rules a migration must not undo.

| Table | Purpose | Notes |
|-------|---------|-------|
| `maps` | Map catalogue and scan workspace | `id` remains the scan/workspace identity; `slug` remains its address. Pending mig 105 adds nullable stable `series_id` and keeps `series_key` as a synchronized compatibility key; mig 106 adds nullable `printing_id`; mig 107 adds `archived`, `duplicate_of_map_id`, and `archive_reason`; mig 108 corrects the status default to `draft`. |
| `series` | Stable survey identity (pending mig 105) | UUID PK, durable unique `key`, mutable `name`, optional code and scale. Rename the display name without changing survey membership. |
| `series_cells` | One index row per survey cell | Pending mig 105 adds UUID `id` and `series_id`; the old `(series_key, sheet_number)` PK remains for compatibility and `(series_id, sheet_number)` is unique. Multiple printings never add denominator cells. |
| `sheet_printings` | Bibliographic identity for one printing of one cell (pending mig 106) | UUID identity; nullable descriptive and date assertions; `review_status` is `unreviewed | verified | uncertain`. No identity is inferred from years/edition labels and there is no bulk printing backfill. |
| `cell_printings` | Institution catalogue item/source assertion | Existing item identity and `(institution, source_ref)` stay intact; pending migrations add `series_id` and nullable `printing_id`. Null printing link means unresolved, not held identity. |
| `map_images` | Image source and asset evidence | Existing map link stays; pending mig 106 adds nullable `source_item_id`, dimensions, content hash and asset version. Each separately scanned copy keeps its own `maps` workspace and processing history. |
| `map_slug_aliases` | Addresses a sheet used to answer on (mig 088) | `slug` PK, `map_id → maps.id`. Written by the trigger when a sheet is demoted off a bare name or deliberately re-minted; `/catalog/[id]` 301s them. A slug is never both canonical and an alias |
| `profiles` | Per-user role | `user`, `mod`, `admin`; read via `fetchUserRole` |
| `scout_candidates` | External discoveries (mig 045) | `source`, `external_id` (unique with source), `manifest_url`, `score`, `category`, `review_status` (mig 095, was `status`; `pending/approved/rejected/ingested`), `reviewed_by` (mig 095, was `reviewer_id`), `map_id` on ingest, `raw` JSONB |
| `map_views` | Per-map open tally (mig 049; mig 095, was `map_opens`) | Fire-and-forget insert from /explore |
| `label_pins` | Point annotations | `map_id → maps.id`, pixel coords. `label_tasks` was dropped in mig 038 |
| `footprints` | Polygon traces + SAM2 output (mig 095, was `footprint_submissions`) | `map_id → maps.id`; `review_status` (mig 095, was `status`) ∈ `draft/submitted/needs_review/approved/rejected`, source ∈ `volunteer/sam-auto/sam-corrected/import` (both widened in mig 055 — 038's lists rejected every SAM2 write); `pixel_polygon`; `run_id` (mig 057) pins a segmentation run so the OCR join cannot mix runs. `review_note`/`review_tags`/`reviewed_by`/`user_id` are column-revoked from `anon` (mig 101, column-level `grant`, since RLS gates rows not columns) — any anon `select` must name columns, not `*` |
| `user_layers` | User GeoJSON (mig 095, was `annotation_sets`) | `map_id → maps.id` nullable, `user_id → auth.users` |
| `ocr_labels` | OCR bbox results (mig 095, was `ocr_extractions`) | `(map_id, run_id, tile_x, tile_y, text, global_xi, global_yi)` unique (mig 077 — the key was position-blind, so eight distinct `Rue` labels in one tile collapsed to one row; `global_xi`/`global_yi` are generated `round(global_x/y)` and exist only because PostgREST cannot name an expression index in `on_conflict`). `global_x`/`global_y` are now `not null`; `global_*` are full-image px — the **derived** axis-aligned box around a label that may run at any angle, whose own rectangle is `rotation_deg` + `label_w`/`label_h` (mig 076; null on pipeline rows, where the size is inverted out of the box instead, and unrecoverable within ~2° of 45°). Every geometry write sends both; `review_status` (mig 095, was `status`) ∈ `pending/validated/rejected`; `text_corrected`/`category_corrected` (mig 095, was `text_validated`/`category_validated`); `reviewed_by`/`reviewed_at` (mig 095, was `validated_by`/`validated_at`); `footprint_id` (mig 050) is the OCR↔footprint join. Read policy inherits the map's gate since mig 065 (published, or any signed-in user) |
| `pipeline_jobs` | Work queue between web and workers (mig 053) | `kind` (10 values incl. `join` mig 061, `layout` mig 070) · `status` (`queued/claimed/running/done/failed/cancelled`) · `payload` jsonb · retry via `attempts < max_attempts`. Partial unique index = one live job per (kind, map). Service-role only. Claim/close with the `claim_job` / `finish_job` RPCs — since mig 077 `claim_job` also reclaims a job held in `claimed`/`running` for over 3 hours with attempts left, because nothing else ever un-stuck one and that partial index then blocked its map for good |
| `worker_keys` | Per-machine revocable worker credentials (mig 053) | `token_hash` (sha256), `kinds`, `revoked_at`. Written in step 2; the table exists now |
| `map_pipeline_status` | Per-map pipeline state — **a view since mig 056** | Machine stages derived from `pipeline_jobs`, human stages from `map_review_marks`. Read-only; nothing writes it |
| `map_review_marks` | The three stages a person asserts (mig 056) | `reviewed_at`, `seg_reviewed_at`, `exported_at`. Written only by the `set_review_mark` RPC |
| `stories`, `story_points` | Stories/tours | `hunts` / `hunt_stops` were dropped in mig 034, `story_progress` in mig 075 — /trip/[id] keeps progress in localStorage. Since mig 059 a story has `review_status` (mig 095, was `status`; `draft/submitted/approved/rejected`) + `reviewed_by`/`reviewed_at`, and **`is_public` is gone** — publishing submits for review, and only `approved` is publicly readable |
| `favorites` | Saved maps (mig 095, was `user_favorites`) | via `data/supabase/favorites.ts` |
| `map_series` | Compatibility series view | Existing output columns retained by pending mig 105; joined by stable series identity, with public/draft role gate. |
| `series_cell_coverage`, `series_printing_availability` | Derived coverage and availability views (pending migs 105–106) | Count distinct cells and printings separately; public maps, external items, and scan workspaces are separate measures. Explicit gates protect service-role reads. |

Migrations 105–108 are additive in the implementation branch and are not yet a production rollout. The migration-level regression fixture is `tests/sql/l7014-model.sql`; it applies these four migrations to a disposable pre-105 schema and checks the identity, uniqueness, relationship, default, archive, and role-gate rules. Run it only in the dedicated local database named `vma_l7014_model` using `npm run test:model-sql`.

For rollout, apply migrations 105–108 before deploying the app code that selects the new columns and views; then regenerate `src/lib/data/supabase/types.ts` from the linked production schema and run the full check/build gates. The branch's type declarations are hand-aligned for local development, not proof that production has the schema. The standalone SQL fixture does not replay the complete migration history or replace `supabase db:test:reset`. Keep printing links null until a reviewer has evidence; do not backfill them from year/edition fields.

`maps.status` was `draft | public | featured` through mig 104. Pending mig 107 adds `archived`; pending mig 108 sets omitted status to `draft`. The older
`pending_georef → georeferenced → processing → published` values fail `maps_status_check`.

**Status transitions live in Postgres** (mig 054), not in the API:
`set_extraction_status(status, user, ids?, map_id?, run_id?)` applies the
`validated_at`/`validated_by` stamp, `revert_recent_validations(map_id, user, window_mins)` undoes
one reviewer's recent work, and `set_footprint_status(id, status, user, …)` moves a polygon out of
`needs_review` exactly once and marks a reshaped one `sam-corrected`;
`set_review_mark(map_id, stage, user)` (mig 056) records a human pipeline stage. With
`claim_job`/`finish_job` (mig 053) these are the write paths the API, the workers and any future
direct client all share. All are `security definer`, granted to `service_role` only.

**One visibility model on `maps`** (mig 060): the `status` enum. `is_public` / `is_featured` were
dropped and the four RLS policies that read them rewritten onto `status`. The only `is_public` left
is `user_layers.is_public`, a per-user sharing flag, not map visibility. Do not add a second
model.

`source_type` (mig 027, extended by mig 041): `ia | bnf | efeo | gallica | rumsey | self | other | r2`.

**Draft maps are not anonymously readable** (mig 063): `maps_select_all … using (true)` had stood
since migration 001, so the publishable key — which ships in every client bundle — returned every
draft row. The gate is authentication, not role:
`status in ('public','featured') or auth.uid() is not null`. Restricting to admin/mod would break
open contribution, because `fetchGeorefQueue` selects drafts by status and the digitalize/trace
pickers are mostly unpublished maps. Covered by a write smoke that fails against the old policy.

**A published map must be georeferenceable** (mig 062): `status in ('public','featured')` requires
`annotation_url` **or** `allmaps_id`. Not `annotation_url NOT NULL` as originally planned — that
deadlocks, since publishing is what enqueues `mirror_annotation`. Full self-hosting is the queue's
job, not the constraint's.

**Publishing enqueues hosting work** (mig 058): moving a map to `public`/`featured` fires
`enqueue_publish_jobs()`, which queues `mirror_annotation` (when `annotation_url` is null) and
`tile_to_r2` (when `source_type` isn't already `r2`). `on conflict do nothing` rides the
one-live-job index, so re-publishing never duplicates. **Mig 080** widened the trigger to
`update of status, is_georeferenced` (mig 095, was `georef_done`) and added a second entry
condition: `is_georeferenced` going false → true
on an already-published map queues `mirror_annotation` too, because georeferencing usually happens
*after* publishing and the old early-return on an unchanged status meant the sync-georef flip queued
nothing. `tile_to_r2` stays on the publish path only — a georeference does not move tiles. Since
2026-09-06 the worker claims both by default (`tile_to_r2` only where vips + rclone are installed),
so a worker left running finishes what publishing starts; `annotation_url NOT NULL` for public maps
waits until that has proven itself over a few publishes.

**Full-text search** (mig 046): both `maps` and `scout_candidates` have a
`search_vector tsvector GENERATED STORED` column + GIN index. `simple` config (not `english`) is
intentional — the corpus is multilingual French/Vietnamese/English. Query via
`.textSearch('search_vector', q, { config: 'simple', type: 'plain' })`.

---

### Map classification (migration 116)

`maps.map_type` is one primary cartographic genre: general_reference, city_plan,
topographic, cadastral, hydrographic, route or thematic; null means unknown.
`map_subjects` is a controlled, deduplicated array of optional themes.
`depicted_state` (observed/proposed/mixed/unknown) describes drawn conditions,
independently of publication `status`. Geographic extent belongs to the existing
region/province fields, and `map_images.content_role` describes a scan's role
(main_map/index_map/legend/text/unknown), independently of the parent genre.

Legacy type assertions are preserved in `map_type_legacy`; plan/regional inputs
normalize on write to city_plan/general_reference. Inherited classifications are
provisional. A reviewed verdict requires classification_reviewed_by,
classification_reviewed_at and a nonblank classification_note; source URLs are
stored separately. Changes to genre, subjects or depicted state invalidate a
review, as does deleting its reviewer. Generic map APIs accept subjects/state
and evidence, but cannot set the reviewer, timestamp or reviewed status.


## Current known debt

| Item | Location | Fix |
|------|---------|-----|
| `label_pins` outlives its feature | `label_tasks` was dropped in mig 038 but `label_pins` remains, now written only by `POST /api/admin/maps/[id]/ocr/apply` | Either fold into `ocr_labels` or document it as the OCR-applied point layer |
| Generated types drift silently | `src/lib/data/supabase/types.ts` | Nothing regenerates them. Remote head is **116** (115 remains pending). The maps/map_images sections were reconciled against linked generated output on 2026-10-06; the remainder keeps the previously reconciled table/RPC types. Re-run after every push: `supabase gen types typescript --linked`. This row named head 075 for five migrations once, which is the drift it exists to warn about |
| Compat views for 095's table renames need dropping | `public.ocr_extractions`, `.footprint_submissions`, `.series_sheets`, `.sheet_sources`, `.map_iiif_sources`, `.map_opens`, `.user_favorites`, `.annotation_sets` | Drop once the deploy that reads the new names has shipped. `maps`/`stories`/`scout_candidates`'s renamed *columns* have no such bridge — see `supabase/CLAUDE.md` |
| Production drifted from the migrations once | `pipeline_jobs_kind_check` allowed `warp` with no migration saying so; corrected in 070 | Nothing to fix now — but it means the migrations are not provably the whole schema. A `db pull` diff would settle it, and needs the direct DB password |
