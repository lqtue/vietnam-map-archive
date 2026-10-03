\set ON_ERROR_STOP on
-- Isolated regression fixture for migrations 105–108. Run only in a disposable local DB.
do $$ begin
 if not exists(select 1 from pg_roles where rolname='anon') then execute 'create role anon nologin'; end if;
 if not exists(select 1 from pg_roles where rolname='authenticated') then execute 'create role authenticated nologin'; end if;
 if not exists(select 1 from pg_roles where rolname='service_role') then execute 'create role service_role nologin bypassrls'; end if;
end $$;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
create function auth.role() returns text language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claim.role',true),''), current_user) $$;
create function public.series_key(text) returns text language sql immutable as $$ select trim(both '-' from regexp_replace(lower($1), '[^a-z0-9]+', '-', 'g')) $$;
create table public.profiles(id uuid primary key, role text);
create table public.maps(
 id uuid primary key default gen_random_uuid(), name text not null, collection text,
 series_key text generated always as (public.series_key(collection)) stored,
 sheet_number text, status text not null default 'pending_georef' check(status in ('draft','public','featured')),
 is_georeferenced boolean default false, bbox float8[], year integer, slug text,
 created_at timestamptz default now(), allmaps_id text, annotation_url text,
 thumbnail text
);
create table public.series_cells(
 series_key text not null, sheet_number text not null, map_id uuid, source text, source_ref text,
 held_by text, note text,
 primary key(series_key,sheet_number)
);
create table public.cell_printings(
 id uuid primary key default gen_random_uuid(), series_key text not null, sheet_number text not null,
 institution text not null, source_ref text not null, title text, url text, rights text,
 unique(institution,source_ref)
);
create table public.map_images(
 id uuid primary key default gen_random_uuid(), map_id uuid references public.maps(id), iiif_base text
);
create index idx_maps_series_key_sheet_number on public.maps(series_key,sheet_number);
create view public.map_series as
select series_key as key,min(collection) as collection,min(name) as name,count(distinct sheet_number) as sheets,
 count(distinct sheet_number) filter(where status in ('public','featured')) as published_sheets,
 null::bigint as survey_sheets,min(year) as first_year,max(year) as last_year,
 null::float8[] as bounds
from public.maps where is_georeferenced and bbox is not null and sheet_number is not null
group by series_key having count(distinct sheet_number)>1;
create policy maps_read on public.maps for select using (status in ('public','featured') or auth.uid() is not null);
create policy maps_contributor_insert on public.maps for insert to authenticated with check (true);
create policy maps_contributor_update on public.maps for update to authenticated using (true) with check (true);
alter table public.maps enable row level security;
create policy cells_read on public.series_cells for select using (true);
alter table public.series_cells enable row level security;
create policy items_read on public.cell_printings for select using (true);
alter table public.cell_printings enable row level security;
create policy images_read on public.map_images for select using (true);
alter table public.map_images enable row level security;
grant usage on schema public, auth to anon, authenticated, service_role;
grant execute on function auth.uid(), auth.role() to anon, authenticated, service_role;
grant execute on function public.series_key(text) to anon, authenticated, service_role;
grant select,insert,update,delete on all tables in schema public to anon,authenticated,service_role;

-- Legacy production-shaped rows exist before the additive migrations run.
insert into public.maps(id,name,collection,sheet_number,status,is_georeferenced,bbox,year,slug,allmaps_id)
values('11111111-1111-4111-8111-111111111111','Legacy L7014 scan','L7014 Test','6330-4','public',true,
       array[106.5,10.75,106.75,11.0]::float8[],1965,'legacy-l7014-address','legacytestscan001');
insert into public.series_cells(series_key,sheet_number,map_id,held_by,source,source_ref)
values('l7014-test','6330-4','11111111-1111-4111-8111-111111111111','map',null,null);
insert into public.cell_printings(series_key,sheet_number,institution,source_ref,title,url)
values('l7014-test','6330-4','TTU','legacy-ttu-item','Legacy catalogue record','https://ttu.example/item');
insert into public.map_images(map_id,iiif_base)
values('11111111-1111-4111-8111-111111111111','https://images.example/legacy');

\ir ../../supabase/migrations/105_series_identity.sql
\ir ../../supabase/migrations/106_sheet_printings.sql
\ir ../../supabase/migrations/107_map_archiving.sql
\ir ../../supabase/migrations/108_maps_status_default.sql

