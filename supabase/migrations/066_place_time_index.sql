-- Migration 066 — the place-time index
--
-- Design: docs/plans/platform-design.md §0. Until now every map-derived row lived in
-- source-image pixel space and was warped to lng/lat in TypeScript, per
-- request, so "what was here in 1923" could not be one query. This adds the
-- derived geometry that makes it one.
--
-- Pixel coordinates stay the master. `geom` is derived, disposable and
-- rebuildable: it is written by the same server routes that write the pixel
-- coordinates (they already hold the map's transformer), and recomputed by the
-- new `warp` job when a map is re-georeferenced. Nothing hand-edits it.
--
-- `geom_src` is the staleness contract — a short hash of the GCP set the warp
-- used, so a row whose georeference has since moved is a queryable defect
-- rather than silent drift. `geom_rmse` is that map's own GCP residual in
-- metres, carried into every result so a caller can weigh a 1799 sketch
-- differently from a 1923 cadastral plan.

create extension if not exists postgis with schema extensions;

-- ── derived geometry ─────────────────────────────────────────────────────
alter table public.ocr_extractions
  add column if not exists geom      extensions.geography(Point, 4326),
  add column if not exists geom_src  text,
  add column if not exists geom_rmse double precision;

alter table public.footprint_submissions
  add column if not exists geom      extensions.geography(Polygon, 4326),
  add column if not exists geom_src  text,
  add column if not exists geom_rmse double precision;

create index if not exists ocr_extractions_geom_gix
  on public.ocr_extractions using gist (geom);
create index if not exists footprint_submissions_geom_gix
  on public.footprint_submissions using gist (geom);

-- A map that has been re-georeferenced needs its rows warped again. One more
-- job kind, claimed like any other; the runner is the server-side executor,
-- because the warp needs the annotation and the service key.
alter table public.pipeline_jobs drop constraint if exists pipeline_jobs_kind_check;
alter table public.pipeline_jobs
  add constraint pipeline_jobs_kind_check
    check (kind in (
      'ingest_map', 'tile_to_r2', 'mirror_annotation', 'sync_allmaps',
      'ocr', 'seg', 'join', 'warp', 'render_preview', 'build_pmtiles'
    ));

-- ── context_at ───────────────────────────────────────────────────────────
-- Everything the archive knows about a spot. `security definer` with an
-- explicit `p_public_only` for the same reason `search_labels` (065) takes one:
-- the API calls this on the service client and already knows the caller's role.
--
-- Radius, not containment: a label's geometry is its bbox centre, so the honest
-- question is "near here". Rows with a null `geom` are invisible to this
-- function by construction — an ungeoreferenced map has no position to report.
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
    select jsonb_agg(x order by x->>'distance_m') as v from (
      select jsonb_build_object(
               'id', e.id, 'map_id', e.map_id, 'map_name', v.name, 'year', v.year,
               'text', coalesce(e.text_validated, e.text),
               'category', coalesce(e.category_validated, e.category),
               'status', e.status,
               'distance_m', round(st_distance(e.geom, p.here)::numeric, 1),
               'geom_rmse', e.geom_rmse,
               'lng', st_x(e.geom::geometry), 'lat', st_y(e.geom::geometry)
             ) as x
        from public.ocr_extractions e
        join visible v on v.id = e.map_id
        cross join params p
       where e.geom is not null
         and e.status <> 'rejected'
         and st_dwithin(e.geom, p.here, p.radius)
       order by st_distance(e.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  footprint as (
    select jsonb_agg(x order by x->>'distance_m') as v from (
      select jsonb_build_object(
               'id', f.id, 'map_id', f.map_id, 'map_name', v.name, 'year', v.year,
               'name', f.name, 'feature_type', f.feature_type,
               'category', f.category, 'source', f.source, 'status', f.status,
               'distance_m', round(st_distance(f.geom, p.here)::numeric, 1),
               'geom_rmse', f.geom_rmse,
               'geometry', st_asgeojson(f.geom::geometry)::jsonb
             ) as x
        from public.footprint_submissions f
        join visible v on v.id = f.map_id
        cross join params p
       where f.geom is not null
         and f.status = 'approved'
         and st_dwithin(f.geom, p.here, p.radius)
       order by st_distance(f.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  -- Maps that cover the point at all: bbox is [minLon, minLat, maxLon, maxLat].
  covering as (
    select jsonb_agg(x order by x->>'year') as v from (
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
    select jsonb_agg(x order by x->>'distance_m') as v from (
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
         and (not p_public_only or s2.status = 'approved')
         and st_dwithin(
               st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography,
               p.here, p.radius)
       order by 1
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

-- ── map_context ──────────────────────────────────────────────────────────
-- The map-centric view: what one sheet knows, and how much of it is indexed.
-- `stale` counts rows warped against a georeference that has since changed —
-- the defect the `warp` job clears.
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
      'total',  (select count(*) from public.ocr_extractions e where e.map_id = m.id),
      'warped', (select count(*) from public.ocr_extractions e
                  where e.map_id = m.id and e.geom is not null),
      'stale',  (select count(*) from public.ocr_extractions e
                  where e.map_id = m.id and e.geom is not null
                    and p_geom_src is not null and e.geom_src <> p_geom_src)
    ),
    'footprints', jsonb_build_object(
      'total',  (select count(*) from public.footprint_submissions f where f.map_id = m.id),
      'warped', (select count(*) from public.footprint_submissions f
                  where f.map_id = m.id and f.geom is not null),
      'stale',  (select count(*) from public.footprint_submissions f
                  where f.map_id = m.id and f.geom is not null
                    and p_geom_src is not null and f.geom_src <> p_geom_src),
      'approved', (select count(*) from public.footprint_submissions f
                    where f.map_id = m.id and f.status = 'approved')
    ),
    'geom_rmse', (select max(e.geom_rmse) from public.ocr_extractions e where e.map_id = m.id)
  ) end
    from public.maps m
   where m.id = p_map_id
     and (not p_public_only or m.status in ('public', 'featured'));
$$;

revoke all on function public.context_at(double precision, double precision, double precision, integer, integer, boolean, integer) from public, anon, authenticated;
revoke all on function public.map_context(uuid, text, boolean) from public, anon, authenticated;
grant execute on function public.context_at(double precision, double precision, double precision, integer, integer, boolean, integer) to service_role;
grant execute on function public.map_context(uuid, text, boolean) to service_role;
