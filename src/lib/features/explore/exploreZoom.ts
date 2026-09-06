/**
 * exploreZoom.ts — overlay-stack + camera helpers for /explore.
 *
 * Deliberately NOT `$lib/features/stories/shared/mapPickHandlers.createMapPickHandlers`: that
 * factory clears the overlay stack on every pick (the /explore?mode=story and /explore?mode=annotate
 * single-overlay behaviour), whereas /explore is additive — tapping a row adds
 * to the stack and removal is explicit via the Layers panel ×.
 */
import { get } from 'svelte/store';
import type { MapListItem } from '$lib/data/maps/types';
import type { MapStore } from '$lib/map/stores/mapStore';
import { layersStore, toHistoricalRef } from '$lib/map/stores/layersStore';
import { resolveBounds, type Bbox } from '$lib/core/geo/mapBounds';
import { bboxContainsPoint } from './spatialLookup';
import { boundsCenter, boundsZoom } from '$lib/ui/searchUtils';

export interface ExploreZoom {
  /** Adds `map` to the overlay stack. Returns false if it has no annotation or is already on. */
  addMapOverlay(map: MapListItem, options?: { clear?: boolean }): boolean;
  setViewFromBounds(bounds: Bbox): void;
  zoomToMap(map: MapListItem, options?: { force?: boolean }): Promise<void>;
}

export function createExploreZoom(mapStore: MapStore): ExploreZoom {
  function addMapOverlay(map: MapListItem, { clear = false } = {}): boolean {
    const ref = toHistoricalRef(map);
    if (!ref.allmapsId) return false;
    if (clear) layersStore.clearOverlays();
    if (layersStore.isOverlay(map.id)) return false;
    layersStore.addOverlay(ref);
    return true;
  }

  function setViewFromBounds(bounds: Bbox) {
    const c = boundsCenter(bounds);
    mapStore.setView({ lng: c.lng, lat: c.lat, zoom: boundsZoom(bounds) });
  }

  async function zoomToMap(map: MapListItem, { force = false } = {}) {
    const bounds = await resolveBounds(map);
    if (!bounds) return;
    // Skip the zoom if the map already covers the current viewport centre —
    // avoids yanking the camera when the user adds something they're on.
    const view = get(mapStore);
    if (!force && bboxContainsPoint(bounds, view.lng, view.lat)) return;
    setViewFromBounds(bounds);
  }

  return { addMapOverlay, setViewFromBounds, zoomToMap };
}
