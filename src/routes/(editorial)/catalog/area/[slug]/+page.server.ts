import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { CATALOG_AREAS, coverageAreas } from '$lib/core/catalogAreas';
import { fetchAreaMaps } from '$lib/data/maps/areas';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';

export const load: PageServerLoad = async ({ params }) => {
  const area = CATALOG_AREAS.find((a) => a.slug === params.slug);
  if (!area) error(404, 'No such area');
  const maps = await fetchAreaMaps(adminClient()).catch((err) =>
    dbError(err, 'Area maps could not be loaded')
  );
  const covered = maps.filter((map) => coverageAreas(map).includes(area.name));
  if (!covered.length) error(404, 'No published maps for this area');
  covered.sort((a, b) => (a.year ?? Infinity) - (b.year ?? Infinity) || a.id.localeCompare(b.id));
  return { area, maps: covered };
};
