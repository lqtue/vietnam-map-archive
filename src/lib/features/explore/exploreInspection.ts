import { writable } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { fetchMapsByIds } from '$lib/data/maps/service';
import { resolveSeriesKeys } from '$lib/data/maps/seriesKeys';
import type { MapListItem } from '$lib/data/maps/types';
import type { SeriesRef } from '$lib/map/stores/layersStore';

export function createExploreInspection(options: {
  supabase: SupabaseClient<Database>;
  maps: () => MapListItem[];
  open: (tab: 'info' | 'legend') => void;
  fetch?: typeof fetch;
}) {
  let request = 0;
  let cursors: (string | null)[] = [null];
  let nextCursor: string | null = null;
  let keys: string[] | null = null;
  let controller: AbortController | null = null;
  let state: {
    mapId: string | null;
    maps: MapListItem[];
    series: SeriesRef | null;
    loading: boolean;
    total: number | null;
    page: number;
    hasNext: boolean;
    error: string;
  } = {
    mapId: null,
    maps: [],
    series: null,
    loading: false,
    total: null,
    page: 1,
    hasNext: false,
    error: '',
  };
  const store = writable(state);
  function update(change: Partial<typeof state>) {
    state = { ...state, ...change };
    store.set(state);
  }
  async function inspectMap(detail: { mapId: string; tab: 'info' | 'legend' }) {
    const current = ++request;
    controller?.abort();
    const inSeries = state.maps.some((map) => map.id === detail.mapId);
    update({
      mapId: detail.mapId,
      loading: false,
      series: inSeries ? state.series : null,
      error: '',
    });
    options.open(detail.tab);
    if (![...options.maps(), ...state.maps].some((map) => map.id === detail.mapId)) {
      const maps = await fetchMapsByIds(options.supabase, [detail.mapId]);
      if (current === request) update({ maps });
    }
  }
  async function loadPage() {
    const series = state.series;
    if (!series) return;
    const current = ++request;
    controller?.abort();
    controller = new AbortController();
    update({ loading: true, error: '' });
    try {
      const resolved = keys ?? [
        ...new Set((await resolveSeriesKeys(options.supabase, series)).flat()),
      ];
      if (current !== request) return;
      keys = resolved;
      if (!resolved.length) {
        update({ maps: [], mapId: null, total: 0, hasNext: false });
        return;
      }
      const params = new URLSearchParams({
        filters: JSON.stringify({ series_key: keys }),
        limit: '60',
        sources: '1',
      });
      const cursor = cursors[state.page - 1];
      if (cursor) params.set('cursor', cursor);
      const response = await (options.fetch ?? fetch)(`/api/explore/maps?${params}`, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Series inspection failed (${response.status})`);
      const result = await response.json();
      if (current !== request) return;
      nextCursor = result.nextCursor;
      update({
        maps: result.maps,
        mapId: result.maps[0]?.id ?? null,
        total: result.total.maps,
        hasNext: !!nextCursor,
      });
    } catch (error) {
      if (current === request) {
        console.error('[explore] Series inspection failed', error);
        update({ error: 'Could not load the sheet page. Try again.' });
      }
    } finally {
      if (current === request) update({ loading: false });
    }
  }
  async function inspectSeries(detail: { ref: SeriesRef; tab: 'info' | 'legend' }) {
    cursors = [null];
    keys = null;
    nextCursor = null;
    update({ series: detail.ref, mapId: null, maps: [], total: null, page: 1, hasNext: false });
    options.open(detail.tab);
    await loadPage();
  }
  return {
    subscribe: store.subscribe,
    inspectMap,
    inspectSeries,
    nextPage() {
      if (state.loading || !nextCursor) return;
      cursors = [...cursors.slice(0, state.page), nextCursor];
      update({ page: state.page + 1 });
      void loadPage();
    },
    previousPage() {
      if (state.loading || state.page <= 1) return;
      update({ page: state.page - 1 });
      void loadPage();
    },
    retry: loadPage,
    destroy: () => {
      request += 1;
      controller?.abort();
    },
  };
}
