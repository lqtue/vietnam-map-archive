-- Seven primary types, independent subjects/state/scan roles and review evidence.
-- Geography remains in region(s)/regions_2025; no names, dates, rights, identities
-- or publication statuses change. Legacy classifications are preserved verbatim.
-- Classification evidence below comes from the 2026-10-06 original-map audit.
-- Automated migration is provisional, never a human-reviewed verdict.

alter table public.maps
  add column map_type_legacy text,
  add column map_subjects text[] not null default '{}',
  add column depicted_state text not null default 'unknown',
  add column classification_status text not null default 'needs_review',
  add column classification_note text,
  add column classification_source_url text,
  add column classification_reviewed_at timestamptz,
  add column classification_reviewed_by uuid references auth.users(id) on delete set null;

alter table public.map_images
  add column content_role text not null default 'unknown';

alter table public.maps drop constraint maps_map_type_check;
update public.maps set
  map_type_legacy = map_type,
  map_type = case map_type when 'plan' then 'city_plan' when 'regional' then 'general_reference' else map_type end,
  classification_status = case when map_type is null then 'needs_review' else 'provisional' end,
  classification_note = 'Inherited catalog classification; vocabulary normalized in migration 116. Not a human review.';

-- Navigation purpose is explicitly supported by the Humazur river record,
-- matching 1791 Marine chart and port soundings recorded in the catalog audit.
update public.maps set map_type = 'hydrographic', map_subjects = array['navigation'],
  classification_source_url = source_url,
  classification_note = case id
    when '6b344960-0b67-4240-8274-84983a0c7ede' then 'Humazur item 24330 describes the river to its mouth and alignments for crossing the Thuan-An bar. Provisional source-backed hydrographic classification.'
    when '787439c7-8015-496d-a458-df61b89a4391' then '1791 river/estuary chart; matching David Rumsey edition identifies Depot de la Marine and Hydrographie Francaise. Provisional, not physical-copy identity verification.'
    else 'Port chart with channel soundings and tidal notes in the scan/catalog description. Provisional hydrographic classification.' end
where id in ('6b344960-0b67-4240-8274-84983a0c7ede', '787439c7-8015-496d-a458-df61b89a4391', 'e0aaf392-ea00-4838-b461-8e49d34dd939')
  and map_type_legacy = 'plan';

update public.maps set map_type = 'thematic', map_subjects = array['administrative_boundaries'],
  classification_source_url = source_url,
  classification_note = 'Cochinchine Administrative: administrative divisions dominate the map. Extent remains geographic coverage, not its primary type.'
where id = '76cc876f-6c43-4e4c-b65a-595094db0017' and map_type_legacy = 'regional';

update public.maps set map_subjects = array['land_ownership'], classification_source_url = source_url,
  classification_note = 'Explicit cadastral title and parcel/property-oriented city survey; inherited type retained provisionally.'
where id = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b' and map_type = 'cadastral';
update public.maps set map_subjects = array['transport'] where map_type = 'route';
update public.maps set map_subjects = array['urban_development'], depicted_state = 'proposed',
  classification_source_url = source_url,
  classification_note = 'Coffyn 1862 proposed masterplan; drawn features must not be treated as all built. Geographicus record and existing catalog description.'
where id = 'f9b3c9b2-5a11-4e8a-8b11-c988b28ae6d3' and map_type_legacy = 'plan';
update public.maps set map_subjects = array['economic_activity'], classification_source_url = source_url,
  classification_note = 'Hanoi economique: city plan with an economic subject; primary form retained provisionally.'
where id = 'd0a9dba7-d7cd-492e-9ac1-087a9e62075f' and map_type_legacy = 'plan';

