-- Migration 084 — a series counts sheets, not rows, and knows its denominator
--
-- Two things `map_series` (082) got wrong, both visible on the corpus today.
--
-- 1. It counted ROWS. A sheet is a cell of the survey and a row is one
--    printing of it, which is the distinction `fetchSheetEditions` is built on
--    and migration 012's dropped `UNIQUE (series, sheet_number)` was dropped
--    for. The Indochine 1:25,000 holds three cells twice — sheets 2, 13 and 14,
--    two editions each (Vinh Yen 1906 and 1919, Hoai Duc Phu 1911 and 1925,
--    Phu Tu Son 1911 and 1925) — so /explore offered "56 sheets" over 53 cells.
--    The same arithmetic also let two editions of ONE cell qualify as a series,
--    which is a map printed twice, not a survey.
--
-- 2. It had no denominator. `maps` only contains successes, so "9 sheets" was
--    the whole truth the view could tell about a survey of 627 — which is the
--    absence migration 083 exists to fill, and nothing has read `series_sheets`
--    since. `survey_sheets` is what the survey contains. It is null for a
--    survey whose index has never been imported, which reads honestly as "not
--    counted" rather than as zero.
--
-- What is deliberately NOT exposed is the other count `series_sheets` can give:
-- how many cells reach a reader by ANY route (461 of L7014's 627 — 452 as
-- pixels in the mosaic, 9 as warped `maps` rows). The one caller is a row in
-- /explore that a reader switches on, and that row must say what it draws.
-- Labelling the warped-sheets layer 461 would promise the mosaic's 452 from a
-- control that cannot draw them. Add it when something asks "what does the
-- archive hold", which is a different question from "what will this draw".
--
-- What this does NOT fix, so the next reader does not find it here as a bug in
-- the view: the three AMS L909 city maps (Hà Nội, Huế, Sài Gòn) are not a
-- series and never have been. None of the three carries a `sheet_number`, and
-- Sài Gòn is filed under `Vietnam Map Archive` rather than with the other two,
-- so 082's gate has always excluded them and /explore has never offered L909.
-- That is three `maps` rows to correct, not a view to loosen — the gate is
-- right, the rows are wrong.
--
-- `series_sheets` carries no visibility gate of its own (083: a gap in a survey
-- is catalogue information). That is safe here because the join only ever
-- widens a row that already passed the gate below: a survey with nothing
-- published still has no row at all for an anonymous reader.

drop view if exists public.map_series;

create view public.map_series
with (security_invoker = true)
as
  with idx as (
    select
      series_key,
      count(*) as survey_sheets
      from public.series_sheets
     group by series_key
  )
  select
    public.series_key(m.collection)                                as key,
    m.collection                                                   as collection,
    m.collection                                                   as name,
    -- Cells, not printings. See the header.
    count(distinct m.extra_metadata->>'sheet_number')              as sheets,
    count(distinct m.extra_metadata->>'sheet_number')
      filter (where m.status in ('public', 'featured'))            as published_sheets,
    -- What the survey contains, from its own index (mig 083). Null where no
    -- index was imported.
    i.survey_sheets                                                as survey_sheets,
    min(m.year)                                                    as first_year,
    max(m.year)                                                    as last_year,
    -- [minLon, minLat, maxLon, maxLat] — the union of the sheets' own boxes,
    -- which is what "zoom to this layer" means. Postgres arrays are 1-indexed.
    array[
      min(m.bbox[1]), min(m.bbox[2]), max(m.bbox[3]), max(m.bbox[4])
    ]::float8[]                                                    as bounds
    from public.maps m
    left join idx i on i.series_key = public.series_key(m.collection)
   -- The gate is explicit because a service-client caller bypasses RLS, and a
   -- draft series must not be offered to a reader who would resolve it to an
   -- empty layer.
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and m.collection is not null
     and m.georef_done
     and m.bbox is not null
     and array_length(m.bbox, 1) = 4
     -- A numbered sheet is what makes a collection a survey rather than a
     -- bucket of unrelated maps.
     and m.extra_metadata->>'sheet_number' is not null
   group by m.collection, i.survey_sheets
   -- One cell is a map, not a series — including one cell held twice.
  having count(distinct m.extra_metadata->>'sheet_number') > 1;

comment on view public.map_series is
  'One row per sheet series (maps.collection) with georeferenced sheets: its bounds, year span, the number of distinct cells held as maps rows, and — from series_sheets (083) — how many cells the survey contains. security_invoker, plus the explicit published-or-signed-in gate in the body.';

grant select on public.map_series to anon, authenticated, service_role;
