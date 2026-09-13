/**
 * /catalog/series/<key>/<number> — one sheet of a survey.
 *
 * The record a sheet gets when it has no `maps` row: 452 of the L7014
 * 1:50,000's held sheets are cells of a pre-tiled mosaic, drawable on the map
 * and previously absent from every list, every search and every URL.
 *
 * A sheet the archive does not hold gets a page too, because "this survey
 * contains a sheet here and nobody has found a scan of it" is the most useful
 * thing this table knows — but those pages are `noindex` (see the component),
 * since 166 of L7014's 627 say exactly that and thin pages should not compete
 * in search with the sheets that exist.
 */

import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesSheet, cellCamera } from '$lib/data/maps/seriesSheets';

export const load: PageServerLoad = async ({ params }) => {
  const key = decodeURIComponent(params.key);
  const number = decodeURIComponent(params.number);
  const supabase = adminClient();

  const { data: series } = await supabase
    .from('map_series')
    .select('key,name,collection,first_year,last_year,published_sheets')
    .eq('key', key)
    .maybeSingle();
  if (!series || !series.published_sheets) throw error(404, 'No such series');

  const sheet = await fetchSeriesSheet(supabase, key, number);
  if (!sheet) throw error(404, 'That series contains no such sheet');

  // A sheet held as a `maps` row has a catalogue record of its own, and that is
  // the better page — this one exists for the cells that do not. Carry enough
  // to link there rather than duplicating it.
  let map: { id: string; name: string; year: number | null; status: string } | null = null;
  if (sheet.map_id) {
    const { data } = await supabase
      .from('maps')
      .select('id,name,year,status')
      .eq('id', sheet.map_id)
      .in('status', ['public', 'featured'])
      .maybeSingle();
    map = data as typeof map;
  }

  return {
    series,
    sheet,
    map,
    camera: sheet.bbox ? cellCamera(sheet.bbox) : null,
  };
};
