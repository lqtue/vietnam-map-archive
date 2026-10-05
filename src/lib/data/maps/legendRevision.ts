import { writable } from 'svelte/store';

/** Notify the legend list and map markers after a saved correction. */
export const legendRevision = writable<Record<string, number>>({});
export function invalidateLegend(mapId: string) {
  legendRevision.update((revisions) => ({ ...revisions, [mapId]: (revisions[mapId] ?? 0) + 1 }));
}
