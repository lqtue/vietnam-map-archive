import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import {
  cartomundiItemsBySeries,
  cartomundiSeriesById,
  cartomundiSheetsBySeries,
} from '$lib/data/maps/cartomundi';

const ARCHIVE_SERIES: Record<string, string> = {
  '175': 'indochine-1-25-000-tonkin-thanh-hoa',
  '243': 'indochine-1-25-000-tonkin-thanh-hoa',
  '325': 'indochine-1-100-000-1st-edition-sgi-1900-1947',
  '561': 'indochine-1-100-000-2nd-edition-sgi-1947-1959',
};

export const load: PageServerLoad = async ({ params }) => {
  const series = cartomundiSeriesById(params.id);
  if (!series) error(404, 'CartoMundi series not found');
  const key = ARCHIVE_SERIES[params.id];
  return {
    series,
    sheets: cartomundiSheetsBySeries(params.id),
    items: cartomundiItemsBySeries(params.id),
    archiveHref: key ? `/catalog/series/${key}` : null,
  };
};
