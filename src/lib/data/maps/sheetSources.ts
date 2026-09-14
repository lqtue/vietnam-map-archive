/**
 * sheetSources.ts — which printings of a cell exist, and where.
 *
 * `series_sheets` (083) is one row per cell and answers "does the archive hold
 * this". `sheet_sources` (087) is one row per known PRINTING of a cell at an
 * institution and answers the other half: what else was printed of this ground,
 * and who has it. L7014 cell 6330-4 is the case that forced it — the 1965
 * Vietnamese SÀI GÒN reprinted in Hanoi in 1978, at Texas Tech, and the 1984
 * DMA recompilation titled THÀNH PHỐ HỒ CHÍ MINH, at Perry-Castañeda. One cell,
 * two maps, and a table keyed on the cell can say only one of them.
 *
 * Deliberately separate from `seriesSheets.ts`: these rows are not sheets of
 * the archive's index and must never be mistaken for them. A `sheet_sources`
 * row asserts that a printing EXISTS, not that the archive has it or could
 * serve it, and the moment the two are conflated a coverage percentage starts
 * counting other libraries' holdings as its own.
 */

import type { SupabaseClient } from '@supabase/supabase-js';
import { fetchSeriesSheetIndex, type SeriesSheetView } from './seriesSheets';

/**
 * One printing, as a reader would be shown it.
 *
 * `institution` is the display name rather than the short code the column
 * stores, because the code is a database join key and 'PCL' is not a library.
 */
export interface SheetPrinting {
  /**
   * Who holds this scan. Every row this module returns names one; `null` is
   * reserved for a printing the archive serves itself, which the series page
   * pushes into the same list. That is the signal a reader needs — it is what
   * separates "this is ours" from "Texas Tech has one too" inside a single
   * list — and a sentinel string would have to be excluded from the display
   * everywhere instead of being absent.
   */
  institution: string | null; // 'Perry-Castañeda' | 'Texas Tech' | 'ANU' | 'IGN'
  year: number | null;
  edition: string | null;
  part: 'whole' | 'W' | 'E' | 'assemblage' | null;
  url: string | null;
  rights: string | null;
  held: boolean; // true when the archive serves this printing
}

interface SheetSourceRow {
  series_key: string;
  sheet_number: string;
  institution: string;
  year: number | null;
  edition: string | null;
  part: SheetPrinting['part'];
  url: string | null;
  rights: string | null;
}

const COLUMNS = 'series_key,sheet_number,institution,year,edition,part,url,rights';

/**
 * The column's short code to the name of the library. 087 stores the code so
 * the two tables share one vocabulary in SQL; the name is a display concern and
 * lives here, once. An unknown code falls through unchanged rather than being
 * dropped — a new institution should appear in the UI looking unpolished, not
 * vanish from it.
 */
const INSTITUTION_NAME: Record<string, string> = {
  PCL: 'Perry-Castañeda',
  TTU: 'Texas Tech',
  ANU: 'ANU',
  IGN: 'IGN',
};

/**
 * `series_sheets.source` records where the archive found its own scan, and its
 * vocabulary is nearly but not quite 087's. The one real difference is
 * 'CartoMundi': that is the union catalogue the Indochine scans were discovered
 * through, while IGN is the library that holds the paper and serves it over
 * Nakala. Left unmapped, all 75 held Indochine cells would read as unheld next
 * to the very IGN record they were mirrored from.
 */
const ARCHIVE_SOURCE_INSTITUTION: Record<string, string> = {
  PCL: 'PCL',
  TTU: 'TTU',
  ANU: 'ANU',
  IGN: 'IGN',
  CartoMundi: 'IGN',
};

/**
 * Editions compare loosely because the corpus does not agree with itself about
 * leading zeros — `work/l7014/sheets.json` holds both "003" and "3" for cells of
 * one survey, and an earlier backfill wrote the integer form into 433 rows of
 * `series_sheets` (see `scripts/oneoff/fix_l7014_editions.mjs`). Comparing them
 * literally would call a held sheet unheld on a typographic difference. Only
 * leading zeros, case and surrounding space are folded: "3-DMA" and "3" stay
 * different, because the suffix names the issuing agency.
 */
function sameEdition(a: string, b: string): boolean {
  const fold = (s: string) =>
    s
      .trim()
      .toLowerCase()
      .replace(/^0+(?=\d)/, '');
  return fold(a) === fold(b);
}

