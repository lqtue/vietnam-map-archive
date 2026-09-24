import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';

/**
 * Tally one row per map open (migration 049).
 *
 * This is the only way to learn which maps get looked at: Cloudflare Web
 * Analytics reports requestPath and has no query-string dimension, so
 * /explore's `?map=` is invisible to it.
 *
 * Fire-and-forget by design — a dropped tally must never interrupt opening a
 * map, so nothing awaits the insert and failures only warn.
 */
export function recordMapOpen(supabase: SupabaseClient<Database>, mapId: string): void {
  void supabase
    .from('map_views')
    .insert({ map_id: mapId })
    .then(({ error }) => {
      if (error) console.warn('recordMapOpen:', error.message);
    });
}
