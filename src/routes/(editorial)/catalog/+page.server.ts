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
import { fetchInstitutionCatalog } from '$lib/data/maps/institutions';
import { dbError } from '$lib/server/http';

export const load: PageServerLoad = async ({ url }) => {
  const [series, { areas, regions }, { institutions }] = await Promise.all([
    fetchSeriesIndex(adminClient()),
    fetchCoverageIndex(adminClient()).catch((err) =>
      dbError(err, 'Area index could not be loaded')
    ),
    // The band is a convenience; a failed read drops it rather than the whole catalog.
    fetchInstitutionCatalog(adminClient()).catch((err) => {
      console.error('[catalog] institution index:', err);
      return { institutions: [] };
    }),
  ]);
  return {
    series,
    areas,
    regions,
    // Name and count only: the catalog's per-institution map lists are its own page's to ship.
    institutions: institutions
      .map((i) => ({
        slug: i.slug,
        label: i.short,
        count: i.maps.length,
        sources: i.sourceItems,
        series: i.series.length + i.cartomundiSeries.length + i.otherSeries,
      }))
      .sort((a, b) => b.count - a.count || b.sources - a.sources || a.label.localeCompare(b.label)),
    initialArea: url.searchParams.get('area') ?? '',
    initialRegion: url.searchParams.get('region') ?? '',
  };
};
