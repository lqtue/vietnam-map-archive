/**
 * Bidirectional URL ↔ mapStore + layerStore sync.
 *
 * Hash format:  #@<lat>,<lng>,<zoom>z,<rotation>r&base=<key>
 *
 * Examples:
 *   #@10.7765,106.7010,14z,0r
 *   #@10.7765,106.7010,14z,0r&base=g-satellite
 *
 * The hash carries the camera and the basemap only. The selected map lives in
 * the `?map=<id>` QUERY param, which is what /archive, /scan?mode=triage
 * and every share link point at — see `$lib/features/explore/exploreUrl.ts`. The hash
 * used to carry a second `&map=` copy of the same thing; that writer is gone.
 * Old links are still honoured: a `map=` found in the hash is migrated into
 * `?map=` on init so the page's normal deeplink handler picks it up.
 *
 * Design:
 *   - Store → URL: debounced (300ms) to avoid history spam
 *   - URL → Store: on popstate (back/forward) and on init
 *   - A suppression flag prevents infinite loops
 *   - Call `initUrlSync()` once in your root shell component's onMount
 *   - Call the returned teardown function in onDestroy
 */

import { get } from 'svelte/store';
import { replaceState, pushState } from '$app/navigation';
import type { MapStore, MapStoreValue } from './mapStore';
import type { LayerStore, LayerStoreValue } from './layerStore';
import { debounce } from '$lib/core/utils/debounce';

// ── Precision helpers ────────────────────────────────────────────────

function round(n: number, decimals: number): number {
  const f = Math.pow(10, decimals);
  return Math.round(n * f) / f;
}

// ── Serialisation ────────────────────────────────────────────────────

interface UrlState {
  lat?: number;
  lng?: number;
  zoom?: number;
  rotation?: number;
  basemap?: string;
  /** Legacy only — old links that still carry `&map=` in the hash. */
  legacyMapId?: string | null;
}

function stateToHash(map: MapStoreValue, layer: LayerStoreValue): string {
  const lat = round(map.lat, 5);
  const lng = round(map.lng, 5);
  const zoom = round(map.zoom, 2);
  const rot = round(map.rotation, 4);

  let hash = `@${lat},${lng},${zoom}z,${rot}r`;

  if (layer.basemap !== 'g-streets') {
    hash += `&base=${encodeURIComponent(layer.basemap)}`;
  }

  return hash;
}

function hashToState(hash: string): UrlState {
  const result: UrlState = {};
  if (!hash || hash === '#') return result;

  const raw = hash.startsWith('#') ? hash.slice(1) : hash;

  // Split on first '&' to separate camera from params
  const ampIdx = raw.indexOf('&');
  const cameraPart = ampIdx >= 0 ? raw.slice(0, ampIdx) : raw;
  const paramsPart = ampIdx >= 0 ? raw.slice(ampIdx + 1) : '';

  // Parse camera: @lat,lng,zoomz,rotationr
  if (cameraPart.startsWith('@')) {
    const body = cameraPart.slice(1); // remove @
    const segments = body.split(',');

    if (segments.length >= 2) {
      const lat = parseFloat(segments[0]);
      const lng = parseFloat(segments[1]);
      if (isFinite(lat) && isFinite(lng)) {
        result.lat = lat;
        result.lng = lng;
      }
    }

    if (segments.length >= 3) {
      const zoom = parseFloat(segments[2].replace('z', ''));
      if (isFinite(zoom)) result.zoom = zoom;
    }

    if (segments.length >= 4) {
      const rotation = parseFloat(segments[3].replace('r', ''));
      if (isFinite(rotation)) result.rotation = rotation;
    }
  }

  // Parse key=value params
  if (paramsPart) {
    const pairs = paramsPart.split('&');
    for (const pair of pairs) {
      const eqIdx = pair.indexOf('=');
      if (eqIdx < 0) continue;
      const key = pair.slice(0, eqIdx);
      const val = decodeURIComponent(pair.slice(eqIdx + 1));
      if (key === 'map') result.legacyMapId = val || null;
      if (key === 'base') result.basemap = val;
    }
  }

  return result;
}

