/**
 * Reading a position out of a typed string.
 *
 * Three things get typed into a location search on this archive, and only the
 * first is ordinary:
 *
 *   1. Modern lat/lon, decimal or DMS, off a phone or Google Maps.
 *   2. A graticule reading off a historical sheet — degrees, minutes, seconds,
 *      in the sheet's own datum, not WGS84.
 *   3. A **military grid reference**: `XS 8965 4123`, `YD 850 418`, `48P XS
 *      896 412`. This is what every US Army map of Vietnam carried, what every
 *      after-action report, coordinate in a memoir, and unit history quotes,
 *      and it is the reason this module exists. It is a UTM grid on the
 *      **Indian 1960 datum** (Everest 1830 Modified) — the same lettering as
 *      modern MGRS, but different numbers: reading a wartime grid as if it were
 *      WGS84 puts you ~480 m east-southeast of where the reference meant.
 *
 * So a grid reference resolves to *two* answers, not one, and this module
 * returns both rather than picking for the reader: the Indian 1960 reading
 * first, because that is what the sheets say, and the WGS84 reading after it,
 * for a grid that came off a modern device.
 *
 * Everything here is pure. The datum shift is `./datum`; the projection maths
 * is Snyder's series for the transverse Mercator, good to centimetres inside a
 * zone, which is four orders of magnitude finer than the grid squares it is
 * decoding.
 */
import { INDIAN_1960, WGS84, shiftToWgs84, type DatumParams } from './datum';

/** Which reading a hit is. The UI turns this into words; core stays wordless. */
export type CoordSystem = 'latlon' | 'mgrs' | 'utm';
export type CoordDatum = 'wgs84' | 'indian1960';

export interface CoordHit {
  /** WGS84, always — whatever datum it was read in. */
  lat: number;
  lng: number;
  /** The reference as it should be written back, normalised. */
  ref: string;
  system: CoordSystem;
  datum: CoordDatum;
  /** Half-width of the square this reference actually names, in metres. */
  precisionM: number;
  /** `[w, s, e, n]` — that square, so the camera lands at its scale. */
  bbox: [number, number, number, number];
}

/**
 * The window a decoded grid reference has to fall in to be believed. A bare
 * `XS 896 412` names a different square in every UTM zone on earth; the archive
 * is Vietnamese, so Vietnam plus its near waters is the whole answer space.
 */
const VN = { west: 101.5, south: 7.0, east: 114.0, north: 24.0 };

/** The UTM zones that cover it: 48 is 102–108°E, 49 is 108–114°E. */
const VN_ZONES = [48, 49];

const DATUMS: Record<CoordDatum, DatumParams> = {
  indian1960: INDIAN_1960,
  wgs84: WGS84,
};

// ── Transverse Mercator ───────────────────────────────────────────────────

const K0 = 0.9996;
const FALSE_EASTING = 500_000;
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

/** Central meridian of a UTM zone, in degrees. */
export function zoneCentralMeridian(zone: number): number {
  return (zone - 1) * 6 - 180 + 3;
}

/** The UTM zone a longitude falls in. */
export function lonToZone(lon: number): number {
  return Math.floor((lon + 180) / 6) + 1;
}

/**
 * UTM easting/northing → `[lon, lat]` **in the same datum**, northern
 * hemisphere. Snyder, *Map Projections — A Working Manual*, §8.
 */