-- Stable series survives label changes; one index cell can have several printings.
do $$
declare s uuid; c uuid; c2 uuid; p1 uuid; p2 uuid; m1 uuid; m2 uuid; m3 uuid; m4 uuid; item1 uuid; item2 uuid; item3 uuid;
begin
 perform set_config('request.jwt.claim.role','service_role',true);
 select id into s from series where key='l7014-test';
 select id into c from series_cells where series_key='l7014-test' and sheet_number='6330-4';
 select id into m1 from maps where name='Legacy L7014 scan';
 select id into item1 from cell_printings where source_ref='legacy-ttu-item';
 if s is null or c is null or (select series_id from maps where id=m1) is distinct from s
   or (select series_id from cell_printings where id=item1) is distinct from s then raise exception 'legacy identity backfill failed'; end if;
 if exists(select 1 from sheet_printings) then raise exception 'migration guessed printing identities'; end if;
 if (select name from maps where id=m1) is distinct from 'Legacy L7014 scan'
   or (select slug from maps where id=m1) is distinct from 'legacy-l7014-address'
   or (select year from maps where id=m1) is distinct from 1965
   or (select bbox from maps where id=m1) is distinct from array[106.5,10.75,106.75,11.0]::float8[]
   or (select status from maps where id=m1) is distinct from 'public'
   or (select allmaps_id from maps where id=m1) is distinct from 'legacytestscan001'
   or not exists(select 1 from map_images where map_id=m1 and iiif_base='https://images.example/legacy')
   or not exists(select 1 from series_cells where id=c and map_id=m1 and held_by='map') then
   raise exception 'legacy map or source data changed during migration'; end if;
 insert into series_cells(series_key,sheet_number,series_id) values('l7014-test','other-cell',s) returning id into c2;
 insert into sheet_printings(cell_id,printed_title,edition_statement,part,review_status,evidence) values(c,'Test','1st ed.','W','verified','{"citation":"fixture evidence"}') returning id into p1;
 begin
   insert into sheet_printings(cell_id,printed_title,review_status,evidence) values(c,'Unreviewed claim','verified','{}');
   raise exception 'verified printing without evidence was accepted';
 exception when check_violation then null; end;
 insert into sheet_printings(cell_id,printed_title,edition_statement,part,review_status) values(c,'Test','2nd ed.','E','unreviewed') returning id into p2;
 insert into sheet_printings(cell_id,printed_title,part) values(c,'Whole','whole');
 insert into sheet_printings(cell_id,printed_title,part) values(c,'Assemblage','assemblage');
 if (select count(*) from series_cells where series_id=s and sheet_number='6330-4') <> 1 then raise exception 'printings duplicated cell index'; end if;
 update cell_printings set printing_id=p1 where id=item1;
 insert into cell_printings(series_key,sheet_number,series_id,printing_id,institution,source_ref,url) values
 ('l7014-test','6330-4',s,p1,'PCL','item-2','https://pcl.example/item-2') returning id into item2;
 if item1=item2 then raise exception 'institution items collapsed'; end if;
 insert into cell_printings(series_key,sheet_number,series_id,printing_id,institution,source_ref) values
 ('l7014-test','6330-4',s,p2,'ANU','item-3') returning id into item3;
 update maps set printing_id=p1 where id=m1;
 update maps set collection='Renamed label' where id=m1;
 if (select series_id from maps where id=m1) <> s or (select series_key from maps where id=m1)<>'l7014-test' then raise exception 'collection rename changed series identity'; end if;
 if (select slug from maps where id=m1)<>'legacy-l7014-address' then raise exception 'collection rename changed map address'; end if;
 insert into maps(name,collection,status,series_id) values('Nullable series link','Renamed label','draft',s) returning id into m3;
 update maps set series_id=null where id=m3;
 if (select series_key from maps where id=m3) is not null then raise exception 'cleared series FK retained legacy key'; end if;
 insert into maps(name,collection,sheet_number,status,series_id,printing_id,allmaps_id)
 values('Scan B','Renamed label','6330-4','public',s,p1,'modelscan0000002') returning id into m2;
 -- Unknown source discoveries remain legal and unresolved; image links stay scan-specific.
 insert into cell_printings(series_key,sheet_number,series_id,institution,source_ref) values('l7014-test','9999-9',s,'Unknown','unindexed') returning id into item1;
 insert into map_images(map_id,source_item_id,width,height,asset_version) values(m1,item2,100,100,gen_random_uuid());
 -- Different item is a scan source assertion but not a new cell or scan workspace.
 insert into map_images(map_id,source_item_id,width,height,asset_version) values(m2,item2,101,100,gen_random_uuid());
 begin
   insert into map_images(map_id,source_item_id) values(m1,item3);
   raise exception 'conflicting scan/source printing link accepted';
 exception when others then if sqlerrm not like 'image source item printing must match%' then raise; end if; end;
 begin
   update maps set printing_id=p2 where id=m1;
   raise exception 'map printing update contradicted existing source item';
 exception when others then if sqlerrm not like 'existing image source item conflicts%' then raise; end if; end;
 begin
   update cell_printings set printing_id=p2 where id=item2;
   raise exception 'source item printing update contradicted existing map';
 exception when others then if sqlerrm not like 'source item update conflicts with linked map%' then raise; end if; end;
 begin
   update sheet_printings set cell_id=c2 where id=p1;
   raise exception 'linked printing moved to another cell';
 exception when others then if sqlerrm not like 'cannot move a printing to another cell%' then raise; end if; end;
 begin
   update series set key='renamed-key' where id=s;
   raise exception 'series stable key changed';
 exception when others then if sqlerrm not like 'series key is immutable%' then raise; end if; end;
 begin
   update series_cells set sheet_number='moved-cell' where id=c;
   raise exception 'cell moved after printing identity attached';
 exception when others then if sqlerrm not like 'cannot move a series cell while printing identities are attached%' then raise; end if; end;
 if (select count(distinct id) from maps where printing_id=p1)<>2 then raise exception 'independent scans merged'; end if;
 -- Explicit cell and printing consistency.
 begin
   insert into maps(name,collection,sheet_number,status,series_id,printing_id) values('Wrong cell','Renamed label','9999-9','draft',s,p1);
   raise exception 'wrong cell link was accepted';
 exception when others then if sqlerrm not like 'map sheet_number must match%' then raise; end if; end;
 -- Public gate excludes a draft-only series from both invoker views, even service-role queries.
 insert into series(key,name) values('draft-test','Private');
 insert into series_cells(series_key,sheet_number) values('draft-test','1');
 insert into maps(name,collection,sheet_number,status,series_id) values('Draft only','Draft Test','1','draft',(select id from series where key='draft-test'));
 insert into series_cells(series_key,sheet_number,series_id) values('l7014-test','draft-only-other',s);
 insert into series_cells(series_key,sheet_number,series_id) values('l7014-test','archived-only',s);
 insert into maps(name,collection,sheet_number,status,series_id) values('Draft only other cell','L7014 label B','draft-only-other','draft',s);
 insert into maps(name,collection,sheet_number,status,series_id) values('Archived only cell','L7014 label B','archived-only','draft',s);
 insert into maps(name,status) values('Standalone map','draft');
 if (select count(*) from maps where name='Standalone map' and series_id is null and printing_id is null)<>1 then raise exception 'standalone map links were required'; end if;
 perform set_config('request.jwt.claim.role','service_role',true);
 if exists(select 1 from series_cell_coverage where key='draft-test') then raise exception 'draft series leaked through coverage'; end if;
 if exists(select 1 from series_printing_availability where key='draft-test') then raise exception 'draft series leaked through availability'; end if;
 insert into maps(name,status,archive_reason) values('Archived target fixture','archived','fixture target') returning id into m4;
 update maps set status='archived',archive_reason='fixture archived cell' where name='Archived only cell';
 begin
   insert into maps(name,status,duplicate_of_map_id) values('Invalid service archive','archived',m4);
   raise exception 'service role bypassed archive target validation';
 exception when others then if sqlerrm not like 'duplicate target must be an active%' then raise; end if; end;
 -- Insert status omission uses draft after 108.
 insert into maps(name) values('default status fixture') returning id into item1;
 if (select status from maps where id=item1)<>'draft' then raise exception 'maps status default is not draft'; end if;
 -- Archive protects identity, rejects self/cycles/chains, and only permits one-hop live targets.
 update maps set status='archived',duplicate_of_map_id=m1,archive_reason='duplicate reviewed' where id=m2;
 insert into maps(name,status) values('Second archived duplicate','draft') returning id into m3;
 begin update maps set status='archived',duplicate_of_map_id=m2 where id=m3; raise exception 'duplicate chain accepted';
 exception when others then if sqlerrm not like 'duplicate target must be an active%' then raise; end if; end;
 begin update maps set status='archived' where id=m1; raise exception 'referenced survivor archived';
 exception when others then if sqlerrm not like 'map with duplicate records%' and sqlerrm not like 'map change would invalidate archived duplicate links%' then raise; end if; end;
 begin update maps set duplicate_of_map_id=m2 where id=m1; raise exception 'active map given duplicate target';
 exception when others then if sqlerrm not like 'new row for relation%' and sqlerrm not like 'duplicate target is valid%' then raise; end if; end;
 begin update maps set duplicate_of_map_id=m2 where id=m2; raise exception 'self duplicate accepted';
 exception when others then if sqlerrm not like 'new row for relation%' and sqlerrm not like 'duplicate target must be an active%' then raise; end if; end;
