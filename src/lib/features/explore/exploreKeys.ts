/**
 * exploreKeys.ts — the keyboard time scrubber for /explore.
 *
 * ← / →  step the top overlay to the previous / next map by year
 * ↑ / ↓  raise / lower the top overlay's opacity
 *
 * Stepping deliberately keeps the camera where it is. That is the whole point:
 * hold a spot still and walk the years over it, which is the fastest way to see
 * a canal fill in or a block subdivide. Zooming to each new sheet would undo it.
 */
import type { MapListItem } from '$lib/data/maps/types';

export const OPACITY_STEP = 0.1;

/** Maps that can actually be overlaid, oldest first. Ties break on name so the walk is stable. */
export function timeOrder(maps: MapListItem[]): MapListItem[] {
  return maps
    .filter((m) => !!m.allmaps_id || !!m.annotation_url)
    .slice()
    .sort((a, b) => {
      const ay = a.year ?? Number.POSITIVE_INFINITY;
      const by = b.year ?? Number.POSITIVE_INFINITY;
      return ay !== by ? ay - by : (a.name ?? '').localeCompare(b.name ?? '');
    });
}

/**
 * The map one step older (`-1`) or newer (`+1`) than `currentId`.
 *
 * Returns null at either end — a wrap-around would silently jump the reader
 * from 1968 back to 1799, which reads as a bug rather than a feature. Also
 * null when the current map is not in the list, since there is no position to
 * step from.
 */
export function stepByYear(
  maps: MapListItem[],
  currentId: string | null,
  dir: -1 | 1
): MapListItem | null {
  const ordered = timeOrder(maps);
  if (!ordered.length) return null;
  const i = currentId ? ordered.findIndex((m) => m.id === currentId) : -1;
  if (i < 0) return null;
  return ordered[i + dir] ?? null;
}
