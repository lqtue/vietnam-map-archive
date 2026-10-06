import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { CATALOG_AREAS, coverageAreas } from '$lib/core/catalogAreas';
import { CATALOG_REGIONS, geographicRegions } from '$lib/core/catalogRegions';
import { readAllParallel } from '$lib/data/supabase/paged';

/** One complete public read: no drafts, no silent PostgREST 1,000-row cutoff. */
export async function fetchAreaMaps(client: SupabaseClient<Database>) {
  const { data, error } = await readAllParallel((from, to) =>
    client
      .from('maps')
      .select(
        'id,slug,name,year,date_label,thumbnail,region,regions,collection,holding_institution'
      )
      .in('status', ['public', 'featured'])
      .order('id')
      .range(from, to)
  );
  if (error) throw error;
  return data;
}

export async function fetchCoverageIndex(client: SupabaseClient<Database>) {
  const { data: maps, error } = await readAllParallel((from, to) =>
    client
      .from('maps')
      .select('id,region,regions')
      .in('status', ['public', 'featured'])
      .order('id')
      .range(from, to)
  );
  if (error) throw error;
  const areas = CATALOG_AREAS.map((area) => ({
    ...area,
    count: maps.filter((map) => coverageAreas(map).includes(area.name)).length,
  })).filter((area) => area.count > 0);
  const counts = new Map<string, number>();
  for (const map of maps)
    for (const key of geographicRegions(map)) counts.set(key, (counts.get(key) ?? 0) + 1);
  const regions = CATALOG_REGIONS.map(({ key, en, vi }) => ({
    key,
    en,
    vi,
    count: counts.get(key) ?? 0,
  })).filter((region) => region.count > 0);
  return { areas, regions };
}

export async function fetchAreaIndex(client: SupabaseClient<Database>) {
  return (await fetchCoverageIndex(client)).areas;
}