// ── Sync engine ──────────────────────────────────────────────────────

export interface UrlSyncOptions {
  mapStore: MapStore;
  layerStore: LayerStore;
  /** Debounce interval for store→URL writes (ms). Default 300. */
  debounceMs?: number;
  /** Use replaceState instead of pushState for camera moves. Default true. */
  replaceOnMove?: boolean;
}

/**
 * Starts bidirectional sync between stores and the URL hash.
 *
 * Returns a teardown function to call on component destroy.
 *
 * Usage:
 * ```svelte
 * <script>
 *   import { onMount, onDestroy } from 'svelte';
 *   import { initUrlSync } from '$lib/map/stores/urlStore';
 *
 *   let teardown;
 *   onMount(() => { teardown = initUrlSync({ mapStore, layerStore }); });
 *   onDestroy(() => teardown?.());
 * </script>
 * ```
 */
export function initUrlSync(options: UrlSyncOptions): () => void {
  const { mapStore, layerStore, debounceMs = 300, replaceOnMove = true } = options;

  let suppressStoreToUrl = false;

  // ── URL → Stores (on init + popstate) ────────────────────────────

  function applyHashToStores() {
    const parsed = hashToState(window.location.hash);
    if (Object.keys(parsed).length === 0) return;

    suppressStoreToUrl = true;

    const mapPatch: Partial<MapStoreValue> = {};
    if (parsed.lat !== undefined) mapPatch.lat = parsed.lat;
    if (parsed.lng !== undefined) mapPatch.lng = parsed.lng;
    if (parsed.zoom !== undefined) mapPatch.zoom = parsed.zoom;
    if (parsed.rotation !== undefined) mapPatch.rotation = parsed.rotation;

    if (Object.keys(mapPatch).length > 0) {
      mapStore.setAll(mapPatch);
    }

    if (parsed.basemap) {
      layerStore.setBasemap(parsed.basemap);
    }

    // Release suppression on next tick so the store subscription fires
    // but we catch it before it writes back to the URL
    requestAnimationFrame(() => {
      suppressStoreToUrl = false;
    });
  }

  function onPopState() {
    applyHashToStores();
  }

  /**
   * Old share links put the selected map in the hash (`…&map=<id>`). Move it to
   * `?map=<id>` once on init so the page's deeplink handler — the single reader
   * of that param — treats it exactly like a fresh link. No-op when the query
   * already carries a map.
   */
  function migrateLegacyMapHash() {
    const { legacyMapId } = hashToState(window.location.hash);
    if (!legacyMapId) return;
    const url = new URL(window.location.href);
    if (url.searchParams.has('map')) return;
    url.searchParams.set('map', legacyMapId);
    replaceState(url, {});
  }

  // ── Stores → URL (debounced) ─────────────────────────────────────

  function writeHashFromStores() {
    if (suppressStoreToUrl) return;

    const mapVal = get(mapStore);
    const layerVal = get(layerStore);
    const hash = '#' + stateToHash(mapVal, layerVal);

    if (hash !== window.location.hash) {
      // Use SvelteKit's navigation helpers to avoid router conflicts
      const url = new URL(window.location.href);
      url.hash = hash;
      if (replaceOnMove) {
        replaceState(url, {});
      } else {
        pushState(url, {});
      }
    }
  }

  const debouncedWrite = debounce(writeHashFromStores, debounceMs);

  function scheduleWrite() {
    if (suppressStoreToUrl) return;
    debouncedWrite();
  }

  // ── Subscribe to stores ──────────────────────────────────────────

  const unsubMap = mapStore.subscribe(() => scheduleWrite());
  const unsubLayer = layerStore.subscribe(() => scheduleWrite());

  // ── Initialise from URL ──────────────────────────────────────────

  if (typeof window !== 'undefined') {
    migrateLegacyMapHash();
    applyHashToStores();
    window.addEventListener('popstate', onPopState);
  }

  // ── Teardown ─────────────────────────────────────────────────────

  return () => {
    unsubMap();
    unsubLayer();
    debouncedWrite.cancel();
    if (typeof window !== 'undefined') {
      window.removeEventListener('popstate', onPopState);
    }
  };
}
