-- Every province a map covers, not just the dominant one (scripts/oneoff/backfill_map_region.mjs).
-- `region` / `region_2025` (mig 109) stay the single province holding most of the sheet; these two
-- list each province holding at least 10% of its land, most first, so a sheet cut by a boundary
-- or a large regional sheet is found under all of them. Null when `region` would be null for want
-- of a bbox or of Vietnamese land; a country-scale sheet has a list but no single region.
alter table public.maps add column if not exists regions text[];
alter table public.maps add column if not exists regions_2025 text[];
comment on column public.maps.regions is 'Provinces (63-set, to 30 Jun 2025) each holding >=10% of the sheet''s land, largest first; derived from bbox. Modern locator, not the historical place name.';
comment on column public.maps.regions_2025 is 'The same list under the 34 provinces in force from 1 Jul 2025, de-duplicated; derived from regions.';
