/**
 * Sheets that are two halves of one printed plan, so their legends read together.
 *
 * The 1942 Plan de Saïgon and Plan de Cholon were scanned as separate images with separate
 * georeferences, and some Cholon legend entries are printed on the Saigon half.
 *
 * ponytail: a constant, not a column. Move to `maps.extra_metadata` / a series row when a
 * second pair appears (ROADMAP `saigon-1942-pair-view`).
 */
const PAIRS: string[][] = [
  [
    '6989a04e-0f51-439e-9390-a6678aff374c', // Plan de Saïgon
    '8c605819-a8c3-4b2f-aa4a-6fad12893eab', // Plan de Cholon
  ],
];

/** The sheet and its partners, the sheet first; just the sheet when it has none. */
export function pairedSheets(mapId: string | null): string[] {
  if (!mapId) return [];
  const group = PAIRS.find((ids) => ids.includes(mapId));
  return group ? [mapId, ...group.filter((id) => id !== mapId)] : [mapId];
}
