\set ON_ERROR_STOP on
-- Run only in a fresh disposable local database named vma_map_taxonomy.
do $$ begin
  if current_database() <> 'vma_map_taxonomy' or coalesce(inet_server_addr()::text, '127.0.0.1') not in ('127.0.0.1', '127.0.0.1/32', '::1', '::1/128') then
    raise exception 'Requires isolated local vma_map_taxonomy database';
  end if;
end $$;
begin;
do $$ begin
  if not exists(select from pg_roles where rolname='anon') then create role anon; end if;
  if not exists(select from pg_roles where rolname='authenticated') then create role authenticated; end if;
end $$;
create schema auth; create table auth.users(id uuid primary key);
create table public.maps(id uuid primary key default gen_random_uuid(),map_type text,source_url text,series_key text,extra_metadata jsonb, constraint maps_map_type_check check(map_type in ('plan','regional','topographic','cadastral','route')));
create table public.map_images(id uuid primary key default gen_random_uuid(),map_id uuid references maps(id),is_primary boolean);
insert into maps(id,map_type) values ('6b344960-0b67-4240-8274-84983a0c7ede','plan'),('787439c7-8015-496d-a458-df61b89a4391','plan'),('e0aaf392-ea00-4838-b461-8e49d34dd939','plan'),('76cc876f-6c43-4e4c-b65a-595094db0017','regional'),('f9b3c9b2-5a11-4e8a-8b11-c988b28ae6d3','plan'),('3d065384-bb09-4b8c-b46b-bf006d0c3ba3','plan');
insert into maps(id,map_type,series_key,extra_metadata) values ('aaaaaaaa-0000-0000-0000-000000000001','plan','ams-l909-viet-nam-city-maps-1-12-500','{"scan_side":"verso"}');
insert into map_images(map_id,is_primary) values('aaaaaaaa-0000-0000-0000-000000000001',true),('6b344960-0b67-4240-8274-84983a0c7ede',true);
\ir ../../supabase/migrations/116_map_taxonomy.sql

do $$
declare m uuid; reviewer uuid := gen_random_uuid();
begin
  if (select count(*) from maps where map_type='hydrographic') <> 3 then raise exception 'chart backfill'; end if;
  if not exists(select from maps where id='f9b3c9b2-5a11-4e8a-8b11-c988b28ae6d3' and depicted_state='proposed' and map_subjects=array['urban_development']) then raise exception 'proposal backfill'; end if;
  if not exists(select from maps where id='76cc876f-6c43-4e4c-b65a-595094db0017' and map_type='thematic' and map_subjects=array['administrative_boundaries']) then raise exception 'administrative subject backfill'; end if;
  if not exists(select from map_images where map_id='aaaaaaaa-0000-0000-0000-000000000001' and content_role='index_map') then raise exception 'verso role'; end if;
  if not exists(select from map_images where map_id='6b344960-0b67-4240-8274-84983a0c7ede' and content_role='main_map') then raise exception 'primary scan role'; end if;
  insert into auth.users(id) values(reviewer);
  insert into public.maps(map_type) values('plan') returning id into m;
  if (select map_type <> 'city_plan' or map_type_legacy <> 'plan' from public.maps where id=m) then raise exception 'legacy plan compatibility'; end if;
  update public.maps set map_type='regional', map_subjects=array['transport','transport'] where id=m;
  if (select map_type <> 'general_reference' or map_subjects <> array['transport'] from public.maps where id=m) then raise exception 'normalization'; end if;
  begin
    update public.maps set map_type='bogus' where id=m;
    raise exception 'invalid type accepted';
  exception when check_violation then null; end;
  begin
    update public.maps set map_subjects=array['bogus'] where id=m;
    raise exception 'invalid subject accepted';
  exception when check_violation then null; end;
  begin
    update public.maps set depicted_state='bogus' where id=m;
    raise exception 'invalid state accepted';
  exception when check_violation then null; end;
  begin
    update public.maps set map_subjects=array[null]::text[] where id=m;
    raise exception 'null subject accepted';
  exception when check_violation then null; end;
  begin
    update public.maps set classification_status='reviewed' where id=m;
    raise exception 'review without evidence accepted';
  exception when check_violation then null; end;
  update public.maps set classification_status='reviewed',classification_note='Native legend checked',classification_reviewed_by=reviewer,classification_reviewed_at=now() where id=m;
  update public.maps set depicted_state='proposed' where id=m;
  if (select classification_status <> 'needs_review' or classification_reviewed_at is not null or classification_reviewed_by is not null from public.maps where id=m) then raise exception 'classification change kept stale review'; end if;
  update public.maps set classification_status='reviewed',classification_reviewed_by=reviewer,classification_reviewed_at=now() where id=m;
  delete from auth.users where id=reviewer;
  if (select classification_status <> 'needs_review' from public.maps where id=m) then raise exception 'deleted reviewer kept verdict'; end if;
  begin
    update public.map_images set content_role='bogus';
    raise exception 'invalid scan role accepted';
  exception when check_violation then null; end;
end $$;
rollback;
