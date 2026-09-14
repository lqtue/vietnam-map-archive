/**
 * Ellipsoids and datum shifts.
 *
 * A coordinate read off a historical map — from its printed graticule, or from
 * the military grid the sheet carries — is in that map's own datum, not WGS84.
 * In Vietnam that gap is 300–400 m, which is a city block: far enough to land
 * on the wrong side of a river, close enough that nobody notices it is wrong.
 *
 * The shift is a Helmert 3-parameter geocentric translation (`towgs84 =
 * [dX, dY, dZ]`, metres, from the EPSG registry): geodetic → ECEF on the source
 * ellipsoid, add the translation, ECEF → geodetic on WGS84.
 *
 * Extracted from `features/admin/neatlineDatum.ts` (which still owns the
 * operator-facing preset list) so `core/geo/coordinates.ts` can use it too —
 * `core` may not import `features`.
 */

/** A source datum: its ellipsoid, and the translation that puts it on WGS84. */
export interface DatumParams {
  /** Semi-major axis (m). */
  a: number;
  /** Semi-minor axis (m). */
  b: number;
  /** Geocentric translation to WGS84 (m). */
  dX: number;
  dY: number;
  dZ: number;
}

/** WGS84 ellipsoid, as a no-op datum. */
export const WGS84: DatumParams = {
  a: 6378137.0,
  b: 6356752.31424518,
  dX: 0,
  dY: 0,
  dZ: 0,
};

/**
 * EPSG:4131 — the datum printed on the US Army / AMS sheets of Vietnam, and so
 * the datum of every grid reference written during the war. Everest 1830
 * Modified (EPSG:7018); `towgs84` from EPSG transformation 1052, the mainland
 * South Vietnam fit.
 */
export const INDIAN_1960: DatumParams = {
  a: 6377304.063,
  b: 6356103.038993155,
  dX: 198,
  dY: 881,
  dZ: 317,
};

export function geographicToECEF(
  lon: number,
  lat: number,
  a: number,
  b: number
): [number, number, number] {
  const toRad = Math.PI / 180;
  const φ = lat * toRad;
  const λ = lon * toRad;
  const e2 = 1 - (b * b) / (a * a);
  const N = a / Math.sqrt(1 - e2 * Math.sin(φ) ** 2);
  return [N * Math.cos(φ) * Math.cos(λ), N * Math.cos(φ) * Math.sin(λ), N * (1 - e2) * Math.sin(φ)];
}

export function ecefToGeographic(
  X: number,
  Y: number,
  Z: number,
  a: number,
  b: number
): [number, number] {
  const toDeg = 180 / Math.PI;
  const e2 = 1 - (b * b) / (a * a);
  const lon = Math.atan2(Y, X);
  const p = Math.sqrt(X * X + Y * Y);
  // Bowring iterative lat
  let lat = Math.atan2(Z, p * (1 - e2));
  for (let i = 0; i < 10; i++) {
    const N = a / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
    lat = Math.atan2(Z + e2 * N * Math.sin(lat), p);
  }
  return [lon * toDeg, lat * toDeg];
}

/** Shifts one `[lon, lat]` pair from `datum` onto WGS84. */
export function shiftToWgs84(geo: [number, number], datum: DatumParams): [number, number] {
  const [X, Y, Z] = geographicToECEF(geo[0], geo[1], datum.a, datum.b);
  const [lon, lat] = ecefToGeographic(X + datum.dX, Y + datum.dY, Z + datum.dZ, WGS84.a, WGS84.b);
  return [+lon.toFixed(8), +lat.toFixed(8)];
}
