/**
 * Share page loader. Server-rendered on purpose: this is the URL people paste
 * into chat apps and social media, so the crawler has to see the title, the
 * description and the image without running any JavaScript.
 *
 * Only published maps resolve — a draft link 404s rather than leaking a record
 * that is not meant to be public yet.
 */

import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';

export const load: PageServerLoad = async ({ params }) => {
  const id = assertUuid(params.id, 'map id');

  const { data: map } = await adminClient()
    .from('maps')
    .select(
      'id, name, dc_description, year, year_label, creator, dc_publisher, holding_institution, collection, map_type, location, thumbnail, iiif_image, allmaps_id, annotation_url, georef_done, status, bbox, iiif_manifest, map_iiif_sources(iiif_image, source_type)'
    )
    .eq('id', id)
    .in('status', ['public', 'featured'])
    .maybeSingle();

  if (!map) throw error(404, 'No published map with that id');

  // The places this sheet names, most-attested first. Two jobs: it tells a
  // reader what is on the map before they open it, and it is the only crawl
  // path to the /place pages, which otherwise exist without being linked.
  const { data: places } = await adminClient()
    .from('place_names')
    .select('name_key, name, mentions, category')
    .contains('map_ids', [id])
    .order('mentions', { ascending: false })
    .limit(40);

  return { map, places: places ?? [] };
};
