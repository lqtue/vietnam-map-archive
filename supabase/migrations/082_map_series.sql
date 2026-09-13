-- Migration 082 — a sheet series is something the archive already knows
--
-- `/explore` can put a whole series on the map as one layer (the Cartomundi
-- Indochine 1:25,000, 56 sheets warped live under one opacity slider). Until
-- now the series itself was a constant in `map/constants.ts`: its name, its
-- bounds, its sheet count and the fact that it is not published yet were four
-- hand-maintained facts about rows the database already holds. Adding the next
-- series meant an edit, a build and a deploy, and the four facts drifted the
-- moment a sheet was added or published.
--
-- They are not facts about the code. `maps.collection` is what makes a series a
-- series; the bounds are the union of its sheets' `bbox`; the sheet count is a
-- count; and whether to offer it to an anonymous reader is whether any of its
-- sheets are published. All four are one `group by` away, so this is a view and
-- not a table — nothing to keep in sync, and a sheet added to a collection
-- joins its series with no migration and no deploy.
--
-- The gate is said out loud rather than left to `security_invoker`, which is
-- migration 081's lesson repeated: a caller on the service client bypasses RLS,
-- and this view is read by the browser client today but will be read by a route
-- tomorrow. `auth.uid()` is null for a service-key caller and set for a
-- signed-in browser one, which is the line migration 063 draws. The effect is
-- that a wholly-draft series — which is what Cartomundi is right now — has no
-- row at all for an anonymous reader, so the UI needs no `draft` flag of its
-- own: a series it cannot see is a series it is not offered.
--
-- Only georeferenced sheets with a bbox count. A sheet with no georeference
-- cannot be drawn and would widen the series' bounds to nothing, and a series'
-- `sheets` is a promise about what appears when the row is switched on.
--
-- A collection is not automatically a series. "Vietnam Map Archive" is the
-- archive's default bucket — 36 unrelated sheets, 1791 to 1968, at every scale
-- there is — and stacking those on one another is noise, not a survey. What
-- separates the two is already in the data: a survey's sheets are *numbered*
-- sheets of one map, so `extra_metadata->>'sheet_number'` is the test. On the
-- corpus it draws the line exactly where it belongs — 62 of 62 Cartomundi rows
-- and 15 of 15 L7014 rows carry one, and none of the 36 in the bucket do.
-- The consequence to know: a genuine series whose rows were ingested without
-- sheet numbers will not appear here, and the fix is to number the rows rather
-- than to loosen this — the number is what a reader needs to say which sheet
-- they are looking at anyway.

-- The series' stable short key, and the id the overlay stack carries. Derived
-- rather than stored so it cannot drift from the collection it names.
-- `f_unaccent` (migration 065) is the same wrapper `label_key` uses.
create or replace function public.series_key(p_collection text)
returns text
language sql immutable parallel safe
as $$
  select nullif(btrim(regexp_replace(
           lower(public.f_unaccent(p_collection)), '[^a-z0-9]+', '-', 'g'), '-'), '')
$$;

comment on function public.series_key(text) is
  'maps.collection -> the short stable key /explore uses to identify a sheet series.';

drop view if exists public.map_series;

create view public.map_series
with (security_invoker = true)
as
  select
    public.series_key(m.collection)                                as key,
    m.collection                                                   as collection,
    m.collection                                                   as name,
    count(*)                                                       as sheets,
    count(*) filter (where m.status in ('public', 'featured'))     as published_sheets,
    min(m.year)                                                    as first_year,
    max(m.year)                                                    as last_year,
    -- [minLon, minLat, maxLon, maxLat] — the union of the sheets' own boxes,
    -- which is what "zoom to this layer" means. Postgres arrays are 1-indexed.
    array[
      min(m.bbox[1]), min(m.bbox[2]), max(m.bbox[3]), max(m.bbox[4])
    ]::float8[]                                                    as bounds
    from public.maps m
   -- See the header: the gate is explicit because a service-client caller
   -- bypasses RLS, and a draft series must not be offered to a reader who
   -- would resolve it to an empty layer.
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and m.collection is not null
     and m.georef_done
     and m.bbox is not null
     and array_length(m.bbox, 1) = 4
     -- See the header: a numbered sheet is what makes a collection a survey
     -- rather than a bucket of unrelated maps.
     and m.extra_metadata->>'sheet_number' is not null
   group by m.collection
   -- One sheet is a map, not a series.
   --
   -- Worth knowing, because it falls out of this and the gate together rather
   -- than being decided anywhere: the count is of the rows *this reader* can
   -- see, so a survey with only one published sheet is not offered to an
   -- anonymous reader at all — switching it on would draw a single sheet and
   -- call it a series. It appears the moment a second sheet is published.
  having count(*) > 1;

comment on view public.map_series is
  'One row per sheet series (maps.collection) that has georeferenced sheets: its bounds, sheet count and year span. Read by /explore to offer a whole series as one layer. security_invoker, plus the explicit published-or-signed-in gate in the body.';

grant select on public.map_series to anon, authenticated, service_role;