end $$;

-- Public readers cannot see draft map rows or private archive targets.
set role anon;
select set_config('request.jwt.claim.role','anon',false);
select set_config('request.jwt.claim.sub','',false);
do $$ begin
 if exists(select 1 from maps where name in ('Draft only','Draft only other cell','Archived only cell')) then raise exception 'anonymous map gate exposed draft/archive'; end if;
 if exists(select 1 from maps where name='Scan B') then raise exception 'anonymous map gate exposed archived duplicate'; end if;
 if not exists(select 1 from maps where name='Legacy L7014 scan') then raise exception 'public legacy scan missing'; end if;
 if (select held_cell_count from series_cell_coverage where key='l7014-test')<>1 then raise exception 'anonymous coverage counted non-public cell'; end if;
 if exists(select 1 from series_cell_coverage_detail where key='l7014-test' and sheet_number in ('draft-only-other','archived-only') and held) then raise exception 'anonymous detail exposed non-public held flag'; end if;
 if not (select known_source from series_cell_coverage_detail where key='l7014-test' and sheet_number='6330-4') then raise exception 'linked institution URL was not visible'; end if;
 if (select known_source from series_cell_coverage_detail where key='l7014-test' and sheet_number='draft-only-other') then raise exception 'empty source cell claimed obtainable'; end if;
 if (select printing_count from series_printing_availability where key='l7014-test')<>1 then raise exception 'unverified printing counted in public availability'; end if;
 if (select item_linked_printing_count from series_printing_availability where key='l7014-test')<>1 then raise exception 'unverified printing counted as available'; end if;
