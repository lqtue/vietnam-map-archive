import { writable } from 'svelte/store';

/** Transient browser interaction; lets the mobile drawer expose the map while placing a point. */
export type LegendPickingSession = { active: true; cancel: () => void };
export const legendPicking = writable<LegendPickingSession | null>(null);
