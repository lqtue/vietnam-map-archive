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
import { fetchCoverageIndex } from '$lib/data/maps/areas';
import { dbError } from '$lib/server/http';

export const load: PageServerLoad = async ({ url }) => {
  const [series, { areas, regions }] = await Promise.all([
    fetchSeriesIndex(adminClient()),
    fetchCoverageIndex(adminClient()).catch((err) =>
      dbError(err, 'Area index could not be loaded')
    ),
  ]);
  return {
    series,
    areas,
    regions,
    initialArea: url.searchParams.get('area') ?? '',
    initialRegion: url.searchParams.get('region') ?? '',
  };
};
