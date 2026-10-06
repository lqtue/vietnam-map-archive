-- A combined label has its own searchable text and navigation envelope. The
-- original readings and oriented rectangles remain untouched, in click order.
-- No nesting: ungroup first. All membership changes are one service-only RPC.
alter table public.ocr_labels
  add column if not exists is_text_group boolean not null default false,
  add column if not exists text_group_id uuid,
  add column if not exists text_group_order integer;

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'ocr_labels_map_id_id_unique' and conrelid = 'public.ocr_labels'::regclass) then
    alter table public.ocr_labels add constraint ocr_labels_map_id_id_unique unique (map_id, id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ocr_labels_text_group_fk' and conrelid = 'public.ocr_labels'::regclass) then
    alter table public.ocr_labels add constraint ocr_labels_text_group_fk
      foreign key (map_id, text_group_id) references public.ocr_labels(map_id, id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'ocr_labels_text_group_shape' and conrelid = 'public.ocr_labels'::regclass) then
    alter table public.ocr_labels add constraint ocr_labels_text_group_shape check (
      (text_group_id is null and text_group_order is null) or
      (text_group_id is not null and text_group_order >= 0 and text_group_order is not null
       and text_group_id <> id and not is_text_group)
    );
  end if;
end $$;
create unique index if not exists ocr_labels_text_group_order_idx
  on public.ocr_labels(text_group_id, text_group_order) where text_group_id is not null;

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
  if p_bounds is distinct from v_bounds then
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

create or replace function public.ungroup_text_boxes(p_map_id uuid, p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform id from public.ocr_labels where id = p_id and map_id = p_map_id and is_text_group for update;
  if not found then raise exception 'Group not found' using errcode = '22023'; end if;
  update public.ocr_labels set text_group_id = null, text_group_order = null
    where text_group_id = p_id and map_id = p_map_id;
  delete from public.ocr_labels where id = p_id and map_id = p_map_id;
end $$;

revoke all on function public.group_text_boxes(uuid, uuid[], text, text, double precision[], text, text, double precision, uuid) from public, anon, authenticated;
revoke all on function public.ungroup_text_boxes(uuid, uuid) from public, anon, authenticated;
grant execute on function public.group_text_boxes(uuid, uuid[], text, text, double precision[], text, text, double precision, uuid) to service_role;
grant execute on function public.ungroup_text_boxes(uuid, uuid) to service_role;
-- Existing column-level grants do not automatically cover additive columns.
grant select (is_text_group, text_group_id, text_group_order) on public.ocr_labels to anon, authenticated;

-- Search/context expose the combined label, rather than its parts.
create or replace function public.search_labels(
  p_q           text,
  p_public_only boolean default true,
  p_limit       integer default 50
)
returns table (
  id          uuid,
  map_id      uuid,
  label       text,
  category    text,
  confidence  double precision,
  x           double precision,
  y           double precision,
  w           double precision,
  h           double precision,
  sim         real,
  lng         double precision,
  lat         double precision,
  geom_rmse   double precision
)
language sql
stable
security definer
set search_path = public, extensions
as $$
  with q as (
    select lower(public.f_unaccent(btrim(p_q))) as key
  ),
  hits as (
    select distinct on (e.map_id, public.label_key(e.text, e.text_corrected))
           e.id,
           e.map_id,
           coalesce(e.text_corrected, e.text)                 as label,
           coalesce(e.category_corrected, e.category)         as category,
           e.confidence,
           e.global_x, e.global_y, e.global_w, e.global_h,
           word_similarity(q.key, public.label_key(e.text, e.text_corrected)) as sim,
           e.geom, e.geom_rmse
      from public.ocr_labels e
      join public.maps m on m.id = e.map_id
      cross join q
     where length(q.key) >= 2
       and word_similarity(q.key, public.label_key(e.text, e.text_corrected)) >= 0.5
       and e.review_status <> 'rejected'
       and e.text_group_id is null
       and coalesce(e.category_corrected, e.category)
           in ('street', 'hydrology', 'place', 'building', 'institution')
       and e.global_x is not null
       and (not p_public_only or m.status in ('public', 'featured'))
     order by e.map_id, public.label_key(e.text, e.text_corrected), e.confidence desc
  )
  select id, map_id, label, category, confidence,
         global_x, global_y, global_w, global_h, sim,
         st_x(geom::geometry), st_y(geom::geometry), geom_rmse
    from hits
   order by sim desc, confidence desc
   limit greatest(1, least(p_limit, 200));
$$;

-- Search/context expose the combined label, rather than its parts.
create or replace function public.context_at(
  p_lng         double precision,
  p_lat         double precision,
  p_radius_m    double precision default 150,
  p_year_from   integer default null,
  p_year_to     integer default null,
  p_public_only boolean default true,
  p_limit       integer default 50
)
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
  with params as (
    select st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography as here,
           greatest(1, least(p_radius_m, 5000))                    as radius,
           greatest(1, least(p_limit, 200))                        as lim
  ),
  visible as (
    select m.id, m.name, m.year, m.status, m.allmaps_id
      from public.maps m
     where (not p_public_only or m.status in ('public', 'featured'))
       and (p_year_from is null or m.year >= p_year_from)
       and (p_year_to   is null or m.year <= p_year_to)
  ),
  label as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'id', e.id, 'map_id', e.map_id, 'map_name', v.name, 'year', v.year,
               'text', coalesce(e.text_corrected, e.text),
               'category', coalesce(e.category_corrected, e.category),
               'status', e.review_status,
               'distance_m', round(st_distance(e.geom, p.here)::numeric, 1),
               'geom_rmse', e.geom_rmse,
               'lng', st_x(e.geom::geometry), 'lat', st_y(e.geom::geometry)
             ) as x
        from public.ocr_labels e
        join visible v on v.id = e.map_id
        cross join params p
       where e.geom is not null
         and e.review_status <> 'rejected'
         and e.text_group_id is null
         and st_dwithin(e.geom, p.here, p.radius)
       order by st_distance(e.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  footprint as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'id', f.id, 'map_id', f.map_id, 'map_name', v.name, 'year', v.year,
               'name', f.name, 'feature_type', f.feature_type,
               'category', f.category, 'source', f.source, 'status', f.review_status,
               'distance_m', round(st_distance(f.geom, p.here)::numeric, 1),
               'geom_rmse', f.geom_rmse,
               'geometry', st_asgeojson(f.geom::geometry)::jsonb
             ) as x
        from public.footprints f
        join visible v on v.id = f.map_id
        cross join params p
       where f.geom is not null
         and f.review_status = 'approved'
         and st_dwithin(f.geom, p.here, p.radius)
       order by st_distance(f.geom, p.here)
       limit (select lim from params)
    ) s
  ),
  covering as (
    select jsonb_agg(x order by (x->>'year')::integer nulls last) as v from (
      select jsonb_build_object(
               'id', v.id, 'name', v.name, 'year', v.year,
               'status', v.status, 'allmaps_id', v.allmaps_id
             ) as x
        from visible v
        join public.maps m on m.id = v.id
       where m.bbox is not null
         and array_length(m.bbox, 1) = 4
         and p_lng between m.bbox[1] and m.bbox[3]
         and p_lat between m.bbox[2] and m.bbox[4]
       order by v.year
       limit (select lim from params)
    ) s
  ),
  story as (
    select jsonb_agg(x order by (x->>'distance_m')::numeric) as v from (
      select jsonb_build_object(
               'story_id', sp.story_id, 'point_id', sp.id, 'title', sp.title,
               'story_title', s2.title,
               'distance_m', round(
                 st_distance(
                   st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography,
                   p.here
                 )::numeric, 1)
             ) as x
        from public.story_points sp
        join public.stories s2 on s2.id = sp.story_id
        cross join params p
       where sp.lon is not null and sp.lat is not null
         and (not p_public_only or s2.review_status = 'approved')
         and st_dwithin(
               st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography,
               p.here, p.radius)
       order by st_distance(
                  st_setsrid(st_makepoint(sp.lon, sp.lat), 4326)::geography, p.here)
       limit (select lim from params)
    ) s
  )
  select jsonb_build_object(
    'at',         jsonb_build_array(p_lng, p_lat),
    'radius_m',   (select radius from params),
    'maps',       coalesce((select v from covering), '[]'::jsonb),
    'labels',     coalesce((select v from label), '[]'::jsonb),
    'footprints', coalesce((select v from footprint), '[]'::jsonb),
    'stories',    coalesce((select v from story), '[]'::jsonb)
  );
