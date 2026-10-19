-- Deploy migrations 125 and 126 before deploying the bounded Explore client.
-- Bounded Explore results with full-set facets. Service-role-only because visibility
-- is passed by the authenticated API, never by a public RPC caller.
create or replace function public.explore_area_text(text[]) returns text
language sql immutable parallel safe set search_path = public as $$
 select array_to_string($1,' ');
$$;

alter table public.maps add column if not exists explore_search_vector tsvector generated always as (
 to_tsvector('simple', public.f_unaccent(coalesce(name,'') || ' ' || coalesce(original_title,'') || ' ' || coalesce(creator,'') || ' ' || coalesce(publisher,'') || ' ' || coalesce(holding_institution,'') || ' ' || coalesce(collection,'') || ' ' || coalesce(location,'') || ' ' || coalesce(region,'') || ' ' || coalesce(shelfmark,'') || ' ' || coalesce(date_label,'') || ' ' || coalesce(sheet_number,'') || ' ' || coalesce(year::text,'') || ' ' || coalesce(public.explore_area_text(regions),'') || ' ' || coalesce(public.explore_area_text(regions_2025),'')))
) stored;
create index if not exists maps_explore_search_vector_idx on public.maps using gin(explore_search_vector)
 where is_georeferenced and status in ('public','featured','draft');

create index if not exists maps_explore_replacements_idx
 on public.maps(series_key, (extra_metadata->>'mirrors_original_for'))
 where is_georeferenced and status in ('public','featured','draft')
  and extra_metadata->>'mirrors_original_for' is not null;

-- PostgreSQL's built-in geometric index keeps point lookups independent of
-- archive-wide JSON construction; no PostGIS extension is required.
create index if not exists maps_explore_bbox_idx on public.maps using gist
 ((box(point(bbox[1],bbox[2]),point(bbox[3],bbox[4]))))
 where is_georeferenced and bbox is not null and cardinality(bbox)=4
  and bbox[1]<bbox[3] and bbox[2]<bbox[4];

