import { isPartialSeriesIndex } from '$lib/core/seriesIndexScope';
/**
 * seriesIndex.ts — the surveys the archive holds part of, and how much of each.
 *
 * Read by the band at the top of `/catalog`, the way in to the coverage pages.
 * The qualifying rule below is a filter the database does not apply for us.
 *
 * Which surveys qualify is `map_series`'s decision (migration 082/084), not
 * this module's — a numbered sheet, more than one of them, and this reader
 * allowed to see them. Callers read it on the service client, which bypasses
 * the view's own gate, so the anonymous filter is applied here the same way
 * the single series page applies it.
 */

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { fetchMapSeries } from './service';
import type { SeriesTally } from './seriesSheets';
import { readAll } from '$lib/data/supabase/paged';

export interface SeriesIndexEntry {
  key: string;
  /**
   * `maps.collection` — the column a sheet row actually carries, and so what
   * /catalog's series filter matches on. Distinct from `name` only in
   * principle: `map_series` aliases both to the same column today, and a
   * filter keyed on a display name would break the day it stops doing that.
   */
  collection: string;
  name: string;
  firstYear: number | null;
  lastYear: number | null;
  /** Distinct cells with a public served scan, from the role-aware view. */
  sheets: number;
  publishedSheets: number;
  itemLinkedPrintings: number;
  knownPrintings: number;
  /**
   * [minLon, minLat, maxLon, maxLat], the union of the survey's sheets — what
   * "zoom to this layer" means. Carried so a link into /explore can fit the
   * survey instead of dropping it on the reader's last camera, which for a
   * country-sized layer is one corner of it.
   */
  bounds: [number, number, number, number];
  /**
   * The survey's own index, tallied: what it contains, and how each cell
   * stands. The status rule is `sheetStatus`, called rather than re-spelled —
   * a second copy of "held_by, else source, else nothing" is a signal that
   * drifts silently, and the number it produces looks right either way.
   */
  index: SeriesTally;
}

export async function fetchSeriesIndex(
  supabase: SupabaseClient<Database>
): Promise<SeriesIndexEntry[]> {
  const all = await fetchMapSeries(supabase);
  /* Every series with a published sheet. One whose index was never imported (a newly added survey) has no
     coverage page — that route 404s on purpose — so `hasDenominator` is false for it and the band
     opens its drawer instead of linking. It gets a coverage page the moment someone imports its
     index. */
  const series = all.filter((s) => s.publishedSheets > 0);

  const [
    { data: coverage, error: coverageError },
    { data: availability, error: availabilityError },
  ] = await Promise.all([
    supabase.from('series_cell_coverage').select('key,publicly_held_cell_count'),
    supabase
      .from('series_printing_availability')
      .select('key,item_linked_printing_count,printing_count'),
  ]);
  if (coverageError) console.error('series cell coverage:', coverageError);
  if (availabilityError) console.error('series printing availability:', availabilityError);
  const publicCellsByKey = new Map(
    (coverage ?? []).map((row) => [row.key ?? '', row.publicly_held_cell_count ?? 0])
  );
  const availabilityByKey = new Map(
    (availability ?? []).map((row) => [
      row.key ?? '',
      {
        itemLinked: row.item_linked_printing_count ?? 0,
        known: row.printing_count ?? 0,
      },
    ])
  );

  // Per-cell counts come from the role-aware derived view. Legacy held_by and
  // map_id snapshots are ignored; a source-item reference only makes a cell
  // obtainable when the view confirms an institution item exists.
  const { data: cells, error: cellError } = await readAll((from, to) =>
    supabase
      .from('series_cell_coverage_detail')
      .select('key,sheet_number,publicly_held,known_source')
      .order('key')
      .order('sheet_number')
      .range(from, to)
  );
  if (cellError) console.error('series cell coverage detail:', cellError);
  const held = new Map<string, SeriesTally>();
  for (const c of cells ?? []) {
    const k = c.key ?? '';
    if (!k) continue;
    const t = held.get(k) ?? { total: 0, held: 0, obtainable: 0, no_scan: 0 };
    t.total += 1;
    if (c.publicly_held) t.held += 1;
    else if (c.known_source) t.obtainable += 1;
    else t.no_scan += 1;
    held.set(k, t);
  }

  return series.map((s) => {
    const index = held.get(s.key) ?? { total: 0, held: 0, obtainable: 0, no_scan: 0 };
    return {
      key: s.key,
      collection: s.collection,
      name: s.name,
      firstYear: s.firstYear ?? null,
      lastYear: s.lastYear ?? null,
      sheets: s.sheets,
      publishedSheets: publicCellsByKey.get(s.key) ?? 0,
      itemLinkedPrintings: availabilityByKey.get(s.key)?.itemLinked ?? 0,
      knownPrintings: availabilityByKey.get(s.key)?.known ?? 0,
      bounds: s.bounds,
      index: isPartialSeriesIndex(s.key) ? { ...index, partial: true } : index,
    };
  });
}
