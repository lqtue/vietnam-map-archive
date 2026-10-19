import type { SupabaseClient } from '@supabase/supabase-js';
import type { SeriesRef } from '$lib/map/stores/layersStore';

/** Resolve saved collection labels only when their original durable key is absent. */
export async function resolveSeriesKeys(db: SupabaseClient, ref: SeriesRef): Promise<string[][]> {
  return Promise.all(
    ref.parts.map(async (part) => {
      const key = part.seriesKey ?? ref.key;
      const exact = await db.from('map_series').select('key').eq('key', key).limit(1);
      if (exact.error) throw exact.error;
      if (exact.data?.length) return [key];
      const legacy = await db
        .from('map_series')
        .select('key')
        .eq('collection', part.collection)
        .order('key')
        .limit(100);
      if (legacy.error) throw legacy.error;
      return (legacy.data ?? []).flatMap((row) => (row.key ? [row.key as string] : []));
    })
  );
}
