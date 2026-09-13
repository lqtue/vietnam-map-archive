-- Migration 083 — what a series contains, as opposed to what we hold
--
-- `maps` answers "which sheets do we have". Nothing answers "which sheets are
-- there", and the difference is not a detail: measured on 2026-09-13, the
-- L7014 city series was offered publicly at 9 of 24 sheets and the UI said
-- "9 sheets", because 9 is all `maps` knows about. A series row is a claim
-- about coverage, and a claim about coverage cannot be made from a table that
-- only contains successes.
--
-- The same absence hides three other things. A sheet nobody has looked for is
-- indistinguishable from a sheet that does not exist (the Indochine series is
-- missing 20 numbers out of its own sequence, and until they were counted by
-- hand nothing in the system knew). A scan that is known to exist somewhere
-- but has never been fetched has nowhere to be recorded (50 L7014 sheets sit
-- at Texas Tech, identified, unfetched, and that fact lived in a JSON file in
-- `work/`). And a sheet whose number is simply wrong looks like two different
-- gaps -- Dong Van was filed as 42 alongside Hung Yen, which made 41 read as
-- missing and 42 as duplicated, when the lattice says plainly that the sheets
-- run west to east and 43, 44, 45 follow along the same row.
--
-- So: one row per sheet the *survey* contains, whether or not we hold it.
--
-- Status is deliberately NOT a column, because every value of it is a lie
-- waiting to go stale. It is derivable and should be derived:
--
--     held_by is not null                     -> held and served
--     held_by is null and source is not null  -> obtainable, not yet fetched
--     held_by is null and source is null      -> no known scan anywhere
--
-- `held_by` exists rather than deriving from `map_id` because a survey is not
-- served only one way. 452 of L7014's cells are pixels in a pre-tiled raster
-- archive and have no `maps` row at all; 9 are `maps` rows warped live. Both
-- are held. Keyed off `map_id` alone the mosaic's 452 would read as gaps,
-- which is the same error this table exists to stop, one level down.
--
-- `series_key` is migration 082's function over `maps.collection`, so a survey
-- keeps one identity whether its sheets are `maps` rows warped live, cells in
-- a pre-tiled raster mosaic, or not held at all. That is what lets the L7014
-- city sheets and the L7014 mosaic be one survey of 627 sheets rather than two
-- unrelated things that happen to share a name -- which they already are on the
-- ground, and were not anywhere in the database.

create table public.series_sheets (
  series_key   text not null,
  sheet_number text not null,
  -- The sheet's own name as the series prints it, which is not always the
  -- name of the `maps` row: a row may be named from a different edition.
  name         text,
  -- The cell the series assigns this sheet, from the survey's own index --
  -- NOT from any scan's georeference. This is what makes a gap locatable on
  -- a map before anything has been scanned. [minLon, minLat, maxLon, maxLat].
  bbox         float8[],
  -- Where a scan can be got, and its identifier there. Null source means no
  -- known scan anywhere, which is a research task, not a processing one.
  source       text,
  source_ref   text,
  -- How this sheet reaches a reader, if it does: 'map' (see map_id below) or
  -- a raster layer key such as 'raster:l7014'. Null means we do not serve it.
  held_by      text,
  -- The row we hold for this sheet, when held_by = 'map'. `on delete set null`
  -- so retiring a bad map leaves the sheet recorded as a gap rather than
  -- vanishing the fact that the survey contains it.
  map_id       uuid references public.maps(id) on delete set null,
  note         text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  primary key (series_key, sheet_number)
);

comment on table public.series_sheets is
  'One row per sheet a survey contains, held or not. The denominator `maps` cannot provide. Status is derived from held_by and source, never stored.';

create index series_sheets_map_id_idx on public.series_sheets (map_id);
create index series_sheets_unheld_idx on public.series_sheets (series_key) where held_by is null;

-- A map_id that is not marked held is a row that would not be counted, which
-- is the bug this table exists to prevent. The converse is deliberately NOT
-- asserted: `on delete set null` above must be allowed to fire, and an
-- equality check would block the delete instead.
--
-- ponytail: leaves one stale state reachable -- held_by = 'map' with a null
-- map_id, after the map it pointed at was deleted. It reads as "held, served
-- by nothing", which is visible in one query
-- (`where held_by = 'map' and map_id is null`) and is the correct thing to
-- look at after retiring a sheet anyway. Add a trigger only if that query
-- starts coming back non-empty for reasons nobody remembers.
alter table public.series_sheets add constraint series_sheets_held_by_map
  check (map_id is null or held_by = 'map');

alter table public.series_sheets enable row level security;

-- Readable by everyone: a gap in a survey is catalogue information, and saying
-- "we hold 9 of 24" in public is more honest than saying "9".
create policy series_sheets_read on public.series_sheets
  for select using (true);

grant select on public.series_sheets to anon, authenticated, service_role;
