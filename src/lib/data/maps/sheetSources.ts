/** Reads institution catalogue items separately from canonical printing identities and scans. */

import type { SupabaseClient } from '@supabase/supabase-js';
import { readAll } from '$lib/data/supabase/paged';
import { queryError } from '$lib/data/supabase/queryError';

// Large .in() URLs are echoed in response headers. Node's fetch rejects them
// above its header limit, even when the same query succeeds in Cloudflare.
const ID_BATCH = 100;

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
  printingId?: string | null;
  title?: string | null;
  reviewStatus?: string | null;
  unresolved?: boolean;
  scans?: { url: string; name: string }[];
  institutions?: string[];
  sourceItems?: { institution: string | null; url: string | null; rights: string | null }[];
}

export interface CanonicalSheetPrinting {
  id: string;
  cell_id: string;
  printed_title: string | null;
  edition_statement: string | null;
  edition_label: string | null;
  issuing_agency: string | null;
  content_year: number | null;
  edition_year: number | null;
  printing_year: number | null;
  printing_month: number | null;
  printer: string | null;
  printing_statement: string | null;
  part: SheetPrinting['part'];
  review_status: string;
}

/** Reviewed printings keyed to the legacy cell address during the compatibility rollout. */
export async function fetchCanonicalSheetPrintings(
  db: SupabaseClient,
  seriesKey: string
): Promise<Record<string, CanonicalSheetPrinting[]>> {
  const cellsResult = await readAll((from, to) =>
    db
      .from('series_cells')
      .select('id,sheet_number')
      .eq('series_key', seriesKey)
      .order('sheet_number')
      .range(from, to)
  );
  if (cellsResult.error) throw queryError('Printing cells', cellsResult.error);
  const cells = cellsResult.data ?? [];
  const cellIds = cells.map((cell) => cell.id);
  if (!cellIds.length) return {};
  const data: CanonicalSheetPrinting[] = [];
  for (let start = 0; start < cellIds.length; start += ID_BATCH) {
    const printingsResult = await readAll((from, to) =>
      db
        .from('sheet_printings')
        .select(
          'id,cell_id,printed_title,edition_statement,edition_label,issuing_agency,content_year,edition_year,printing_year,printing_month,printer,printing_statement,part,review_status'
        )
        .in('cell_id', cellIds.slice(start, start + ID_BATCH))
        .order('id')
        .range(from, to)
    );
    if (printingsResult.error) throw queryError('Sheet printings', printingsResult.error);
    data.push(...(printingsResult.data as CanonicalSheetPrinting[]));
  }
  const numberByCell = new Map(cells.map((cell) => [cell.id, cell.sheet_number]));
  const result: Record<string, CanonicalSheetPrinting[]> = {};
  for (const row of data ?? []) {
    // Public readers receive reviewed identities. Pending assertions remain in
    // admin data and do not become a public bibliographic claim.
    if (row.review_status !== 'verified') continue;
    const number = numberByCell.get(row.cell_id);
    if (!number) continue;
    (result[number] ??= []).push(row as CanonicalSheetPrinting);
  }
  return result;
}

interface SheetSourceRow {
  id: string;
  series_key: string;
  series_id?: string;
  sheet_number: string;
  institution: string;
  year: number | null;
  edition: string | null;
  part: SheetPrinting['part'];
  url: string | null;
  rights: string | null;
  printing_id?: string | null;
  title?: string | null;
  review_status?: string | null;
}

const COLUMNS =
  'id,series_key,sheet_number,institution,year,edition,part,url,rights,printing_id,title';

/**
 * The column's short code to the name of the library. 087 stores the code so
 * the two tables share one vocabulary in SQL; the name is a display concern and
 * lives here, once. An unknown code falls through unchanged rather than being
 * dropped — a new institution should appear in the UI looking unpolished, not
 * vanish from it.
 */
