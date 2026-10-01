/**
 * What the front page still needs from the browser.
 *
 * The catalogue itself moved to `(editorial)/+page.server.ts` — it is the same
 * for every reader, so it belongs in the HTML. What is left is the part that
 * cannot be: the signed-in reader's favorites, and the thumbnails a map has to
 * be asked for one annotation at a time.
 *
 * Nothing here is home-specific except the 400px thumbnail width, which is
 * what `FeaturedSheet` renders.
 */

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import type { MapListItem } from '$lib/data/maps/types';
import type { SeriesIndexEntry } from '$lib/data/maps/seriesIndex';
import { fetchMapsByIds } from '$lib/data/maps/service';
import { fetchFavorites } from '$lib/data/supabase/favorites';
import { annotationUrlForSource } from '$lib/core/iiif/annotationUrl';

type Client = SupabaseClient<Database>;

/** A survey standing in the front page's strip, with one of its own scans as the picture. */
export interface FeaturedSeries {
  entry: SeriesIndexEntry;
  thumbnail?: string;
}

export interface HomeFavorites {
  maps: MapListItem[];
  ids: string[];
}

/**
 * sessionStorage rather than localStorage, and it caches misses as well as
 * hits: a `null` records that a source has no annotation to derive a thumbnail
 * from, which stops being true the moment someone georeferences that sheet.
 * One tab's lifetime is the right memory for a fact with that shelf life.
 */
const THUMB_CACHE_KEY = 'vma-thumb-cache-v1';

function readCache(): Record<string, string | null> {
  try {
    return JSON.parse(sessionStorage.getItem(THUMB_CACHE_KEY) ?? '{}');
  } catch {
    return {};
  }
}

function writeCache(source: string, value: string | null): void {
  try {
    sessionStorage.setItem(THUMB_CACHE_KEY, JSON.stringify({ ...readCache(), [source]: value }));
  } catch {
    /* private mode or quota — the cache is an optimisation, not state */
  }
}

/** The IIIF image a map's Allmaps annotation points at, 400px wide. */
async function fetchThumbnailUrl(source: string): Promise<string | null> {
  const cache = readCache();
  if (Object.prototype.hasOwnProperty.call(cache, source)) return cache[source];

  let url: string | null = null;
  try {
    const response = await fetch(annotationUrlForSource(source));
    if (response.ok) {
      const id = (await response.json())?.items?.[0]?.target?.source?.id;
      if (id) url = `${id}/full/,400/0/default.jpg`;
    }
  } catch {
    /* offline or CORS — falls through as a miss, same as a 404 */
  }
  writeCache(source, url);
  return url;
}

/**
 * The reader's favorites, and only those maps. It used to fetch the whole
 * catalogue and filter it in the browser, which is the same rows every visitor
 * already has in the page — for a handful of ids.
 */
export async function loadFavorites(supabase: Client, userId?: string): Promise<HomeFavorites> {
  if (!userId) return { maps: [], ids: [] };

  const ids = await fetchFavorites(supabase, userId);
  return { maps: await fetchMapsByIds(supabase, ids), ids };
}

/**
 * Thumbnails for the maps the page can actually show, resolved in one pass and
 * returned as one Map. Assigning per resolution — which is what a `.set()` plus
 * a self-assignment in the loop does — re-renders the featured sheet once per
 * network round trip.
 *
 * Maps that already carry a `thumbnail` column, or that have no IIIF source to
 * ask, are skipped rather than fetched and discarded.
 */
export async function resolveThumbnails(maps: MapListItem[]): Promise<Map<string, string>> {
  const entries = await Promise.all(
    maps
      .filter((m) => !m.thumbnail && (m.annotation_url ?? m.allmaps_id))
      .map(async (m) => {
        const url = await fetchThumbnailUrl((m.annotation_url ?? m.allmaps_id) as string);
        return url ? ([m.id, url] as [string, string]) : null;
      })
  );
  return new Map(entries.filter((e): e is [string, string] => e !== null));
}
