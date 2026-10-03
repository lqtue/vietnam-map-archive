/**
 * /catalog/series/<key> — one survey, every sheet it contains.
 *
 * Every cell of a survey, held or not — the list `maps` alone cannot produce, since a
 * cell nobody holds has no row. (Until 2026-10-03 L7014 was mostly a pre-tiled mosaic
 * with no `maps` rows; every sheet is a `maps` row now.)
 *
 * Server-rendered, like the share and place pages, so the coverage of a survey
 * is readable without running JavaScript.
 *
 * The survey's identity and name come from `map_series` (migration 082/084),
 * which is gated to what this reader may see; the sheet list comes from
 * `series_cells` (083), which carries no gate of its own because a gap in a
 * survey is catalogue information. Reading them together is safe in that
 * order — a survey with nothing published has no `map_series` row, so this
 * route 404s before it ever reaches the sheet list.
 */

import { readAll } from '$lib/data/supabase/paged';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesSheetIndex, tally } from '$lib/data/maps/seriesSheets';
import {
  fetchCanonicalSheetPrintings,
  fetchSheetSources,
  type SheetPrinting,
} from '$lib/data/maps/sheetSources';
import { SERIES_NOTES } from './notes';

/**
 * One printing of one cell, held or not.
 *
 * The shape was declared here while `$lib/data/maps/sheetSources.ts` was being
 * written beside it, deliberately spelled the same so the merge would be a
 * concatenation rather than a translation layer. That module now exists, so the
 * local copy is gone: a second declaration of a shape two files must agree on
 * does not error when it drifts, it just stops type-checking the thing it was
 * written to check.
 *
 * `institution` is null on a held printing, and that is the useful signal
 * rather than a missing value — it is what separates "this is ours" from
 * "Texas Tech has one too" in a single list.
 */

/**
 * The half marker the Indochine ingest writes into the record's name —
 * "Phu Xuyen (W)", "Cua Day (E)". Anchored at the end because a sheet name may
 * legitimately contain brackets elsewhere.
 */
const HALF_IN_NAME = /\((W|E)\)\s*$/;

/**
 * Which piece of paper a record is.
 *
 * `maps.sheet_half` (backfilled from `extra_metadata.sheet_half`, mig 095) is
 * the authority: `ingest_indochine_nakala.mjs` derives it from the Cartomundi
 * note ("Demi-feuille Ouest") and cross-checks it against the brackets in the
 * title before it will insert a row, so it is the value that was actually
 * verified. The name marker is the fallback, for a row
 * that reached `maps` by some other route — a hand edit in the catalogue
 * editor, or a survey cut the same way that nobody has written an ingest for.
 *
 * Absent both, the record covers the whole cell. That is not a guess: every
 * L7014 row is a whole sheet, and `sheet_half: 'whole'` is what the Indochine
 * ingest writes for a demi-format sheet, which is one piece of paper carrying
 * the entire cell.
 */
function sheetPart(
  half: unknown,
  name: string | null,
  provenance: unknown
): 'whole' | 'W' | 'E' | 'assemblage' {
  // 62 of the Indochine rows are two half-sheets joined by a third party, which
  // `extra_metadata.scan_provenance` records after matching physical marks on
  // the paper — cell 36 carries the same blue pencil "36" as IGN's west half.
  // Calling those a whole sheet is the one answer that is plainly untrue: the
  // survey never printed a whole sheet for those cells, and the page reading
  // "Whole sheet · Held" beside IGN's actual west and east halves invites
  // exactly the wrong conclusion about what the archive is serving.
  if (typeof provenance === 'string' && /^assembled edition/i.test(provenance)) return 'assemblage';
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
  return new Set(printings.flatMap((p) => (p.held && p.printingId ? [p.printingId] : []))).size;
}

