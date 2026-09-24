-- Migration 095 — one review vocabulary, and the names the schema should have had
--
-- Eight tables and a dozen columns carry names left over from earlier features
-- (`ocr_extractions`, `footprint_submissions`) or from a review model that grew
-- three different words for the same idea (`status`/`validated_by` on OCR labels,
-- `status`/`reviewer_id` on scout candidates, `status` on stories and footprints).
-- This is the schema half of that cleanup: rename, backfill, and recreate every
-- function/view whose body is opaque text and therefore does NOT follow a
-- rename — Postgres tracks renames for views, policies, indexes, constraints and
-- triggers (they are stored as parsed expressions keyed by attnum/OID), but a
-- PL/pgSQL or SQL function body is a string, and a table's declared return type
-- is only safe because ALTER TABLE RENAME renames the row type with it.
--
-- Compat views (section 1) keep the live site and the R2 worker answering
-- between `db push` and deploy. They are dropped in a later migration, once the
-- deploy carrying the renamed reads has shipped — do not add that migration here.
--
-- Data changes (the name-cleanup rules, the rights/language collapses) are
-- migration 096, kept separate per docs/db-guidelines.md §10 (schema change and
-- its own backfill together; unrelated changes apart).

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Table renames + compat views
-- ────────────────────────────────────────────────────────────────────────────

alter table public.ocr_extractions       rename to ocr_labels;
alter table public.footprint_submissions rename to footprints;
alter table public.series_sheets         rename to series_cells;
alter table public.sheet_sources         rename to cell_printings;
alter table public.map_iiif_sources      rename to map_images;
alter table public.map_opens             rename to map_views;
alter table public.user_favorites        rename to favorites;
alter table public.annotation_sets       rename to user_layers;

-- ────────────────────────────────────────────────────────────────────────────
-- 2. Column renames — one review vocabulary
-- ────────────────────────────────────────────────────────────────────────────

alter table public.ocr_labels
  rename column status              to review_status;
alter table public.ocr_labels
  rename column text_validated      to text_corrected;
alter table public.ocr_labels
  rename column category_validated  to category_corrected;
alter table public.ocr_labels
  rename column validated_by        to reviewed_by;
alter table public.ocr_labels
  rename column validated_at        to reviewed_at;

alter table public.footprints
  rename column status to review_status;

alter table public.scout_candidates
  rename column status      to review_status;
alter table public.scout_candidates
  rename column reviewer_id to reviewed_by;

alter table public.stories
  rename column status to review_status;

alter table public.maps
  rename column georef_done  to is_georeferenced;
alter table public.maps
  rename column dc_publisher to publisher;
alter table public.maps
  rename column dc_description to description;
alter table public.maps
  rename column year_label   to date_label;

-- Views, RLS policies, CHECK constraints and index predicates that read any of
-- the columns above are stored as parsed expressions (by attnum), not text, so
-- they follow the rename with no action here — verified on a from-scratch
-- replay. Only opaque function bodies (section 4) need rewriting.

-- ────────────────────────────────────────────────────────────────────────────
-- 3. Compat views — old name, new table, same shape callers already read
--
-- Plain `select *` where no column moved; an aliased select where one did.
-- Both forms are simple/auto-updatable views, so PostgREST upserts with
-- `on_conflict` keep working — checked directly against the OCR worker's
-- write path (an upsert through `ocr_extractions` with the same
-- `on_conflict` key mig 077 defined, merging rather than duplicating).
-- ────────────────────────────────────────────────────────────────────────────

create view public.ocr_extractions
with (security_invoker = true) as
select
  id, map_id, run_id, tile_x, tile_y, tile_w, tile_h,
  global_x, global_y, global_w, global_h,
  category, text, confidence, rotation_deg, notes, model, prompt, created_at,
  review_status         as status,
  reviewed_at           as validated_at,
  reviewed_by           as validated_by,
  text_corrected        as text_validated,
  category_corrected    as category_validated,
  footprint_id, geom, geom_src, geom_rmse, label_w, label_h, global_xi, global_yi
from public.ocr_labels;

comment on view public.ocr_extractions is
  'Compat alias for ocr_labels (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.ocr_extractions to anon, authenticated, service_role;

create view public.footprint_submissions
with (security_invoker = true) as
select
  id, user_id, pixel_polygon, name,
  review_status as status,
  created_at, feature_type, map_id, iiif_canvas, source, valid_from, valid_to,
  confidence, temporal_status, category, updated_at, run_id, geom, geom_src, geom_rmse,
  review_tags, review_note, reviewed_by, reviewed_at
