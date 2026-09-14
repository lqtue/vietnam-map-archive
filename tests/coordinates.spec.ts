/**
 * Typing a position into the location search.
 *
 * The case this exists for is the third one: a **military grid reference** off
 * a US Army sheet — `XS 8965 4123`, `48Q XD 850 418`. Those are UTM on the
 * **Indian 1960** datum, and read as WGS84 they land ~370 m southwest of what
 * the reference meant. That is a wrong answer that looks entirely right: a
 * point on a map, in the correct neighbourhood, off by a city block. No error
 * appears, nothing 404s, and the reader has no way to tell. Hence the anchors
 * below, which are grid squares the historical record fixes independently.
 *
 * Browser-less pure checks, riding the Playwright runner like the rest.
 */
import { test, expect } from '@playwright/test';
import {
  parseCoordinateQuery,
  hundredKmSquare,
  latBand,
  lonToZone,
  _internals,
} from '../src/lib/core/geo/coordinates';
import { WGS84, INDIAN_1960, shiftToWgs84 } from '../src/lib/core/geo/datum';

/** Metres between two WGS84 points, near enough at these latitudes. */
function metres(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const dy = (a.lat - b.lat) * 111_320;
  const dx = (a.lng - b.lng) * 111_320 * Math.cos((a.lat * Math.PI) / 180);
  return Math.hypot(dx, dy);
}

/**
 * The 100 km square letters are the half of the scheme that is pure lookup, and
 * the half that is silently wrong if the row offset or the column set is off by
 * one — every decoded reference then lands 100 km away, which is far enough to
 * look like a different bug entirely.
 *
 * These five squares are fixed by the historical record, not by this code:
 * Saigon is XS, Khe Sanh is XD, the Ia Drang is YA, Huế is YD, Đà Nẵng is BT.
 */
test('the 100 km squares match the ones the war was fought in', () => {
  const places: [string, number, number, string][] = [
    ['Saigon / Tân Sơn Nhứt', 10.8188, 106.6519, '48P XS'],
    ['Khe Sanh combat base', 16.6547, 106.7331, '48Q XD'],
    ['LZ X-Ray, Ia Drang', 13.5667, 107.7167, '48P YA'],
    ['Huế citadel', 16.4698, 107.5769, '48Q YD'],
    ['Đà Nẵng', 16.0544, 108.2022, '49Q BT'],
  ];
  for (const [name, lat, lon, expected] of places) {
    const zone = lonToZone(lon);
    const [e, n] = _internals.geodeticToUtm(lon, lat, zone, WGS84);
    expect(`${zone}${latBand(lat)} ${hundredKmSquare(e, n, zone)}`, name).toBe(expected);
  }
});

test('a wartime grid reference resolves on the datum the sheet was printed in', () => {
  // XD 850 418 is the Khe Sanh combat base. The base is at 16.6547, 106.7331.
  const hits = parseCoordinateQuery('48Q XD 850 418');
  const indian = hits.find((h) => h.datum === 'indian1960')!;
  const wgs = hits.find((h) => h.datum === 'wgs84')!;

  expect(indian).toBeTruthy();
  // The Indian 1960 reading — the correct one — is inside the base perimeter.
  expect(metres(indian, { lat: 16.6547, lng: 106.7331 })).toBeLessThan(300);
  // Read as WGS84 the same string lands ~480 m east-southeast. This is the
  // error the feature exists to avoid.
  expect(metres(wgs, indian)).toBeGreaterThan(400);
  expect(metres(wgs, indian)).toBeLessThan(600);

  // The wartime reading comes first: the sheets say Indian 1960.
  expect(hits[0].datum).toBe('indian1960');
});

test('a bare grid reference needs no zone, because the letters carry it', () => {
  // The three column-letter sets are disjoint, so a column letter is legal in
  // only one zone-mod-3 class — and Vietnam's 48/49 are different classes.
  // The row letters repeat every 2,000,000 m, but Vietnam is 1,683 km tall, so
  // only one repetition ever falls inside it. A bare reference is unambiguous.
  const bare = parseCoordinateQuery('XD 850 418');
  const full = parseCoordinateQuery('48Q XD 850 418');
  expect(bare.length).toBe(2);
  expect(bare[0].lat).toBeCloseTo(full[0].lat, 6);
  expect(bare[0].lng).toBeCloseTo(full[0].lng, 6);
  // And it writes the zone back, so the reader learns what was assumed.
  expect(bare[0].ref).toBe('48Q XD 850 418');
});

