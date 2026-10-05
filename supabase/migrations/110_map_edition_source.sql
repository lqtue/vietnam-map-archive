-- `edition` was read like a column and lived in `extra_metadata`: now it is one.
--
-- `maps.edition` (450 public rows: "1", "2-AMS", "3-DMA", "Édition de Janvier 1926") is backfilled from
-- the JSON key. `source_archive` stays a JSON tag: the L7014 scripts use it ('PCL' | 'TTU') to tell two
-- scans of one cell apart. But on the 510 PCL rows it was the only place that said who holds the sheet,
-- and those rows had no `holding_institution`, so the Institution facet skipped half the archive. It is
-- copied there under the name 12 other rows already use.
--
-- Additive: the JSON keys stay. The edit form drops `sheet_number`, `sheet_half` and `edition` from a
-- row's custom fields on its next save.
alter table public.maps add column if not exists edition text;
comment on column public.maps.edition is 'The edition as printed on the sheet: "5-DMA", "2-AMS (29 ETB)", "3". Null when the sheet states none (Indochine sheets are told apart by year).';

update public.maps
   set edition = nullif(btrim(extra_metadata ->> 'edition'), '')
 where edition is null
   and nullif(btrim(extra_metadata ->> 'edition'), '') is not null;

update public.maps
   set holding_institution = 'Perry-Castañeda Library Map Collection, University of Texas at Austin'
 where holding_institution is null
   and extra_metadata ->> 'source_archive' = 'PCL';
