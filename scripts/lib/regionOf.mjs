// @ts-nocheck — a plain script module (run by node, imported by one test); tests/map-region.spec.ts pins it.
// Which Vietnamese province a map's bbox mostly lies in — pure, so a check can run it.
//
// Two labels per map, both modern and both a locator, not the historical name: `region` is the
// province as it stood until 30 June 2025 (63, the set the boundary file draws and the set most
// sources still use); `region_2025` is the same ground under the 34 provinces in force since
// 1 July 2025 (Resolution 202/2025/QH15), derived from the first by MERGED below.

/** Boundary file: geoBoundaries gbOpen VNM ADM1, simplified, public domain, pinned to a commit. */
export const BOUNDARY_URL =
  'https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/VNM/ADM1/geoBoundaries-VNM-ADM1_simplified.geojson';

/** Neighbouring countries, same pin. Sheets of Cambodia, Laos and southern China are in the archive, and
 *  a border sheet's centre or most of its land can lie across the line: it must not be filed under
 *  whichever Vietnamese province is nearest. */
export const NEIGHBOUR_URLS = ['KHM', 'LAO', 'CHN'].map(
  (c) =>
    `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/${c}/ADM0/geoBoundaries-${c}-ADM0_simplified.geojson`
);

/** The file's own spellings that are not the province's name. Hà Tây is already inside Hà Nội. */
const FIX = { 'Ho Chi Minh': 'Hồ Chí Minh', 'Côn Đảo': 'Bà Rịa–Vũng Tàu' };
export const cleanName = (n) => FIX[n.trim()] ?? n.trim();

/** 63 → 34: every province that was merged, by the province that now holds it. The other 11
 *  (Hà Nội, Cao Bằng, Điện Biên, Hà Tĩnh, Lai Châu, Lạng Sơn, Nghệ An, Quảng Ninh, Sơn La,
 *  Thanh Hóa, and Huế) keep their own name — Huế is Thừa Thiên Huế before. */
export const MERGED = {
  'Tuyên Quang': ['Tuyên Quang', 'Hà Giang'],
  'Lào Cai': ['Lào Cai', 'Yên Bái'],
  'Thái Nguyên': ['Thái Nguyên', 'Bắc Kạn'],
  'Phú Thọ': ['Phú Thọ', 'Vĩnh Phúc', 'Hòa Bình'],
  'Bắc Ninh': ['Bắc Ninh', 'Bắc Giang'],
  'Hưng Yên': ['Hưng Yên', 'Thái Bình'],
  'Hải Phòng': ['Hải Phòng', 'Hải Dương'],
  'Ninh Bình': ['Ninh Bình', 'Hà Nam', 'Nam Định'],
  'Quảng Trị': ['Quảng Trị', 'Quảng Bình'],
  'Đà Nẵng': ['Đà Nẵng', 'Quảng Nam'],
  'Quảng Ngãi': ['Quảng Ngãi', 'Kon Tum'],
  'Gia Lai': ['Gia Lai', 'Bình Định'],
  'Khánh Hòa': ['Khánh Hòa', 'Ninh Thuận'],
  'Lâm Đồng': ['Lâm Đồng', 'Đắk Nông', 'Bình Thuận'],
  'Đắk Lắk': ['Đắk Lắk', 'Phú Yên'],
  'Hồ Chí Minh': ['Hồ Chí Minh', 'Bình Dương', 'Bà Rịa–Vũng Tàu'],
  'Đồng Nai': ['Đồng Nai', 'Bình Phước'],
  'Tây Ninh': ['Tây Ninh', 'Long An'],
  'Cần Thơ': ['Cần Thơ', 'Sóc Trăng', 'Hậu Giang'],
  'Vĩnh Long': ['Vĩnh Long', 'Bến Tre', 'Trà Vinh'],
  'Đồng Tháp': ['Đồng Tháp', 'Tiền Giang'],
  'Cà Mau': ['Cà Mau', 'Bạc Liêu'],
  'An Giang': ['An Giang', 'Kiên Giang'],
};
const SAME = {
  'Thừa Thiên Huế': 'Huế',
};
const BY_OLD = new Map();
for (const [now, olds] of Object.entries(MERGED)) for (const o of olds) BY_OLD.set(o, now);
export const provinceNow = (old) => BY_OLD.get(old) ?? SAME[old] ?? old;

/** A bbox wider than this is a country-scale sheet no single province describes: it gets the list
 *  (`regions`) but no dominant `region`. 'Province de Thua-thien' is 1.5° wide and is one province;
 *  the next widest is 4°. */
export const MAX_WIDTH_DEG = 2;

/** Ray casting over a ring of [lng, lat]. */
/** @param {number[][]} ring */
function inRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
/** A polygon is its outer ring minus its holes. */
/** @param {number[][][]} poly */
const inPolygon = (x, y, poly) =>
  inRing(x, y, poly[0]) && !poly.slice(1).some((h) => inRing(x, y, h));

/**
 * Build a locator from boundary GeoJSON: `(lng, lat) → name or null`.
 * @param {{ features: any[] }} geojson
 * @returns {((lng: number, lat: number) => string | null) & { intersecting: (bbox: number[]) => string[] }}
 */
