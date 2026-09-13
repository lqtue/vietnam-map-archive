-- Migration 086 — which printing of a sheet the archive holds
--
-- A sheet is a cell of a survey; an edition is one printing of that cell, and
-- the two are not the same fact. L7014's 627 cells were printed and reprinted
-- from 1963 to 1989 — the same ground, resurveyed, with roads, hamlets and
-- spellings that moved between printings — so "we hold 6329-1" is only half an
-- answer. Which one? 083 could not say: it recorded that a sheet is held and
-- how it reaches a reader, and stopped there.
--
-- The answer existed in two places, neither of them reachable from the page
-- that needs it. For the 9 cells held as `maps` rows it is `year` plus
-- `extra_metadata->>'edition'` on the row. For the 452 held as cells of the
-- pre-tiled mosaic there is no row at all: the GeoPDF's own XMP carries the
-- edition and date, `scripts/l7014_mosaic.py` reads it while warping, and it
-- was last seen in `work/l7014/sheets.json` — a file on one laptop. So the
-- coverage page could tell a reader that 461 of 627 sheets are held and not
-- which printing any of them is, which for a survey spanning 26 years is the
-- difference between a citation and a guess.
--
-- Two nullable columns, describing **the printing this row refers to**:
-- for a held sheet, the one served; for an obtainable one, the one the source
-- has catalogued, when that is known. Null means nobody has recorded it, which
-- is honest and common — 62 of the L7014 GeoPDFs carry no edition in their XMP.
--
-- `year` is smallint and not a date: a sheet is stamped with a year, and the
-- month it was printed is not on the paper. `edition` is text because the
-- series does not agree with itself about what an edition looks like — "003",
-- "3-DMA" and "2-AMS" are all real values off the same survey, and coercing
-- them to a number would lose the issuing agency, which is the half that says
-- whether two printings came from the same office.
--
-- Deliberately not a foreign key to anything, and deliberately duplicated from
-- `maps` for the rows that have one: this table is the survey's index, and it
-- has to answer at the same resolution for a cell that is a `maps` row and one
-- that is pixels in a mosaic. Keyed off `maps` alone the 452 would be blank,
-- which is migration 083's whole lesson repeated one column down.

alter table public.series_sheets
  add column if not exists year smallint,
  add column if not exists edition text;

comment on column public.series_sheets.year is
  'Year printed on the sheet of the printing this row refers to. Null when unrecorded.';
comment on column public.series_sheets.edition is
  'Edition as the series prints it — "003", "3-DMA", "2-AMS". Text, not a number: the suffix names the issuing agency.';
