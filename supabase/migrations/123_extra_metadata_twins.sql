-- Migration 123 — `extra_metadata` stops carrying copies of typed columns
--
-- `maps.sheet_number`, `maps.sheet_half` and `maps.edition` are columns (095, 104, 110). Each
-- migration backfilled the column from the JSON key and left the key behind ("a later cleanup
-- migration strips the JSON keys once nothing reads them", 095). This is that cleanup. One fact,
-- one writer: the column. Docs: docs/plans/model-dedup-plan.md, step 1.
--
-- Measured on production, 2026-10-16 (read-only, GET): 1,562 maps rows. The key is present on
-- 1,462 rows (`sheet_number`), 725 (`sheet_half`) and 529 (`edition`; 6 of those hold an empty
-- string, 523 hold a value). On every one the trimmed JSON text equals the trimmed column, so this
-- migration strips 1,462 + 725 + 529 keys from 1,463 rows and skips none. A row whose key disagrees
-- with its column keeps the key (nothing is lost, a person looks); the expected count of those is 0,
-- and the `raise notice` at the end reports the real number when this runs.
--
-- What is left alone:
--   * `series` (693 rows, "L7014" / "L909") has no column twin. `series.code` is null for all six
--     series, so there is nothing to compare it with. Nothing in src/, scripts/, work/ or worker/
--     reads it (the one-off scripts that did are frozen). It stays.
--   * Every other key (`source_archive`, `part_of`, `mirrors_original_for`, `scan_provenance`, ...).
--
-- Readers: none left. src/ reads the columns (checked: `fetchSheetEditions`, `fetchSeriesSheets`, the
-- series page, the edit form). In SQL the last readers were 046's `search_vector` (rebuilt on the
-- column in 095) and the 082/084 `map_series` view (same, 095); 104 and 110 only read the keys to
-- backfill. Nothing needs redefining, and no definer function, RLS policy or grant changes.
--
-- Deploy order: **app first, then this push.** The app must stop reading the keys before they go.
-- (It already does; the one write path that kept them, the edit form's custom-field list, has
-- filtered them since 110, and the bulk upload script strips them on insert.)
-- Pushing first would also be safe today for the same reason, but the order is the rule.
--
-- `maps.updated_at` is not moved: the sitemap's `lastmod` reads it, and a tidy-up that touched 1,463
-- sheets would tell every crawler they had changed. The `maps_updated_at` trigger is switched off for
-- this one statement and back on after, inside this migration's transaction.
--
-- Two other row triggers fire on this update and do nothing here. `maps_assign_slug` acts only on
-- an empty or changed slug. `maps_normalize_taxonomy` (116) resets a human classification review
-- whenever its own normalising (subjects sorted and de-duplicated, `plan` -> `city_plan`) changes
-- a row, so a no-op update on an un-normalised row would wipe that review. Checked on production
-- 2026-10-18 (read-only): of the 1,463 rows this touches, 0 differ from their normalised form and
-- 0 carry a classification review.

alter table public.maps disable trigger maps_updated_at;

with twins as (
  select id,
         array_remove(array[
           case when extra_metadata ? 'sheet_number' and nullif(btrim(extra_metadata ->> 'sheet_number'), '') is not distinct from nullif(btrim(sheet_number), '')
                then 'sheet_number' end,
           case when extra_metadata ? 'sheet_half' and nullif(btrim(extra_metadata ->> 'sheet_half'), '')   is not distinct from nullif(btrim(sheet_half), '')
                then 'sheet_half' end,
           case when extra_metadata ? 'edition' and nullif(btrim(extra_metadata ->> 'edition'), '')      is not distinct from nullif(btrim(edition), '')
                then 'edition' end
         ], null) as dead
    from public.maps
   where extra_metadata ?| array['sheet_number', 'sheet_half', 'edition']
)
update public.maps m
   set extra_metadata = m.extra_metadata - t.dead
  from twins t
 where m.id = t.id
   and t.dead <> '{}'::text[];
-- (`dead` holds a key only where the key is present AND its trimmed text equals the trimmed column;
-- null and '' count as the same "nothing", so an empty twin of an empty column goes too.)

alter table public.maps enable trigger maps_updated_at;

do $$
declare v_left integer;
begin
  select count(*) into v_left
    from public.maps
   where extra_metadata ?| array['sheet_number', 'sheet_half', 'edition'];
  raise notice 'migration 123: % maps row(s) still carry a twin key because it disagrees with its column (expected 0)', v_left;
end $$;
