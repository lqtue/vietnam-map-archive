-- 120 — `parcel`: the block a street grid encloses, holding plots and buildings.
--
-- The 1882 cadastral sheet is resolved top-down (owner's call, 2026-10-11):
--   1. parcels — every block outline, exact;
--   2. roads — the negative space: neatline minus water minus parcels;
--   3. per parcel — the land_plots and buildings inside it.
-- Until now a block and a lot inside it were both `land_plot`, so a block
-- holding its own lots read as overlapping plots, and nothing could tell
-- the outline roads are cut from from the subdivisions within it.
--
-- The constraint kept its pre-095 name through the table rename; both are
-- dropped so this replays on a stack where it was ever renamed.

alter table public.footprints drop constraint if exists footprint_submissions_feature_type_check;
alter table public.footprints drop constraint if exists footprints_feature_type_check;

alter table public.footprints
  add constraint footprints_feature_type_check
  check (feature_type in (
    'parcel', 'building', 'land_plot', 'road', 'waterway', 'green_space', 'water_body', 'other'
  ));
