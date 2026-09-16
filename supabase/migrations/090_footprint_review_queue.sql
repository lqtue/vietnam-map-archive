-- Migration 090 — one definition of "awaiting review", and a verdict that means
-- something.
--
-- Two halves of the same feature disagreed about which rows are in the queue:
--
--   * `fetchSubmittedFootprints` (the /scan?mode=shapes list) selects
--     `status = 'submitted'`.
--   * `set_footprint_status` (054) updates only `status = 'needs_review'`.
--
-- So every row the reviewer could see was a row the RPC refused, and the panel
-- answered 409 "That footprint is not awaiting review" on a polygon it had just
-- drawn for review. Measured on production 2026-09-16: 46 volunteer-traced
-- polygons on the 1882 cadastral, all `submitted`, none reachable.
--
-- The second half is the verdict. 055's own column comment reads
-- `draft → submitted → approved | rejected`, and /api/export/footprints
-- defaults to `status=approved` — but the only verdicts 054 accepted were
-- `submitted` and `rejected`, and the API narrowed that again to those two. So
-- `approved` was unreachable from any caller and the export's default has
-- always returned nothing. Nothing caught it because no `seg` job has ever
-- completed and no volunteer polygon has ever been decided.
--
-- After this: both inboxes are the queue, a decision is `approved` or
-- `rejected`, and a decided row still cannot be re-decided without a
-- deliberate reset.

create or replace function public.set_footprint_status(
  p_id            uuid,
  p_status        text,
  p_user          uuid,
  p_pixel_polygon jsonb default null,
  p_feature_type  text  default null,
  p_name          text  default null,
  p_category      text  default null
)
returns public.footprint_submissions
language plpgsql
security definer
set search_path = public
as $$
declare
  updated public.footprint_submissions;
begin
  -- `submitted` is an inbox, not a decision, so it is no longer a verdict.
  if p_status not in ('approved', 'rejected') then
    raise exception 'set_footprint_status: status must be approved or rejected (got %)', p_status;
  end if;

  update public.footprint_submissions f
     set status        = p_status,
         pixel_polygon = coalesce(p_pixel_polygon, f.pixel_polygon),
         feature_type  = coalesce(p_feature_type, f.feature_type),
         name          = coalesce(p_name, f.name),
         category      = coalesce(p_category, f.category),
         source        = case
                           when p_pixel_polygon is not null or p_feature_type is not null
                           then 'sam-corrected'
                           else f.source
                         end
   -- Both inboxes: `needs_review` is where MapSAM2 writes, `submitted` where a
   -- volunteer's trace lands. A row only leaves once — re-deciding an already
   -- approved or rejected polygon needs a deliberate reset, not a second click.
   where f.id = p_id
     and f.status in ('needs_review', 'submitted')
  returning f.* into updated;

  return updated;  -- null row when the id was missing or already decided
end;
$$;

revoke all on function public.set_footprint_status(uuid, text, uuid, jsonb, text, text, text)
  from public, anon, authenticated;
grant execute on function public.set_footprint_status(uuid, text, uuid, jsonb, text, text, text)
  to service_role;

comment on column public.footprint_submissions.status is
  'Lifecycle: draft → submitted → approved | rejected. MapSAM2 output enters as '
  'needs_review instead of submitted; both are the review queue, and both leave '
  'it only via set_footprint_status().';
