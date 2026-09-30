-- Close direct PostgREST paths around moderation, draft visibility and slugs.
-- Deploy with the application changes that route map-view inserts through the API.

drop policy if exists "stories_insert" on public.stories;
create policy "stories_insert" on public.stories for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and review_status in ('draft', 'submitted')
    and reviewed_by is null and reviewed_at is null
  );

drop policy if exists "story_points_insert" on public.story_points;
create policy "story_points_insert" on public.story_points for insert to authenticated
  with check (exists (
    select 1 from public.stories s
    where s.id = story_id and s.user_id = (select auth.uid())
      and s.review_status in ('draft', 'submitted')
  ));

drop policy if exists "story_points_update_own" on public.story_points;
create policy "story_points_update_own" on public.story_points for update to authenticated
  using (exists (
    select 1 from public.stories s
    where s.id = story_id and s.user_id = (select auth.uid())
      and s.review_status in ('draft', 'submitted')
  ))
  with check (exists (
    select 1 from public.stories s
    where s.id = story_id and s.user_id = (select auth.uid())
      and s.review_status in ('draft', 'submitted')
  ));

drop policy if exists "story_points_delete_own" on public.story_points;
create policy "story_points_delete_own" on public.story_points for delete to authenticated
  using (exists (
    select 1 from public.stories s
    where s.id = story_id and s.user_id = (select auth.uid())
      and s.review_status in ('draft', 'submitted')
  ));

drop policy if exists "map_iiif_sources_select_all" on public.map_images;
create policy "map_images_select_visible_parent" on public.map_images for select
  using (exists (
    select 1 from public.maps m where m.id = map_id
      and (m.status in ('public', 'featured') or (select auth.uid()) is not null)
  ));

-- The view contains staff-only jobs and review marks and runs as its owner.
revoke select on public.map_pipeline_status from public, anon, authenticated;

-- A session can still create a draft, but cannot choose a pre-existing address,
-- clear it, or make a published map yield its canonical slug to a draft.
create or replace function public.maps_guard_contributor_slug()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if (select auth.uid()) is not null and (select auth.role()) <> 'service_role' then
    if tg_op = 'INSERT' and coalesce(new.slug, '') <> '' then
      raise exception 'slug is server-assigned';
    elsif tg_op = 'UPDATE' and new.slug is distinct from old.slug then
      raise exception 'slug is staff-controlled';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists aaa_maps_guard_contributor_slug on public.maps;
create trigger aaa_maps_guard_contributor_slug
  before insert or update on public.maps
  for each row execute function public.maps_guard_contributor_slug();

create or replace function public.maps_demote_bare_slug()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_stem text := coalesce(public.map_slug_base(new.name), 'sheet');
  v_incumbent public.maps%rowtype;
begin
  if new.slug = v_stem then return null; end if;

  select * into v_incumbent from public.maps
   where slug = v_stem and id is distinct from new.id;
  if not found then return null; end if;

  -- An unpublished contribution must not re-address a published sheet.
  if new.status = 'draft' and v_incumbent.status in ('public', 'featured') then
    return null;
  end if;

  update public.maps set slug = public.map_slug_mint(
    v_incumbent.name, v_incumbent.year, v_incumbent.id, v_stem
  ) where id = v_incumbent.id;
  return null;
end;
$$;

-- Browser inserts bypass all API validation and quota checks.
drop policy if exists "footprints_insert" on public.footprints;
revoke insert on public.footprints from anon, authenticated;
revoke insert on public.footprint_submissions from anon, authenticated;

-- Reserve a per-account slot atomically before accepting a footprint. A
-- read-then-insert count races under parallel requests and used to fail open.
create table if not exists public.contribution_quotas (
  user_id uuid not null,
  kind text not null,
  window_start timestamptz not null,
  used integer not null check (used > 0),
  primary key (user_id, kind, window_start)
);
alter table public.contribution_quotas enable row level security;
revoke all on public.contribution_quotas from public, anon, authenticated;

create or replace function public.consume_contribution_quota(
  p_user_id uuid, p_kind text, p_limit integer
)
returns boolean language plpgsql security definer set search_path = '' as $$
declare v_used integer;
begin
  if p_kind <> 'footprints' or p_limit < 1 or p_limit > 1000 then
    raise exception 'invalid contribution quota';
  end if;
  insert into public.contribution_quotas (user_id, kind, window_start, used)
  values (p_user_id, p_kind, date_trunc('hour', now()), 1)
  on conflict (user_id, kind, window_start) do update
    set used = public.contribution_quotas.used + 1
    where public.contribution_quotas.used < p_limit
  returning used into v_used;
  return v_used is not null;
end;
$$;
revoke all on function public.consume_contribution_quota(uuid, text, integer)
  from public, anon, authenticated;
