/**
 * /catalog/series/<key> — one survey, every sheet it contains.
 *
 * The list `maps` could never produce. A survey's sheets reach a reader by more
 * than one route: 9 of the L7014 1:50,000's held sheets are `maps` rows warped
 * live, and 452 are cells of a pre-tiled raster mosaic with no `maps` row at
 * all. Before this page the second group was drawable on the map and invisible
 * everywhere else.
 *
 * Server-rendered, like the share and place pages, so the coverage of a survey
 * is readable without running JavaScript.
 *
 * The survey's identity and name come from `map_series` (migration 082/084),
 * which is gated to what this reader may see; the sheet list comes from
 * `series_sheets` (083), which carries no gate of its own because a gap in a
 * survey is catalogue information. Reading them together is safe in that
 * order — a survey with nothing published has no `map_series` row, so this
 * route 404s before it ever reaches the sheet list.
 */

import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesSheetIndex, tally } from '$lib/data/maps/seriesSheets';
import { SERIES_NOTES } from './notes';

/**
 * One printing of one cell.
 *
 * The field names are `SheetPrinting` in `$lib/data/maps/sheetSources.ts`,
 * which is being written alongside this page and will supply the printings the
 * archive does *not* hold (Perry-Castañeda, Texas Tech, ANU, IGN). Spelling the
 * shape the same way now means the merge below is a concatenation rather than a
 * translation layer. The one field of that shape this page does not carry is
 * `rights` — nothing here renders a licence, and it is ~45 bytes a row.
 */
interface SheetPrinting {
  /**
   * Who holds the scan — the fact that identifies a printing the archive does
   * not serve. Null on every held printing, deliberately: the row's Source
   * column already answers "where did this come from" (`series_sheets.source`,
   * "CartoMundi" for the Indochine sheets) and `maps.holding_institution`
   * answers a different question ("IGN", who licenses it). Printing both in one
   * row without the sentence that separates them reads as a contradiction, and
   * the record behind each link states it in full anyway.
   */
  institution: string | null;
  year: number | null;
  edition: string | null;
  /** Which piece of paper. See `sheetPart`. */
  part: 'whole' | 'W' | 'E' | 'assemblage';
  /** The record for this printing: an internal `/catalog/<id>` while `held`. */
  url: string | null;
  /** True when the archive serves this printing itself. */
  held: boolean;
}

/**
 * The half marker the Indochine ingest writes into the record's name —
 * "Phu Xuyen (W)", "Cua Day (E)". Anchored at the end because a sheet name may
 * legitimately contain brackets elsewhere.
 */
const HALF_IN_NAME = /\((W|E)\)\s*$/;

/**
 * Which piece of paper a record is.
 *
 * `extra_metadata.sheet_half` is the authority: `ingest_indochine_nakala.mjs`
 * derives it from the Cartomundi note ("Demi-feuille Ouest") and cross-checks it
 * against the brackets in the title before it will insert a row, so it is the
 * value that was actually verified. The name marker is the fallback, for a row
 * that reached `maps` by some other route — a hand edit in the catalogue
 * editor, or a survey cut the same way that nobody has written an ingest for.
 *
 * Absent both, the record covers the whole cell. That is not a guess: every
 * L7014 row is a whole sheet, and `sheet_half: 'whole'` is what the Indochine
 * ingest writes for a demi-format sheet, which is one piece of paper carrying
 * the entire cell.
 */
function sheetPart(half: unknown, name: string | null): 'whole' | 'W' | 'E' {
  if (half === 'W' || half === 'E') return half;
  if (half === 'whole') return 'whole';
  const marked = HALF_IN_NAME.exec(name ?? '');
  return marked ? (marked[1] as 'W' | 'E') : 'whole';
}

/**
 * How many *printings* a pile of records represents.
 *
 * Counting the records is what this page did until Sept 2026, and it is right
 * only for a survey whose cell is one sheet of paper. The Indochine 1:25,000
 * issued most of serie 243 as a **west and an east half-sheet**: two records,
 * two scans, one map. Nine of its cells hold two records and the badge called
 * all nine "2 editions" — six of them falsely, because cells 34, 37, 39, 67, 70
 * and "73 bis" are half-sheet pairs and only 2, 13 and 14 are genuinely two
 * printings (Vinh Yen 1906/1919, Hoai Duc Phu and Phu Tu Son 1911/1925).
 *
 * So: the two opposite halves of a cell are one printing, and a printing is
 * counted once for every time the *same* piece of paper appears. A cell held as
 * a whole sheet and as a later pair of halves is two printings; a cell holding
 * two western halves twenty years apart is two printings; a cell holding one of
 * each is one.
 *
 * Years are deliberately not part of this. Cell 34 pairs a 1903 eastern half
 * with a 1917 western one, cell 39 a 1904 with a 1923, "73 bis" a 1905 with a
 * 1927 — the halves of a cell were revised on their own schedules and reissued
 * separately. They are still one printing of the cell in the sense this badge
 * means (one complete map's worth of paper), and the page surfaces the year
 * spread in the disclosure instead of pretending the cell was printed twice.
 */
