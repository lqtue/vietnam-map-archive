-- Migration 085 — 083's check constraint never fired, because NULL is not false
--
-- `series_sheets_held_by_map` was written to stop the one state that would
-- silently undercount a survey: a row pointing at a `maps` row without saying
-- it is held, which `held_by is not null` then skips. It reads
--
--     check (map_id is null or held_by = 'map')
--
-- and the case it exists to catch is exactly `held_by IS NULL`, where
-- `held_by = 'map'` evaluates to NULL rather than false. A CHECK constraint
-- rejects only false, so the row is accepted. The constraint fires solely on a
-- non-null `held_by` that is some other string — a typo — and not on the
-- absence the comment above it describes.
--
-- Verified rather than reasoned: inserting `(map_id = <a real map>, held_by =
-- null)` against a database at migration 083 returns INSERT 0 1.
--
-- `is not distinct from` is null-aware and treats NULL as a value, so the
-- comparison is false where it was NULL and the row is rejected.
--
-- Nothing in the corpus violates it (measured 2026-09-13: 67 rows carry a
-- `map_id`, all 67 with `held_by = 'map'`; the other 636 are 452 `raster:l7014`
-- and 184 null with no `map_id`), so this tightens without a backfill. The
-- converse is still deliberately not asserted, for 083's reason: `on delete set
-- null` must be allowed to fire.

alter table public.series_sheets drop constraint series_sheets_held_by_map;

alter table public.series_sheets add constraint series_sheets_held_by_map
  check (map_id is null or held_by is not distinct from 'map');
