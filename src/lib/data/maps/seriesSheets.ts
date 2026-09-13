/**
 * seriesSheets.ts — what a survey contains, read for display.
 *
 * `series_sheets` (migration 083) is one row per sheet a survey contains, held
 * or not. Until now nothing read it: the catalogue could only show a sheet that
 * had a `maps` row, which for the L7014 1:50,000 meant **9 of 461 held sheets
 * were visible**. The other 452 reach a reader as pixels in a pre-tiled raster
 * mosaic and have no `maps` row at all, so they were in the archive, drawable
 * on the map, and absent from every list and every search.
 *
 * A sheet's status is derived here exactly as 083's comment specifies, and is
 * never stored:
 *
 *     held_by set                    -> held
 *     held_by null, source set       -> obtainable, nobody has fetched it
 *     both null                      -> no known scan anywhere
 *
 * `bbox` is the cell the survey's own index assigns, not a georeference — for
 * L7014 an exact 15' x 15' lattice cell. It is right to a few metres and is
 * what lets an unheld sheet be drawn as a gap; nothing should warp against it.
 *
 * This file is deliberately separate from `service.ts`, which reads `maps`.
 * These rows are not maps and do not become `MapListItem`s: a sheet is a cell
 * of a survey, and conflating the two is what made the mosaic invisible.
 */

import type { SupabaseClient } from '@supabase/supabase-js';

export type SheetStatus = 'held' | 'obtainable' | 'no_scan';

export interface SeriesSheet {
  series_key: string;
  sheet_number: string;
  name: string | null;
  bbox: number[] | null;
  source: string | null;
  source_ref: string | null;
  held_by: string | null;
  map_id: string | null;
  note: string | null;
}

export interface SeriesSheetView extends SeriesSheet {
  status: SheetStatus;
  /** How a held sheet reaches the reader, in words. Null when not held. */
  heldAs: string | null;
}

const COLUMNS = 'series_key,sheet_number,name,bbox,source,source_ref,held_by,map_id,note';

export function sheetStatus(row: Pick<SeriesSheet, 'held_by' | 'source'>): SheetStatus {
  if (row.held_by) return 'held';
  return row.source ? 'obtainable' : 'no_scan';
}

/**
 * `held_by` is either the literal `'map'` or a layer key such as
 * `'raster:l7014'`. The distinction matters to a reader: one is a sheet warped
 * live from its own scan, the other a cell of a mosaic that was warped once and
 * pre-tiled, which is why it has no catalogue record of its own.
 */
function heldAs(held_by: string | null): string | null {
  if (!held_by) return null;
  if (held_by === 'map') return 'Warped from its own scan';
  if (held_by.startsWith('raster:')) return 'Part of the pre-tiled mosaic';
  return held_by;
}

function decorate(row: SeriesSheet): SeriesSheetView {
  return { ...row, status: sheetStatus(row), heldAs: heldAs(row.held_by) };
}

/**
 * Every sheet of one survey, ordered by sheet number the way a person reads it
 * — `numeric` collation so `6329-4` precedes `6330-1` and `10` follows `9`.
 *
 * Paged explicitly: PostgREST caps an unbounded select at 1000 rows and says
 * nothing about it, and L7014 alone is 627 today with the Cochinchine surveys
 * in the scout queue running to 826.
 */
export async function fetchSeriesSheets(
  db: SupabaseClient,
  seriesKey: string
): Promise<SeriesSheetView[]> {
  const page = 1000;
  const out: SeriesSheet[] = [];
  for (let from = 0; ; from += page) {
    const { data, error } = await db
      .from('series_sheets')
      .select(COLUMNS)
      .eq('series_key', seriesKey)
      .range(from, from + page - 1);
    if (error) throw error;
    out.push(...((data ?? []) as SeriesSheet[]));
    if (!data || data.length < page) break;
  }
  return out
    .map(decorate)
    .sort((a, b) => a.sheet_number.localeCompare(b.sheet_number, undefined, { numeric: true }));
}

export async function fetchSeriesSheet(
  db: SupabaseClient,
  seriesKey: string,
  sheetNumber: string
): Promise<SeriesSheetView | null> {
  const { data, error } = await db
    .from('series_sheets')
    .select(COLUMNS)
    .eq('series_key', seriesKey)
    .eq('sheet_number', sheetNumber)
    .maybeSingle();
  if (error) throw error;
  return data ? decorate(data as SeriesSheet) : null;
}

export interface SeriesTally {
  total: number;
  held: number;
  obtainable: number;
  no_scan: number;
}

export function tally(sheets: SeriesSheetView[]): SeriesTally {
  return {
    total: sheets.length,
    held: sheets.filter((s) => s.status === 'held').length,
    obtainable: sheets.filter((s) => s.status === 'obtainable').length,
    no_scan: sheets.filter((s) => s.status === 'no_scan').length,
  };
}

/**
 * The camera for a cell: centre, and a zoom that fits the wider span in the
 * viewport. 360 degrees over 512 px is web-mercator z0, so halving per level
 * gives the fit; 0.6 of it leaves the sheet a margin rather than bleeding it to
 * the window edge. Clamped because a degenerate bbox would otherwise ask for a
 * zoom no basemap has.
 */
export function cellCamera(bbox: number[]): { lng: number; lat: number; zoom: number } {
  const [w, s, e, n] = bbox;
  const span = Math.max(Math.abs(e - w), Math.abs(n - s), 1e-6);
  const zoom = Math.min(16, Math.max(4, Math.log2(360 / span) + 0.6));
  return { lng: (w + e) / 2, lat: (s + n) / 2, zoom: Math.round(zoom * 100) / 100 };
}
