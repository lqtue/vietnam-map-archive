import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchInstitution } from '$lib/data/maps/institutions';

export const load: PageServerLoad = async ({ params }) => {
  const institution = await fetchInstitution(adminClient(), params.slug);
  if (!institution) error(404, 'No such institution');
  return institution;
};
