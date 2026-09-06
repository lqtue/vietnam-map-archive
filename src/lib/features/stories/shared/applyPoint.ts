/**
 * applyPoint.ts — the "show this story point on the map" primitive.
 *
 * Three call sites used to hand-roll this: /explore?mode=story (editor + preview),
 * /trip/[id] (playback) and /explore (story playback). Each one resolved the
 * point's `overlayMapId` against the catalogue, swapped the overlay stack and
 * framed the camera at zoom 17.
 */
import type { MapListItem } from '$lib/data/maps/types';
import type { StoryPoint } from './types';
import type { MapStore } from '$lib/map/stores/mapStore';
import { toHistoricalRef, layersStore } from '$lib/map/stores/layersStore';

export type LayersStore = typeof layersStore;

/** Zoom a story playback frames a point at when the point pins no camera. */
export const STORY_POINT_ZOOM = 17;

/**
 * Resolve a story's `overlayMapId` against the catalogue. The id may be a
 * `maps.id` UUID (new) or a legacy `allmaps_id`, so both are matched.
 */
export function resolveMapRef(
  mapList: MapListItem[],
  id: string | null | undefined
): MapListItem | null {
  if (!id) return null;
  return mapList.find((m) => m.id === id || m.allmaps_id === id) ?? null;
}

/**
 * Swap the overlay stack to the point's pinned historical layer. No-op when the
 * point pins nothing, or when the pinned map has no usable annotation source.
 */
export function applyPointOverlay(
  point: StoryPoint,
  mapList: MapListItem[],
  layers: LayersStore = layersStore
): void {
  if (!point.overlayMapId) return;
  const found = resolveMapRef(mapList, point.overlayMapId);
  if (!found) return;
  const ref = toHistoricalRef(found);
  if (!ref.allmapsId) return;
  layers.clearOverlays();
  layers.addOverlay(ref);
}

/**
 * Frame the camera on a point and apply its pinned overlay. A point that
 * carries its own `camera.zoom` wins over the default story zoom.
 */
export function applyStoryPoint(
  point: StoryPoint,
  mapList: MapListItem[],
  mapStore: MapStore,
  layers: LayersStore = layersStore
): void {
  if (point.coordinates) {
    mapStore.setView({
      lng: point.coordinates[0],
      lat: point.coordinates[1],
      zoom: point.camera?.zoom ?? STORY_POINT_ZOOM,
    });
  }
  applyPointOverlay(point, mapList, layers);
}
