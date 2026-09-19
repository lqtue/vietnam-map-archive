-- Migration 091 — preserve the reason a segmentation result was corrected.
--
-- A verdict alone says whether a polygon survived, but not what the model did
-- wrong. These fields turn the existing review queue into training evidence:
-- accepted examples, rejected false positives, and corrected contours all stay
-- tied to the producing `run_id` on footprint_submissions.

alter table public.footprint_submissions
  add column if not exists review_tags text[] not null default '{}',
  add column if not exists review_note text,
  add column if not exists reviewed_by uuid references auth.users(id) on delete set null,
  add column if not exists reviewed_at timestamptz;

alter table public.footprint_submissions
  drop constraint if exists footprint_submissions_review_tags_check;

alter table public.footprint_submissions
  add constraint footprint_submissions_review_tags_check
  check (review_tags <@ array[
    'boundary_too_wide', 'boundary_too_small', 'needs_split', 'needs_merge',
    'wrong_class', 'text_or_ornament', 'water_land_confusion', 'false_positive',
    'missed_neighbour', 'uncertain'
  ]::text[]);

comment on column public.footprint_submissions.review_tags is
  'Structured reviewer diagnosis for algorithm evaluation and model tuning; set with the final verdict.';
comment on column public.footprint_submissions.review_note is
  'Optional free-text context for a segmentation review decision.';
comment on column public.footprint_submissions.reviewed_by is
  'Staff reviewer who made the final segmentation verdict.';
comment on column public.footprint_submissions.reviewed_at is
  'Time the final segmentation verdict was recorded.';

-- Adding optional arguments otherwise creates an overload, and seven-argument
-- callers would keep resolving to migration 090's function forever.
drop function if exists public.set_footprint_status(uuid, text, uuid, jsonb, text, text, text);

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
returns public.footprint_submissions
language plpgsql
security definer
set search_path = public
as $$
declare
  updated public.footprint_submissions;
begin
  if p_status not in ('approved', 'rejected') then
    raise exception 'set_footprint_status: status must be approved or rejected (got %)', p_status;
  end if;

  update public.footprint_submissions f
     set status        = p_status,
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
     and f.status in ('needs_review', 'submitted')
  returning f.* into updated;

  return updated;
end;
$$;

revoke all on function public.set_footprint_status(uuid, text, uuid, jsonb, text, text, text, text[], text)
  from public, anon, authenticated;
grant execute on function public.set_footprint_status(uuid, text, uuid, jsonb, text, text, text, text[], text)
  to service_role;
