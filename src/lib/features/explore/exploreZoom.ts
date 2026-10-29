/**
 * exploreZoom.ts — overlay-stack + camera helpers for /explore.
 *
 * Deliberately NOT `$lib/features/stories/shared/mapPickHandlers.createMapPickHandlers`: that
 * factory clears the overlay stack on every pick (the story and annotate
 * single-overlay behaviour), whereas /explore is additive — tapping a row adds
 * to the stack and removal is explicit via the Layers panel ×.
 */
import { get } from 'svelte/store';
import type OlMap from 'ol/Map';
import { transform, transformExtent } from 'ol/proj';
import type { MapListItem } from '$lib/data/maps/types';
import type { MapStore } from '$lib/map/stores/mapStore';
import { layersStore, toHistoricalRef } from '$lib/map/stores/layersStore';
import { resolveBounds, type Bbox } from '$lib/core/geo/mapBounds';
import { bboxContainsPoint, bboxOnScreen } from './spatialLookup';
import { boundsCenter, boundsZoom } from '$lib/ui/searchUtils';

export interface ExploreZoom {
  /** Adds `map` to the overlay stack. Returns false if it has no annotation or is already on. */
  addMapOverlay(map: MapListItem, options?: { clear?: boolean }): boolean;
  setViewFromBounds(bounds: Bbox): void;
  /**
   * Bring a box (or a point, as a zero-size box) into view without losing the
   * reader's place: nothing moves if it is already on screen, otherwise the
   * camera pans to it at the reader's own zoom. False before the map exists.
   */
  reveal(target: Bbox): boolean;
  zoomToMap(map: MapListItem, options?: { force?: boolean }): Promise<void>;
}

export function createExploreZoom(
  mapStore: MapStore,
  getMap: () => OlMap | null = () => null
): ExploreZoom {
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

  // A jump to a new zoom is what lost readers their place: the street they
  // were reading vanished and nothing on screen said where they had landed.
  // A pan at the same zoom keeps both, and the animation shows the direction.
  function reveal(target: Bbox): boolean {
    const map = getMap();
    const size = map?.getSize();
    if (!map || !size) return false;
    const view = map.getView();
    const projection = view.getProjection();
    const viewport = transformExtent(view.calculateExtent(size), projection, 'EPSG:4326') as Bbox;
    if (bboxOnScreen(viewport, target)) return true;
    const c = boundsCenter(target);
    view.cancelAnimations();
    view.animate({ center: transform([c.lng, c.lat], 'EPSG:4326', projection), duration: 400 });
    return true;
  }

  async function zoomToMap(map: MapListItem, { force = false } = {}) {
    const bounds = await resolveBounds(map);
    if (!bounds) return;
    if (!force && reveal(bounds)) return;
    // No map yet: skip the zoom if the sheet already covers the view centre.
    const view = get(mapStore);
    if (!force && bboxContainsPoint(bounds, view.lng, view.lat)) return;
    setViewFromBounds(bounds);
  }

  return { addMapOverlay, setViewFromBounds, reveal, zoomToMap };
}
