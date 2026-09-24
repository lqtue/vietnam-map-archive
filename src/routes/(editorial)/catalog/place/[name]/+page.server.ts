/**
 * Place page loader — one URL per attested place name.
 *
 * Server-rendered, like the share page: this is the page a search engine or a
 * person arriving from outside should be able to read without running any
 * JavaScript. Everything interactive is one click away at /explore.
 *
 * The gazetteer view (migration 067) does the grouping, so a name written three
 * ways across four decades is one page, not three. Draft maps are gated by the
 * view's `security_invoker` plus migration 065's read policy — but this loader
 * runs on the service client, so it filters published maps explicitly rather
 * than relying on that.
 */

import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
// `placeKey` *is* this route's slug→key rule (unaccent, lowercase, punctuation
// to single spaces) and is the client twin of Postgres's `place_key`. It used
// to be reimplemented here, which is one more copy to drift.
import { placeKey, placeCoreKey, keyToSlug } from '$lib/core/utils/placeKey';

export const load: PageServerLoad = async ({ params }) => {
  const raw = decodeURIComponent(params.name);
  const key = placeKey(raw);
  if (!key || key.length < 2) throw error(404, 'No such place');

  const supabase = adminClient();
  // Look the place up by its identity, not its spelling. `core_key` (migration
  // 081) is the proper name with the generic word stripped, so every slug this
  // route has ever minted still resolves: `/rue-catinat` and `/catinat` are one
  // row, and `/village-de-khanh-hoi` finds `Khánh Hội`.
  const { data: place } = await supabase
    .from('place_names')
    .select(
      'name_key, name, variants, years, first_year, last_year, map_ids, mentions, category, lng, lat, geom_rmse, core_key'
    )
    .eq('core_key', placeCoreKey(raw))
    .maybeSingle();

  if (!place) throw error(404, 'No place with that name in the archive');

  // One page, one address. A variant's slug is a real link, not a 404, but it
  // is not the canonical one — send it on rather than serving the same page at
  // two URLs, which is the duplicate-content case the root layout's canonical
  // tag exists to close.
  const slug = keyToSlug(place.name_key as string);
  if (slug !== keyToSlug(key)) throw redirect(301, `/catalog/place/${slug}`);

  // The sheets that name it, oldest first. Published only: an anonymous reader
  // must not learn a draft's title from a place page.
  const { data: maps } = await supabase
    .from('maps')
    // `year_label` stays this page's own field name; the column moved to
    // `date_label` (mig 095).
    .select(
      'id, name, year, year_label:date_label, thumbnail, holding_institution, location, status'
    )
    .in('id', (place.map_ids as string[]) ?? [])
    .in('status', ['public', 'featured'])
    .order('year');

  if (!maps?.length) throw error(404, 'No published map names that place');

  return { place, maps, slug };
};
