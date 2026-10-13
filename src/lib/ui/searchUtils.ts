// Shared search utilities: bounds helpers.
// Coordinate parsing lives in `$lib/core/geo/coordinates.ts` — this file carried
// a second, weaker copy (decimal pairs only, no datum, no grid references) that
// nothing ever called.

/**
 * Center of a bounding box.
 */
export function boundsCenter(bounds: [number, number, number, number]): {
  lng: number;
  lat: number;
} {
  return {
    lng: (bounds[0] + bounds[2]) / 2,
    lat: (bounds[1] + bounds[3]) / 2,
  };
}

/**
 * Rough zoom level estimate from bounds extent.
 */
export function boundsZoom(bounds: [number, number, number, number]): number {
  const lonSpan = bounds[2] - bounds[0];
  const latSpan = bounds[3] - bounds[1];
  const maxSpan = Math.max(lonSpan, latSpan);

  if (maxSpan <= 0) return 16;
  // Approximate: 360 degrees = zoom 1, halving each level
  const zoom = Math.log2(360 / maxSpan);
  return Math.max(2, Math.min(18, Math.round(zoom)));
}
