-- Migration 124 — an edition is "3", not "003"
--
-- `docs/plans/model-dedup-plan.md`, step 2. The same L7014 sheet carried its edition in two
-- spellings: `maps.edition` says "1" and `series_cells.edition` says "001". The scans' own XMP
-- (read by `scripts/l7014/l7014_mosaic.py`) pads the number to three digits; the ingest script
-- (`l7014_ingest_list.py`, `lstrip("0")`) and migration 110's backfill did not, so the two copies
-- of one fact disagreed on every sheet that has both. Any check that compares a sheet with its cell
-- reports them as different editions when they are the same one.
--
-- The house form is the unpadded number. 086 keeps the issuing agency in the value ("3-DMA" is not
-- a number), so the rule touches only leading zeros of the leading digit run and nothing else:
--
--     regexp_replace(edition, '^0+(?=[0-9])', '')
--
--     "001" -> "1"     "003-DMA" -> "3-DMA"     "000" -> "0"
--     "3-DMA", "2-AMS (29 ETB)", "1st printing 12-66", "Edition de mai 1904"   unchanged
--
-- Measured on production 2026-10-16 (read-only, REST, before this migration):
--
--     series_cells    1,151 rows   "001" 202, "002" 170, "003" 53, "004" 6, "005" 1, "006" 1
--                                  = 433 padded; 12 others ("1","2","3","3-DMA",...) and 706 null
--     cell_printings  1,670 rows   "001" 212, "002" 176, "003" 59, "004" 6, "005" 2, "006" 1
--                                  = 456 padded; the other 1,214 are agency forms, French edition
--                                  sentences, printing notes or null, none of which start with 0
--     maps            1,562 rows   0 padded (21 distinct values, none start with 0). Not touched:
--                                  the table already holds the house form, so there is nothing to
--                                  update and the maps triggers are not fired for nothing.
--
-- No unique key includes `edition` (cell_printings is unique on (institution, source_ref)), so the
-- rewrite cannot collide.
--
-- Effect on the 1,525 maps that point at a cell (same series_id and sheet_number), edition set on both:
--
--     disagree before:   438   = 432 only zero padding + 6 real
--     disagree after:      6   padding-only 432 -> 0; real 6 -> 6, untouched
--
-- The real ones are different printings or an agency suffix on one side only, and a person settles
-- them (a `metadata-conflict` review item); this migration does not guess. They are 6641-3 ("2" vs
-- "4-DMA"), 6150-1 ("3-DMA" vs "003", which becomes "3"), 6329-1 ("2-AMS (29 ETB)" vs "3-DMA"),
-- 6530-3 ("2" vs "3"), 6330-4 ("3" vs "5-DMA") and 6731-1 ("1" vs "2"). The plan counted 431 + 7;
-- the read that fed this header, with the same pairing rule, finds 432 + 6.
--
-- Idempotent: a second run matches nothing. Re-derive the padding if the loader ever pads again —
-- `l7014_mosaic.py` now writes the unpadded form itself (`edition_label`).
--
-- Deploy order: none. No reader depends on the padding. The series page sorts its "version" column by
-- year, not by the edition string (its comment names "003" sorting before "1-AMS" as the reason), and
-- nothing in `src/` compares two editions with `===` or parses one as a number. The only place the old
-- form was visible is the series page's "Editions" note, edited in the same commit.

update public.series_cells
   set edition = regexp_replace(edition, '^0+(?=[0-9])', '')
 where edition ~ '^0+[0-9]';

update public.cell_printings
   set edition = regexp_replace(edition, '^0+(?=[0-9])', '')
 where edition ~ '^0+[0-9]';