function distinctPrintings(printings: SheetPrinting[]): number {
  let whole = 0;
  let west = 0;
  let east = 0;
  for (const p of printings) {
    if (p.part === 'W') west++;
    else if (p.part === 'E') east++;
    else whole++;
  }
  return whole + Math.max(west, east);
}

export const load: PageServerLoad = async ({ params }) => {
  const key = decodeURIComponent(params.key);
  const supabase = adminClient();

  // `map_series` runs on the service client here, so its own gate is not
  // enough — filter to what an anonymous reader may see, the same way the
  // place page does.
  const { data: series } = await supabase
    .from('map_series')
    .select('key,name,collection,sheets,published_sheets,first_year,last_year,bounds')
    .eq('key', key)
    .maybeSingle();

  if (!series || !series.published_sheets) throw error(404, 'No such series');

  const sheets = await fetchSeriesSheetIndex(supabase, key);
  if (!sheets.length) throw error(404, 'That series has no index');

  /**
   * Which printings of each cell the archive publishes.
   *
   * `series_sheets` is keyed `(series_key, sheet_number)` — one row per cell —
   * so it can name the printing it serves and cannot enumerate the others. Ten
   * cells are held in more than one record, and a page that silently showed one
   * of them would be making a claim about the archive that is not true.
   *
   * Published only: the second row behind L7014 6541-4 is a known-bad
   * three-point georeference, deliberately left as a draft, and counting it
   * would advertise an edition no reader can open.
   */
  // `map_series.collection` is nullable in the view's type. Without it there is
  // nothing to group on, and no printings to count.
  const { data: rows } = series.collection
    ? await supabase
        .from('maps')
        .select('id,name,year,extra_metadata')
        .eq('collection', series.collection)
        .in('status', ['public', 'featured'])
        .not('extra_metadata->>sheet_number', 'is', null)
        .order('year', { ascending: true })
    : { data: [] };

  const printings: Record<string, SheetPrinting[]> = {};
  for (const row of rows ?? []) {
    const meta = (row.extra_metadata ?? {}) as {
      sheet_number?: string;
      sheet_half?: string;
      edition?: string;
    };
    if (!meta.sheet_number) continue;
    (printings[meta.sheet_number] ??= []).push({
      institution: null,
      year: row.year,
      edition: meta.edition ?? null,
      part: sheetPart(meta.sheet_half, row.name),
      url: `/catalog/${row.id}`,
      held: true,
    });
  }

  /**
   * Only the cells whose Version column cannot tell the whole truth on one
   * line, so the payload carries the exceptions rather than a list of one
   * against every sheet of a 627-sheet survey. Ten cells qualify today.
   *
   * When `$lib/data/maps/sheetSources.ts` lands, the printings the archive does
   * not hold merge in **here**, before the trim:
   *
   *     const known = await fetchSheetSources(supabase, key);
   *     for (const [n, external] of Object.entries(known)) {
   *       (printings[n] ??= []).push(...external.filter((p) => !p.held));
   *     }
   *
   * The trim then keeps any cell with something to say — including a cell the
   * archive does not hold at all, whose only entries are elsewhere. `editions`
   * stays a count of the printings *this archive serves*, which is what the
   * badge claims, so it is computed before the merge would widen the list.
   */
  const editions: Record<string, number> = {};
  for (const [number, cell] of Object.entries(printings)) {
    if (cell.length < 2) {
      delete printings[number];
      continue;
    }
    const count = distinctPrintings(cell);
    if (count > 1) editions[number] = count;
  }

  // Prose about the survey itself, when it has been written. Undefined is a
  // normal state — the page renders no panel rather than an empty one.
  return {
    series,
    sheets,
    counts: tally(sheets),
    editions,
    printings,
    note: SERIES_NOTES[key],
  };
};