const INSTITUTION_NAME: Record<string, string> = {
  PCL: 'Perry-Castañeda',
  USGS: 'USGS',
  Princeton: 'Princeton',
  TTU: 'Texas Tech',
  ANU: 'ANU',
  IGN: 'IGN',
};

/**
/** A held claim requires an explicit map→printing or image→source-item link. */
export function isPrintingHeld(
  row: Pick<SheetSourceRow, 'id' | 'printing_id'>,
  archiveLinks: { printing_id: string | null; source_item_id: string | null }[]
): boolean {
  return archiveLinks.some(
    (link) =>
      (row.printing_id != null && link.printing_id === row.printing_id) ||
      link.source_item_id === row.id
  );
}

/**
 * Every known printing of every cell of one survey, keyed by sheet number.
 *
 * Paged explicitly because PostgREST caps unbounded selects at 1000 rows.
 *
 * Legacy institution items remain in the response. A missing printing link
 * means unresolved and never counts as a held printing.
 */
export async function fetchSheetSources(
  db: SupabaseClient,
  seriesKey: string
): Promise<Record<string, SheetPrinting[]>> {
  const page = 1000;
  const rows: SheetSourceRow[] = [];
  for (let from = 0; ; from += page) {
    const { data, error } = await db
      .from('cell_printings')
      .select(COLUMNS)
      .eq('series_key', seriesKey)
      .order('id')
      .range(from, from + page - 1);
    if (error) throw queryError('Source items', error);
    rows.push(...((data ?? []) as SheetSourceRow[]));
    if (!data || data.length < page) break;
  }

  // Explicit archive links only. Missing year/edition is not identity evidence.
  const archiveResult = await readAll((from, to) =>
    db
      .from('maps')
      .select('printing_id,map_images(source_item_id)')
      .eq('series_key', seriesKey)
      .in('status', ['public', 'featured'])
      .order('id')
      .range(from, to)
  );
  if (archiveResult.error) throw queryError('Source maps', archiveResult.error);
  const archiveRows = archiveResult.data ?? [];
  const linkedPrintingIds = [
    ...new Set(rows.flatMap((row) => (row.printing_id ? [row.printing_id] : []))),
  ];
  const verifiedPrintingIds = new Set<string>();
  for (let start = 0; start < linkedPrintingIds.length; start += ID_BATCH) {
    const { data: linkedPrintings, error: printingError } = await db
      .from('sheet_printings')
      .select('id,review_status')
      .in('id', linkedPrintingIds.slice(start, start + ID_BATCH));
    if (printingError) throw queryError('Source printings', printingError);
    for (const printing of linkedPrintings ?? []) {
      if (printing.review_status === 'verified') verifiedPrintingIds.add(printing.id);
    }
  }
  const archiveLinks = archiveRows.flatMap((m) => [
    {
      printing_id: m.printing_id && verifiedPrintingIds.has(m.printing_id) ? m.printing_id : null,
      source_item_id: null,
    },
    ...((m.map_images ?? []) as { source_item_id: string | null }[]).map((image) => ({
      printing_id: m.printing_id && verifiedPrintingIds.has(m.printing_id) ? m.printing_id : null,
      source_item_id: image.source_item_id,
    })),
  ]);

  const out: Record<string, SheetPrinting[]> = {};
  for (const r of rows) {
    (out[r.sheet_number] ??= []).push({
      institution: INSTITUTION_NAME[r.institution] ?? r.institution,
      year: r.year ?? null,
      edition: r.edition ?? null,
      part: r.part ?? null,
      url: r.url ?? null,
      rights: r.rights ?? null,
      held: isPrintingHeld(r, archiveLinks),
      printingId: r.printing_id && verifiedPrintingIds.has(r.printing_id) ? r.printing_id : null,
      title: r.title ?? null,
      reviewStatus: r.printing_id
        ? verifiedPrintingIds.has(r.printing_id)
          ? 'verified'
          : 'unreviewed'
        : null,
      unresolved: !(r.printing_id && verifiedPrintingIds.has(r.printing_id)),
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
