/**
 * geoMapSetup.ts — the store pair every geo-map mode (/explore, /explore?mode=annotate,
 * /explore?mode=story, /trip) instantiates.
 */
import { onDestroy } from 'svelte';
import { createMapStore } from '$lib/map/stores/mapStore';
import { createLayerStore } from '$lib/map/stores/layerStore';
import { topOverlay } from '$lib/map/stores/layersStore';

/**
 * Call during component init: the returned stores are per-instance, and the
 * layersStore → mapStore mirror below is torn down with the component.
 */
export function createGeoMapStores() {
  const mapStore = createMapStore();
  const layerStore = createLayerStore();
  // One-way mirror, layersStore.overlays[0] → mapStore.activeMapId. The stack is
  // the source of truth; activeMapId is what the legacy readers
  // (MapWorkspace.selectedMap, story playback, share) still look at. The URL no
  // longer reads it — `?map=` is the only map-in-URL mechanism now.
  const unmirror = topOverlay.subscribe((ref) =>
    mapStore.setActiveMap(ref?.mapId ?? null, ref?.allmapsId ?? null)
  );
  onDestroy(unmirror);
  return { mapStore, layerStore };
}
