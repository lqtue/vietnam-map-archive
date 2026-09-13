/**
 * /catalog/series — every survey the archive holds part of.
 *
 * The one thing that listed surveys was the /explore rail, which is a control
 * inside a full-screen tool behind `ssr = false`: no address, nothing for a
 * crawler to follow, and nothing for the command palette to offer. So the
 * coverage pages existed and were reachable only by someone who already knew
 * they did.
 *
 * Which surveys qualify is `map_series`'s decision (migration 082/084), not
 * this page's — a numbered sheet, more than one of them, and this reader
 * allowed to see them. Reading it on the service client means its own gate is
 * bypassed, so the anonymous filter is applied here the same way the single
 * series page applies it.
 */

import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchMapSeries } from '$lib/data/maps/service';
import { sheetStatus } from '$lib/data/maps/seriesSheets';

export const load: PageServerLoad = async () => {
  const supabase = adminClient();
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
     detector makes. */
  const { data: cells } = await supabase.from('series_sheets').select('series_key,held_by,source');

  const held = new Map<string, { held: number; total: number }>();
  for (const c of cells ?? []) {
    const k = c.series_key as string;
    const t = held.get(k) ?? { held: 0, total: 0 };
    t.total += 1;
    if (sheetStatus(c as { held_by: string | null; source: string | null }) === 'held') t.held += 1;
    held.set(k, t);
  }

  return {
    series: series.map((s) => ({
      key: s.key,
      name: s.name,
      sheets: s.sheets,
      firstYear: s.firstYear ?? null,
      lastYear: s.lastYear ?? null,
      // Null where the survey's index was never imported, which is not zero —
      // AMS L909 has three sheets and no index, and must not read "3 of 0".
      index: held.get(s.key) ?? null,
    })),
  };
};