from public.footprints;

comment on view public.footprint_submissions is
  'Compat alias for footprints (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.footprint_submissions to anon, authenticated, service_role;

create view public.series_sheets
with (security_invoker = true) as
select * from public.series_cells;

comment on view public.series_sheets is
  'Compat alias for series_cells (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.series_sheets to anon, authenticated, service_role;

create view public.sheet_sources
with (security_invoker = true) as
select * from public.cell_printings;

comment on view public.sheet_sources is
  'Compat alias for cell_printings (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.sheet_sources to anon, authenticated, service_role;

create view public.map_iiif_sources
with (security_invoker = true) as
select * from public.map_images;

comment on view public.map_iiif_sources is
  'Compat alias for map_images (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.map_iiif_sources to anon, authenticated, service_role;

create view public.map_opens
with (security_invoker = true) as
select * from public.map_views;

comment on view public.map_opens is
  'Compat alias for map_views (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.map_opens to anon, authenticated, service_role;

create view public.user_favorites
with (security_invoker = true) as
select * from public.favorites;

comment on view public.user_favorites is
  'Compat alias for favorites (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.user_favorites to anon, authenticated, service_role;

create view public.annotation_sets
with (security_invoker = true) as
select * from public.user_layers;

comment on view public.annotation_sets is
  'Compat alias for user_layers (mig 095). Dropped once the deploy has shipped.';
grant select, insert, update, delete on public.annotation_sets to anon, authenticated, service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. maps column changes
-- ────────────────────────────────────────────────────────────────────────────

-- search_vector depends on dc_coverage/dc_subject (being dropped) and reads
-- dc_publisher/year_label (already renamed above), so it has to go before the
-- drops below and gets rebuilt in full at the end of this section.
alter table public.maps drop column search_vector;

-- Dead/duplicated columns. iiif_manifest and dc_coverage/dc_subject are folded
-- into search_vector's rebuild below or dropped outright; legend_done and
-- help_needed have no writer left (their trigger was dropped in mig 075) and
-- ia_identifier has no reader.
alter table public.maps
  drop column if exists iiif_manifest,
  drop column if exists ia_identifier,
  drop column if exists dc_coverage,
  drop column if exists dc_subject,
  drop column if exists legend_done,
  drop column if exists help_needed;

-- sheet_number / sheet_half as real columns. The JSON keys in extra_metadata
-- stay — old deployed code and scripts/ still read them — this only adds the
-- typed columns new code reads/writes. A later cleanup migration strips the
-- JSON keys once nothing reads them.
alter table public.maps
  add column if not exists sheet_number text,
  add column if not exists sheet_half   text check (sheet_half in ('E', 'W', 'whole'));

update public.maps set sheet_number = extra_metadata ->> 'sheet_number'
 where extra_metadata ? 'sheet_number' and sheet_number is distinct from extra_metadata ->> 'sheet_number';

update public.maps set sheet_half = extra_metadata ->> 'sheet_half'
 where extra_metadata ? 'sheet_half' and sheet_half is distinct from extra_metadata ->> 'sheet_half';

create index if not exists idx_maps_collection_sheet_number
  on public.maps (collection, sheet_number);

-- triage_reviewed_at/by as real columns, same reasoning: extra_metadata's
-- sibling, triage, keeps its 'validated_at'/'validated_by' keys (set_triage_key
-- below now writes both), and this adds the typed columns.
alter table public.maps
  add column if not exists triage_reviewed_at timestamptz,
  add column if not exists triage_reviewed_by uuid references auth.users(id) on delete set null;

update public.maps set triage_reviewed_at = (triage ->> 'validated_at')::timestamptz
 where triage ? 'validated_at' and triage ->> 'validated_at' is not null;

-- Guarded by an existence check against auth.users: triage_reviewed_by is a
-- real FK (on delete set null), unlike the JSON key it backfills from, so a
-- stale uuid in triage.validated_by (a deleted account) must not fail the
-- whole migration the way it would with a bare cast.
update public.maps m set triage_reviewed_by = (m.triage ->> 'validated_by')::uuid
 where m.triage ? 'validated_by'
   and m.triage ->> 'validated_by' is not null
   and exists (select 1 from auth.users u where u.id = (m.triage ->> 'validated_by')::uuid);

