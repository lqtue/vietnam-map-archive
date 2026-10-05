import { writable } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { fetchSeriesSheets, fetchMapsByIds } from '$lib/data/maps/service';
import type { MapListItem } from '$lib/data/maps/types';
import type { SeriesRef } from '$lib/map/stores/layersStore';

export function createExploreInspection(options: {
  supabase: SupabaseClient<Database>;
  maps: () => MapListItem[];
  open: (tab: 'info' | 'legend') => void;
}) {
  let request = 0;
  let state: {
    mapId: string | null;
    maps: MapListItem[];
    series: SeriesRef | null;
    loading: boolean;
  } = { mapId: null, maps: [], series: null, loading: false };
  const store = writable(state);
  function update(change: Partial<typeof state>) {
    state = { ...state, ...change };
    store.set(state);
  }
  async function inspectMap(detail: { mapId: string; tab: 'info' | 'legend' }) {
    const current = ++request;
    update({
      mapId: detail.mapId,
      loading: false,
      series: state.maps.some((map) => map.id === detail.mapId) ? state.series : null,
    });
    options.open(detail.tab);
    if (![...options.maps(), ...state.maps].some((map) => map.id === detail.mapId)) {
      const maps = await fetchMapsByIds(options.supabase, [detail.mapId]);
      if (current === request) update({ maps: [...state.maps, ...maps] });
    }
  }
  async function inspectSeries(detail: { ref: SeriesRef; tab: 'info' | 'legend' }) {
    const current = ++request;
    update({ series: detail.ref, mapId: null, maps: [], loading: true });
    options.open(detail.tab);
    try {
      const members = await Promise.all(
        detail.ref.parts.map((part) =>
          fetchSeriesSheets(
            options.supabase,
            part.seriesKey ?? detail.ref.key,
            part.seriesKey ? undefined : part.collection
          )
        )
      );
      const ids = [...new Set(members.flat().map((member) => member.id))];
      let maps = options.maps().filter((map) => ids.includes(map.id));
      const missing = ids.filter((id) => !maps.some((map) => map.id === id));
      for (let from = 0; from < missing.length; from += 100) {
        if (current !== request) return;
        maps = [
          ...maps,
          ...(await fetchMapsByIds(options.supabase, missing.slice(from, from + 100))),
        ];
      }
      if (current !== request) return;
      maps = maps.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
      update({ maps, mapId: maps[0]?.id ?? null });
    } catch (error) {
      console.error('[explore] Series inspection failed', error);
    } finally {
      if (current === request) update({ loading: false });
    }
  }
  return {
    subscribe: store.subscribe,
    inspectMap,
    inspectSeries,
    destroy: () => {
      request += 1;
    },
  };
}
