import { writable } from 'svelte/store';
import type { MapListItem } from '$lib/data/maps/types';
import { resolveMapRef } from '$lib/data/maps/resolveRef';
import { matchMapsAtPoint, type ResolvedMap } from './spatialLookup';

const CACHE_LIMIT = 100;
const REQUEST_LIMIT = 4;

/** Metadata follows explicit selections; coverage stays a bounded server page. */
export function createExploreRuntime(fetcher: typeof fetch = fetch) {
  const maps = writable<MapListItem[]>([]);
  const error = writable<string | null>(null);
  const coverage = writable({
    matches: [] as ResolvedMap[],
    total: 0,
    hasNext: false,
    loading: false,
    error: false,
    page: 1,
  });
  const cache = new Map<string, MapListItem>();
  const complete = new Set<string>();
  const pending = new Map<string, Promise<MapListItem | null>>();
  const failed = new Set<string>();
  let pinned = new Set<string>();
  let active = 0;
  let disposed = false;
  const waiting: (() => void)[] = [];
  const abort = new AbortController();
  let point: [number, number] | null = null;
  let coverageCursor: string | null = null;
  let coverageRequest: AbortController | null = null;
  let coveragePage = 1;

  function publish() {
    for (const [id] of cache) {
      if (cache.size <= CACHE_LIMIT) break;
      if (!pinned.has(id)) {
        cache.delete(id);
        complete.delete(id);
      }
    }
    maps.set([...cache.values()]);
  }
  function remember(map: MapListItem, full = false): MapListItem {
    if (!disposed) {
      const previous = cache.get(map.id);
      cache.delete(map.id);
      cache.set(map.id, previous ? { ...previous, ...map } : map);
      if (full) complete.add(map.id);
      publish();
    }
    return map;
  }
  async function read(ref: string, direction = 0): Promise<MapListItem | null> {
    if (active >= REQUEST_LIMIT) await new Promise<void>((resolve) => waiting.push(resolve));
    if (disposed) return null;
    active += 1;
    try {
      const params = new URLSearchParams({ ref, direction: String(direction) });
      const response = await fetcher(`/api/explore/map?${params}`, { signal: abort.signal });
      if (!response.ok) throw new Error('Could not load the selected map.');
      const body = (await response.json()) as { map: MapListItem | null };
      if (!body.map && !direction) throw new Error('Map not found');
      return body.map ? remember(body.map, true) : null;
    } finally {
      active -= 1;
      waiting.shift()?.();
    }
  }
  function ensure(ref: string): Promise<MapListItem | null> {
    const found = resolveMapRef([...cache.values()], ref);
    if (found && complete.has(found.id)) return Promise.resolve(remember(found));
    const inflight = pending.get(ref);
    if (inflight) return inflight;
    const task = read(ref)
      .then((map) => {
        failed.delete(ref);
        if (!failed.size) error.set(null);
        return map;
      })
      .catch(() => {
        if (!disposed) {
          failed.add(ref);
          error.set('Could not load selected map details.');
        }
        return null;
      })
      .finally(() => pending.delete(ref));
    pending.set(ref, task);
    return task;
  }
  async function step(ref: string, direction: -1 | 1) {
    try {
      return await read(ref, direction);
    } catch {
      if (!disposed) error.set('Could not load the next map. Try the arrow again.');
      return null;
    }
  }
  async function locate(nextPoint: [number, number], next = false) {
    point = nextPoint;
    if (!next) {
      coverageCursor = null;
      coveragePage = 1;
    }
    coverageRequest?.abort();
    const request = new AbortController();
    coverageRequest = request;
    coverage.update((value) => ({ ...value, loading: true, error: false }));
    try {
      const params = new URLSearchParams({ point: JSON.stringify(point), limit: '100' });
      if (next && coverageCursor) params.set('cursor', coverageCursor);
      const response = await fetcher(`/api/explore/maps?${params}`, { signal: request.signal });
      if (!response.ok) throw new Error('Coverage lookup failed');
      const body = (await response.json()) as {
        maps: MapListItem[];
        total: { maps: number };
        nextCursor: string | null;
      };
      if (disposed || request.signal.aborted) return;
      coverageCursor = body.nextCursor;
      if (next) coveragePage++;
      coverage.set({
        matches: matchMapsAtPoint(body.maps, point[0], point[1], true),
        total: body.total.maps,
        hasNext: !!coverageCursor,
        loading: false,
        error: false,
        page: coveragePage,
      });
    } catch {
      if (!disposed && !request.signal.aborted) {
        coverage.set({
          matches: [],
          total: 0,
          hasNext: false,
          loading: false,
          error: true,
          page: coveragePage,
        });
      }
    }
  }
  return {
    maps: { subscribe: maps.subscribe },
    error: { subscribe: error.subscribe },
    coverage: { subscribe: coverage.subscribe },
    remember,
    ensure,
    step,
    locate,
    pin(ids: string[]) {
      pinned = new Set(ids);
      publish();
      for (const id of ids) void ensure(id);
    },
    nextCoverage: () => point && locate(point, true),
    resetCoverage: () => point && locate(point),
    retry: () => {
      for (const ref of failed) void ensure(ref);
    },
    destroy() {
      disposed = true;
      abort.abort();
      coverageRequest?.abort();
      waiting.splice(0).forEach((resolve) => resolve());
    },
  };
}
