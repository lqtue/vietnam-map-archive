/**
 * The signed-in reader's favorited map ids, shared by every heart in the
 * catalog (grid card, list row, drawer, sheet page) so they agree and the
 * list is fetched once per session. The home page keeps its own copy.
 * Browser-only: only ever filled from `onMount`, never during SSR.
 */
import { writable, get } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { fetchFavorites, addFavorite, removeFavorite } from '$lib/data/supabase/favorites';

export const favoriteIds = writable<Set<string>>(new Set());

let loadedFor: string | null = null;
let inFlight: Promise<void> | null = null;

export function loadFavoriteIds(supabase: SupabaseClient<Database>, userId: string): Promise<void> {
  if (loadedFor === userId) return inFlight ?? Promise.resolve();
  loadedFor = userId;
  inFlight = fetchFavorites(supabase, userId).then((ids) => favoriteIds.set(new Set(ids)));
  return inFlight;
}

/** Optimistic flip; puts it back if the write fails. */
export async function toggleFavorite(
  supabase: SupabaseClient<Database>,
  userId: string,
  mapId: string
): Promise<void> {
  const was = get(favoriteIds).has(mapId);
  const set = (on: boolean) =>
    favoriteIds.update((s) => {
      const next = new Set(s);
      if (on) next.add(mapId);
      else next.delete(mapId);
      return next;
    });
  set(!was);
  const ok = was
    ? await removeFavorite(supabase, userId, mapId)
    : await addFavorite(supabase, userId, mapId);
  if (!ok) set(was);
}