$$;

create or replace view public.place_names
with (security_invoker = true)
as
  select
    -- The most-attested spelling's key. Unique per group by construction: two
    -- rows sharing a place_key share a core_key and so share a group.
    mode() within group (order by public.place_key(e.text, e.text_corrected))  as name_key,
    mode() within group (order by coalesce(e.text_corrected, e.text))          as name,
    array_agg(distinct coalesce(e.text_corrected, e.text))                     as variants,
    array_remove(array_agg(distinct m.year), null)                             as years,
    min(m.year)                                                                as first_year,
    max(m.year)                                                                as last_year,
    array_agg(distinct e.map_id)                                               as map_ids,
    count(*)                                                                   as mentions,
    mode() within group (order by coalesce(e.category_corrected, e.category))  as category,
    extensions.st_y(
      extensions.st_centroid(
        extensions.st_collect(e.geom::extensions.geometry))::extensions.geometry) as lat,
    extensions.st_x(
      extensions.st_centroid(
        extensions.st_collect(e.geom::extensions.geometry))::extensions.geometry) as lng,
    max(e.geom_rmse)                                                           as geom_rmse,
    public.place_core_key(e.text, e.text_corrected)                            as core_key
    from public.ocr_labels e
    join public.maps m on m.id = e.map_id
    -- The visibility gate, said out loud. `security_invoker` alone was the
    -- whole story until now, and it is no story at all for the callers that
    -- matter: /catalog/place/[name] and /api/search both read this view on the
    -- service client, which bypasses RLS. A draft sheet's labels therefore
    -- reached the aggregate — not the sheet list, which the loader filters by
    -- status itself, but `mentions`, `years` and `first_year`, so an
    -- unpublished map moved a public page's dates. `auth.uid()` is null for a
    -- service-key caller and set for a signed-in browser one, which is exactly
    -- the line migration 063 draws.
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and e.review_status <> 'rejected'
     and e.text_group_id is null
     and coalesce(e.category_corrected, e.category)
         in ('street', 'hydrology', 'place', 'building', 'institution')
     and length(public.place_key(e.text, e.text_corrected)) >= 2
   group by public.place_core_key(e.text, e.text_corrected);