function utmToGeodetic(
  easting: number,
  northing: number,
  zone: number,
  { a, b }: DatumParams
): [number, number] {
  const e2 = 1 - (b * b) / (a * a);
  const ep2 = e2 / (1 - e2);
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));

  const x = easting - FALSE_EASTING;
  const M = northing / K0;
  const mu = M / (a * (1 - e2 / 4 - (3 * e2 ** 2) / 64 - (5 * e2 ** 3) / 256));

  const φ1 =
    mu +
    ((3 * e1) / 2 - (27 * e1 ** 3) / 32) * Math.sin(2 * mu) +
    ((21 * e1 ** 2) / 16 - (55 * e1 ** 4) / 32) * Math.sin(4 * mu) +
    ((151 * e1 ** 3) / 96) * Math.sin(6 * mu) +
    ((1097 * e1 ** 4) / 512) * Math.sin(8 * mu);

  const sin1 = Math.sin(φ1);
  const cos1 = Math.cos(φ1);
  const tan1 = Math.tan(φ1);
  const C1 = ep2 * cos1 ** 2;
  const T1 = tan1 ** 2;
  const N1 = a / Math.sqrt(1 - e2 * sin1 ** 2);
  const R1 = (a * (1 - e2)) / (1 - e2 * sin1 ** 2) ** 1.5;
  const D = x / (N1 * K0);

  const lat =
    φ1 -
    ((N1 * tan1) / R1) *
      (D ** 2 / 2 -
        ((5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4) / 24 +
        ((61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6) / 720);

  const lon =
    zoneCentralMeridian(zone) * RAD +
    (D -
      ((1 + 2 * T1 + C1) * D ** 3) / 6 +
      ((5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5) / 120) /
      cos1;

  return [lon * DEG, lat * DEG];
}

/** `[lon, lat]` in `datum` → UTM easting/northing in that zone. Snyder §8. */
function geodeticToUtm(
  lon: number,
  lat: number,
  zone: number,
  { a, b }: DatumParams
): [number, number] {
  const e2 = 1 - (b * b) / (a * a);
  const ep2 = e2 / (1 - e2);
  const φ = lat * RAD;
  const Δλ = (lon - zoneCentralMeridian(zone)) * RAD;

  const N = a / Math.sqrt(1 - e2 * Math.sin(φ) ** 2);
  const T = Math.tan(φ) ** 2;
  const C = ep2 * Math.cos(φ) ** 2;
  const A = Math.cos(φ) * Δλ;
  const M =
    a *
    ((1 - e2 / 4 - (3 * e2 ** 2) / 64 - (5 * e2 ** 3) / 256) * φ -
      ((3 * e2) / 8 + (3 * e2 ** 2) / 32 + (45 * e2 ** 3) / 1024) * Math.sin(2 * φ) +
      ((15 * e2 ** 2) / 256 + (45 * e2 ** 3) / 1024) * Math.sin(4 * φ) -
      ((35 * e2 ** 3) / 3072) * Math.sin(6 * φ));

  const easting =
    FALSE_EASTING +
    K0 *
      N *
      (A + ((1 - T + C) * A ** 3) / 6 + ((5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5) / 120);
  const northing =
    K0 *
    (M +
      N *
        Math.tan(φ) *
        (A ** 2 / 2 +
          ((5 - T + 9 * C + 4 * C ** 2) * A ** 4) / 24 +
          ((61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6) / 720));

  return [easting, northing];
}

// ── The 100 km square letters ─────────────────────────────────────────────

/** Easting letters, by `zone % 3`. Index 0 is the 100–200 km column. */
const COLUMN_SETS = ['STUVWXYZ', 'ABCDEFGH', 'JKLMNPQR'];
/** Northing letters. I and O are skipped, so the cycle is 20 × 100 km. */
const ROW_LETTERS = 'ABCDEFGHJKLMNPQRSTUV';
/** Latitude bands, 8° each from 80°S. I and O skipped here too. */
const BANDS = 'CDEFGHJKLMNPQRSTUVWX';

/** Even-numbered zones start their row letters five along. */
const rowOffset = (zone: number) => (zone % 2 === 0 ? 5 : 0);

/** The 100 km square letters for a UTM position — the inverse of the decode. */
export function hundredKmSquare(easting: number, northing: number, zone: number): string {
  const col = COLUMN_SETS[zone % 3][Math.floor(easting / 100_000) - 1];
  const row = ROW_LETTERS[(Math.floor(northing / 100_000) + rowOffset(zone)) % 20];
  return `${col}${row}`;
}

/** Latitude band letter for a latitude — the `P` in `48P`. */
export function latBand(lat: number): string {
  return BANDS[Math.max(0, Math.min(19, Math.floor((lat + 80) / 8)))];
}

// ── Parsing ───────────────────────────────────────────────────────────────

/** A grid reference: `[48P ]XS 8965 4123`, with or without zone, band, spaces. */
const GRID_RE = /^(?:(\d{1,2})\s*([C-HJ-NP-X])?[\s,]*)?([A-Z])[\s]?([A-Z])[\s,]*([\d\s]{2,12})$/i;
/** Bare UTM: `48P 683000 1192000`, the letter optional and only a hint. */
const UTM_RE =
  /^(\d{1,2})\s*([C-HJ-NP-X])?[\s,]+(\d{4,7}(?:\.\d+)?)\s*E?[\s,]+(\d{4,8}(?:\.\d+)?)\s*N?$/i;

const inVietnam = (lon: number, lat: number) =>
  lon >= VN.west && lon <= VN.east && lat >= VN.south && lat <= VN.north;

/** Metres → degrees, so a square in metres becomes a bbox. */
function boxAround(lon: number, lat: number, halfM: number): [number, number, number, number] {
  const dLat = halfM / 111_320;
  const dLon = halfM / (111_320 * Math.max(0.2, Math.cos(lat * RAD)));
  return [lon - dLon, lat - dLat, lon + dLon, lat + dLat];
}

function hitFromUtm(
  easting: number,
  northing: number,
  zone: number,
  datum: CoordDatum,
  system: CoordSystem,
  ref: string,
  precisionM: number
): CoordHit | null {
  const [lon0, lat0] = utmToGeodetic(easting, northing, zone, DATUMS[datum]);
  if (!Number.isFinite(lon0) || !Number.isFinite(lat0)) return null;
  // A zone is 6° wide; AMS sheets carry the neighbour's grid a little past the
  // junction, but nothing like a whole zone. Past that the square belongs to
  // someone else, and decoding it here would invent a position.
  if (Math.abs(lon0 - zoneCentralMeridian(zone)) > 3.5) return null;
  const [lng, lat] = datum === 'wgs84' ? [lon0, lat0] : shiftToWgs84([lon0, lat0], DATUMS[datum]);
  if (!inVietnam(lng, lat)) return null;
  return {
    lat,
    lng,
    ref,
    system,
    datum,
    precisionM,
    bbox: boxAround(lng, lat, Math.max(precisionM, 60)),
  };
}

/**
 * A grid reference, in both datums, for every zone/cycle that lands in Vietnam.
 *
 * Without a zone the same letters repeat every 6° of longitude and every
 * 2,000,000 m north, so more than one square can be real: both are returned,
 * labelled, rather than guessed between.
 */
function parseGridRef(input: string): CoordHit[] {
  const m = input.match(GRID_RE);
  if (!m) return [];
  const [, zoneStr, bandStr, colLetter, rowLetter, digitStr] = m;

  const digits = digitStr.replace(/\s/g, '');
  if (digits.length % 2 !== 0 || digits.length < 2 || digits.length > 10) return [];
  const half = digits.length / 2;
  /** Side of the square the reference names: 10 km at 2 figures, 1 m at 10. */
  const unit = 10 ** (5 - half);
  const eastDigits = Number(digits.slice(0, half)) * unit;
  const northDigits = Number(digits.slice(half)) * unit;

  const col = colLetter.toUpperCase();
  const row = rowLetter.toUpperCase();
  const band = bandStr?.toUpperCase();
  const zones = zoneStr ? [Number(zoneStr)] : VN_ZONES;

  const hits: CoordHit[] = [];
  for (const zone of zones) {
    if (zone < 1 || zone > 60) continue;
    const colIdx = COLUMN_SETS[zone % 3].indexOf(col);
    const rowIdx = ROW_LETTERS.indexOf(row);
    if (colIdx < 0 || rowIdx < 0) continue;

    const easting = (colIdx + 1) * 100_000 + eastDigits + unit / 2;
    const base = ((rowIdx - rowOffset(zone) + 20) % 20) * 100_000;

    // The letters repeat every 2,000,000 m. Vietnam spans two of those cycles.
    for (const cycle of [0, 1, 2]) {
      const northing = base + cycle * 2_000_000 + northDigits + unit / 2;
      const ref =
        `${zone}${band ?? latBandFor(northing, zone)} ${col}${row} ` +
        `${digits.slice(0, half)} ${digits.slice(half)}`;
      for (const datum of ['indian1960', 'wgs84'] as CoordDatum[]) {
        const hit = hitFromUtm(easting, northing, zone, datum, 'mgrs', ref, unit / 2);
        if (hit) hits.push(hit);
      }
    }
  }
  return dedupe(hits);
}

/** Band letter for a northing, used to write a reference back in full. */
function latBandFor(northing: number, zone: number): string {
  const [, lat] = utmToGeodetic(FALSE_EASTING, northing, zone, WGS84);
  return latBand(lat);
}

function parseUtmRef(input: string): CoordHit[] {
  const m = input.match(UTM_RE);
  if (!m) return [];
  const zone = Number(m[1]);
  const easting = Number(m[3]);
  const northing = Number(m[4]);
  if (zone < 1 || zone > 60 || easting < 100_000 || easting > 900_000) return [];

  const hits: CoordHit[] = [];
  for (const datum of ['indian1960', 'wgs84'] as CoordDatum[]) {
    const ref = `${zone}${latBandFor(northing, zone)} ${Math.round(easting)}E ${Math.round(northing)}N`;
    const hit = hitFromUtm(easting, northing, zone, datum, 'utm', ref, 30);
    if (hit) hits.push(hit);
  }
  return hits;
}

/** One angle: `10.7769`, `10°46'36"N`, `N 10 46 36`, `106 42.05 E`. */
function parseAngle(part: string): { deg: number; hemi: string | null; dms: boolean } | null {
  const t = part
    .trim()
    .replace(/[º˚∘]/g, '°')
    .replace(/[′’`]/g, "'")
    .replace(/[″”]|''/g, '"');
  const m = t.match(
    /^([NSEW])?\s*(-?\d+(?:\.\d+)?)\s*°?\s*(?:(\d+(?:\.\d+)?)\s*'?\s*(?:(\d+(?:\.\d+)?)\s*"?\s*)?)?([NSEW])?$/i
  );
  if (!m) return null;
  const [, hemiBefore, d, mi, se, hemiAfter] = m;
  if (hemiBefore && hemiAfter) return null;

  const deg = Number(d);
  const minutes = mi ? Number(mi) : 0;
  const seconds = se ? Number(se) : 0;
  if (minutes >= 60 || seconds >= 60) return null;

  const magnitude = Math.abs(deg) + minutes / 60 + seconds / 3600;
  return {
    deg: deg < 0 ? -magnitude : magnitude,
    hemi: (hemiBefore ?? hemiAfter ?? null)?.toUpperCase() ?? null,
    dms: Boolean(mi || se || /[°'"]/.test(t)),
  };
}

/** Every way the two halves of a pair can be split, best guess first. */
function splitPair(input: string): [string, string][] {
  const trimmed = input.trim();
  const comma = trimmed.indexOf(',');
  const splits: [string, string][] = [];
  if (comma > 0) splits.push([trimmed.slice(0, comma), trimmed.slice(comma + 1)]);
  // No comma, or the comma is inside one half ("10 46 36 N 106 42 3 E"):
  // every whitespace boundary is a candidate, and only one of them parses.
  const ws = [...trimmed.matchAll(/\s+/g)];
  for (const match of ws) {
    const at = match.index ?? 0;
    splits.push([trimmed.slice(0, at), trimmed.slice(at + match[0].length)]);
  }
  return splits;
}

function parseLatLon(input: string): CoordHit[] {
  for (const [left, right] of splitPair(input)) {
    const a = parseAngle(left);
    const b = parseAngle(right);
    if (!a || !b) continue;

    let lat: number, lng: number;
    if (a.hemi && b.hemi) {
      // Hemispheres say which is which, in either order.
      const ns = 'NS'.includes(a.hemi) ? a : 'NS'.includes(b.hemi) ? b : null;
      const ew = 'EW'.includes(a.hemi) ? a : 'EW'.includes(b.hemi) ? b : null;
      if (!ns || !ew || ns === ew) continue;
      lat = ns.hemi === 'S' ? -Math.abs(ns.deg) : Math.abs(ns.deg);
      lng = ew.hemi === 'W' ? -Math.abs(ew.deg) : Math.abs(ew.deg);
    } else if (!a.hemi && !b.hemi) {
      // "1968 1972" and "2 5" are a year range and a page reference, not a
      // position. A bare pair has to look like one: a decimal point somewhere,
      // or the minutes and seconds that make it a graticule reading.
      if (!a.dms && !b.dms && !/\./.test(left + right)) continue;
      // Bare pair: lat first, unless only the other order is possible.
      const latFirst = Math.abs(a.deg) <= 90 && Math.abs(b.deg) <= 180;
      const lonFirst = Math.abs(b.deg) <= 90 && Math.abs(a.deg) <= 180;
      // Both legal and the first looks like a Vietnamese longitude: it is one.
      const swap = !latFirst || (lonFirst && Math.abs(a.deg) > 90);
      if (swap && !lonFirst) continue;
      lat = swap ? b.deg : a.deg;
      lng = swap ? a.deg : b.deg;
    } else {
      continue;
    }
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) continue;

    const dms = a.dms || b.dms;
    const ref = `${formatAngle(lat, 'NS', dms)} ${formatAngle(lng, 'EW', dms)}`;
    const hits: CoordHit[] = [
      {
        lat,
        lng,
        ref,
        system: 'latlon',
        datum: 'wgs84',
        precisionM: 0,
        bbox: boxAround(lng, lat, 120),
      },
    ];
    // A graticule reading off an AMS sheet is written in degrees, minutes and
    // seconds, and is ~370 m out if taken as WGS84 — so offer that reading too,
    // but only for DMS: a bare decimal pair came off a modern device.
    if (dms && inVietnam(lng, lat)) {
      const [sLng, sLat] = shiftToWgs84([lng, lat], INDIAN_1960);
      hits.push({
        lat: sLat,
        lng: sLng,
        ref,
        system: 'latlon',
        datum: 'indian1960',
        precisionM: 0,
        bbox: boxAround(sLng, sLat, 120),
      });
    }
    return hits;
  }
  return [];
}

function formatAngle(value: number, hemis: string, dms: boolean): string {
  const hemi = value < 0 ? hemis[1] : hemis[0];
  const abs = Math.abs(value);
  if (!dms) return `${abs.toFixed(5)}°${hemi}`;
  const d = Math.floor(abs);
  const m = Math.floor((abs - d) * 60);
  const s = ((abs - d) * 60 - m) * 60;
  return `${d}°${String(m).padStart(2, '0')}'${s.toFixed(1).padStart(4, '0')}"${hemi}`;
}

/** Two readings closer than 50 m are the same place said twice. */
function dedupe(hits: CoordHit[]): CoordHit[] {
  const kept: CoordHit[] = [];
  for (const h of hits) {
    const near = kept.some(
      (k) =>
        k.datum === h.datum && Math.abs(k.lat - h.lat) < 0.0005 && Math.abs(k.lng - h.lng) < 0.0005
    );
    if (!near) kept.push(h);
  }
  return kept;
}

/**
 * Everything `input` could be a position for, most likely first.
 *
 * Empty when it is not a coordinate at all — which is the common case, since
 * this runs on every keystroke in a search box that is mostly typed place
 * names.
 */
export function parseCoordinateQuery(input: string): CoordHit[] {
  const q = input.trim();
  if (!q || q.length > 60) return [];
  // A grid reference needs letters and digits; a lat/lon pair needs two numbers.
  // Anything else is a place name, and asking is cheaper than parsing.
  if (!/\d/.test(q)) return [];

  const grid = parseGridRef(q);
  if (grid.length) return grid;
  const utm = parseUtmRef(q);
  if (utm.length) return utm;
  return parseLatLon(q);
}

/** Exposed for the tests: forward UTM, to check the decode round-trips. */
export const _internals = { geodeticToUtm, utmToGeodetic };
