-- Migration 059 — stories join the moderation model (architecture step 7)
--
-- Decision 4: contributions are open, and every shared row carries a status
-- plus who reviewed it. Stories were the last shared table still gating
-- visibility on a boolean the author sets themselves.
--
-- `is_public` is dropped rather than kept alongside `status`: two visibility
-- models on one table is exactly the mess docs/guides/db-guidelines.md warns about on
-- `maps`. Publishing now means "submitted"; a mod approves.

alter table public.stories
  add column if not exists status text not null default 'draft'
    check (status in ('draft', 'submitted', 'approved', 'rejected')),
  add column if not exists reviewed_by uuid references auth.users(id) on delete set null,
  add column if not exists reviewed_at timestamptz;

comment on column public.stories.status is
  'draft = private to its author · submitted = awaiting review · approved = publicly visible · rejected = sent back.';

-- Anything already public was, in effect, approved.
update public.stories set status = 'approved' where is_public = true;

-- Two policies read stories.is_public, so they have to go before the column
-- does — Postgres refuses to drop a column a policy depends on.
drop policy if exists "stories_select" on public.stories;
drop policy if exists "story_points_select" on public.story_points;

alter table public.stories drop column if exists is_public;

create index if not exists idx_stories_status on public.stories (status) where status = 'submitted';

create policy "stories_select"
  on public.stories for select
  using (
    status = 'approved'
    or user_id = auth.uid()
    or exists (select 1 from public.profiles where id = auth.uid() and role in ('mod', 'admin'))
  );

create policy "story_points_select"
  on public.story_points for select
  using (
    exists (
      select 1 from public.stories
      where id = story_id
        and (
          status = 'approved'
          or user_id = auth.uid()
          or exists (select 1 from public.profiles where id = auth.uid() and role in ('mod', 'admin'))
        )
    )
  );

-- An author may edit their own story, but not review it: the status column is
-- guarded by set_story_status(), which the API calls with the service key.
drop policy if exists "stories_update_own" on public.stories;
create policy "stories_update_own"
  on public.stories for update
  using (user_id = auth.uid())
  with check (user_id = auth.uid() and status in ('draft', 'submitted'));

-- Review decision on one story. Approving records the reviewer; sending it back
-- to draft clears the stamp, so a re-submission is reviewed fresh.
create or replace function public.set_story_status(p_id uuid, p_status text, p_user uuid)
returns public.stories
language plpgsql
security definer
set search_path = public
as $$
declare
  updated public.stories;
begin
  if p_status not in ('draft', 'submitted', 'approved', 'rejected') then
    raise exception 'set_story_status: unknown status %', p_status;
  end if;

  update public.stories s
     set status      = p_status,
         reviewed_by = case when p_status in ('approved', 'rejected') then p_user else null end,
         reviewed_at = case when p_status in ('approved', 'rejected') then now() else null end
   where s.id = p_id
  returning s.* into updated;

  return updated;
end;
$$;

revoke all on function public.set_story_status(uuid, text, uuid) from public, anon, authenticated;
grant execute on function public.set_story_status(uuid, text, uuid) to service_role;