-- A composite FK prevents cross-map membership; this prevents attaching boxes
-- to an ordinary reading through a direct service-role write.
create or replace function public.check_text_group_parent()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.text_group_id is not null and not exists (
    select 1 from public.ocr_labels where id = new.text_group_id
      and map_id = new.map_id and is_text_group and text_group_id is null
  ) then raise exception 'Parent must be a text group' using errcode = '23514'; end if;
  return new;
end $$;
drop trigger if exists ocr_labels_text_group_parent on public.ocr_labels;
create trigger ocr_labels_text_group_parent before insert or update of text_group_id, map_id
  on public.ocr_labels for each row execute function public.check_text_group_parent();
revoke all on function public.check_text_group_parent() from public, anon, authenticated;

-- Group verdicts leave the source readings intact.
create or replace function public.set_extraction_status(
  p_status  text,
  p_user    uuid,
  p_ids     uuid[] default null,
  p_map_id  uuid   default null,
  p_run_id  text   default null
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  if p_status not in ('validated', 'rejected', 'pending') then
    raise exception 'set_extraction_status: status must be validated, rejected or pending (got %)', p_status;
  end if;
  if p_ids is null and p_map_id is null then
    raise exception 'set_extraction_status: pass p_ids or p_map_id';
  end if;

  update public.ocr_labels e
     set review_status = p_status,
         reviewed_at    = case when p_status = 'validated' then now() else null end,
         reviewed_by    = case when p_status = 'validated' then p_user else null end
   where e.text_group_id is null
     and (p_ids    is null or e.id     = any(p_ids))
     and (p_map_id is null or e.map_id = p_map_id)
     and (p_run_id is null or e.run_id = p_run_id);

  get diagnostics n = row_count;
  return n;
end;
$$;

-- Group verdicts leave the source readings intact.
create or replace function public.revert_recent_validations(
  p_map_id      uuid,
  p_user        uuid,
  p_window_mins integer default 30
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  update public.ocr_labels e
     set review_status = 'pending',
         reviewed_at    = null,
         reviewed_by    = null
   where e.text_group_id is null
     and e.map_id      = p_map_id
     and e.review_status = 'validated'
     and e.reviewed_by  = p_user
     and e.reviewed_at  > now() - make_interval(mins => p_window_mins);

  get diagnostics n = row_count;
  return n;
end;
$$;
