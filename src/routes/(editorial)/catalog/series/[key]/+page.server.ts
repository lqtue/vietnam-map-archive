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
import { fetchSeriesSheets, tally } from '$lib/data/maps/seriesSheets';

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

  const sheets = await fetchSeriesSheets(supabase, key);
  if (!sheets.length) throw error(404, 'That series has no index');

  return { series, sheets, counts: tally(sheets) };
};
