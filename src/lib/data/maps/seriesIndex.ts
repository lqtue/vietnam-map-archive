/**
 * seriesIndex.ts — the surveys the archive holds part of, and how much of each.
 *
 * Read by two surfaces that must agree: `/catalog/series`, which lists every
 * survey, and the band at the top of `/catalog`, which is the way in to it.
 * They were one function's worth of logic in a route load until the band
 * needed the same rows — and two copies of "which surveys qualify" is exactly
 * the drift this is here to prevent, because the qualifying rule below is a
 * filter the database does not apply for us.
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
import { sheetStatus, type SeriesTally } from './seriesSheets';

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
  /** Distinct cells held as `maps` rows — the 9 of L7014, not the 461. */
  sheets: number;
  publishedSheets: number;
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
  /* A survey whose index was never imported has no coverage page — that route
     404s on purpose — so it is not offered here either. AMS L909 is the one:
     three sheets, and nobody has decided what the survey contains. It appears
     the moment someone imports its index, which is the point of reading this
     rather than listing surveys by hand. */
  const series = all.filter((s) => s.publishedSheets > 0 && s.surveySheets != null);

  /* Held counts come from the survey's own index, because a sheet reaches a
     reader by more than one route: 452 of L7014's 461 are mosaic cells with no
     `maps` row, and `publishedSheets` cannot see them. Two columns over ~700
     rows is cheaper than a per-series round trip, and the same read the drift
     detector makes. `held_by` is the whole test — `sheetStatus` in
     `seriesSheets.ts` owns the rule, and `sheetStatus` is called here rather
     than reimplemented — including the half that separates two kinds of
     *unheld*, which the drawer draws as a coverage bar. */
  const { data: cells } = await supabase.from('series_cells').select('series_key,held_by,source');

  const held = new Map<string, SeriesTally>();
  for (const c of cells ?? []) {
    const k = c.series_key as string;
    const t = held.get(k) ?? { total: 0, held: 0, obtainable: 0, no_scan: 0 };
    t.total += 1;
    t[sheetStatus(c)] += 1;
    held.set(k, t);
  }

  return series.map((s) => ({
    key: s.key,
    collection: s.collection,
    name: s.name,
    firstYear: s.firstYear ?? null,
    lastYear: s.lastYear ?? null,
    sheets: s.sheets,
    publishedSheets: s.publishedSheets,
    bounds: s.bounds,
    // Always set: the filter above kept only surveys whose index exists, and
    // `survey_sheets` is a count over the very rows this counts.
    index: held.get(s.key)!,
  }));
}
