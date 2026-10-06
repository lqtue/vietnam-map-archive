\set ON_ERROR_STOP on
-- Run only in a fresh disposable local database named vma_text_groups.
-- Spatial functions are stand-ins: this fixture verifies membership, evidence
-- preservation, visibility and transactions, not Allmaps/PostGIS accuracy.
do $$ begin
 if current_database() <> 'vma_text_groups' or coalesce(inet_server_addr()::text, '127.0.0.1') not in ('127.0.0.1', '127.0.0.1/32', '::1', '::1/128') then
  raise exception 'This fixture requires the isolated local vma_text_groups database';
 end if;
end $$;
begin;
create role anon;
create role authenticated;
create role service_role;
create schema auth;
create function auth.uid() returns uuid language sql as $$ select null::uuid $$;
create schema extensions;
create extension pg_trgm with schema extensions;
create domain extensions.geography as text;
create domain extensions.geometry as text;
create function extensions.st_makepoint(float8,float8) returns text language sql as $$ select 'point'::text $$;
create function extensions.st_setsrid(text,integer) returns text language sql as $$ select $1 $$;
create function extensions.st_x(text) returns float8 language sql as $$ select 1::float8 $$;
create function extensions.st_y(text) returns float8 language sql as $$ select 1::float8 $$;
create function extensions.st_distance(text,text) returns float8 language sql as $$ select 0::float8 $$;
create function extensions.st_dwithin(text,text,float8) returns boolean language sql as $$ select true $$;
create function extensions.st_asgeojson(text) returns text language sql as $$ select '{}'::text $$;
create function extensions.st_centroid(text) returns text language sql as $$ select $1 $$;
create function extensions.collect_step(text,text) returns text language sql as $$ select $2 $$;
create aggregate extensions.st_collect(text) (sfunc=extensions.collect_step, stype=text);
create function public.f_unaccent(text) returns text language sql as $$ select $1 $$;
create function public.label_key(text,text) returns text language sql as $$ select lower(coalesce($2,$1)) $$;
create function public.place_key(text,text) returns text language sql as $$ select public.label_key($1,$2) $$;
create function public.place_core_key(text,text) returns text language sql as $$ select public.label_key($1,$2) $$;
create table maps(id uuid primary key, name text, year integer, status text, allmaps_id text, bbox float8[]);
create table ocr_labels (
 id uuid primary key default gen_random_uuid(), map_id uuid references maps, run_id text not null,
 tile_x integer not null, tile_y integer not null, tile_w integer not null, tile_h integer not null,
 global_x float8 not null, global_y float8 not null, global_w float8, global_h float8,
 label_w float8, label_h float8, rotation_deg float8,
 text text not null, text_corrected text, category text not null, category_corrected text,
 confidence float8 not null, review_status text default 'pending', reviewed_at timestamptz,
 reviewed_by uuid, model text, prompt text, notes text,
 geom extensions.geography, geom_src text, geom_rmse float8,
 unique(map_id,run_id,tile_x,tile_y,text)
);
create table footprints (id uuid, map_id uuid, name text, feature_type text, category text, source text,
 review_status text, geom extensions.geography, geom_rmse float8);
create table stories (id uuid, title text, review_status text);
create table story_points (id uuid, story_id uuid, title text, lon float8, lat float8);
\ir ../../supabase/migrations/112_text_box_groups.sql
\ir ../../supabase/migrations/113_text_group_bounds_tolerance.sql
\ir ../../supabase/migrations/114_text_groups_across_runs.sql
insert into maps values ('00000000-0000-0000-0000-000000000001','Public',1882,'public',null,null),
 ('00000000-0000-0000-0000-000000000002','Draft',1898,'draft',null,null);
