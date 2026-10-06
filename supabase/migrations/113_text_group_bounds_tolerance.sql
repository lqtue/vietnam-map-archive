-- PostgREST serializes stored doubles through JSON; JavaScript recomputes the
-- envelope from those values. Exact equality can reject an unchanged selection
-- after a last-decimal rounding difference. Keep the stale-selection guard,
-- allowing only one millionth of a source-image pixel on each bound.
create or replace function public.group_text_boxes(
  p_map_id uuid, p_ids uuid[], p_text text, p_category text,
  p_bounds double precision[], p_geom text, p_geom_src text,
  p_geom_rmse double precision, p_user uuid
) returns uuid language plpgsql security definer set search_path = public, extensions as $$
declare
  v_id uuid := gen_random_uuid();
  v_run text;
  v_bounds double precision[];
begin
  if p_ids is null or cardinality(p_ids) not between 2 and 100 or p_text is null or length(btrim(p_text)) = 0
     or p_category is null or p_user is null
     or (select count(distinct x) from unnest(p_ids) x) <> cardinality(p_ids) then
    raise exception 'Invalid group' using errcode = '22023';
  end if;
  -- Stable lock order prevents overlapping selections from deadlocking.
  perform id from public.ocr_labels where map_id = p_map_id and id = any(p_ids) order by id for update;
  if (select count(*) from public.ocr_labels where map_id = p_map_id and id = any(p_ids)
        and text_group_id is null and not is_text_group
        and global_w > 0 and global_h > 0) <> cardinality(p_ids) then
    raise exception 'Boxes missing or already grouped' using errcode = '22023';
  end if;
  if (select count(distinct run_id) from public.ocr_labels where id = any(p_ids)) <> 1 then
    raise exception 'Choose boxes from the same OCR run' using errcode = '22023';
  end if;
  select min(run_id), array[min(global_x), min(global_y),
    max(global_x + global_w) - min(global_x), max(global_y + global_h) - min(global_y)]
    into v_run, v_bounds from public.ocr_labels where id = any(p_ids);
  -- The server warps this envelope before calling us. Abort if a box moved in
  -- the meantime rather than saving mismatched pixel and geographic positions.
  if cardinality(p_bounds) is distinct from 4 or exists (
    select 1 from generate_series(1, 4) i
    where p_bounds[i] is null or not (abs(p_bounds[i] - v_bounds[i]) <= 0.000001)
  ) then
    raise exception 'Boxes changed; reload and try again' using errcode = '22023';
  end if;
  insert into public.ocr_labels (id, map_id, run_id, tile_x, tile_y, tile_w, tile_h,
    global_x, global_y, global_w, global_h, label_w, label_h, rotation_deg,
    text, category, confidence, model, prompt, is_text_group,
    geom, geom_src, geom_rmse, notes)
  values (v_id, p_map_id, v_run, round(v_bounds[1]), round(v_bounds[2]), 0, 0,
    v_bounds[1], v_bounds[2], v_bounds[3], v_bounds[4], v_bounds[3], v_bounds[4], 0,
    btrim(p_text), p_category, 1, 'manual-group', 'manual-group', true,
    p_geom::extensions.geography, p_geom_src, p_geom_rmse,
    'Grouped by ' || p_user::text);
  update public.ocr_labels e set text_group_id = v_id, text_group_order = u.n - 1
    from unnest(p_ids) with ordinality u(id, n) where e.id = u.id;
  return v_id;
end $$;