/** The smallest box holding both; either may be absent. */
function unionBox(a?: number[] | null, b?: number[] | null): number[] | undefined {
  if (a?.length !== 4) return b?.length === 4 ? b : undefined;
  if (b?.length !== 4) return a;
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
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
  const canonicalPrintings = await fetchCanonicalSheetPrintings(supabase, key);
  const verifiedPrintingIds = new Set(
    Object.values(canonicalPrintings).flatMap((items) => items.map((printing) => printing.id))
  );

  /**
   * Which printings of each cell the archive publishes.
   *
   * `series_cells` is keyed `(series_key, sheet_number)` — one row per cell —
   * so it can name the printing it serves and cannot enumerate the others. Ten
   * cells are held in more than one record, and a page that silently showed one
   * of them would be making a claim about the archive that is not true.
   *
   * Published only: the second row behind L7014 6541-4 is a known-bad
   * three-point georeference, deliberately left as a draft, and counting it
   * would advertise an edition no reader can open.
   */
  const { data: rows } = await readAll((from, to) =>
    supabase
      .from('maps')
      .select('id,name,year,sheet_number,sheet_half,extra_metadata,bbox,printing_id')
      .eq('series_key', key)
      .in('status', ['public', 'featured'])
      .not('sheet_number', 'is', null)
      .order('year', { ascending: true })
      .order('id')
      .range(from, to)
  );

  const printings: Record<string, SheetPrinting[]> = {};
  const scansByPrinting = new Map<string, { url: string; name: string }[]>();
  /** Per cell, the union of the georeferenced records' boxes — see `coverage` below. */
  const reach: Record<string, number[]> = {};
  for (const row of rows ?? []) {
    if (!row.sheet_number) continue;
    const box = unionBox(reach[row.sheet_number], row.bbox);
    if (box) reach[row.sheet_number] = box;
    // `edition`/`scan_provenance` have no columns of their own (mig 095) — only
    // `sheet_number`/`sheet_half` moved off `extra_metadata`.
    const meta = (row.extra_metadata ?? {}) as {
      edition?: string;
      scan_provenance?: string;
    };
    const item: SheetPrinting = {
      institution: null,
      year: row.year,
      edition: meta.edition ?? null,
      part: sheetPart(row.sheet_half, row.name, meta.scan_provenance),
      url: `/catalog/${row.id}`,
      rights: null,
      held: true,
      printingId: row.printing_id ?? null,
      unresolved: row.printing_id == null,
    };
    const verifiedPrintingId =
      row.printing_id && verifiedPrintingIds.has(row.printing_id) ? row.printing_id : null;
    item.printingId = verifiedPrintingId;
    item.unresolved = !verifiedPrintingId;
    if (verifiedPrintingId) {
      const scans = scansByPrinting.get(verifiedPrintingId) ?? [];
      scans.push({ url: `/catalog/${row.id}`, name: row.name });
      scansByPrinting.set(verifiedPrintingId, scans);
      if (!(printings[row.sheet_number] ?? []).some((p) => p.printingId === verifiedPrintingId)) {
        (printings[row.sheet_number] ??= []).push(item);
      }
    } else {
      (printings[row.sheet_number] ??= []).push(item);
    }
  }

  for (const [number, canonical] of Object.entries(canonicalPrintings)) {
    for (const printing of canonical) {
      const existing = (printings[number] ?? []).find((p) => p.printingId === printing.id);
      const scans = scansByPrinting.get(printing.id) ?? [];
      if (existing) {
        existing.year = printing.printing_year ?? printing.edition_year ?? printing.content_year;
        existing.edition = printing.edition_label ?? printing.edition_statement;
        existing.part = printing.part ?? existing.part;
        existing.title = printing.printed_title;
        existing.scans = scans;
      } else {
        (printings[number] ??= []).push({
          institution: null,
          year: printing.printing_year ?? printing.edition_year ?? printing.content_year,
          edition: printing.edition_label ?? printing.edition_statement,
          part: printing.part,
          url: null,
          rights: null,
          held: false,
          printingId: printing.id,
          title: printing.printed_title,
          reviewStatus: 'verified',
          unresolved: false,
          scans,
        });
      }
    }
  }

  /**
   * Only the cells whose Version column cannot tell the whole truth on one
   * line, so the payload carries the exceptions rather than a list of one
   * against every sheet of a 627-sheet survey. Ten cells qualify today.
   *
   * When `$lib/data/maps/sheetSources.ts` lands, the printings the archive does
   * not hold merge in **here**, before the trim:
   *
   * The item catalogue is merged beside these verified identities below;
   * unknown source items remain explicitly unresolved.
   */
  // `editions` counts only what the archive SERVES, which is what the badge
  // claims, so it is computed before the merge below widens the list.
  const editions: Record<string, number> = {};
  for (const [number, cell] of Object.entries(printings)) {
    if (cell.length < 2) continue;
    const count = distinctPrintings(cell);
    if (count > 1) editions[number] = count;
  }

  // Every printing anyone is known to hold, merged in beside ours.
  const known = await fetchSheetSources(supabase, key);
  for (const [number, external] of Object.entries(known)) {
    for (const item of external) {
      const matching = item.printingId
        ? (printings[number] ?? []).find((p) => p.printingId === item.printingId)
        : undefined;
      if (matching) {
        matching.institutions = [
          ...new Set([...(matching.institutions ?? []), item.institution ?? '']),
        ].filter(Boolean);
        const sourceItem = { institution: item.institution, url: item.url, rights: item.rights };
        const sourceItems = matching.sourceItems ?? [];
        if (
          !sourceItems.some(
            (existing) =>
              existing.url === sourceItem.url &&
              existing.institution === sourceItem.institution &&
              existing.rights === sourceItem.rights
          )
        ) {
          matching.sourceItems = [...sourceItems, sourceItem];
        }
      } else {
        (printings[number] ??= []).push(item);
      }
    }
  }

  // Keep a cell that has anything to say, which now includes one the archive
  // does not hold at all: its entries are all elsewhere, and those links are
  // the whole answer the Source column can give for a gap. A cell with one
  // held printing and no second anywhere still carries nothing.
  for (const [number, cell] of Object.entries(printings)) {
    if (
      cell.length < 2 &&
      !cell.some((p) => !p.held) &&
      !cell.some((p) => p.unresolved) &&
      !canonicalPrintings[number]?.length
    )
      delete printings[number];
  }

  /**
   * Where each cell sits, for the coverage map.
   *
   * `series_cells.bbox` is the extent of ONE record — for a cell printed as a
   * west and an east half that is half a cell, so the map showed the 1:100,000's
   * halves as a ragged scatter while /explore, which draws every record at its
   * georeference, showed a continuous quilt. The cell's box joined with its
   * records' boxes is the footprint /explore actually paints. Rounded to three
   * decimals (about 100 m): the payload is ~200–600 boxes.
   */
  const coverage = sheets.map((s) => ({
    bbox:
      unionBox(s.bbox ?? undefined, reach[s.sheet_number])?.map((n) => Math.round(n * 1e3) / 1e3) ??
      null,
    status: s.status,
  }));

  // Prose about the survey itself, when it has been written. Undefined is a
  // normal state — the page renders no panel rather than an empty one.
  return {
    series,
    sheets,
    coverage,
    counts: tally(sheets),
    editions,
    printings,
    canonicalPrintings,
    note: SERIES_NOTES[key],
  };
};