-- created_by: every insert path audited (BulkUpload -> POST /api/admin/maps,
-- scout ingest -> POST /api/admin/scout, scripts/seed-test-db.mjs,
-- tests/write.spec.ts) uses adminClient() / the service-role key, which never
-- carries a auth.uid(). The default is therefore inert today — service-role
-- inserts still land created_by = null, exactly as before — and only takes
-- effect the day a write path starts inserting with a *user* token, at which
-- point it also switches on the dormant "edit own draft" branch of
-- maps_update_own_or_mod (mig 079). No current path does that today.
alter table public.maps alter column created_by set default auth.uid();

-- NOT NULL: all 560 live rows are filled for every one of the six spec'd
-- columns (checked against a production snapshot). status/created_at/
-- updated_at are safe outright — every insert path sets or defaults them.
-- source_type gets a default first: BulkUpload's create step and
-- scripts/seed-test-db.mjs both insert without it today, relying on
-- nullability, so NOT NULL alone would break those live paths; 'other' is
-- already a valid value of source_type_check and nothing reads source_type as
-- a signal of "unset".
--
-- iiif_image and thumbnail are deliberately NOT made NOT NULL here: BulkUpload
-- creates a map row (POST /api/admin/maps), tiles it out-of-band, and only
-- then PATCHes iiif_image/thumbnail in (backfillCreated()) — the gap between
-- create and that PATCH is a real, live "not tiled yet" state, not a bug. The
-- same two columns are also left unset by several tests/write.spec.ts
-- fixtures and by scripts/seed-test-db.mjs (thumbnail throughout; iiif_image
-- in most fixtures). Neither an empty-string default nor rewriting those call
-- sites to fabricate a URL would be honest. Left nullable; whoever updates
-- those call sites to always set a placeholder can add the constraint after.
alter table public.maps alter column status     set not null;
alter table public.maps alter column created_at set not null;
alter table public.maps alter column updated_at set not null;
alter table public.maps alter column source_type set default 'other';
update public.maps set source_type = 'other' where source_type is null;
alter table public.maps alter column source_type set not null;

-- search_vector: same expression as mig 046, minus dc_coverage/dc_subject,
-- extra_metadata->>'sheet_number' -> sheet_number, dc_publisher -> publisher,
-- year_label -> date_label. Dropped above (ahead of the dc_coverage/dc_subject
-- drops it depended on); re-added here with the new expression, which also
-- recreates its GIN index.
alter table public.maps
  add column search_vector tsvector
  generated always as (
    to_tsvector('simple',
      coalesce(name, '') || ' ' ||
      coalesce(original_title, '') || ' ' ||
      coalesce(creator, '') || ' ' ||
      coalesce(publisher, '') || ' ' ||
      coalesce(holding_institution, '') || ' ' ||
      coalesce(collection, '') || ' ' ||
      coalesce(location, '') || ' ' ||
      coalesce(shelfmark, '') || ' ' ||
      coalesce(date_label, '') || ' ' ||
      coalesce(year::text, '') || ' ' ||
      coalesce(sheet_number, '')
    )
  ) stored;

create index idx_maps_search_vector on public.maps using gin (search_vector);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. Functions/views/triggers whose TEXT bodies reference a renamed table,
--    column, or a column just dropped or promoted. Grepped across every
--    function definition in the database (pg_dump --schema-only), not just
--    the obvious ones — sync_primary_iiif_to_map() (writes maps.iiif_manifest,
--    dropped above; reads map_iiif_sources, renamed above) would otherwise
--    have broken silently on the next primary-image flip.
-- ────────────────────────────────────────────────────────────────────────────

create or replace function public.sync_primary_iiif_to_map() returns trigger
language plpgsql as $$
begin
  if new.is_primary = true then
    update public.maps
      set iiif_image  = new.iiif_image,
          source_type = new.source_type
      where id = new.map_id;

    update public.map_images
      set is_primary = false
      where map_id = new.map_id
        and id <> new.id
        and is_primary = true;
  end if;
  return new;
end;
$$;

