/**
 * /catalog — the surveys, server-side; the sheets are still the browser's job.
 *
 * The catalogue itself stays client-side: it is a live search against
 * `/api/search` with facets over the whole result set, and nothing about it is
 * the same for two readers a keystroke apart. The surveys are the opposite —
 * a short list, identical for every anonymous reader, and the entry point to
 * the coverage pages — so they belong in the HTML a crawler gets, the same
 * call `/catalog/series` makes.
 */

import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesIndex } from '$lib/data/maps/seriesIndex';

export const load: PageServerLoad = async () => {
  return { series: await fetchSeriesIndex(adminClient()) };
};
