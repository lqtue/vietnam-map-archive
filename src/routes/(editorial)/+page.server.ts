/**
 * The front page's own data, server-rendered.
 *
 * It used to arrive in `onMount`: the HTML carried a masthead and the words
 * "Opening the archive…", and the featured sheet — the largest thing on the
 * page — appeared a round trip later and shoved everything below it down. A
 * crawler saw no catalogue at all, and the sheet count in the meta description
 * was always the hardcoded fallback, because nothing had counted anything yet.
 *
 * Favorites stay on the client: they need the reader's session, and they are
 * behind a tab nobody signed out can open.
 */

import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchPublishedMapCount, fetchPlaceSpread, SAIGON_PLACE } from '$lib/data/maps/service';
import { fetchSeriesIndex } from '$lib/data/maps/seriesIndex';
import type { FeaturedSeries } from '$lib/features/catalog/homeCatalog';

/**
 * The surveys, each with one of its own catalogued scans as the picture.
 *
 * Which surveys qualify is `fetchSeriesIndex`'s call, the same list /catalog's
 * band shows, so a survey ingested tomorrow reaches the front page with nobody
 * editing this file. A survey is a coverage map rather than a scan, so the
 * picture is only a sample — the coverage map itself lives on the survey's page;
 * the first sheet by name is stable between loads. A failure here is an empty
 * section, never a broken front page.
 */
async function loadFeaturedSeries(
  supabase: ReturnType<typeof adminClient>
): Promise<FeaturedSeries[]> {
  try {
    const index = await fetchSeriesIndex(supabase);
    return await Promise.all(
      index.map(async (entry) => {
        const { data } = await supabase
          .from('maps')
          .select('thumbnail')
          .eq('series_key', entry.key)
          .in('status', ['public', 'featured'])
          .not('thumbnail', 'is', null)
          .order('name')
          .limit(1);
        return { entry, thumbnail: data?.[0]?.thumbnail ?? undefined };
      })
    );
  } catch (err) {
    console.error('loadFeaturedSeries:', err);
    return [];
  }
}

/**
 * The front page's place collections, all four server-rendered so a chip
 * switches with no round trip: 12 list rows each, one query each, in parallel.
 * `area` is the province string `maps.regions` holds (see `catalogAreas.ts`),
 * which is also what `/catalog?area=` filters on.
 */
const PLACES = [
  { key: 'saigon', area: 'Hồ Chí Minh', spec: SAIGON_PLACE },
  { key: 'hanoi', area: 'Hà Nội', spec: { area: 'Hà Nội', namePattern: /hà nội|ha noi|hanoi/i } },
  { key: 'hue', area: 'Thừa Thiên Huế', spec: { area: 'Thừa Thiên Huế', namePattern: /huế|hue/i } },
  { key: 'vietnam', area: '', spec: {} },
];

export const load: PageServerLoad = async () => {
  // The service key, so no row-level policy applies — every query here filters
  // by status itself, and a draft must never reach the front page.
  const supabase = adminClient();

  const [mapCount, series, ...spreads] = await Promise.all([
    fetchPublishedMapCount(supabase),
    loadFeaturedSeries(supabase),
    ...PLACES.map((p) => fetchPlaceSpread(supabase, p.spec)),
  ]);
  const places = PLACES.map(({ key, area }, i) => ({ key, area, ...spreads[i] }));

  return { mapCount, series, places };
};