test('the digit count is the precision, not decoration', () => {
  // 4 / 6 / 8 / 10 figures name a 1 km / 100 m / 10 m / 1 m square, and the
  // point returned is that square's centre — a six-figure reference is not a
  // point and should not zoom like one.
  const sides: [string, number][] = [
    ['48P XS 81 97', 1000],
    ['48P XS 815 975', 100],
    ['48P XS 8150 9750', 10],
    ['48P XS 81500 97500', 1],
  ];
  for (const [ref, side] of sides) {
    const hit = parseCoordinateQuery(ref)[0];
    expect(hit.precisionM * 2, ref).toBe(side);
  }
  // All four name the same corner of Saigon, to within the coarsest square.
  const coarse = parseCoordinateQuery('48P XS 81 97')[0];
  const fine = parseCoordinateQuery('48P XS 81500 97500')[0];
  expect(metres(coarse, fine)).toBeLessThan(750);
});

test('UTM round-trips through the projection on both ellipsoids', () => {
  for (const datum of [WGS84, INDIAN_1960]) {
    for (const [lon, lat] of [
      [106.7009, 10.7769],
      [105.8542, 21.0285],
      [108.2022, 16.0544],
    ] as [number, number][]) {
      const zone = lonToZone(lon);
      const [e, n] = _internals.geodeticToUtm(lon, lat, zone, datum);
      const [lon2, lat2] = _internals.utmToGeodetic(e, n, zone, datum);
      expect(lon2).toBeCloseTo(lon, 8);
      expect(lat2).toBeCloseTo(lat, 8);
    }
  }
});

test('the Indian 1960 shift is the size the EPSG parameters say', () => {
  // 450-500 m across Vietnam: ~440 m west and 130-250 m north. If this number
  // moves, either the ellipsoid or the towgs84 triple was edited, and every
  // grid reference in the archive moved with it.
  const [lng, lat] = shiftToWgs84([106.7009, 10.7769], INDIAN_1960);
  const offset = metres({ lat, lng }, { lat: 10.7769, lng: 106.7009 });
  expect(offset).toBeGreaterThan(450);
  expect(offset).toBeLessThan(520);
  expect((lng - 106.7009) * 111_320 * Math.cos((lat * Math.PI) / 180)).toBeLessThan(-400);
});

test('lat/lon is read in every shape a reader types it', () => {
  const saigon = { lat: 10.7769, lng: 106.7009 };
  for (const q of ['10.7769, 106.7009', '10.7769 106.7009', '106.7009, 10.7769']) {
    const hit = parseCoordinateQuery(q)[0];
    expect(hit, q).toBeTruthy();
    expect(metres(hit, saigon), q).toBeLessThan(1);
  }
  // Hemispheres win over order, in either order.
  for (const q of ['106.7009E 10.7769N', 'N10.7769 E106.7009']) {
    expect(metres(parseCoordinateQuery(q)[0], saigon), q).toBeLessThan(1);
  }
});

test('a graticule reading in DMS also offers the sheet datum', () => {
  const hits = parseCoordinateQuery(`10°46'36"N 106°42'03"E`);
  expect(hits.map((h) => h.datum)).toEqual(['wgs84', 'indian1960']);
  expect(hits[0].lat).toBeCloseTo(10 + 46 / 60 + 36 / 3600, 6);
  expect(hits[0].lng).toBeCloseTo(106 + 42 / 60 + 3 / 3600, 6);
  // Space-separated DMS is the same reading.
  const spaced = parseCoordinateQuery('10 46 36 N, 106 42 3 E');
  expect(spaced[0].lat).toBeCloseTo(hits[0].lat, 9);
  // A decimal pair is off a modern device, so no second datum is guessed.
  expect(parseCoordinateQuery('10.7769, 106.7009').length).toBe(1);
});

/**
 * The parser runs on every keystroke of a field that is mostly typed place
 * names. Anything it claims is a coordinate outranks the place results, so a
 * false positive is worse than a miss.
 */
test('a place name is not a coordinate', () => {
  for (const q of [
    'Ben Thanh market',
    'District 1',
    'Saigon 1968',
    'map 1968',
    '1968 1972', // a year range
    '2 5', // a page reference
    'Highway 1',
    '',
    'Chợ Lớn',
  ]) {
    expect(parseCoordinateQuery(q), q).toEqual([]);
  }
});

test('a reference outside Vietnam, or outside its own zone, is not invented', () => {
  // Row letters repeat worldwide; the archive answers for Vietnam only.
  expect(parseCoordinateQuery('48P AA 123 456')).toEqual([]);
  // A zone is 6° wide. A square whose easting puts it in the next zone is that
  // zone's square, not this one's.
  expect(parseCoordinateQuery('48P XS 999999 999999')).toEqual([]);
  // Out-of-range minutes are a typo, not a position.
  expect(parseCoordinateQuery(`10°76'00"N 106°42'00"E`)).toEqual([]);
});

test('bare UTM eastings and northings work too', () => {
  const hits = parseCoordinateQuery('48P 683000 1192000');
  expect(hits.length).toBe(2);
  expect(hits[0].system).toBe('utm');
  expect(hits[0].datum).toBe('indian1960');
  expect(metres(hits[0], { lat: 10.78, lng: 106.67 })).toBeLessThan(1000);
});
