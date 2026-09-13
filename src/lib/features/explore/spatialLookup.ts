/**
 * spatialLookup.ts — picks the best historical overlay for a given lon/lat.
 *
 * Tries `maps.bbox` first (cheap, DB-side), then falls back to resolving
 * bounds from each map's Allmaps annotation at runtime via fetchMultipleBounds.
 * Most maps in the catalogue don't have `bbox` backfilled yet, so the runtime
 * resolution is what actually makes /explore find anything today.
 *
 * Client-side filtering for MVP. Cheap until the catalogue grows past a few
 * hundred entries; swap for a PostGIS RPC later without changing callers.
 */
import type { MapListItem } from '$lib/data/maps/types';
import { looksValidBbox, unresolvedBoundsSources, type Bbox } from '$lib/core/geo/mapBounds';

// The probe list moved to `core` when `useMapList` (in `map/`) needed the same
// rungs — a shell may not import a feature. Re-exported so callers and
// `tests/bounds-probe.spec.ts` keep their one import site.
export { unresolvedBoundsSources };

export type { Bbox };

// VMA's editorial home base. Used as a fallback view when the user picks
// "Show all maps" or denies location — but coverage is NOT limited to
// this point; the archive covers other areas too (Hanoi, Hue, Cambodia
// border, etc.) and `/explore` treats them all equally.
export const SAIGON_CENTER: [number, number] = [106.70098, 10.77653];
export const SAIGON_DEFAULT_ZOOM = 15;

// Extends MapListItem with a resolved bbox/bounds tuple — same shape either
// way, so downstream code only ever reads `effectiveBbox`.
export interface ResolvedMap extends MapListItem {
  effectiveBbox: Bbox;
}

export function bboxContainsPoint(bbox: Bbox, lon: number, lat: number): boolean {
  return lon >= bbox[0] && lon <= bbox[2] && lat >= bbox[1] && lat <= bbox[3];
}

function bboxArea(bbox: Bbox): number {
  return Math.max(0, bbox[2] - bbox[0]) * Math.max(0, bbox[3] - bbox[1]);
}

/**
 * Synchronous match against the already-loaded map catalogue.
 *
 * Uses each map's effective bbox: `bbox` (DB column) preferred, then `bounds`
 * (runtime enrichment from useMapList → fetchMultipleBounds). Maps with
 * neither resolved yet are skipped — they'll re-appear on the next call
 * after bounds trickle in.
 */
export function matchMapsAtPoint(
  mapList: MapListItem[],
  lon: number,
  lat: number,
  includeDrafts = false
): ResolvedMap[] {
  const visible = mapList.filter(
    (m) =>
      (includeDrafts || m.status === 'public' || m.status === 'featured') &&
      (!!m.allmaps_id || !!m.annotation_url)
  );
  const candidates: ResolvedMap[] = [];
  for (const m of visible) {
    const candidate = looksValidBbox(m.bbox)
      ? (m.bbox as Bbox)
      : looksValidBbox(m.bounds)
        ? (m.bounds as Bbox)
        : null;
    if (!candidate) continue;
    if (!bboxContainsPoint(candidate, lon, lat)) continue;
    candidates.push({ ...m, effectiveBbox: candidate });
  }
  candidates.sort((a, b) => {
    const aa = bboxArea(a.effectiveBbox);
    const ba = bboxArea(b.effectiveBbox);
    if (aa !== ba) return aa - ba;
    return (b.year ?? 0) - (a.year ?? 0);
  });
  return candidates;
}