create or replace function public.explore_maps_page(
 p_query text default '', p_filters jsonb default '{}', p_regions jsonb default '{}',
 p_staff boolean default false, p_limit integer default 60, p_cursor jsonb default null,
 p_point jsonb default null, p_ids jsonb default null, p_sources boolean default false
) returns jsonb language sql stable security invoker set search_path = public as $$
with source as materialized (
 select jsonb_build_object('id',m.id,'name',m.name,'year',m.year,'status',m.status,
 'is_georeferenced',m.is_georeferenced,'bbox',m.bbox,'holding_institution',m.holding_institution,
 'series_key',m.series_key,'collection',m.collection,
 'map_type',case m.map_type when 'plan' then 'city_plan' when 'regional' then 'general_reference' else m.map_type end) as r,
 case when cardinality(m.regions)>0 then m.regions else array_remove(array[m.region],null) end as areas
 from public.maps m
 where (m.status in ('public','featured') or (p_staff and m.status='draft'))
 and (not p_sources or (
  (nullif(m.annotation_url,'') is not null or nullif(m.allmaps_id,'') is not null)
  and not exists (
   select 1 from public.maps replacement
   where replacement.series_key=m.series_key and replacement.is_georeferenced
    and (replacement.status in ('public','featured') or (p_staff and replacement.status='draft'))
    and replacement.extra_metadata->>'mirrors_original_for'=m.id::text
   group by replacement.extra_metadata->>'mirrors_original_for'
   having bool_or(replacement.sheet_half is null)
    or (bool_or(replacement.sheet_half='W') and bool_or(replacement.sheet_half='E'))
  )
 ))
 and m.is_georeferenced
 and (p_ids is null or m.id=any(array(select value::uuid from jsonb_array_elements_text(p_ids))))
 and (p_point is null or (
  m.bbox is not null and cardinality(m.bbox)=4
  and m.bbox[1]<m.bbox[3] and m.bbox[2]<m.bbox[4]
  and box(point(m.bbox[1],m.bbox[2]),point(m.bbox[3],m.bbox[4]))
   @> point((p_point->>0)::float8,(p_point->>1)::float8)
 ))
 and (p_query='' or case when p_query ~ '^\d{4}-\d$' then m.sheet_number=p_query
 else m.explore_search_vector @@ to_tsquery('simple',p_query) end)
), searchable as materialized (
 select r, areas, array(select key from jsonb_each(p_regions) x where exists (
 select 1 from jsonb_array_elements_text(x.value) v where v=any(areas))) as regions
 from source
), tested as materialized (
 select *, array_remove(array[
case when coalesce(jsonb_array_length(p_filters->'area'),0)>0 and not coalesce((areas && array(select jsonb_array_elements_text(p_filters->'area'))),false) then 'area' end,
case when coalesce(jsonb_array_length(p_filters->'region'),0)>0 and not coalesce((regions && array(select jsonb_array_elements_text(p_filters->'region'))),false) then 'region' end,
case when coalesce(jsonb_array_length(p_filters->'type'),0)>0 and not coalesce(((p_filters->'type') ? (r->>'map_type')),false) then 'type' end,
case when coalesce(jsonb_array_length(p_filters->'institution'),0)>0 and not coalesce(((p_filters->'institution') ? (r->>'holding_institution')),false) then 'institution' end,
case when coalesce(jsonb_array_length(p_filters->'series_key'),0)>0 and not coalesce(((p_filters->'series_key') ? (r->>'series_key')),false) then 'series_key' end,
case when coalesce(jsonb_array_length(p_filters->'kind'),0)>0 and not coalesce((case when p_filters->'kind'->>0='surveys' then nullif(r->>'series_key','') is not null else nullif(r->>'series_key','') is null end),false) then 'kind' end,
case when coalesce(jsonb_array_length(p_filters->'status'),0)>0 and not coalesce(((p_filters->'status') ? 'map'),false) then 'status' end,
case when coalesce(jsonb_array_length(p_filters->'year'),0)>0 and not coalesce(((r->>'year')::integer >= coalesce(nullif(p_filters->'year'->>0,'')::integer,-2147483648) and (r->>'year')::integer <= coalesce(nullif(p_filters->'year'->>1,'')::integer,2147483647)),false) then 'year' end
 ],null) as failed from searchable
), matched as materialized (select * from tested where cardinality(failed)=0),
page_candidates as materialized (
 select * from matched where p_cursor is null or
 (coalesce((r->>'year')::integer,2147483648),coalesce(r->>'name','') collate "C",r->>'id') >
 (coalesce((p_cursor->>'year')::integer,2147483648),coalesce(p_cursor->>'name','') collate "C",p_cursor->>'id')
 order by coalesce((r->>'year')::integer,2147483648),coalesce(r->>'name','') collate "C",r->>'id'
 limit least(greatest(p_limit,1),100) + 1
), page as materialized (
 select * from page_candidates
 order by coalesce((r->>'year')::integer,2147483648),coalesce(r->>'name','') collate "C",r->>'id'
 limit least(greatest(p_limit,1),100)
), dimensions as (
select 'area' as dimension, unnest(areas) as value from tested where failed <@ array['area'] union all
select 'region' as dimension, unnest(regions) as value from tested where failed <@ array['region'] union all
select 'map_type' as dimension, r->>'map_type' as value from tested where failed <@ array['type'] union all
select 'institution' as dimension, r->>'holding_institution' as value from tested where failed <@ array['institution'] union all
select 'series_key' as dimension, r->>'series_key' as value from tested where failed <@ array['series_key'] union all
select 'kind' as dimension, case when nullif(r->>'series_key','') is null then 'plans' else 'surveys' end as value from tested where failed <@ array['kind'] union all
select 'status' as dimension, 'map' as value from tested where failed <@ array['status']
), tallies as (select dimension,value,count(*) n from dimensions where value is not null and value<>'' group by dimension,value),
facets as (select dimension,jsonb_object_agg(value,n) counts from tallies group by dimension),
bins as (select floor((r->>'year')::numeric/10)::integer*10 decade,count(*) n from tested where failed <@ array['year'] and r->>'year' is not null group by 1)
select jsonb_build_object(
 'maps',coalesce((select jsonb_agg(to_jsonb(m) - array['description','extra_metadata','rights','physical_description','search_vector','explore_search_vector'] order by coalesce((p.r->>'year')::integer,2147483648),coalesce(p.r->>'name','') collate "C",p.r->>'id') from page p join public.maps m on m.id=(p.r->>'id')::uuid),'[]'),
 'total',jsonb_build_object('maps',(select count(*) from matched),'drafts',(select count(*) from matched where r->>'status'='draft'),'scout',0),
 'facets',coalesce((select jsonb_object_agg(dimension,counts) from facets),'{}'),
 'choices',jsonb_build_object(
 'area',coalesce((select jsonb_agg(value order by n desc,value) from (select unnest(areas) value,count(*) n from searchable group by 1) x),'[]'),
 'region',coalesce((select jsonb_agg(value order by n desc,value) from (select unnest(regions) value,count(*) n from searchable group by 1) x),'[]'),
 'type',coalesce((select jsonb_agg(value order by n desc,value) from (select r->>'map_type' value,count(*) n from searchable where nullif(r->>'map_type','') is not null group by 1) x),'[]'),
 'institution',coalesce((select jsonb_agg(value order by n desc,value) from (select r->>'holding_institution' value,count(*) n from searchable where nullif(r->>'holding_institution','') is not null group by 1) x),'[]'),
 'series',coalesce((select jsonb_agg(jsonb_build_object('value',value,'label',label) order by n desc,value) from (select r->>'series_key' value,max(coalesce(r->>'collection',r->>'series_key')) label,count(*) n from searchable where nullif(r->>'series_key','') is not null group by 1) x),'[]')),
 'yearBins',coalesce((select jsonb_agg(jsonb_build_object('decade',decade,'count',n) order by decade) from bins),'[]'),
 'seriesCounts',coalesce((select jsonb_object_agg(k,n) from (select r->>'series_key' k,count(*) n from matched where nullif(r->>'series_key','') is not null group by 1) x),'{}'),
 'nextCursor',case when (select count(*) from page_candidates)>least(greatest(p_limit,1),100) then
 (select jsonb_build_object('year',r->'year','name',r->>'name','id',r->>'id') from page order by coalesce((r->>'year')::integer,2147483648) desc,coalesce(r->>'name','') collate "C" desc,r->>'id' desc limit 1) else null end
);
$$;
revoke all on function public.explore_maps_page(text,jsonb,jsonb,boolean,integer,jsonb,jsonb,jsonb,boolean) from public, anon, authenticated;
grant execute on function public.explore_maps_page(text,jsonb,jsonb,boolean,integer,jsonb,jsonb,jsonb,boolean) to service_role;
