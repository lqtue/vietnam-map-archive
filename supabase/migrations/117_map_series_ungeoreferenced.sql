-- A series is any numbered set of sheets, georeferenced or not.
-- map_series (mig 105) required is_georeferenced and a bbox on every counted
-- sheet, which kept scan-only surveys (1971 provincial maps, Indochine 1st
-- edition) out of /catalog's "Browse by series". The gate is dropped; bounds
-- are taken from the sheets that do have a bbox.
-- ponytail: a series with no bbox at all falls back to a Vietnam-wide extent so
-- every bounds consumer keeps getting four numbers; null-safe bounds would touch
-- the whole layer stack.
create or replace view public.map_series with (security_invoker=true) as
with idx as (select series_id,count(*) as survey_sheets from public.series_cells group by series_id)
select s.key as key,min(m.collection) as collection,s.name as name,
 count(distinct m.sheet_number) as sheets,
 count(distinct m.sheet_number) filter(where m.status in ('public','featured')) as published_sheets,
 i.survey_sheets,min(m.year) as first_year,max(m.year) as last_year,
 (case when count(*) filter(where m.bbox is not null and array_length(m.bbox,1)=4)>0 then
  array[min(m.bbox[1]) filter(where array_length(m.bbox,1)=4),
        min(m.bbox[2]) filter(where array_length(m.bbox,1)=4),
        max(m.bbox[3]) filter(where array_length(m.bbox,1)=4),
        max(m.bbox[4]) filter(where array_length(m.bbox,1)=4)]
  else array[102.0,8.0,110.0,24.0] end)::float8[] as bounds
from public.maps m join public.series s on s.id=m.series_id
left join idx i on i.series_id=s.id
where (m.status in ('public','featured') or auth.uid() is not null)
 and m.sheet_number is not null
 and m.status<>'archived'
group by s.id,s.key,s.name,i.survey_sheets having count(distinct m.sheet_number)>1;
