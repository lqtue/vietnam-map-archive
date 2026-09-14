/**
 * resolveRef.ts — an inbound reference to a sheet, resolved against the
 * catalogue the page already has in hand.
 *
 * Lived in `features/stories/shared/applyPoint.ts` until 2026-09-14, which put
 * a pure two-line lookup behind an import of the OpenLayers layer store: any
 * caller wanting it pulled the map runtime with it, and no browser-less test
 * could reach it at all. It is a question about the catalogue, not about a
 * story or a map, so it belongs here.
 */
import type { MapListItem } from './types';

/**
 * Resolve a `?map=` deep link, or a story's `overlayMapId`, against the
 * catalogue. Three shapes reach here and all three have to land:
 *
 *   * the readable `slug` (migration 088) — what /explore writes today;
 *   * the `maps.id` uuid — every link shared before the slug existed;
 *   * a legacy `allmaps_id` — older still, and carried by saved stories.
 *
 * Null rather than a guess when nothing matches: a reference that resolves to
 * the wrong sheet is worse than one that resolves to none, because the map
 * still draws and nothing reports an error.
 */
export function resolveMapRef(
  mapList: MapListItem[],
  id: string | null | undefined
): MapListItem | null {
  if (!id) return null;
  return mapList.find((m) => m.id === id || m.slug === id || m.allmaps_id === id) ?? null;
}
