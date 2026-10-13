-- Compare-and-review under the same row lock. An old preview must not replace
-- somebody else's correction. Reuses the existing status transition and stamps.
create or replace function public.review_footprint_if_current(
  p_id uuid,
  p_status text,
  p_user uuid,
  p_expected_polygon jsonb,
  p_expected_feature_type text,
  p_expected_status text,
  p_pixel_polygon jsonb default null,
  p_feature_type text default null,
  p_name text default null,
  p_category text default null,
  p_review_tags text[] default null,
  p_review_note text default null
)
returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  current_row public.footprints;
  reviewed_id uuid;
begin
  select * into current_row from public.footprints where id = p_id for update;
  if not found then return null; end if;
  if p_expected_polygon is null or p_expected_feature_type is null or p_expected_status is null
     or current_row.pixel_polygon is distinct from p_expected_polygon
     or current_row.feature_type is distinct from p_expected_feature_type
     or current_row.review_status is distinct from p_expected_status then
    raise exception using errcode = '40001', message = 'Footprint changed; reload before reviewing';
  end if;
  select r.id into reviewed_id from public.set_footprint_status(
    p_id, p_status, p_user, p_pixel_polygon, p_feature_type, p_name,
    p_category, p_review_tags, p_review_note
  ) r;
  if reviewed_id is not null and (
     (p_pixel_polygon is not null and p_pixel_polygon is distinct from current_row.pixel_polygon)
     or (p_feature_type is not null and p_feature_type is distinct from current_row.feature_type)
  ) then
    update public.footprints set geom = null, geom_src = null, geom_rmse = null where id = p_id;
    if current_row.map_id is not null then
      insert into public.pipeline_jobs(kind, map_id, payload)
        values ('warp', current_row.map_id, jsonb_build_object('reason', 'footprint_geometry_review'))
        on conflict (kind, map_id) where status in ('queued', 'claimed', 'running') do nothing;
    end if;
  end if;
  return reviewed_id;
end;
$$;
revoke all on function public.review_footprint_if_current(uuid,text,uuid,jsonb,text,text,jsonb,text,text,text,text[],text) from public, anon, authenticated;
grant execute on function public.review_footprint_if_current(uuid,text,uuid,jsonb,text,text,jsonb,text,text,text,text[],text) to service_role;