create or replace function public.set_extraction_status(
  p_status  text,
  p_user    uuid,
  p_ids     uuid[] default null,
  p_map_id  uuid   default null,
  p_run_id  text   default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  if p_status not in ('validated', 'rejected', 'pending') then
    raise exception 'set_extraction_status: status must be validated, rejected or pending (got %)', p_status;
  end if;
  if p_ids is null and p_map_id is null then
    raise exception 'set_extraction_status: pass p_ids or p_map_id';
  end if;

  update public.ocr_labels e
     set review_status = p_status,
         reviewed_at    = case when p_status = 'validated' then now() else null end,
         reviewed_by    = case when p_status = 'validated' then p_user else null end
   where (p_ids    is null or e.id     = any(p_ids))
     and (p_map_id is null or e.map_id = p_map_id)
     and (p_run_id is null or e.run_id = p_run_id);

  get diagnostics n = row_count;
  return n;
end;
$$;

create or replace function public.revert_recent_validations(
  p_map_id      uuid,
  p_user        uuid,
  p_window_mins integer default 30
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  update public.ocr_labels e
     set review_status = 'pending',
         reviewed_at    = null,
         reviewed_by    = null
   where e.map_id      = p_map_id
     and e.review_status = 'validated'
     and e.reviewed_by  = p_user
     and e.reviewed_at  > now() - make_interval(mins => p_window_mins);

  get diagnostics n = row_count;
  return n;
end;
$$;

create or replace function public.set_extraction_geom(p_rows jsonb) returns integer
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  n integer;
begin
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
    raise exception 'set_extraction_geom: p_rows must be a jsonb array';
  end if;
  if jsonb_array_length(p_rows) > 1000 then
    raise exception 'set_extraction_geom: at most 1000 rows per call (got %)',
      jsonb_array_length(p_rows);
  end if;

  update public.ocr_labels e
     set geom      = case when r.geom is null then null else st_geogfromtext(r.geom) end,
         geom_src  = r.geom_src,
         geom_rmse = r.geom_rmse
    from jsonb_to_recordset(p_rows)
           as r(id uuid, geom text, geom_src text, geom_rmse double precision)
   where e.id = r.id;

  get diagnostics n = row_count;
  return n;
end;
$$;

create or replace function public.set_footprint_geom(p_rows jsonb) returns integer
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  n integer;
begin
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
    raise exception 'set_footprint_geom: p_rows must be a jsonb array';
  end if;
  if jsonb_array_length(p_rows) > 1000 then
    raise exception 'set_footprint_geom: at most 1000 rows per call (got %)',
      jsonb_array_length(p_rows);
  end if;

  update public.footprints f
     set geom      = case when r.geom is null then null else st_geogfromtext(r.geom) end,
         geom_src  = r.geom_src,
         geom_rmse = r.geom_rmse
    from jsonb_to_recordset(p_rows)
           as r(id uuid, geom text, geom_src text, geom_rmse double precision)
   where f.id = r.id;

  get diagnostics n = row_count;
  return n;
end;
$$;

create or replace function public.set_footprint_status(
  p_id            uuid,
  p_status        text,
  p_user          uuid,
  p_pixel_polygon jsonb default null,
  p_feature_type  text  default null,
  p_name          text  default null,
  p_category      text  default null,
  p_review_tags   text[] default null,
  p_review_note   text default null
)
returns public.footprints
language plpgsql
security definer
set search_path = public
as $$
declare
  updated public.footprints;
begin
  if p_status not in ('approved', 'rejected') then
    raise exception 'set_footprint_status: status must be approved or rejected (got %)', p_status;
  end if;

  update public.footprints f
     set review_status = p_status,
         pixel_polygon = coalesce(p_pixel_polygon, f.pixel_polygon),
         feature_type  = coalesce(p_feature_type, f.feature_type),
         name          = coalesce(p_name, f.name),
         category      = coalesce(p_category, f.category),
         review_tags   = coalesce(p_review_tags, f.review_tags),
         review_note   = coalesce(p_review_note, f.review_note),
         reviewed_by   = p_user,
         reviewed_at   = now(),
         source        = case
                           when p_pixel_polygon is not null or p_feature_type is not null
                           then 'sam-corrected'
                           else f.source
                         end
   where f.id = p_id
     and f.review_status in ('needs_review', 'submitted')
  returning f.* into updated;

  return updated;
end;
$$;

create or replace function public.set_story_status(p_id uuid, p_status text, p_user uuid)
returns public.stories
language plpgsql
security definer
set search_path = public
as $$
declare
  updated public.stories;
begin
  if p_status not in ('draft', 'submitted', 'approved', 'rejected') then
    raise exception 'set_story_status: unknown status %', p_status;
  end if;

  update public.stories s
     set review_status = p_status,
         reviewed_by   = case when p_status in ('approved', 'rejected') then p_user else null end,
         reviewed_at   = case when p_status in ('approved', 'rejected') then now() else null end
   where s.id = p_id
  returning s.* into updated;

  return updated;
end;
$$;

-- set_triage_key: triage's 'validated_at'/'validated_by' keys are now also
-- maps.triage_reviewed_at/triage_reviewed_by columns (section 4). The JSON
-- stays the write surface this RPC exposes (old code still reads the keys);
-- mirror the two keys the column pair cares about so the column and the JSON
-- can't drift apart, the way db-guidelines.md §7 asks of any denormalized pair.
create or replace function public.set_triage_key(
  p_map_id uuid,
  p_key    text,
  p_value  jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  updated jsonb;
begin
  if p_key !~ '^[a-z_]+$' then
    raise exception 'set_triage_key: refusing key %', p_key;
  end if;

  update public.maps m
     set triage = case
                    when p_value is null
                      then coalesce(m.triage, '{}'::jsonb) - p_key
                    else jsonb_set(coalesce(m.triage, '{}'::jsonb), array[p_key], p_value, true)
                  end,
         triage_reviewed_at = case
                                 when p_key <> 'validated_at' then m.triage_reviewed_at
                                 when p_value is null then null
                                 else (p_value #>> '{}')::timestamptz
                               end,
         triage_reviewed_by = case
                                 when p_key <> 'validated_by' then m.triage_reviewed_by
                                 when p_value is null then null
                                 else (p_value #>> '{}')::uuid
                               end
   where m.id = p_map_id
  returning m.triage into updated;

  if updated is null then
    raise exception 'set_triage_key: no map %', p_map_id;
  end if;

  return updated;
end;
$$;

-- search_labels, context_at, map_context: 'status'/'text'/'category' stay the
-- JSON/output field names contracts/ pins — only the column each reads from
-- ocr_labels/footprints changes.

create or replace function public.search_labels(
  p_q           text,
  p_public_only boolean default true,
  p_limit       integer default 50
)
returns table (
  id          uuid,
  map_id      uuid,
  label       text,
  category    text,
  confidence  double precision,
  x           double precision,
  y           double precision,
  w           double precision,
  h           double precision,
  sim         real,
  lng         double precision,
  lat         double precision,
  geom_rmse   double precision
)
language sql
stable
security definer
set search_path = public, extensions
as $$
  with q as (
    select lower(public.f_unaccent(btrim(p_q))) as key
  ),
  hits as (
    select distinct on (e.map_id, public.label_key(e.text, e.text_corrected))
           e.id,
           e.map_id,
           coalesce(e.text_corrected, e.text)                 as label,
           coalesce(e.category_corrected, e.category)         as category,
           e.confidence,
           e.global_x, e.global_y, e.global_w, e.global_h,
           word_similarity(q.key, public.label_key(e.text, e.text_corrected)) as sim,
           e.geom, e.geom_rmse
      from public.ocr_labels e
      join public.maps m on m.id = e.map_id
      cross join q
     where length(q.key) >= 2
       and word_similarity(q.key, public.label_key(e.text, e.text_corrected)) >= 0.5
       and e.review_status <> 'rejected'
       and coalesce(e.category_corrected, e.category)
           in ('street', 'hydrology', 'place', 'building', 'institution')
       and e.global_x is not null
       and (not p_public_only or m.status in ('public', 'featured'))
     order by e.map_id, public.label_key(e.text, e.text_corrected), e.confidence desc
  )
  select id, map_id, label, category, confidence,
         global_x, global_y, global_w, global_h, sim,
         st_x(geom::geometry), st_y(geom::geometry), geom_rmse
    from hits
   order by sim desc, confidence desc
   limit greatest(1, least(p_limit, 200));
$$;

create or replace function public.context_at(
  p_lng         double precision,
  p_lat         double precision,
  p_radius_m    double precision default 150,
  p_year_from   integer default null,
  p_year_to     integer default null,
  p_public_only boolean default true,
  p_limit       integer default 50
)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
  with params as (
    select st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography as here,
           greatest(1, least(p_radius_m, 5000))                    as radius,
           greatest(1, least(p_limit, 200))                        as lim
  ),
  visible as (
    select m.id, m.name, m.year, m.status, m.allmaps_id
      from public.maps m
     where (not p_public_only or m.status in ('public', 'featured'))
       and (p_year_from is null or m.year >= p_year_from)
       and (p_year_to   is null or m.year <= p_year_to)
  ),
  label as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'id', e.id, 'map_id', e.map_id, 'map_name', v.name, 'year', v.year,
               'text', coalesce(e.text_corrected, e.text),
               'category', coalesce(e.category_corrected, e.category),
               'status', e.review_status,
               'distance_m', round(st_distance(e.geom, p.here)::numeric, 1),
               'geom_rmse', e.geom_rmse,
               'lng', st_x(e.geom::geometry), 'lat', st_y(e.geom::geometry)
             ) as x
        from public.ocr_labels e
        join visible v on v.id = e.map_id
        cross join params p
       where e.geom is not null
         and e.review_status <> 'rejected'
         and st_dwithin(e.geom, p.here, p.radius)
       order by st_distance(e.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  footprint as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'id', f.id, 'map_id', f.map_id, 'map_name', v.name, 'year', v.year,
               'name', f.name, 'feature_type', f.feature_type,
               'category', f.category, 'source', f.source, 'status', f.review_status,
               'distance_m', round(st_distance(f.geom, p.here)::numeric, 1),
               'geom_rmse', f.geom_rmse,
               'geometry', st_asgeojson(f.geom::geometry)::jsonb
             ) as x
        from public.footprints f
        join visible v on v.id = f.map_id
        cross join params p
       where f.geom is not null
         and f.review_status = 'approved'
         and st_dwithin(f.geom, p.here, p.radius)
       order by st_distance(f.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  covering as (
    select jsonb_agg(x order by (x->>'year')::integer nulls last) as v from (
      select jsonb_build_object(
               'id', v.id, 'name', v.name, 'year', v.year,
               'status', v.status, 'allmaps_id', v.allmaps_id
             ) as x
        from visible v
        join public.maps m on m.id = v.id
       where m.bbox is not null
         and array_length(m.bbox, 1) = 4
         and p_lng between m.bbox[1] and m.bbox[3]
         and p_lat between m.bbox[2] and m.bbox[4]
       order by v.year
       limit (select lim from params)
    ) s
  ),
  story as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'story_id', sp.story_id, 'point_id', sp.id, 'title', sp.title,
               'story_title', s2.title,
               'distance_m', round(
                 st_distance(
                   st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography,
                   p.here
                 )::numeric, 1)
             ) as x
        from public.story_points sp
        join public.stories s2 on s2.id = sp.story_id
        cross join params p
       where sp.lon is not null and sp.lat is not null
         and (not p_public_only or s2.review_status = 'approved')
         and st_dwithin(
               st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography,
               p.here, p.radius)
       order by st_distance(
                  st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography, p.here)
       limit (select lim from params)
    ) s
  )
  select jsonb_build_object(
    'at',         jsonb_build_array(p_lng, p_lat),
    'radius_m',   (select radius from params),
    'maps',       coalesce((select v from covering), '[]'::jsonb),
    'labels',     coalesce((select v from label), '[]'::jsonb),
    'footprints', coalesce((select v from footprint), '[]'::jsonb),
    'stories',    coalesce((select v from story), '[]'::jsonb)
  );
$$;

create or replace function public.map_context(
  p_map_id      uuid,
  p_geom_src    text default null,
  p_public_only boolean default true
)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
  select case when m.id is null then null else jsonb_build_object(
    'map_id', m.id, 'name', m.name, 'year', m.year, 'status', m.status,
    'allmaps_id', m.allmaps_id,
    'labels', jsonb_build_object(
      'total',  (select count(*) from public.ocr_labels e where e.map_id = m.id),
      'warped', (select count(*) from public.ocr_labels e
                  where e.map_id = m.id and e.geom is not null),
      'stale',  (select count(*) from public.ocr_labels e
                  where e.map_id = m.id and e.geom is not null
                    and p_geom_src is not null and e.geom_src <> p_geom_src)
    ),
    'footprints', jsonb_build_object(
      'total',  (select count(*) from public.footprints f where f.map_id = m.id),
      'warped', (select count(*) from public.footprints f
                  where f.map_id = m.id and f.geom is not null),
      'stale',  (select count(*) from public.footprints f
                  where f.map_id = m.id and f.geom is not null
                    and p_geom_src is not null and f.geom_src <> p_geom_src),
      'approved', (select count(*) from public.footprints f
                    where f.map_id = m.id and f.review_status = 'approved')
    ),
    'geom_rmse', (select max(e.geom_rmse) from public.ocr_labels e where e.map_id = m.id)
  ) end
    from public.maps m
   where m.id = p_map_id
     and (not p_public_only or m.status in ('public', 'featured'));
$$;

-- enqueue_publish_jobs: NEW/OLD field access is resolved against the current
-- row type at trigger-fire time, so `new.georef_done` would fail at runtime
-- the moment the column above is renamed — this is the one PL/pgSQL body that
-- reads the renamed maps column as a bare record field rather than through a
-- table alias. The trigger's own `UPDATE OF status, georef_done` column list
-- IS attnum-tracked and follows the rename automatically, but it is dropped
-- and recreated anyway: worth being certain, not just right.
create or replace function public.enqueue_publish_jobs()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  publishing boolean;
  georef_flip boolean;
begin
  if new.status not in ('public', 'featured') then
    return new;
  end if;

  publishing := tg_op = 'INSERT' or old.status is distinct from new.status;

  georef_flip := tg_op = 'UPDATE'
                 and not publishing
                 and coalesce(old.is_georeferenced, false) = false
                 and coalesce(new.is_georeferenced, false) = true;

  if not publishing and not georef_flip then
    return new;
  end if;

  if new.annotation_url is null and new.allmaps_id is not null and new.is_georeferenced then
    insert into public.pipeline_jobs (kind, map_id, payload)
    values ('mirror_annotation', new.id, jsonb_build_object('allmaps_id', new.allmaps_id))
    on conflict do nothing;
  end if;

  if publishing
     and new.iiif_image is not null
     and new.iiif_image not like 'https://iiif.maparchive.vn/%'
  then
    insert into public.pipeline_jobs (kind, map_id, payload)
    values ('tile_to_r2', new.id, jsonb_build_object('iiif_image', new.iiif_image))
    on conflict do nothing;
  end if;

  return new;
end;
$$;

drop trigger if exists maps_enqueue_publish_jobs on public.maps;
create trigger maps_enqueue_publish_jobs
  after insert or update of status, is_georeferenced on public.maps
  for each row execute function public.enqueue_publish_jobs();

-- map_series: a genuine query change, not just a rename — counts sheets off
-- the new maps.sheet_number column instead of the extra_metadata JSON path,
-- and reads series_cells (renamed from series_sheets). is_georeferenced needs
-- no textual change (the view stores it by attnum, same as a policy), but the
-- view is being replaced anyway for the sheet_number change, so it is written
-- out in full for clarity.
create or replace view public.map_series
with (security_invoker = true) as
  with idx as (
    select
      series_key,
      count(*) as survey_sheets
      from public.series_cells
     group by series_key
  )
  select
    public.series_key(m.collection)                                as key,
    m.collection                                                   as collection,
    m.collection                                                   as name,
    count(distinct m.sheet_number)                                 as sheets,
    count(distinct m.sheet_number)
      filter (where m.status in ('public', 'featured'))            as published_sheets,
    i.survey_sheets                                                as survey_sheets,
    min(m.year)                                                    as first_year,
    max(m.year)                                                    as last_year,
    array[
      min(m.bbox[1]), min(m.bbox[2]), max(m.bbox[3]), max(m.bbox[4])
    ]::float8[]                                                    as bounds
    from public.maps m
    left join idx i on i.series_key = public.series_key(m.collection)
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and m.collection is not null
     and m.is_georeferenced
     and m.bbox is not null
     and array_length(m.bbox, 1) = 4
     and m.sheet_number is not null
   group by m.collection, i.survey_sheets
  having count(distinct m.sheet_number) > 1;

comment on view public.map_series is
  'One row per sheet series (maps.collection) with georeferenced sheets: its bounds, year span, the number of distinct cells held as maps rows, and — from series_cells (083/095) — how many cells the survey contains. security_invoker, plus the explicit published-or-signed-in gate in the body. Counts maps.sheet_number (095), not the extra_metadata JSON path.';

-- map_pipeline_status and place_names read no renamed/dropped column in their
-- bodies (checked: map_pipeline_status joins only pipeline_jobs/map_review_marks
-- by id; place_names reads ocr_labels' renamed columns, but a view's column
-- references are attnum-bound like a policy's, so the rename alone carries it)
-- — left as-is, verified by the from-scratch replay in section 6.