/**
 * Does the archive serve THIS printing?
 *
 * Derived, never stored — 083 refused a status column for the reason that
 * applies again here. The test is three-part, and each part is the weakest
 * claim that is still true:
 *
 *   1. the cell is held at all (`held_by` set, which covers both a warped
 *      `maps` row and a cell of the pre-tiled mosaic);
 *   2. this row's institution is the one the archive got its copy from; and
 *   3. the recorded printing does not CONTRADICT this row's.
 *
 * Step 3 is deliberately "does not contradict" rather than "matches". The
 * archive records a year for 446 of its 627 L7014 cells and for 59 of its 75
 * held Indochine cells; requiring a match would mark every unrecorded cell
 * unheld, which turns missing metadata into a claim about the collection.
 *
 * The residue is the opposite error, and it was measured rather than assumed
 * (2026-09-14, over the 1,023 printings the first load carries). 462 of the 535
 * Perry-Castañeda printings read held against 461 cells the archive actually
 * serves: the one extra is 6542-3, which PCL has twice — a GeoPDF and a JPEG
 * with no year and no edition, so nothing contradicts. On the Indochine side
 * 176 IGN printings read held over 74 cells, and most of that is correct rather
 * than residue: serie 243 issued a west and an east half of one printing, both
 * of which the archive holds as separate `maps` rows under one sheet number.
 * The genuinely ambiguous part is 33 rows in 12 groups that share a cell AND a
 * part, all of them cells where no year is recorded on the `series_sheets` row.
 *
 * Both are fixed by recording the printing on the `series_sheets` row, which is
 * the right place for it. The 75th held Indochine cell reads as no printing
 * held at all — the year the archive recorded for it matches no IGN record, and
 * that is a disagreement worth seeing rather than a rule to loosen.
 */
function isHeld(cell: SeriesSheetView | undefined, row: SheetSourceRow): boolean {
  if (!cell?.held_by) return false;
  if (ARCHIVE_SOURCE_INSTITUTION[cell.source ?? ''] !== row.institution) return false;
  if (cell.year != null && row.year != null && cell.year !== row.year) return false;
  if (cell.edition && row.edition && !sameEdition(cell.edition, row.edition)) return false;
  return true;
}

/**
 * Every known printing of every cell of one survey, keyed by sheet number.
 *
 * Paged explicitly: PostgREST caps an unbounded select at 1000 rows and says
 * nothing about it, and this table starts at 1,023 rows over two surveys — so
 * the very first load would have been truncated, and the truncation would have
 * looked like the Indochine survey simply having fewer printings.
 *
 * `sheet_sources` is not in the generated `Database` type (it is newer than the
 * last `supabase gen types` run), so `db` is a bare `SupabaseClient` and the
 * rows are cast once, here, to `SheetSourceRow` — the same shape
 * `seriesSheets.ts` uses. One cast at the boundary rather than `as any` at
 * every field; regenerate the types and the cast is the only line to delete.
 */
export async function fetchSheetSources(
  db: SupabaseClient,
  seriesKey: string
): Promise<Record<string, SheetPrinting[]>> {
  const page = 1000;
  const rows: SheetSourceRow[] = [];
  for (let from = 0; ; from += page) {
    const { data, error } = await db
      .from('sheet_sources')
      .select(COLUMNS)
      .eq('series_key', seriesKey)
      .range(from, from + page - 1);
    if (error) throw error;
    rows.push(...((data ?? []) as SheetSourceRow[]));
    if (!data || data.length < page) break;
  }

  /* The archive's own index, for `held`. Read through `fetchSeriesSheetIndex`
     rather than re-selecting the columns, so the paging and the shape of a
     sheet stay spelled once — a second copy of either drifts silently and the
     number it produces looks right both before and after. */
  const cells = new Map<string, SeriesSheetView>();
  for (const c of await fetchSeriesSheetIndex(db, seriesKey)) cells.set(c.sheet_number, c);

  const out: Record<string, SheetPrinting[]> = {};
  for (const r of rows) {
    (out[r.sheet_number] ??= []).push({
      institution: INSTITUTION_NAME[r.institution] ?? r.institution,
      year: r.year ?? null,
      edition: r.edition ?? null,
      part: r.part ?? null,
      url: r.url ?? null,
      rights: r.rights ?? null,
      held: isHeld(cells.get(r.sheet_number), r),
    });
  }

  /* Oldest printing first, because that is the order a reader asks about a
     survey in; an unrecorded year sorts last rather than as year zero, and the
     institution breaks the tie so the list is stable across reloads. */
  for (const list of Object.values(out)) {
    // 9999 rather than Infinity: two unrecorded years would subtract to NaN,
    // and a NaN comparator does not sort, it shuffles.
    list.sort(
      // `institution` is null only on a printing the archive serves, which
      // this module never emits — but the page merges its own into these lists
      // and then sorts again, so the tiebreak has to survive one.
      (a, b) =>
        (a.year ?? 9999) - (b.year ?? 9999) ||
        (a.institution ?? '').localeCompare(b.institution ?? '')
    );
  }
  return out;
}