grant execute on function public.consume_contribution_quota(uuid, text, integer) to service_role;

drop policy if exists map_opens_insert_public on public.map_views;
revoke insert on public.map_views from anon, authenticated;
revoke insert on public.map_opens from anon, authenticated;

-- Limit anonymous view counters even through the controlled server endpoint.
create or replace function public.record_map_view(p_map_id uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
declare
  v_count integer;
begin
  perform 1 from public.maps
    where id = p_map_id and status in ('public', 'featured');
  if not found then return false; end if;

  -- Serialize the bounded hourly tally so concurrent requests cannot bypass it.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext('map-views-global'));
  select count(*) into v_count from public.map_views
    where created_at >= now() - interval '1 hour';
  if v_count >= 5000 then return false; end if;
  select count(*) into v_count from public.map_views
    where map_id = p_map_id and created_at >= now() - interval '1 hour';
  if v_count >= 200 then return false; end if;
  insert into public.map_views(map_id) values (p_map_id);
  return true;
end;
$$;
revoke all on function public.record_map_view(uuid) from public, anon, authenticated;
grant execute on function public.record_map_view(uuid) to service_role;

-- A worker's self-selected display name is not authority over a claimed job.
alter table public.pipeline_jobs
  add column if not exists worker_key_id uuid references public.worker_keys(id);

drop function if exists public.claim_job(text[], text);
create function public.claim_job(p_kinds text[], p_worker text, p_worker_key_id uuid)
returns public.pipeline_jobs language plpgsql security definer set search_path = '' as $$
declare claimed public.pipeline_jobs;
begin
  update public.pipeline_jobs j
     set status = 'claimed', worker = p_worker, worker_key_id = p_worker_key_id,
         claimed_at = now(), attempts = j.attempts + 1
   where j.id = (
     select id from public.pipeline_jobs
      where kind = any(p_kinds)
        and (status = 'queued' or
          (status in ('claimed', 'running') and attempts < max_attempts
           and greatest(started_at, claimed_at) < now() - interval '3 hours'))
      order by (status <> 'queued'), priority desc, created_at
      for update skip locked limit 1
   )
  returning j.* into claimed;
  return claimed;
end;
$$;
revoke all on function public.claim_job(text[], text, uuid) from public, anon, authenticated;
grant execute on function public.claim_job(text[], text, uuid) to service_role;

drop function if exists public.finish_job(uuid, text, jsonb, text);
create function public.finish_job(
  p_id uuid, p_status text, p_worker_key_id uuid,
  p_result jsonb default '{}', p_error text default null
)
returns public.pipeline_jobs language plpgsql security definer set search_path = '' as $$
declare finished public.pipeline_jobs;
begin
  if p_status not in ('done', 'failed', 'running') then
    raise exception 'finish_job: invalid status';
  end if;
  update public.pipeline_jobs j
     set status = case when p_status = 'failed' and j.attempts < j.max_attempts
                        then 'queued' else p_status end,
         started_at = case when p_status = 'running' then now() else j.started_at end,
         finished_at = case when p_status = 'done' or
                           (p_status = 'failed' and j.attempts >= j.max_attempts)
                            then now() else null end,
         result = case when p_status = 'running' then null else p_result end,
         error = case when p_status = 'running' then null else p_error end
   where j.id = p_id and j.worker_key_id = p_worker_key_id
     and ((p_status = 'running' and j.status = 'claimed')
       or (p_status in ('done', 'failed') and j.status in ('claimed', 'running')))
  returning j.* into finished;
  return finished;
end;
$$;
revoke all on function public.finish_job(uuid, text, uuid, jsonb, text) from public, anon, authenticated;
grant execute on function public.finish_job(uuid, text, uuid, jsonb, text) to service_role;

-- Every direct staff RLS policy derives authority from profiles.role. Hide that
-- role from an AAL1 caller, so bypassing the application API with PostgREST
-- cannot recover staff write permissions. The service client bypasses RLS.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles for select
  using (
    id = (select auth.uid()) and (
      role is null or role not in ('admin', 'mod')
      or (select auth.jwt()->>'aal') = 'aal2'
    )
  );

-- Annotation objects were public even while their map was a draft. The app
-- serves the same stable object path through a status-aware endpoint; keep
-- the object bucket private so a guessed UUID cannot bypass that endpoint.
update public.maps
   set annotation_url = 'https://maparchive.vn/api/maps/' || id || '/annotation'
 where annotation_url ~ (
   '/storage/v1/object/public/annotations/' || id::text || '[.]json$'
 );
insert into storage.buckets (id, name, public)
values ('annotations', 'annotations', false)
on conflict (id) do update set public = false;
