\ir explore-maps-setup.sql
-- Synthetic archive with 100 sheets per series, tied names/years and 3 provinces.
-- Timings include full facets/choices/counts and the bounded first page.
create function pg_temp.benchmark_explore(size integer) returns void language plpgsql as $$
declare t timestamptz; payload jsonb; begin
 truncate public.maps;
 insert into public.maps(id,name,year,status,is_georeferenced,regions,region,holding_institution,collection,series_key,map_type,bbox,allmaps_id)
 select md5(i::text)::uuid,(array['Huế','Hà Nội','Đà Nẵng'])[1+i%3]||' sheet '||(i%100),1900+i%100,'public',true,
 array[(array['Huế','Hà Nội','Đà Nẵng'])[1+i%3]],(array['Huế','Hà Nội','Đà Nẵng'])[1+i%3],
 'BnF','Series '||(i/100),'series-'||(i/100),'topographic',array[100,10,110,20]::float8[],'scan-'||i
 from generate_series(1,size) i;
 analyze public.maps;
 for attempt in 1..3 loop
  t:=clock_timestamp(); payload:=public.explore_maps_page(p_limit=>60);
  raise notice 'rows=% attempt=% elapsed_ms=% response_bytes=% page_rows=% total=%',size,attempt,round(extract(epoch from clock_timestamp()-t)*1000),octet_length(payload::text),jsonb_array_length(payload->'maps'),payload#>>'{total,maps}';
 end loop;
 t:=clock_timestamp(); payload:=public.explore_maps_page(p_limit=>60,p_query=>'hue:*');
 raise notice 'rows=% query=hue elapsed_ms=% response_bytes=% page_rows=% total=%',size,round(extract(epoch from clock_timestamp()-t)*1000),octet_length(payload::text),jsonb_array_length(payload->'maps'),payload#>>'{total,maps}';
 -- 256 separate footprint clusters isolate point index selectivity.
 update public.maps set bbox=array[100+get_byte(uuid_send(id),0)*0.01,10,100+get_byte(uuid_send(id),0)*0.01+0.005,10.005]::float8[];
 analyze public.maps;
 t:=clock_timestamp(); payload:=public.explore_maps_page(p_limit=>60,p_point=>'[100.0025,10.0025]');
 raise notice 'rows=% query=point elapsed_ms=% response_bytes=% page_rows=% total=%',size,round(extract(epoch from clock_timestamp()-t)*1000),octet_length(payload::text),jsonb_array_length(payload->'maps'),payload#>>'{total,maps}';
 t:=clock_timestamp(); payload:=public.explore_maps_page(p_limit=>60,p_ids=>jsonb_build_array(md5('1')::uuid));
 raise notice 'rows=% query=id elapsed_ms=% response_bytes=% page_rows=% total=%',size,round(extract(epoch from clock_timestamp()-t)*1000),octet_length(payload::text),jsonb_array_length(payload->'maps'),payload#>>'{total,maps}';
end $$;
select pg_temp.benchmark_explore(10000);
select pg_temp.benchmark_explore(100000);
rollback;