end $$;
reset role;

-- Signed-in contributors can see drafts, but archived maps remain excluded.
set role authenticated;
select set_config('request.jwt.claim.role','authenticated',false);
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',false);
do $$ begin
 if (select held_cell_count from series_cell_coverage where key='l7014-test')<>2 then raise exception 'authenticated coverage did not include draft cell'; end if;
 if not (select held from series_cell_coverage_detail where key='l7014-test' and sheet_number='draft-only-other') then raise exception 'authenticated detail hid draft cell'; end if;
 if (select held from series_cell_coverage_detail where key='l7014-test' and sheet_number='archived-only') then raise exception 'authenticated detail counted archived cell'; end if;
 begin
   insert into maps(name,collection,status) values('Forbidden known-series insert','L7014 Test','draft');
   raise exception 'non-staff assigned series through collection on insert';
 exception when others then if sqlerrm not like 'catalog identity and asset links are staff-controlled%' then raise; end if; end;
 insert into maps(name,collection,status) values('Unknown collection label','Personal unmapped label','draft');
 if (select series_id from maps where name='Unknown collection label') is not null then raise exception 'unknown display label was assigned a series'; end if;
 begin
   update maps set collection='L7014 Test' where name='Standalone map';
   raise exception 'non-staff assigned series by editing collection';
 exception when others then if sqlerrm not like 'catalog identity and asset links are staff-controlled%' then raise; end if; end;
end $$;
reset role;

-- Service credentials bypass table RLS, so the view's explicit gate must match anonymous visibility.
set role service_role;
select set_config('request.jwt.claim.role','service_role',false);
select set_config('request.jwt.claim.sub','',false);
do $$ begin
 if (select held_cell_count from series_cell_coverage where key='l7014-test')<>1 then raise exception 'service coverage counted draft cell'; end if;
 if exists(select 1 from series_cell_coverage_detail where key='l7014-test' and sheet_number in ('draft-only-other','archived-only') and held) then raise exception 'service detail leaked non-public held flag'; end if;
 if not (select known_source from series_cell_coverage_detail where key='l7014-test' and sheet_number='6330-4') then raise exception 'service lost public institution URL'; end if;
 if (select printing_count from series_printing_availability where key='l7014-test')<>1 then raise exception 'service availability counted unverified printing'; end if;
end $$;
reset role;
select 'L7014 schema assertions passed' as result;
