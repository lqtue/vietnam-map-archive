-- 115: /api/context labels are place names, not legend furniture.
--
-- `context_at` (112) filtered labels by map, geometry, review state and text
-- group, but not by category, so every `legend_entry`, `legend_ref` and `title`
-- row with a geom came back as a "label" at the queried spot. Production held
-- 837 / 1,278 / 61 such rows when this was written (read-only PostgREST count,
-- geom not null, not rejected, uncorrected category), on public maps among
-- them. A legend entry's geom is a derived pixel-space leftover, not a place,
-- and the legend has its own channel (/api/maps/[id]/legend-points). Labels
-- are now limited to the five gazetteer categories `search_labels` and
-- `place_names` already use, by effective category. The body is otherwise
-- exactly 112's.

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
         and e.text_group_id is null
         and coalesce(e.category_corrected, e.category)
             in ('street', 'hydrology', 'place', 'building', 'institution')
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
