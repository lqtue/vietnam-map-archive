/**
 * Share page loader. Server-rendered on purpose: this is the URL people paste
 * into chat apps and social media, so the crawler has to see the title, the
 * description and the image without running any JavaScript.
 *
 * **A draft resolves only for a signed-in reader**, and says so on the page.
 * Anonymous still gets a 404, never a redirect to sign in, which would confirm
 * the id exists. That is the line migration 063 draws on `maps` itself — open
 * contribution means a volunteer legitimately works on unpublished sheets, and
 * anonymous is the boundary that matters — and it is what let `/scan` stop
 * being a public address in Sept 2026: this page is the scan viewer now, so it
 * has to be reachable for every sheet `/scan` could open, draft included.
 *
 * `[id]` takes three shapes, and the route is named for the oldest of them:
 *
 *   * the **slug** (migration 088) — `plan-de-la-ville-de-saigon-1799`, the
 *     canonical address and the only one this page serves;
 *   * a **retired slug**, from `map_slug_aliases` — a name the sheet answered on
 *     before it was demoted or deliberately re-minted;
 *   * the **uuid** — every link the archive published before September 2026.
 *
 * The last two are 301'd to the first. Serving the same record at three
 * addresses is the duplicate-content case the root layout's canonical tag
 * exists to close, and a redirect says which one is the real name; a 404 would
 * just break links that are already in other people's messages.
 */

import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { isUuid } from '$lib/core/utils/mapSlug';
import { localeFromPath } from '$lib/core/i18n';
import { verifiedEditorSourceId } from '$lib/core/iiif/annotationUrl';

// Field names here are this page's own vocabulary, carried over from before
// mig 095 (`dc_description`, `year_label`, `dc_publisher`, `georef_done`,
// `map_iiif_sources`) — `+page.svelte` reads them under those names, so only
// the column/table each is aliased from moved. `iiif_manifest` and
// `dc_subject` were dropped outright: a manifest now lives per source
// (`map_images`, aliased back to `map_iiif_sources` below), and nothing
// replaces the subject field.
const MAP_COLUMNS =
  'id, slug, name, dc_description:description, year, year_label:date_label, creator, dc_publisher:publisher, holding_institution, collection, map_type, location, thumbnail, iiif_image, allmaps_id, annotation_url, georef_done:is_georeferenced, status, bbox, source_url, shelfmark, rights, original_title, physical_description, map_iiif_sources:map_images(iiif_image, iiif_manifest, source_type)';

export const load: PageServerLoad = async ({ params, url, locals }) => {
  const ref = decodeURIComponent(params.id);
  const supabase = adminClient();

  // Unfiltered, and gated below once the row is in hand: the status check needs
  // to know whether there is a session, and asking that on every request would
  // put an auth round trip in front of every share link and every crawl.
  const anyStatus = () => supabase.from('maps').select(MAP_COLUMNS);

  // The canonical address first: one query, no redirect, for every link minted
  // from today on.
  let { data: map } = await anyStatus().eq('slug', ref).maybeSingle();

  if (!map) {
    // A uuid is the old address. Anything else that is not a live slug might be
    // a retired one, so the alias table is the second place to look — it is the
    // only thing standing between a demoted name and a dead link.
    const id = isUuid(ref)
      ? ref
      : ((await supabase.from('map_slug_aliases').select('map_id').eq('slug', ref).maybeSingle())
          .data?.map_id ?? null);

    if (!id) throw error(404, 'No published map at that address');
    ({ data: map } = await anyStatus().eq('id', id).maybeSingle());
    if (!map) throw error(404, 'No published map at that address');

    // The reader stays in the language they arrived in: `/vi/catalog/<uuid>` is
    // rerouted to this loader with the prefix still on `url.pathname`, so
    // rebuilding the target without it would silently drop them into English.
    const prefix = localeFromPath(url.pathname) ? '/vi' : '';
    throw redirect(301, `${prefix}/catalog/${map.slug}`);
  }

  const published = map.status === 'public' || map.status === 'featured';
  if (!published) {
    const { session } = await locals.safeGetSession();
    if (!session) throw error(404, 'No published map at that address');
  }

  // The places this sheet names, most-attested first. Two jobs: it tells a
  // reader what is on the map before they open it, and it is the only crawl
  // path to the /place pages, which otherwise exist without being linked.
  const { data: places } = await supabase
    .from('place_names')
    .select('name_key, name, mentions, category')
    .contains('map_ids', [map.id])
    .order('mentions', { ascending: false })
    .limit(40);

  // IGN's own half-sheets, when this row is a third party's join of them.
  // `mirrors_original_for` is written by the mirroring script and points the
  // other way — from each original to the join it was fetched as the original
  // of — so this is the reverse read, and it is empty for all but the 58 cells
  // that have one.
  //
  // RLS carries the disclosure: while the originals are drafts, an anonymous
  // reader gets none and the page says nothing. It starts telling readers the
  // moment the halves are published, which is exactly when the claim becomes
  // true for them.
  const { data: originals } = await supabase
    .from('maps')
    .select('id, slug, name, year, sheet_half')
    .eq('extra_metadata->>mirrors_original_for', map.id)
    .order('sheet_half');

  // What the map's own live annotation is actually fit to, so the "Fix
  // georeference" link opens the right scan even when it's an R2-hosted
  // rescan rather than the original — see verifiedEditorSourceId.
  const editorSourceId = await verifiedEditorSourceId(map, map.map_iiif_sources ?? []);

  return { map, places: places ?? [], published, originals: originals ?? [], editorSourceId };
};