export function makeLocator(geojson) {
  const feats = geojson.features.map((f) => {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const pts = polys.flatMap((p) => p[0]);
    return {
      name: cleanName(f.properties.shapeName),
      polys,
      box: [
        Math.min(...pts.map((p) => p[0])),
        Math.min(...pts.map((p) => p[1])),
        Math.max(...pts.map((p) => p[0])),
        Math.max(...pts.map((p) => p[1])),
      ],
    };
  });
  const locate = (lng, lat) =>
    feats.find(
      (f) =>
        lng >= f.box[0] &&
        lng <= f.box[2] &&
        lat >= f.box[1] &&
        lat <= f.box[3] &&
        f.polys.some((p) => inPolygon(lng, lat, p))
    )?.name ?? null;
  // Wide sheets need every positive-area overlap, including small cities that a
  // grid or percentage cutoff can miss. Clip outer rings and subtract holes.
  locate.intersecting = (bbox) => [
    ...new Set(
      feats
        .map((f) => ({
          name: f.name,
          area: f.polys.reduce(
            (sum, p) =>
              sum +
              Math.max(
                0,
                clippedArea(p[0], bbox) -
                  p.slice(1).reduce((holes, ring) => holes + clippedArea(ring, bbox), 0)
              ),
            0
          ),
        }))
        .filter((f) => f.area > 1e-12)
        .sort((a, b) => b.area - a.area)
        .map((f) => f.name)
    ),
  ];
  return locate;
}

/** Sutherland–Hodgman clipping against the sheet's geographic rectangle. */
function clippedArea(ring, [w, s, e, n]) {
  let points = ring.slice();
  for (const [axis, bound, direction] of [
    [0, w, 1],
    [0, e, -1],
    [1, s, 1],
    [1, n, -1],
  ]) {
    const clipped = [];
    for (let i = 0; i < points.length; i++) {
      const a = points[(i + points.length - 1) % points.length],
        b = points[i];
      const aIn = direction * (a[axis] - bound) >= 0,
        bIn = direction * (b[axis] - bound) >= 0;
      if (aIn !== bIn) {
        const t = (bound - a[axis]) / (b[axis] - a[axis]);
        clipped.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
      }
      if (bIn) clipped.push(b);
    }
    points = clipped;
  }
  return (
    Math.abs(
      points.reduce((sum, p, i) => {
        const q = points[(i + 1) % points.length];
        return sum + p[0] * q[1] - q[0] * p[1];
      }, 0)
    ) / 2
  );
}

/** Grid points per side sampled across a bbox. */
const GRID = 7;
/** Wide sheets sample land finer. Province membership uses polygon overlap when
 * available; the lower sample share is only a fallback for custom locators. */
const WIDE_GRID = 40;
const WIDE_SHARE = 0.02;
/** Samples on Vietnamese land needed to label a sheet at all (3 of 49): open water is not "in" a province. */
const MIN_LAND = 0.05;
/** A province joins `regions` when it holds this share of the sheet's land samples (5 of 49 at 7×7
 *  = 10%): a sheet cut by a boundary lists both sides, a large sheet lists every province it spans,
 *  and a sliver of one sample does not. The dominant one is still `region`. */
export const MIN_SHARE = 0.1;

/** `[minLng, minLat, maxLng, maxLat]` → `{ region, region_2025, regions, regions_2025, land }`, or null when the bbox is
 *  missing, has almost no Vietnamese land, or has more neighbouring land than
 *  Vietnamese. The province is the one holding most of a 7×7 grid over the sheet, not the one under
 *  its centre: a harbour plan's centre is on the water, and a centre can sit across a boundary from
 *  most of its ground. Open water counts for neither side, so a coastal sheet keeps its province.
 * @param {number[] | null | undefined} bbox
 * @param {(lng: number, lat: number) => string | null} locate
 * @param {(lng: number, lat: number) => unknown} [locateAbroad] truthy over a neighbouring country
 */
export function regionOf(bbox, locate, locateAbroad = () => null) {
  if (!Array.isArray(bbox) || bbox.length !== 4 || bbox.some((n) => !Number.isFinite(n)))
    return null;
  const [w, s, e, n] = bbox;
  if (w >= e || s >= n) return null;
  const wide = e - w > MAX_WIDTH_DEG || n - s > MAX_WIDTH_DEG;
  const G = wide ? WIDE_GRID : GRID;
  const counts = new Map();
  let land = 0;
  let abroad = 0;
  for (let i = 0; i < G; i++)
    for (let j = 0; j < G; j++) {
      const name = locate(w + ((i + 0.5) / G) * (e - w), s + ((j + 0.5) / G) * (n - s));
      if (!name) {
        if (locateAbroad(w + ((i + 0.5) / G) * (e - w), s + ((j + 0.5) / G) * (n - s))) abroad++;
        continue;
      }
      land++;
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
  if (land / G ** 2 < MIN_LAND || (!wide && abroad >= land)) return null;
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const region = ranked[0][0];
  const regions =
    wide && locate.intersecting
      ? locate.intersecting(bbox)
      : ranked.filter(([, c]) => c / land >= (wide ? WIDE_SHARE : MIN_SHARE)).map(([n]) => n);
  return {
    region: wide ? null : region,
    region_2025: wide ? null : provinceNow(region),
    regions,
    regions_2025: [...new Set(regions.map(provinceNow))],
    land: land / G ** 2,
  };
}
