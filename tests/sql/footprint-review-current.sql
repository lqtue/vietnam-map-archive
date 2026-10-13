\set ON_ERROR_STOP on
-- Disposable local database only; this fixture rolls back all objects/data.
do $$ begin
 if current_database() <> 'vma_footprint_review' or coalesce(inet_server_addr()::text,'127.0.0.1') not in ('127.0.0.1','127.0.0.1/32','::1','::1/128') then
  raise exception 'Requires isolated local vma_footprint_review database';
 end if;
end $$;
begin;
do $$ begin
 if not exists(select from pg_roles where rolname='anon') then create role anon; end if;
 if not exists(select from pg_roles where rolname='authenticated') then create role authenticated; end if;
 if not exists(select from pg_roles where rolname='service_role') then create role service_role; end if;
end $$;
create table public.footprints(id uuid primary key, map_id uuid, pixel_polygon jsonb, feature_type text,
 review_status text, name text, category text, review_tags text[] default '{}', review_note text,
 reviewed_by uuid, reviewed_at timestamptz, source text, geom text, geom_src text, geom_rmse double precision);
create table public.pipeline_jobs(id uuid primary key default gen_random_uuid(),kind text,map_id uuid,
 payload jsonb,status text default 'queued');
create unique index idx_pipeline_jobs_one_live on pipeline_jobs(kind,map_id) where status in ('queued','claimed','running');
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


\ir ../../supabase/migrations/121_footprint_review_current.sql

do $$
declare
 original jsonb := '[[0,0],[10,0],[10,10],[0,10],[0,0]]';
 revised jsonb := '[[0,0],[12,0],[12,10],[0,10],[0,0]]';
 fid uuid := 'aaaaaaaa-0000-0000-0000-000000000001';
 mid uuid := 'bbbbbbbb-0000-0000-0000-000000000001';
 reviewer uuid := 'cccccccc-0000-0000-0000-000000000001';
 result uuid;
begin
 insert into footprints(id,map_id,pixel_polygon,feature_type,review_status,source,geom,geom_src,geom_rmse)
 values(fid,mid,original,'parcel','needs_review','import','old-geometry','old-version',5);
 begin
  perform review_footprint_if_current(fid,'approved',reviewer,revised,'parcel','needs_review',revised);
  raise exception 'Stale geometry was accepted';
 exception when serialization_failure then null; end;
 begin
  perform review_footprint_if_current(fid,'approved',reviewer,original,'building','needs_review',revised);
  raise exception 'Stale class was accepted';
 exception when serialization_failure then null; end;
 result := review_footprint_if_current(fid,'approved',reviewer,original,'parcel','needs_review',revised);
 if result <> fid or (select pixel_polygon <> revised or review_status <> 'approved' or source <> 'sam-corrected'
    or reviewed_by <> reviewer or reviewed_at is null or geom is not null or geom_src is not null from footprints where id=fid) then
  raise exception 'Review did not preserve the status/geometry/provenance contract';
 end if;
 if (select count(*) from pipeline_jobs where kind='warp' and map_id=mid) <> 1 then raise exception 'Warp was not queued'; end if;
 begin
  perform review_footprint_if_current(fid,'rejected',reviewer,original,'parcel','needs_review');
  raise exception 'A second stale reviewer overwrote the first';
 exception when serialization_failure then null; end;
 insert into footprints(id,map_id,pixel_polygon,feature_type,review_status,source,geom,geom_src)
 values('aaaaaaaa-0000-0000-0000-000000000002',mid,original,'building','needs_review','import','old-geometry','old-version');
 perform review_footprint_if_current('aaaaaaaa-0000-0000-0000-000000000002','approved',reviewer,
     original,'building','needs_review',null,'road');
 if (select geom is not null or geom_src is not null from footprints where id='aaaaaaaa-0000-0000-0000-000000000002') then
  raise exception 'Retyping kept a stale geometry cache';
 end if;
 if has_function_privilege('anon','public.review_footprint_if_current(uuid,text,uuid,jsonb,text,text,jsonb,text,text,text,text[],text)','execute')
    or has_function_privilege('authenticated','public.review_footprint_if_current(uuid,text,uuid,jsonb,text,text,jsonb,text,text,text,text[],text)','execute')
    or not has_function_privilege('service_role','public.review_footprint_if_current(uuid,text,uuid,jsonb,text,text,jsonb,text,text,text,text[],text)','execute') then
  raise exception 'Service-only execution grant is wrong';
 end if;
end $$;
rollback;
\echo 'footprint current-review fixture passed'