-- A French title containing "topographique" or "plan" does not settle the
-- cartographic method. Keep the inherited type until native symbols are read.
update public.maps set classification_status = 'needs_review', classification_source_url = source_url,
  classification_note = case id
    when '3d065384-bb09-4b8c-b46b-bf006d0c3ba3' then 'Topographic candidate: inspect native relief/survey conventions and legend before reclassifying the 20e Arrondissement map.'
    when '3926cf82-dc2b-437a-95b2-cdc119a9b318' then 'Inspect native soundings and legend to distinguish a port chart from a port/site layout.'
    else 'Environs survey: inspect native legend and relief representation before choosing city plan or topographic.' end
where id in ('3d065384-bb09-4b8c-b46b-bf006d0c3ba3','3926cf82-dc2b-437a-95b2-cdc119a9b318','1bce28f0-aa82-48eb-8e33-8f0b07182c2f','9249c588-678c-4292-be5b-7d47bbd9f6a2','e0193e00-8fd0-412c-92d1-46bbd1ef3d0d','f08aa539-e46e-48f4-8689-dee80bd66ec9')
  and map_type_legacy = 'plan';

update public.map_images as image set content_role = case
  when map.series_key = 'ams-l909-viet-nam-city-maps-1-12-500' and map.extra_metadata->>'scan_side' = 'verso' then 'index_map'
  when image.is_primary then 'main_map'
  else 'unknown' end
from public.maps as map where image.map_id = map.id;

alter table public.maps
  add constraint maps_map_type_check check (map_type in ('general_reference','city_plan','topographic','cadastral','hydrographic','route','thematic')),
  add constraint maps_map_subjects_check check (map_subjects <@ array['administrative_boundaries','urban_development','transport','economic_activity','military_operations','land_ownership','navigation','geology','population','land_use']::text[] and array_position(map_subjects, null) is null),
  add constraint maps_depicted_state_check check (depicted_state in ('observed','proposed','mixed','unknown')),
  add constraint maps_classification_status_check check (classification_status in ('needs_review','provisional','reviewed')),
  add constraint maps_classification_review_check check (classification_status <> 'reviewed' or (classification_reviewed_at is not null and classification_reviewed_by is not null and nullif(btrim(classification_note),'') is not null));
alter table public.map_images add constraint map_images_content_role_check
  check (content_role in ('main_map','index_map','legend','text','unknown'));

-- Older ingest clients can still send plan/regional; the DB stores canonical
-- values. Subsequent classification edits invalidate a prior reviewed verdict.
create function public.normalize_map_taxonomy() returns trigger
language plpgsql set search_path = public as $$
begin
  if tg_op = 'INSERT' then new.map_type_legacy := coalesce(new.map_type_legacy, new.map_type); end if;
  new.map_type := case new.map_type when 'plan' then 'city_plan' when 'regional' then 'general_reference' else new.map_type end;
  new.map_subjects := array(select distinct subject from unnest(new.map_subjects) as subject order by subject);
  if tg_op = 'UPDATE' and (new.map_type is distinct from old.map_type or new.map_subjects is distinct from old.map_subjects or new.depicted_state is distinct from old.depicted_state or (old.classification_reviewed_by is not null and new.classification_reviewed_by is null)) then
    new.classification_status := 'needs_review';
    new.classification_reviewed_at := null;
    new.classification_reviewed_by := null;
  end if;
  return new;
end $$;
revoke execute on function public.normalize_map_taxonomy() from public, anon, authenticated;
create trigger maps_normalize_taxonomy before insert or update on public.maps
  for each row execute function public.normalize_map_taxonomy();

comment on column public.maps.map_type_legacy is 'Pre-taxonomy catalog assertion retained for comparison; not a second current type.';
comment on column public.maps.classification_status is 'Migration/ingest may be provisional. Reviewed requires a human reviewer, date and evidence note.';
comment on column public.maps.depicted_state is 'What is depicted: observed conditions, a proposal, mixed or unknown; independent of publication status.';
comment on column public.map_images.content_role is 'Role of this scan, independent of the map genre and recto/verso side.';
