/**
 * useMapList.ts — fetches the map catalogue + backfills bounds in the background.
 *
 * Returns a Svelte-friendly object whose `subscribe`-style stores can be read.
 * Pattern: caller awaits `loadMaps(supabase)` once, then reads `$maps` reactively.
 *
 * Centralises a fetch flow that was duplicated across ViewMode/CreateMode/AnnotateMode.
 */
import { writable, type Readable, type Writable } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { MapListItem } from '$lib/data/maps/types';
import { fetchMaps } from '$lib/data/maps/service';
import {
  annotationSourceFor,
  fetchMultipleBounds,
  unresolvedBoundsSources,
} from '$lib/core/geo/mapBounds';

export interface MapListController {
  /** Current list of maps. Reactive. */
  maps: Readable<MapListItem[]>;
  /** Fetch maps from Supabase, then backfill bounds asynchronously. Safe to call multiple times. */
  loadMaps: (supabase: SupabaseClient) => Promise<MapListItem[]>;
  /** Direct setter for callers that want to inject a custom list (e.g. tests, URL-param flows). */
  setMaps: (next: MapListItem[]) => void;
}

export function createMapList(): MapListController {
  const store: Writable<MapListItem[]> = writable([]);

  async function loadMaps(supabase: SupabaseClient): Promise<MapListItem[]> {
    const maps = await fetchMaps(supabase);
    store.set(maps);
    // Background: fetch and merge bounds for the maps that still need it —
    // which today is none of them, and that is the point. This asked every
    // georeferenced row for its annotation regardless of the `bbox` the same
    // row was already carrying: 102 requests and ~200 kB on every cold
    // /explore load, competing for the connection pool with the basemap's own
    // byte ranges and the first sheet's tiles. `unresolvedBoundsSources` is
    // the ladder /explore's own probe already climbed; the two are one list
    // now, so a map is asked about once or not at all.
    //
    // Drafts are included because the list is whatever this reader could read.
    const sources = unresolvedBoundsSources(maps, true);
    if (sources.length > 0) {
      fetchMultipleBounds(sources).then((boundsMap) => {
        store.update((cur) =>
          cur.map((m) => {
            const src = annotationSourceFor(m);
            const b = src ? boundsMap.get(src) : undefined;
            return b ? { ...m, bounds: b } : m;
          })
        );
      });
    }
    return maps;
  }

  return {
    maps: { subscribe: store.subscribe },
    loadMaps,
    setMaps: store.set,
  };
}
