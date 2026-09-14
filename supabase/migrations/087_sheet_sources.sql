-- Migration 087 — which printings of a cell exist, and where
--
-- `series_sheets` (083) is keyed `(series_key, sheet_number)`: ONE ROW PER
-- CELL. That is the right shape for the question it was built to answer --
-- "does the archive hold this cell, and how does it reach a reader" -- and it
-- structurally cannot answer the one the archive keeps walking into: which
-- printings of this cell exist, and who has them.
--
-- The cost is not theoretical. Three worked examples, all on the corpus today:
--
--   * L7014 cell 6330-4 is two different maps. Texas Tech holds the 1965
--     Vietnamese SÀI GÒN, "xuất bản lần thứ 3, vẽ và in lại 1978" at Cục Đo đạc
--     và Bản đồ Nhà nước in Hanoi. Perry-Castañeda holds the 1984 DMA
--     recompilation, titled THÀNH PHỐ HỒ CHÍ MINH. Same cell, same lattice,
--     nineteen years and one renaming apart. `series_sheets` has one row, one
--     `year`, one `edition` (086) and one `source`, so recording either erases
--     the other.
--
--   * Indochine cell 39 is three sheets of paper. IGN's own catalogue carries
--     an 1904 eastern half-sheet ("[Dô-] Son"), a 1923 western half-sheet
--     ("Dô- [Son]"), and a 1939 assembly of the two ("Dô-Son", a partial update
--     of the 1932 edition from aerial photographs flown in 1937). One cell,
--     three physical objects, three dates -- and the western half is a printing
--     the archive's row for cell 39 cannot mention at all.
--
--   * Measured 2026-09-14. `series_sheets` holds 706 cells (627 L7014, 79
--     Indochine). The four institutional catalogues sitting in `work/` describe
--     1,023 printings over 613 of those cells: 719 printings over 534 L7014
--     cells, of which 180 have more than one; 304 printings over 79 Indochine
--     cells, of which 78 have more than one and one has six. A table with one
--     row per cell throws away two fifths of what is already known, silently,
--     at import time, and leaves no trace that it did.
--
-- Until now that knowledge lived in untracked JSON and a hand-written markdown
-- table on one laptop (`work/l7014/anu-sources.json`, `work/l7014/sheets.json`,
-- `work/l7014/ttu/EDITIONS.md`, `work/tonkin/sources/ign-serie-*.json`). A
-- laptop is not a catalogue.
--
-- So: one row per KNOWN PRINTING of a cell at an institution. This records what
-- exists in the world, whether or not the archive holds it. `series_sheets`
-- stays the archive's own answer and is not touched.
--
-- WHAT IS DELIBERATELY NOT HERE
--
-- No `held` column. 083 refused to store status for the reason that applies
-- again here -- every stored value of it is a lie waiting to go stale -- and
-- "does the archive serve THIS printing" is derived by comparing this row's
-- institution and printing against the cell's `series_sheets` row. The rule
-- lives once, in `src/lib/data/maps/sheetSources.ts`, next to the reader.
--
-- No foreign key to `series_sheets`, and none to `maps`. Same reasoning as 083
-- and 086: this family of tables is the survey's index, and it has to answer at
-- the same resolution for a cell the archive holds as a `maps` row, a cell it
-- holds as pixels in a pre-tiled mosaic with no row at all, and a cell nobody
-- has ever fetched. A printing at ANU of a cell whose number this archive has
-- not yet added to its index is exactly the discovery this table exists to
-- capture; an FK would reject it, which converts new knowledge into an import
-- error. 083 already keeps `held_by` unconstrained for the mirror-image reason.
-- `series_key` likewise is migration 082's `series_key()` over
-- `maps.collection`, a function and not a table, so there is nothing to point
-- at.
--
-- No numeric edition. 086 settled this and the reasoning is unchanged: "003",
-- "3-DMA" and "2-AMS" are all real values off the one survey, and the suffix
-- names the issuing agency -- which is the half that says whether two printings
-- came from the same office. The four catalogues loaded here widen the case
-- rather than narrow it: IGN states an edition as a French sentence ("Edition
-- d'août 1904", "Mise à jour partielle de l'Edition de 1932"), ANU states it as
-- a printing note ("2nd printing 9-67"), and the SRV redraws state it in
-- Vietnamese ("xuất bản lần thứ 3, vẽ và in lại 1978"). Text, verbatim, as
-- printed.
--
-- `part` exists because the Indochine 1:25,000 issued most cells as a west and
-- an east half, each with its own frame and its own printed corner figures, and
-- later assembled them. Measured over the 304 IGN copy records: 104 west
-- halves, 100 east halves, 79 assemblies, 21 half-format sheets that carry the
-- whole of the cell the series covers. Without this column the 1904 east half
-- and the 1923 west half of cell 39 are two rows that differ only by a year,
-- which reads as two printings of the same paper rather than two halves of one.

create table if not exists public.sheet_sources (
  id           uuid primary key default gen_random_uuid(),
  -- migration 082's `series_key()` over `maps.collection`, the same identity
  -- `series_sheets` files a cell under. Not an FK; see the header.
  series_key   text not null,
  sheet_number text not null,
  -- Short code, matching `series_sheets.source`'s vocabulary on purpose --
  -- 'PCL', 'TTU', 'ANU', 'IGN' -- so the two tables can be compared without a
  -- translation table in SQL. The reader owns the display name.
  institution  text not null,
  -- The institution's own identifier for this item: ANU's DSpace uuid, IGN's
  -- copy `dpKey`, PCL's file name, TTU's sheet PDF. NOT NULL because it is the
  -- deduplication key below, and a table of printings that cannot deduplicate
  -- doubles in size every time the loader runs -- which is the failure mode
  -- that looks like a growing collection rather than like a bug.
  source_ref   text not null,
  -- The title as this printing prints it, which is the point rather than a
  -- decoration: TTU's 6150-3 is KIM BÔI and PCL's is "Thuy Hien", and 6330-4 is
  -- SÀI GÒN at one institution and THÀNH PHỐ HỒ CHÍ MINH at the other. A name
  -- belongs to an edition, not to a cell.
  title        text,
  -- Year printed on this sheet. smallint and not a date, for 086's reason: a
  -- sheet is stamped with a year and the month it was printed is not on the
  -- paper. Null where the catalogue records none -- 98 of the 535 PCL items,
  -- and 21 of the 25 TTU sheets, whose collars give a revision history instead.
  year         smallint,
  edition      text,
  part         text check (part in ('whole', 'W', 'E', 'assemblage')),
  -- Item-level, so a reader can go and look at the thing. Null where the
  -- catalogue has a record but no digitised copy -- 92 of the 304 IGN copies.
  url          text,
  -- Verbatim, and only where the institution states one. ANU is the only one of
  -- the four that does — 156 of its 160 items carry some casing of "Copyright
  -- Expired", three carry "Copyright expires 50 yrs after date of Publication",
  -- one carries nothing. IGN's dump carries a `tr38Licence` field on every
  -- one of the 304 copy records and it is null on all 304; PCL and TTU state
  -- nothing item-level at all. Null therefore means "not stated", never
  -- "in copyright" -- do not render it as a restriction.
  rights       text,
  note         text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  -- One row per item held by one institution. Keyed on the item and NOT on
  -- (series_key, sheet_number, institution): a cell number corrected later --
  -- and 083's header records one, Dong Van filed as 42 -- must MOVE the
  -- existing row rather than leave a duplicate behind under the old number.
  constraint sheet_sources_item unique (institution, source_ref)
);

comment on table public.sheet_sources is
  'One row per known printing of a cell at an institution. What exists in the world, held or not; series_sheets (083) stays the archive''s own answer. Whether the archive serves a given printing is derived, never stored.';

comment on column public.sheet_sources.institution is
  'Short code sharing series_sheets.source''s vocabulary: PCL, TTU, ANU, IGN. Display names live in src/lib/data/maps/sheetSources.ts.';
comment on column public.sheet_sources.edition is
  'Edition as this printing states it, verbatim. Text, not a number — "2-AMS", "Edition d''août 1904", "2nd printing 9-67", "xuất bản lần thứ 3, vẽ và in lại 1978" are all real values.';
comment on column public.sheet_sources.part is
  'Which part of the cell this sheet of paper is: whole | W | E | assemblage. The Indochine 1:25,000 issued most cells as two halves and assembled them later.';
comment on column public.sheet_sources.rights is
  'Rights statement as the institution gives it. Null means not stated, not restricted.';

-- The read: every printing of every cell of one survey, grouped by cell
-- (`fetchSheetSources`). `series_key` alone would serve it; the second column
-- keeps the grouping ordered without a sort and answers the single-cell lookup
-- the sheet drawer makes.
create index if not exists sheet_sources_cell_idx
  on public.sheet_sources (series_key, sheet_number);

-- No separate index on `institution`: "what does ANU hold" is a prefix scan of
-- the unique constraint's own index above, which is (institution, source_ref).

create or replace function public.sheet_sources_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger sheet_sources_updated_at
  before update on public.sheet_sources
  for each row execute function public.sheet_sources_set_updated_at();

alter table public.sheet_sources enable row level security;

-- Readable by everyone, for 083's reason one level down: a printing that exists
-- at another institution is catalogue information. Saying "we hold the 1984
-- recompilation; Texas Tech has the 1978 Hanoi reprint" in public is the whole
-- value of the table, and hiding it would leave the reader with the same
-- half-answer this migration exists to end.
drop policy if exists sheet_sources_read on public.sheet_sources;
create policy sheet_sources_read on public.sheet_sources
  for select using (true);

grant select on public.sheet_sources to anon, authenticated, service_role;
