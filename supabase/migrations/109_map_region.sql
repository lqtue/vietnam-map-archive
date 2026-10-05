-- A province-level locator for every map, derived from its bbox centre (scripts/oneoff/backfill_map_region.mjs).
-- Two columns because Vietnam went from 63 to 34 provinces on 1 July 2025: `region` is the province
-- until 30 June 2025, `region_2025` the same ground under the 34 in force now. Both are modern names, a
-- way to say where a sheet is, not what its own era called the place. Null when no one province
-- describes the map (a country-scale sheet) or the bbox is missing.
alter table public.maps add column if not exists region text;
alter table public.maps add column if not exists region_2025 text;
comment on column public.maps.region is 'Province (63-province set, to 30 Jun 2025) containing the bbox centre; derived, not hand-entered. A modern locator, not the historical place name. Null for country-scale sheets.';
comment on column public.maps.region_2025 is 'The same ground under the 34 provinces in force from 1 Jul 2025; derived from region. Null when region is.';
