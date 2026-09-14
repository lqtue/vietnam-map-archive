/**
 * /catalog/series — every survey the archive holds part of.
 *
 * The one thing that listed surveys was the /explore rail, which is a control
 * inside a full-screen tool behind `ssr = false`: no address, nothing for a
 * crawler to follow, and nothing for the command palette to offer. So the
 * coverage pages existed and were reachable only by someone who already knew
 * they did.
 *
 * Which surveys qualify, and where the held counts come from, is
 * `fetchSeriesIndex` — shared with the band at the top of /catalog, which is
 * now the way in to this page.
 */

import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesIndex } from '$lib/data/maps/seriesIndex';

export const load: PageServerLoad = async () => {
  return { series: await fetchSeriesIndex(adminClient()) };
};
