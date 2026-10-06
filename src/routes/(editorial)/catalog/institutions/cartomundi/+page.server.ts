import type { PageServerLoad } from './$types';
import { cartomundiSeries, cartomundiSummary } from '$lib/data/maps/cartomundi';

export const load: PageServerLoad = async () => ({
  series: cartomundiSeries(),
  summary: cartomundiSummary(),
});
