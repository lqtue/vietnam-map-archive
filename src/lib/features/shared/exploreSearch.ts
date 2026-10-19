import { derived, get, writable } from 'svelte/store';
import { debounce } from '$lib/core/utils/debounce';
import type { CatalogSearchController } from './catalogSearch';
import type { Row, Selected } from './catalogFilters';

export interface ExploreSearchPage {
  maps: Row[];
  total: { maps: number; drafts: number; scout: number };
  facets: Record<string, Record<string, number>>;
  choices: {
    area: string[];
    region: string[];
    type: string[];
    institution: string[];
    series: { value: string; label: string }[];
  };
  yearBins: { decade: number; count: number }[];
  seriesCounts: Record<string, number>;
  nextCursor: string | null;
}

/** Selected layers are matched independently of the current archive page. */
export function createExplorePickedFilter(request: typeof fetch = fetch) {
  const ids = writable<string[] | null>(null);
  let inflight: AbortController | null = null;
  let generation = 0;
  let destroyed = false;
  let signature = '';
  return {
    ids: { subscribe: ids.subscribe },
    async update(query: string, filters: Selected, mapIds: string[]) {
      const nextSignature = JSON.stringify([query, filters, [...new Set(mapIds)].sort()]);
      if (destroyed || signature === nextSignature) return;
      signature = nextSignature;
      const ticket = ++generation;
      inflight?.abort();
      const active =
        !!query.trim() || Object.values(filters).some((values) => values.some(Boolean));
      if (!active) {
        ids.set(null);
        return;
      }
      const controller = new AbortController();
      inflight = controller;
      const matches: string[] = [];
      try {
        for (let start = 0; start < mapIds.length; start += 100) {
          const params = new URLSearchParams({
            q: query,
            filters: JSON.stringify(filters),
            ids: JSON.stringify(mapIds.slice(start, start + 100)),
            limit: '100',
          });
          const response = await request(`/api/explore/maps?${params}`, {
            signal: controller.signal,
          });
          if (!response.ok) throw new Error('Could not filter selected maps');
          const body: ExploreSearchPage = await response.json();
          matches.push(...body.maps.map((row) => row.id));
        }
        if (!destroyed && ticket === generation) ids.set(matches);
      } catch {
        // Keep selected layers accessible when filtering fails; the archive shows its own error.
        if (!destroyed && ticket === generation) ids.set(null);
      }
    },
    destroy() {
      destroyed = true;
      generation++;
      inflight?.abort();
    },
  };
}

/** Explore keeps one page of rows. Counts and choices always come from the whole query. */
export function createExploreSearch(
  options: { fetch?: typeof fetch; debounceMs?: number } = {}
): CatalogSearchController {
  const request = options.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const query = writable('');
  const selected = writable<Selected>({});
  const includeScout = writable(false);
  const loading = writable(false);
  const mapsReady = writable(false);
  const mapsError = writable(false);
  const data = writable<ExploreSearchPage | null>(null);
  const page = writable(1);
  const hasNext = derived(data, ($data) => !!$data?.nextCursor);
  let cursors: (string | null)[] = [null];
  let started = false;
  let destroyed = false;
  let generation = 0;
  let inflight: AbortController | null = null;
  let unsubscribe: (() => void)[] = [];

  async function load() {
    const ticket = ++generation;
    inflight?.abort();
    const controller = new AbortController();
    inflight = controller;
    loading.set(true);
    mapsReady.set(false);
    mapsError.set(false);
    const params = new URLSearchParams({
      q: get(query).trim(),
      filters: JSON.stringify(get(selected)),
      limit: '60',
    });
    const cursor = cursors[get(page) - 1];
    if (cursor) params.set('cursor', cursor);
    try {
      const response = await request(`/api/explore/maps?${params}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`Map search failed (${response.status})`);
      const next: ExploreSearchPage = await response.json();
      if (destroyed || ticket !== generation) return;
      data.set(next);
      mapsReady.set(true);
    } catch (error) {
      if (destroyed || ticket !== generation) return;
      mapsError.set(true);
      data.set(null);
      console.error('[explore search]', error);
    } finally {
      if (!destroyed && ticket === generation) loading.set(false);
    }
  }

  const schedule = debounce(() => void load(), options.debounceMs ?? 150);
  function reset() {
    // Invalidate immediately, including the debounce window before the next request.
    generation++;
    inflight?.abort();
    cursors = [null];
    page.set(1);
    data.set(null);
    mapsReady.set(false);
    mapsError.set(false);
    loading.set(true);
    schedule();
  }

  function start() {
    if (started || destroyed) return;
    started = true;
    unsubscribe = [query.subscribe(reset), selected.subscribe(reset)];
    schedule.cancel();
    void load();
  }

  function destroy() {
    destroyed = true;
    generation++;
    inflight?.abort();
    schedule.cancel();
    unsubscribe.forEach((stop) => stop());
    unsubscribe = [];
  }

  const rawMaps = derived(data, ($data) => $data?.maps ?? []);
  const emptyRows = writable<Row[]>([]);
  return {
    query,
    selected,
    includeScout,
    loading,
    mapsReady,
    mapsError,
    rawMaps,
    rawScout: emptyRows,
    filteredMaps: rawMaps,
    filteredScout: emptyRows,
    results: rawMaps,
    labels: writable([]),
    facets: derived(data, ($data) => $data?.facets ?? {}),
    total: derived(data, ($data) => $data?.total ?? { maps: 0, drafts: 0, scout: 0 }),
    areaChoices: derived(data, ($data) => $data?.choices.area ?? []),
    regionChoices: derived(data, ($data) => $data?.choices.region ?? []),
    typeChoices: derived(data, ($data) => $data?.choices.type ?? []),
    institutionChoices: derived(data, ($data) => $data?.choices.institution ?? []),
    seriesChoices: derived(data, ($data) => $data?.choices.series ?? []),
    yearBins: derived(data, ($data) => $data?.yearBins ?? []),
    seriesCounts: derived(data, ($data) => $data?.seriesCounts ?? {}),
    pagination: {
      page,
      hasNext,
      next() {
        const cursor = get(data)?.nextCursor;
        if (!cursor || get(loading)) return;
        cursors = [...cursors.slice(0, get(page)), cursor];
        page.update((n) => n + 1);
        void load();
      },
      previous() {
        if (get(page) <= 1 || get(loading)) return;
        page.update((n) => n - 1);
        void load();
      },
    },
    toggleFacet(group, value) {
      selected.update((s) => {
        const values = new Set(s[group] ?? []);
        if (values.has(value)) values.delete(value);
        else values.add(value);
        return { ...s, [group]: [...values] };
      });
    },
    clearGroup(group) {
      selected.update((s) => ({ ...s, [group]: [] }));
    },
    setSingle(group, value) {
      selected.update((s) => ({ ...s, [group]: value ? [value] : [] }));
    },
    start,
    refresh() {
      if (destroyed) return;
      schedule.cancel();
      void load();
    },
    destroy,
  };
}