insert into ocr_labels (id,map_id,run_id,tile_x,tile_y,tile_w,tile_h,global_x,global_y,global_w,global_h,
 label_w,label_h,rotation_deg,text,category,confidence,review_status,geom,notes) values
 ('00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000001','run',10,20,100,100,10,20,20,10,18,8,15,'Rue','street',0.8,'validated','point','original'),
 ('00000000-0000-0000-0000-000000000012','00000000-0000-0000-0000-000000000001','second-run',40,30,100,100,40,30,30,10,28,8,15,'Ollier','street',0.9,'pending','point',null),
 ('00000000-0000-0000-0000-000000000013','00000000-0000-0000-0000-000000000002','run',0,0,100,100,0,0,20,10,20,10,0,'Draft','street',1,'pending','point',null);
create temp table original as select * from ocr_labels;
do $$ declare g uuid; n integer; begin
 g := public.group_text_boxes('00000000-0000-0000-0000-000000000001',
 array['00000000-0000-0000-0000-000000000012','00000000-0000-0000-0000-000000000011']::uuid[],
 'Ollier Rue','street',array[10.00000000001,20,59.99999999999,20]::float8[], 'point', 'version', 2, '00000000-0000-0000-0000-000000000099');
 if (select text_group_order from ocr_labels where id='00000000-0000-0000-0000-000000000012') <> 0 then raise exception 'lost click order'; end if;
 if (select run_id from ocr_labels where id=g) <> 'second-run' then raise exception 'group did not follow first selected run'; end if;
 if (select count(*) from search_labels('Ollier')) <> 1 or (select label from search_labels('Ollier')) <> 'Ollier Rue' then raise exception 'search duplicated parts'; end if;
 if (select count(*) from place_names) <> 1 then raise exception 'gazetteer exposed parts or draft'; end if;
 if jsonb_array_length(context_at(1,1)->'labels') <> 1 then raise exception 'context exposed parts'; end if;
 -- The group, rather than either source reading, receives the verdict.
 n := public.set_extraction_status('validated','00000000-0000-0000-0000-000000000099',null,'00000000-0000-0000-0000-000000000001','second-run');
 if n <> 1 or (select review_status from ocr_labels where id='00000000-0000-0000-0000-000000000012') <> 'pending' then raise exception 'verdict changed original'; end if;
 begin
  perform public.group_text_boxes('00000000-0000-0000-0000-000000000001',array[g,'00000000-0000-0000-0000-000000000011']::uuid[], 'Nested','street',array[10,20,60,20]::float8[],null,null,null,'00000000-0000-0000-0000-000000000099');
  raise exception 'nested group accepted';
 exception when invalid_parameter_value then null; end;
 perform public.ungroup_text_boxes('00000000-0000-0000-0000-000000000001',g);
 if exists ((select * from original except select * from ocr_labels) union all (select * from ocr_labels except select * from original)) then raise exception 'ungroup changed original readings'; end if;
 begin
  perform public.group_text_boxes('00000000-0000-0000-0000-000000000001',array['00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000013']::uuid[], 'Cross map','street',array[0,0,70,40]::float8[],null,null,null,'00000000-0000-0000-0000-000000000099');
  raise exception 'cross-map group accepted';
 exception when invalid_parameter_value then null; end;
 begin
  perform public.group_text_boxes('00000000-0000-0000-0000-000000000001',array['00000000-0000-0000-0000-000000000011','00000000-0000-0000-0000-000000000012']::uuid[], 'Changed','street',array[0,0,70,40]::float8[],null,null,null,'00000000-0000-0000-0000-000000000099');
  raise exception 'stale bounds accepted';
 exception when invalid_parameter_value then null; end;
 if (select count(*) from ocr_labels) <> 3 then raise exception 'failed group partially wrote'; end if;
 if has_function_privilege('anon','public.group_text_boxes(uuid,uuid[],text,text,double precision[],text,text,double precision,uuid)','execute')
 or has_function_privilege('authenticated','public.ungroup_text_boxes(uuid,uuid)','execute') then raise exception 'public grouping RPC'; end if;
end $$;
rollback;
\echo 'PASS: grouping order, single search result, draft visibility, original geometry/status, ungroup, atomic rejection, RPC grants'
