-- Migration 104 — a sheet's series is a column, not a function of its display string
--
-- `series_key(m.collection)` (082) was called in three views and every one of the
-- catalogue's series filters matched the raw `collection` string, so the display
-- text *was* the identity: two spellings of one survey were two series, and an
-- edit to the label re-filed the sheet. This gives the key its own name.
--
-- `maps.series_key` is generated from `collection`, so nothing can write it and
-- nothing can drift from it. That is deliberately the smallest step
-- (docs/knowledge-system-plan.md §5, `series-identity`): `collection` is still the
-- display string and still the only input. Making the key independent of the label
-- needs a `series` table, which should wait until scale, producer and edition need
-- columns of their own.
--
-- The second half is a data fix the first one exposed. 221 first-edition
-- (Indochine 1:100,000, serie 325) rows carry `extra_metadata.sheet_number`, but
-- only 33 had the typed column: 095 backfilled it once, and the Nakala ingest
-- script wrote only the JSON afterwards. `map_series` counts the column, so the
-- survey could not have appeared however many of its sheets were georeferenced.
-- The ingest script now writes the columns itself.

update public.maps
   set sheet_number = extra_metadata ->> 'sheet_number'
 where sheet_number is null
   and extra_metadata ->> 'sheet_number' is not null;

update public.maps
   set sheet_half = extra_metadata ->> 'sheet_half'
 where sheet_half is null
   and extra_metadata ->> 'sheet_half' in ('E', 'W', 'whole');

alter table public.maps
  add column if not exists series_key text
  generated always as (public.series_key(collection)) stored;

comment on column public.maps.series_key is
  'The survey this sheet belongs to: series_key(collection), generated. Null for a sheet in no survey (the city plans carry no collection). What series_cells.series_key and map_series.key are keyed on.';

-- Replaces 095's (collection, sheet_number): every lookup that needed it now
-- reads the key, and the plain `collection` index (026) still serves the filter.
drop index if exists public.idx_maps_collection_sheet_number;
create index if not exists idx_maps_series_key_sheet_number
  on public.maps (series_key, sheet_number);

-- Same body as 095's view and the same columns, reading the key instead of
-- recomputing it. One row per key where it used to be one per `collection`
-- string, which differ only when two spellings fold together.
create or replace view public.map_series
with (security_invoker = true) as
  with idx as (
    select
      series_key,
      count(*) as survey_sheets
      from public.series_cells
     group by series_key
  )
  select
    m.series_key                                                   as key,
    min(m.collection)                                              as collection,
    min(m.collection)                                              as name,
    count(distinct m.sheet_number)                                 as sheets,
    count(distinct m.sheet_number)
      filter (where m.status in ('public', 'featured'))            as published_sheets,
    i.survey_sheets                                                as survey_sheets,
    min(m.year)                                                    as first_year,
    max(m.year)                                                    as last_year,
    array[
      min(m.bbox[1]), min(m.bbox[2]), max(m.bbox[3]), max(m.bbox[4])
    ]::float8[]                                                    as bounds
    from public.maps m
    left join idx i on i.series_key = m.series_key
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and m.series_key is not null
     and m.is_georeferenced
     and m.bbox is not null
     and array_length(m.bbox, 1) = 4
     and m.sheet_number is not null
   group by m.series_key, i.survey_sheets
  having count(distinct m.sheet_number) > 1;

comment on view public.map_series is
  'One row per sheet series (maps.series_key) with georeferenced sheets: its bounds, year span, the number of distinct cells held as maps rows, and — from series_cells (083/095) — how many cells the survey contains. security_invoker, plus the explicit published-or-signed-in gate in the body.';
