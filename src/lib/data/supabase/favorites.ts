import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './types';

export async function fetchFavorites(
  supabase: SupabaseClient<Database>,
  userId: string
): Promise<string[]> {
  const { data, error } = await supabase
    .from('favorites')
    .select('map_id')
    .eq('user_id', userId);

  if (error) {
    console.error('Failed to fetch favorites:', error);
    return [];
  }

  return (data || []).map((row) => row.map_id);
}

export async function addFavorite(
  supabase: SupabaseClient<Database>,
  userId: string,
  mapId: string
): Promise<boolean> {
  const { error } = await supabase
    .from('favorites')
    .upsert({ user_id: userId, map_id: mapId }, { onConflict: 'user_id,map_id' });

  if (error) {
    console.error('Failed to add favorite:', error);
    return false;
  }

  return true;
}

export async function removeFavorite(
  supabase: SupabaseClient<Database>,
  userId: string,
  mapId: string
): Promise<boolean> {
  const { error } = await supabase
    .from('favorites')
    .delete()
    .eq('user_id', userId)
    .eq('map_id', mapId);

  if (error) {
    console.error('Failed to remove favorite:', error);
    return false;
  }

  return true;
}
