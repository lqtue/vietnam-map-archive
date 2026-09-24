/**
 * wkb.spec.ts — the EWKB point parser, against rows production actually holds.
 *
 * A wrong parse does not throw: it drops a label into the Gulf of Guinea, or
 * silently returns null and the hero's last stage renders empty. Both look like
 * "no data" from the outside, so the coordinates are asserted here.
 */
import { test, expect } from '@playwright/test';

import { parsePointHex } from '../src/lib/core/geo/wkb';

// Three rows copied from `ocr_labels` on the 1882 Plan Cadastral.
const SAIGON = [
  { hex: '0101000020E6100000F2F122769AAC5A40D685270D98882540', lng: 106.696928, lat: 10.766785 },
  { hex: '0101000020E610000050EAE46F2FAD5A4031962BB45A8D2540', lng: 106.70602, lat: 10.776083 },
  { hex: '0101000020E6100000759FB16984AC5A4090FD2425DA8D2540', lng: 106.695582, lat: 10.777055 },
];

test('an SRID-carrying point parses to its lng/lat', () => {
  for (const row of SAIGON) {
    const p = parsePointHex(row.hex);
    expect(p).not.toBeNull();
    expect(p![0]).toBeCloseTo(row.lng, 5);
    expect(p![1]).toBeCloseTo(row.lat, 5);
  }
});

test('every parsed point lands on the sheet, not off Africa', () => {
  // The cheap check that catches a byte-order slip: swapped halves put these
  // near 0,0. The sheet's bbox is 106.689,10.762 → 106.708,10.792.
  for (const row of SAIGON) {
    const [lng, lat] = parsePointHex(row.hex)!;
    expect(lng).toBeGreaterThan(106.6);
    expect(lng).toBeLessThan(106.8);
    expect(lat).toBeGreaterThan(10.7);
    expect(lat).toBeLessThan(10.9);
  }
});

test('a point with no SRID parses from the shorter offset', () => {
  // 0101000000 + the same two doubles as the first row above.
  const noSrid = '0101000000' + SAIGON[0].hex.slice(18);
  const p = parsePointHex(noSrid);
  expect(p![0]).toBeCloseTo(SAIGON[0].lng, 5);
  expect(p![1]).toBeCloseTo(SAIGON[0].lat, 5);
});

test('anything that is not a little-endian point returns null', () => {
  expect(parsePointHex(null)).toBeNull();
  expect(parsePointHex('')).toBeNull();
  expect(parsePointHex('deadbeef')).toBeNull();
  // Big-endian byte order marker.
  expect(parsePointHex('00' + SAIGON[0].hex.slice(2))).toBeNull();
  // A LINESTRING (type 2), not a point.
  expect(parsePointHex('0102000020E6100000' + SAIGON[0].hex.slice(18))).toBeNull();
  // Truncated mid-coordinate.
  expect(parsePointHex(SAIGON[0].hex.slice(0, 30))).toBeNull();
});
