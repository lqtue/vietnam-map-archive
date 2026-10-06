import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchInstitutionCatalog } from '$lib/data/maps/institutions';
import { cartomundiSummary } from '$lib/data/maps/cartomundi';

export const load: PageServerLoad = async () => ({
  ...(await fetchInstitutionCatalog(adminClient())),
  cartomundi: cartomundiSummary(),
});
