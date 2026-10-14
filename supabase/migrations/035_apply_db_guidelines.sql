-- ============================================================
-- Migration 035 — Apply DB design guidelines
-- Ref: docs/guides/db-guidelines.md
--
-- Changes:
--   1. profiles.role CHECK: add 'cataloger'
--   2. georef_submissions.submitted_by → user_id
--   3. georef_submissions: add updated_at auto-trigger
--   4. label_tasks: drop dead `region` column
--   5. label_tasks: add updated_at auto-trigger
--   6. annotation_sets: add updated_at auto-trigger
--   7. footprint_submissions: add updated_at + auto-trigger
-- ============================================================


-- ---- 1. profiles.role: add 'cataloger' to allowed values ----

alter table public.profiles
  drop constraint if exists profiles_role_check;

alter table public.profiles
  add constraint profiles_role_check
    check (role in ('admin', 'cataloger', 'user'));

comment on column public.profiles.role is
  'User role. admin: full write access. cataloger: can enrich map metadata. user: default volunteer.';


-- ---- 2. georef_submissions.submitted_by → user_id ----

alter table public.georef_submissions
  rename column submitted_by to user_id;

comment on column public.georef_submissions.user_id is
  'User who claimed and submitted this georef task. Null if unclaimed.';


-- ---- 3. georef_submissions: auto-update trigger ----
-- Table already has updated_at column (migration 002) but no trigger.

create or replace function public.georef_submissions_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger georef_submissions_updated_at
  before update on public.georef_submissions
  for each row execute function public.georef_submissions_set_updated_at();


-- ---- 4. label_tasks: drop dead `region` column ----
-- Added in migration 008 as a placeholder; never populated or read in code.

alter table public.label_tasks
  drop column if exists region;


-- ---- 5. label_tasks: auto-update trigger ----
-- Table already has updated_at column (migration 008) but no trigger.

create or replace function public.label_tasks_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger label_tasks_updated_at
  before update on public.label_tasks
  for each row execute function public.label_tasks_set_updated_at();


-- ---- 6. annotation_sets: auto-update trigger ----
-- Table already has updated_at column (migration 007) but no trigger.

create or replace function public.annotation_sets_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger annotation_sets_updated_at
  before update on public.annotation_sets
  for each row execute function public.annotation_sets_set_updated_at();


-- ---- 7. footprint_submissions: add updated_at + trigger ----
-- Status changes (needs_review → submitted/rejected) are mutations;
-- updated_at is needed to track when a review happened.

alter table public.footprint_submissions
  add column if not exists updated_at timestamptz default now();

create or replace function public.footprint_submissions_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger footprint_submissions_updated_at
  before update on public.footprint_submissions
  for each row execute function public.footprint_submissions_set_updated_at();
