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
   * How many printings of each cell the archive publishes.
   *
   * `series_sheets` is keyed `(series_key, sheet_number)` — one row per cell —
   * so it can name the printing it serves and cannot enumerate the others. Ten
   * cells are held in more than one edition (three of them with two *published*
   * printings fourteen years apart), and a page that silently showed one of the
   * two would be making a claim about the archive that is not true.
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
        .select('extra_metadata')
        .eq('collection', series.collection)
        .in('status', ['public', 'featured'])
        .not('extra_metadata->>sheet_number', 'is', null)
    : { data: [] };

  const editions: Record<string, number> = {};
  for (const r of rows ?? []) {
    const n = (r.extra_metadata as { sheet_number?: string } | null)?.sheet_number;
    if (n) editions[n] = (editions[n] ?? 0) + 1;
  }
  // Only the cells with more than one, so the payload carries the exceptions
  // rather than a 1 against every sheet of a 627-sheet survey.
  for (const n of Object.keys(editions)) if (editions[n] < 2) delete editions[n];

  // Prose about the survey itself, when it has been written. Undefined is a
  // normal state — the page renders no panel rather than an empty one.
  return { series, sheets, counts: tally(sheets), editions, note: SERIES_NOTES[key] };
};
