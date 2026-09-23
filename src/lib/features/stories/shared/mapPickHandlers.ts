/**
 * mapPickHandlers.ts — the catalog pick / zoom handlers shared by the
 * two-sidebar map editors (the story and annotate modes).
 *
 * `mapList` and `shellMap` are passed as getters because both are `bind:`-ed
 * from MapWorkspace and change after this factory runs.
 */
import type OlMap from 'ol/Map';
import type { MapListItem } from '$lib/data/maps/types';
import type { MapStore } from '$lib/map/stores/mapStore';
import { toHistoricalRef, layersStore as globalLayersStore } from '$lib/map/stores/layersStore';
import { fetchAnnotationBounds } from '$lib/core/geo/mapBounds';
import { boundsCenter, boundsZoom } from '$lib/ui/searchUtils';

export interface MapPickHandlerOptions {
  mapStore: MapStore;
  mapList: () => MapListItem[];
  layersStore?: typeof globalLayersStore;
  /** When supplied, zoom-to-map also glides the OL view (annotate-mode behaviour). */
  shellMap?: () => OlMap | null;
  /** A catalog-row click adds to the overlay stack instead of replacing it
   *  (Studio mode — a project can hold several maps). Off by default: Create
   *  mode's Browse click means "pin this map here". */
  stackOverlays?: boolean;
}

export function createMapPickHandlers(opts: MapPickHandlerOptions) {
  const { mapStore, mapList, shellMap, stackOverlays = false } = opts;
  const layers = opts.layersStore ?? globalLayersStore;

  async function resolveBounds(map: MapListItem) {
    const known = map.bounds ?? map.bbox ?? null;
    if (known) return known;
    const src = map.annotation_url ?? map.allmaps_id;
    return src ? await fetchAnnotationBounds(src) : null;
  }

  async function handleZoomToMap(event: CustomEvent<{ map: MapListItem }>) {
    const bounds = await resolveBounds(event.detail.map);
    if (!bounds) return;
    const center = boundsCenter(bounds);
    const zoom = boundsZoom(bounds);
    mapStore.setView({ lng: center.lng, lat: center.lat, zoom });
    const ol = shellMap?.();
    if (ol) {
      const { fromLonLat } = await import('ol/proj');
      ol.getView().animate({ center: fromLonLat([center.lng, center.lat]), zoom, duration: 400 });
    }
  }

  function handleZoomToOverlay(e: CustomEvent<{ mapId: string }>) {
    const m = mapList().find((x) => x.id === e.detail.mapId);
    if (m) handleZoomToMap(new CustomEvent('zoomToMap', { detail: { map: m } }));
  }

  /** Catalog row click = swap the top overlay to this map, then frame it.
   *  With `stackOverlays`, it adds to the stack instead of replacing it. */
  async function handlePickMap(event: CustomEvent<MapListItem>) {
    const item = event.detail;
    if (!item?.id) return;
    const map = mapList().find((m) => m.id === item.id) ?? ({ ...item } as MapListItem);
    const ref = toHistoricalRef(map);
    if (ref.allmapsId) {
      if (!stackOverlays) layers.clearOverlays();
      layers.addOverlay(ref);
    }
    const bounds = await resolveBounds(map);
    if (!bounds) return;
    const center = boundsCenter(bounds);
    mapStore.setView({ lng: center.lng, lat: center.lat, zoom: boundsZoom(bounds) });
  }

  function handlePickLocation(
    event: CustomEvent<{
      lat: number;
      lng: number;
      bbox?: [number, number, number, number];
      zoom?: number;
    }>
  ) {
    const { lat, lng, bbox, zoom } = event.detail;
    if (bbox) {
      const c = boundsCenter(bbox);
      mapStore.setView({ lng: c.lng, lat: c.lat, zoom: boundsZoom(bbox) });
    } else {
      mapStore.setView({ lng, lat, zoom: zoom ?? 15 });
    }
  }

  return { handlePickMap, handleZoomToMap, handleZoomToOverlay, handlePickLocation };
}
