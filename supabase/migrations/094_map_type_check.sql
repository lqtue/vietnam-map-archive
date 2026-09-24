-- Migration 094 — map_type gets the CHECK constraint status and source_type
-- already have (mig 038, 041). It never got one at 026, and the values it has
-- drifted from that migration's own comment ("cadastral", "topographic",
-- "city_plan", "panorama") to what ingest actually writes today.
--
-- Asserted against reality first, per the db-guidelines lesson: `select
-- distinct map_type from maps` on 2026-09-23 returned exactly these five
-- values plus null. 'panorama' and 'city_plan' from the original comment have
-- never been written by any script in the repo.

alter table public.maps
  add constraint maps_map_type_check
  check (map_type in ('topographic', 'plan', 'regional', 'route', 'cadastral'));
