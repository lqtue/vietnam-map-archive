#!/usr/bin/env node
// Select the maps worth digitalizing for one study area, and cut each one down
// to just that area in its own source pixels.
//
//   node --env-file=.env scripts/collection_aoi.mjs --aoi district4
//   node --env-file=.env scripts/collection_aoi.mjs --aoi district4 --enqueue-ocr
//
// Two jobs, because doing either alone wastes the other:
//
// 1. WHICH SHEETS. Coverage alone picks the wrong maps. "Carte du Sud-Vietnam"
//    (1958) contains 100% of District 4 — in 23x26 pixels, at 105 m per pixel,
//    one pixel per city block. A study area needs sheets that both *contain*
//    it and *resolve* it, so the ranking is on ground resolution (metres per
//    source pixel) with coverage as a second gate.
//
// 2. WHICH PIXELS. The study area is a small part of most sheets, and the
//    georeference already knows which part: run the AOI backwards through the
//    annotation and you get the rectangle to crop, in source pixels. Passed as
//    the job's `neatline`, that becomes `ocr.py --crop`, which restricts the
//    tile grid and therefore the IIIF region requests. On the 1930 Gia Dinh
//    province sheet District 4 is ~1% of the paper; OCR'ing the whole thing to
//    read one district is ~100x the tiles, the API spend and the wall time.
//
//    The trade: a legend, title or scale bar outside the AOI is not read. For a
//    study-area pass that is the point; a whole-sheet run is a separate job.
//
// Needs `maps.bbox` — run scripts/oneoff/backfill_map_bbox.mjs first.
//
// Flags: --min-cov 0.15 · --max-mpp 3 · --pad-px 100 · --limit N · --dry
//        --tile-metres 1400  (ground per Gemini call; the tile is derived)
//        --force · --json · --selftest

import { readFileSync, existsSync } from 'node:fs';
import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';

// Named study areas. The geometry is defined once, in a file, with its
// provenance in the file — not retyped as a bbox at each call site.
const AREAS = {
  district4: 'work/analysis/district4/district4.geojson',
};

const args = process.argv.slice(2);
const flag = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i > -1 ? args[i + 1] : fallback;
};
const dry = args.includes('--dry');
const enqueue = args.includes('--enqueue-ocr');
// Re-queue sheets that already hold extractions. Additive, not destructive:
// `ocr_labels` is keyed by (map_id, run_id, tile_x, tile_y, text), so a
// new run sits beside the old ones and the series picks a run_id. Needed
// because the two sheets already OCR'd were read whole-sheet at the 2.34x
// downsample, and one of them across five separate experimental runs.
const force = args.includes('--force');
const asJson = args.includes('--json');
const minCov = Number(flag('min-cov', 0.15));
const maxMpp = Number(flag('max-mpp', 3));
// A small margin, because a label sits beside the thing it names and can be
// printed just past the boundary. Kept deliberately small for two reasons:
// the AOI polygon already overshoots ~7% (canal centrelines put half of each
// canal inside the ring), and a study area that reaches the edge of the
// mapped area will pull the sheet's *marginalia* into the crop. On the 1959
// Đô thành Sài Gòn sheet the street-name index begins within 200px of the
// river, so a 200px pad fed a dense column of index entries to OCR — hundreds
// of junk labels at map coordinates they never had. Raise it only for a sheet
// whose study area sits well inside the neatline.
const padPx = Number(flag('pad-px', 100));
const limit = Number(flag('limit', Infinity));
// How much *ground* one Gemini call is asked to read, in metres. This is the
// knob that matters, and it is not pixels.
//
// Measured on the 1959 sheet (2.80 m/px), same crop, same 1:1 rendering, only
// the tile size changed:
//
//     2048 px tile = 5.7 km of ground per call ->  5 labels,  0 street names
//     1024 px tile = 2.9 km                    -> 10 labels,  1 street name
//      512 px tile = 1.4 km                    -> 15 labels,  4 street names
//
// Three times the labels off an unchanged scan, and only the 512 px run found
// the district's own name on the sheet. Rendering did not cause it: 1024 px
// rendered 1:1 and rendered at 2x gave byte-identical output, so upsampling
// past the scan buys nothing. What starves the read is one call covering too
// much ground.
//
// A fixed pixel tile therefore means something different on every sheet - 2048
// px is 1.7 km on the 1923 sheet and 5.7 km on the 1959 one, which is why the
// coarse sheets looked empty and got blamed on their scans. Fixing the ground
// footprint makes sheets comparable, which a time series needs anyway.
const tileMetres = Number(flag('tile-metres', 1400));
// At least 1024 px reaches the model even for a small tile: upsampling adds no
// information, but a very small image is not what these prompts expect.
const MIN_RENDER = 1024;
// The pixel ceiling exists so the rule can only ever make a sheet finer. A
// sharp sheet needs a huge tile to reach 1400 m — 1882 at 0.34 m/px wants 4118
// px — and raising it there did measurable harm: that sheet went from 0.70 km
// per call to 1.39 km and its District 4 label count fell 11 -> 10, the only
// regression in the collection. Every sheet the change made *much* finer
// improved (1895 9 -> 11, 1942 13 -> 23, 1959 1 -> 5). So cap at 2048 px and
// let sharp sheets keep the smaller ground footprint they already had.
const TILE_PX_RANGE = [384, 2048];

// Metres per degree at District 4's latitude (10.76N). Good to ~0.1% over a
// study area this size; a full projection would be false precision.
const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 109368;

/** Absolute polygon area of a ring, by the shoelace formula. Unsigned, so
 *  winding order does not matter; rotation-invariant, which is the point. */
export function ringArea(ring) {
  let a = 0;
  for (let i = 0, n = ring.length; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

/** Sum of `ringArea` over several rings — the outer ring of each part of a
 *  Polygon or MultiPolygon, kept separate on purpose. Concatenating rings
 *  before running the shoelace formula (holes into their outer ring, or one
 *  MultiPolygon part into another) turns the implicit closing edges between
 *  them into a self-intersecting shape whose *signed* area can be anything,
 *  including near zero when two parts happen to wind oppositely — summing
 *  each ring's unsigned area separately cannot do that. */
export function polygonArea(rings) {
  return rings.reduce((sum, r) => sum + ringArea(r), 0);
}

/** Fraction of `aoi`'s area that falls inside `bbox`. 0 when they miss. */
export function coverage(bbox, aoi) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return 0;
  const w = Math.min(bbox[2], aoi[2]) - Math.max(bbox[0], aoi[0]);
  const h = Math.min(bbox[3], aoi[3]) - Math.max(bbox[1], aoi[1]);
  if (w <= 0 || h <= 0) return 0;
  return (w * h) / ((aoi[2] - aoi[0]) * (aoi[3] - aoi[1]));
}

/** The AOI clipped to a map's extent, or null when they are disjoint. */
export function clip(bbox, aoi) {
  const r = [
    Math.max(bbox[0], aoi[0]),
    Math.max(bbox[1], aoi[1]),
    Math.min(bbox[2], aoi[2]),
    Math.min(bbox[3], aoi[3]),
  ];
  return r[0] < r[2] && r[1] < r[3] ? r : null;
}

/**
 * An `[x, y, w, h]` crop in source pixels covering every point in `ring`,
 * padded, then clamped to the image. Null when the area misses the sheet.
 *
 * Points outside the georeference's control-point hull extrapolate, and can
 * land off the paper entirely — hence the clamp, not an assertion.
 */
export function pixelRect(points, imgW, imgH, pad = 0) {
  const xs = points.map((p) => p[0]).filter(Number.isFinite);
  const ys = points.map((p) => p[1]).filter(Number.isFinite);
  if (!xs.length) return null;
  const x0 = Math.max(0, Math.floor(Math.min(...xs) - pad));
  const y0 = Math.max(0, Math.floor(Math.min(...ys) - pad));
  const x1 = Math.min(imgW, Math.ceil(Math.max(...xs) + pad));
  const y1 = Math.min(imgH, Math.ceil(Math.max(...ys) + pad));
  if (x1 <= x0 || y1 <= y0) return null;
  return [x0, y0, x1 - x0, y1 - y0];
}

function selftest() {
  const eq = (a, b, msg) => {
    if (Math.abs(a - b) > 1e-9) throw new Error(`${msg}: ${a} !== ${b}`);
  };
  const aoi = [0, 0, 2, 2]; // 4 square degrees
  eq(coverage([-1, -1, 3, 3], aoi), 1, 'a map containing the AOI covers all of it');
  eq(coverage([0, 0, 1, 2], aoi), 0.5, 'half the AOI is half coverage');
  eq(coverage([0, 0, 1, 1], aoi), 0.25, 'a quarter is a quarter');
  eq(coverage([5, 5, 6, 6], aoi), 0, 'a disjoint map covers nothing');
  eq(coverage([2, 0, 3, 2], aoi), 0, 'touching edge-on is not coverage');
  eq(coverage(null, aoi), 0, 'a missing bbox covers nothing');
  eq(coverage([0.9, 0.9, 1.1, 1.1], aoi), 0.01, 'a small inset scores small');
  if (JSON.stringify(clip([-1, -1, 1, 1], aoi)) !== '[0,0,1,1]') throw new Error('clip');
  if (clip([5, 5, 6, 6], aoi) !== null) throw new Error('clip disjoint should be null');

  // Shoelace: a unit square is 1 either winding, a 2x3 rectangle is 6.
  eq(
    ringArea([
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ]),
    1,
    'unit square'
  );
  eq(
    ringArea([
      [0, 0],
      [0, 1],
      [1, 1],
      [1, 0],
    ]),
    1,
    'winding order must not matter'
  );
  eq(
    ringArea([
      [0, 0],
      [2, 0],
      [2, 3],
      [0, 3],
    ]),
    6,
    '2x3 rectangle'
  );
  // Rotating a square by 45 degrees must not change its area — this is the
  // property the resolution measure depends on.
  eq(
    ringArea([
      [1, 0],
      [0, 1],
      [-1, 0],
      [0, -1],
    ]),
    2,
    'rotated square keeps its area'
  );
  eq(
    ringArea([
      [0, 0],
      [1, 1],
      [2, 2],
    ]),
    0,
    'a degenerate ring has no area'
  );

  // `polygonArea` is what stands between the AOI's real shape and the bug this
  // replaces: `ringArea` given a single flattened concatenation of several
  // rings (a MultiPolygon's parts, or an outer ring plus its holes), which
  // treats the whole thing as one self-intersecting ring instead of several.
  {
    // Two square parts of a MultiPolygon, wound oppositely and far enough
    // apart that concatenating them is not a no-op the way today's one-ring
    // AOI happens to make it.
    const partA = [
      [0, 0],
      [2, 0],
      [2, 2],
      [0, 2],
    ]; // area 4
    const partB = [
      [10, 0],
      [10, 3],
      [13, 3],
      [13, 0],
    ]; // area 9, wound the other way
    eq(polygonArea([partA, partB]), 13, 'MultiPolygon: rings summed, not concatenated');
    const concatenated = ringArea([...partA, ...partB]);
    if (Math.abs(concatenated - 13) < 1e-9) {
      throw new Error('fixture no longer demonstrates the concatenation bug — pick other rings');
    }

    // A ring with a hole: outer-rings-only means the hole is dropped, not
    // flattened in alongside the outer ring (which is what corrupts the area
    // today — see the module-level comment above `outerRings`).
    const outer = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
    ]; // area 100
    const hole = [
      [3, 3],
      [3, 7],
      [7, 7],
      [7, 3],
    ]; // area 16 — must not be subtracted or added in
    eq(polygonArea([outer]), 100, 'polygon with a hole: outer ring only');
    const flattenedWithHole = ringArea([...outer, ...hole]);
    if (Math.abs(flattenedWithHole - 100) < 1e-9) {
      throw new Error('fixture no longer demonstrates the hole-flattening bug — pick other rings');
    }
  }

  const pts = [
    [100, 200],
    [300, 500],
  ];
  if (JSON.stringify(pixelRect(pts, 1000, 1000, 0)) !== '[100,200,200,300]')
    throw new Error('rect');
  // Padding grows the rect but never past the image, and never negative.
  if (JSON.stringify(pixelRect(pts, 1000, 1000, 150)) !== '[0,50,450,600]')
    throw new Error('rect pad clamps at 0');
  if (JSON.stringify(pixelRect(pts, 250, 250, 0)) !== '[100,200,150,50]')
    throw new Error('rect clamps to image');
  // Extrapolated points off the paper: clamped away to nothing, not negative.
  if (
    pixelRect(
      [
        [-900, -900],
        [-800, -800],
      ],
      1000,
      1000,
      0
    ) !== null
  )
    throw new Error('offsheet should be null');
  if (pixelRect([[NaN, NaN]], 1000, 1000, 0) !== null) throw new Error('NaN should be null');
  console.log('selftest ok');
}
if (args.includes('--selftest')) {
  selftest();
  process.exit(0);
}

// ── resolve the study area ───────────────────────────────────────────────────
// Either a polygon (a name from AREAS, or a .geojson path) or a bare bbox. A
// polygon is better: its corners are land, so the pixel crop follows the shape
// of the district instead of the shape of its bounding box.
const rawAoi = flag('aoi', 'district4');
let ring = null;
// One entry per polygon's outer ring — never flattened together with holes
// or with each other. See `polygonArea` for why. `ring` stays the flat point
// list for the two uses that only need an unordered bag of points (the bbox
// below, and the pixel-space rect in `aoiInPixels`); `outerRings` is what
// area gets computed from.
let outerRings = null;
let aoiBbox = null;
const asPath = AREAS[rawAoi] ?? rawAoi;
if (typeof asPath === 'string' && /\.(geo)?json$/i.test(asPath)) {
  if (!existsSync(asPath)) {
    console.error(`no such AOI file: ${asPath}`);
    process.exit(1);
  }
  const obj = JSON.parse(readFileSync(asPath, 'utf8'));
  const geom =
    obj.type === 'Feature'
      ? obj.geometry
      : obj.type === 'FeatureCollection'
        ? obj.features[0].geometry
        : obj;
  // Outer rings only; a study area's holes do not change its extent, and for
  // a metres-per-pixel ratio (not an exact area) dropping them rather than
  // subtracting them is the simplest correct thing to do.
  outerRings =
    geom.type === 'MultiPolygon' ? geom.coordinates.map((poly) => poly[0]) : [geom.coordinates[0]];
  ring = outerRings.flat(1);
  const lon = ring.map((p) => p[0]);
  const lat = ring.map((p) => p[1]);
  aoiBbox = [Math.min(...lon), Math.min(...lat), Math.max(...lon), Math.max(...lat)];
} else {
  aoiBbox = String(rawAoi).split(',').map(Number);
  if (
    aoiBbox.length !== 4 ||
    aoiBbox.some((n) => !Number.isFinite(n)) ||
    aoiBbox[0] >= aoiBbox[2] ||
    aoiBbox[1] >= aoiBbox[3]
  ) {
    console.error(
      `bad --aoi: ${rawAoi}\nuse minLng,minLat,maxLng,maxLat, a .geojson path, or one of: ${Object.keys(AREAS)}`
    );
    process.exit(1);
  }
  ring = [
    [aoiBbox[0], aoiBbox[1]],
    [aoiBbox[2], aoiBbox[1]],
    [aoiBbox[2], aoiBbox[3]],
    [aoiBbox[0], aoiBbox[3]],
  ];
  outerRings = [ring];
}

// The study area's true ground area — the polygon's, not its bounding box's.
const aoiGroundArea = polygonArea(outerRings) * M_PER_DEG_LON * M_PER_DEG_LAT;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: maps, error } = await db
  .from('maps')
  .select('id, name, year, status, bbox, iiif_image, allmaps_id, annotation_url, source_type')
  .not('bbox', 'is', null);
if (error) throw error;

const touching = maps.map((m) => ({ m, cov: coverage(m.bbox, aoiBbox) })).filter((r) => r.cov > 0);

/** Source pixel dimensions, which only the IIIF info.json knows. */
async function pixelSize(iiif) {
  if (!iiif) return null;
  const base = iiif.replace(/\/info\.json$/, '').replace(/\/$/, '');
  try {
    const res = await fetch(`${base}/info.json`);
    if (!res.ok) return null;
    const j = await res.json();
    return typeof j.width === 'number' && typeof j.height === 'number' ? [j.width, j.height] : null;
  } catch {
    return null;
  }
}

/** The AOI ring in this map's source pixels, via the inverse georeference. */
async function aoiInPixels(m, imgW, imgH) {
  const url =
    m.annotation_url ||
    (m.allmaps_id ? `https://annotations.allmaps.org/images/${m.allmaps_id}` : null);
  if (!url) return { rect: null, why: 'no annotation' };
  try {
    const res = await fetch(url);
    if (!res.ok) return { rect: null, why: `annotation HTTP ${res.status}` };
    const parsed = parseAnnotation(await res.json());
    if (!parsed.length) return { rect: null, why: 'annotation has no map' };
    const t = GcpTransformer.fromGeoreferencedMap(parsed[0]);
    const toResource = (p) => {
      try {
        return t.transformToResource([p[0], p[1]]);
      } catch {
        return [NaN, NaN];
      }
    };
    // Transform each outer ring on its own — same reason `outerRings` is kept
    // apart from a single flattened `ring` at the AOI-resolution step above.
    const pxRings = outerRings.map((r) => r.map(toResource));
    const pts = pxRings.flat(1);
    if (pts.some((p) => !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) {
      return { rect: null, why: 'AOI does not transform' };
    }
    // Ground metres per source pixel, from the georeference itself. Comparing
    // the AOI's real area with the pixel area it maps onto is rotation- and
    // skew-invariant, and it is measured over the study area rather than over
    // the whole sheet — the earlier bbox/width ratio was neither, and read
    // 0.33 m/px on the 1912 sheet where the truth is nearer 1.8.
    const pxArea = polygonArea(pxRings);
    const mpp = pxArea > 0 ? Math.sqrt(aoiGroundArea / pxArea) : null;
    const rect = pixelRect(pts, imgW, imgH, padPx);
    return { rect, mpp, why: rect ? null : 'AOI falls outside the sheet' };
  } catch (e) {
    return { rect: null, why: String(e?.message ?? e) };
  }
}

const rows = [];
let cursor = 0;
async function worker() {
  while (cursor < touching.length) {
    const { m, cov } = touching[cursor++];
    const size = await pixelSize(m.iiif_image);
    const [w, h] = size ?? [null, null];
    const row = {
      ...m,
      cov,
      w,
      h,
      mpp: null,
      aoiDeg: clip(m.bbox, aoiBbox),
      rect: null,
      rectWhy: null,
    };
    if (w) {
      const { rect, mpp, why } = await aoiInPixels(m, w, h);
      row.rect = rect;
      row.mpp = mpp ?? null;
      row.rectWhy = why;
    } else {
      row.rectWhy = 'no image';
    }
    rows.push(row);
  }
}
await Promise.all(Array.from({ length: Math.min(8, touching.length) }, worker));

rows.sort((a, b) => (a.mpp ?? Infinity) - (b.mpp ?? Infinity));
const picked = rows
  .filter((r) => r.cov >= minCov && r.mpp !== null && r.mpp <= maxMpp && r.rect)
  .slice(0, limit);
const rejected = rows.filter((r) => !picked.includes(r));

const sheetShare = (r) => (r.rect[2] * r.rect[3]) / (r.w * r.h);

/** Tile geometry for one sheet, sized so each call reads `tileMetres` of ground. */
function tiling(r) {
  const raw = Math.round(tileMetres / r.mpp);
  const tile = Math.min(TILE_PX_RANGE[1], Math.max(TILE_PX_RANGE[0], raw));
  const overlap = Math.round(tile / 4);
  const step = tile - overlap;
  const tiles =
    Math.ceil(Math.max(r.rect[2] - overlap, 1) / step) *
    Math.ceil(Math.max(r.rect[3] - overlap, 1) / step);
  return { tile, overlap, render: Math.max(tile, MIN_RENDER), tiles, ground: tile * r.mpp };
}

if (asJson) {
  console.log(JSON.stringify({ aoi: aoiBbox, minCov, maxMpp, padPx, picked, rejected }, null, 2));
} else {
  const km2 =
    ((aoiBbox[2] - aoiBbox[0]) * M_PER_DEG_LON * (aoiBbox[3] - aoiBbox[1]) * M_PER_DEG_LAT) / 1e6;
  console.log(
    `AOI ${rawAoi}  bbox ${aoiBbox.map((n) => n.toFixed(4)).join(',')}  (${km2.toFixed(2)} km² box, ${ring.length} ring points)`
  );
  console.log(
    `${maps.length} maps with a bbox · ${touching.length} touch the AOI · gates: coverage >= ${(minCov * 100).toFixed(0)}%, <= ${maxMpp} m/px · crop pad ${padPx}px\n`
  );
  console.log(`=== COLLECTION — ${picked.length} maps ===`);
  console.log(`each call reads ~${tileMetres} m of ground, so the tile is sized per sheet\n`);
  console.log('year   cov   m/px    tile px   ground/call   tiles   crop x,y,w,h          name');
  for (const r of picked) {
    console.log(
      [
        String(r.year ?? '????').padEnd(5),
        `${(r.cov * 100).toFixed(0).padStart(3)}%`,
        `${r.mpp.toFixed(2).padStart(5)}`,
        `${String(tiling(r).tile).padStart(6)}px`,
        `${(tiling(r).ground / 1000).toFixed(2).padStart(9)} km`,
        String(tiling(r).tiles).padStart(5),
        r.rect.join(',').padEnd(21),
        r.name.slice(0, 30),
      ].join('  ')
    );
  }
  const totalPx = picked.reduce((s, r) => s + r.w * r.h, 0);
  const cropPx = picked.reduce((s, r) => s + r.rect[2] * r.rect[3], 0);
  const calls = picked.reduce((s, r) => s + tiling(r).tiles, 0);
  console.log(
    `\nwhole sheets ${(totalPx / 1e6).toFixed(0)} Mpx → District 4 crops ${(cropPx / 1e6).toFixed(0)} Mpx ` +
      `(${((cropPx / totalPx) * 100).toFixed(0)}% of the paper, ${(totalPx / cropPx).toFixed(1)}x less to read)`
  );
  console.log(
    `${calls} Gemini calls total — the crop is what pays for reading the district this finely`
  );
  console.log(`\n=== REJECTED — ${rejected.length} ===`);
  for (const r of rejected) {
    const why =
      r.mpp === null
        ? 'no image'
        : r.cov < minCov
          ? `covers only ${(r.cov * 100).toFixed(0)}%`
          : r.mpp > maxMpp
            ? `${r.mpp.toFixed(1)} m/px too coarse`
            : (r.rectWhy ?? 'no crop');
    console.log(`${String(r.year ?? '????').padEnd(5)}  ${why.padEnd(24)} ${r.name.slice(0, 44)}`);
  }
  console.log(
    `\n--maps for work/analysis/district4/series.py:\n${picked.map((r) => r.id).join(',')}`
  );
}

if (!enqueue) process.exit(0);

// ── queue the crops ─────────────────────────────────────────────────────────
// Same `pipeline_jobs` row /api/admin/maps/[id]/ocr writes, plus `neatline`,
// which vma_worker.py turns into `ocr.py --crop x,y,w,h`. Nothing runs until a
// worker claims it:
//   source work/ocr/.venv/bin/activate && python work/worker/vma_worker.py
const { data: live } = await db
  .from('pipeline_jobs')
  .select('map_id')
  .eq('kind', 'ocr')
  .in('status', ['queued', 'claimed', 'running']);
const inFlight = new Set((live ?? []).map((r) => r.map_id));

// One count per map, not one big select. `.select('map_id').in(...)` looked
// simpler and was wrong: PostgREST caps a response at 1000 rows, and the two
// maps already OCR'd hold 916 + 84 = exactly 1000, so the second map's rows
// fell off the end and it was queued twice.
const hasOcr = new Set();
for (const r of picked) {
  const { count, error: cErr } = await db
    .from('ocr_labels')
    .select('*', { count: 'exact', head: true })
    .eq('map_id', r.id);
  if (cErr) throw cErr;
  if (count) hasOcr.add(r.id);
}

console.log(`\n${dry ? 'would queue' : 'queueing'} ocr (cropped to the AOI):`);
let queued = 0;
for (const r of picked) {
  if (inFlight.has(r.id)) {
    console.log(`  skip ${r.year} ${r.name.slice(0, 38)} — already in flight`);
    continue;
  }
  if (hasOcr.has(r.id) && !force) {
    console.log(
      `  skip ${r.year} ${r.name.slice(0, 38)} — already has extractions (--force to add a run)`
    );
    continue;
  }
  const t = tiling(r);
  console.log(
    `  ${dry ? '(dry) ' : ''}${r.year}  ${r.rect.join(',').padEnd(22)}  ` +
      `${t.tile}px x${t.tiles}  ${r.name.slice(0, 30)}`
  );
  if (dry) continue;
  // Per map, not per second: a shared run_id would collapse every map's run
  // summary into one and break `--ocr-run-id` seeding for segmentation.
  const run_id = `${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}-${r.id.slice(0, 8)}`;
  const { error: insErr } = await db.from('pipeline_jobs').insert({
    kind: 'ocr',
    map_id: r.id,
    payload: {
      run_id,
      tile_size: t.tile,
      overlap: t.overlap,
      render_size: t.render,
      concurrency: 3,
      min_confidence: 0.5,
      auto: true,
      neatline: r.rect,
      aoi: rawAoi,
    },
  });
  if (insErr && insErr.code !== '23505') throw insErr; // 23505 = one-live-job index
  if (!insErr) queued++;
}
if (!dry) console.log(`queued ${queued}`);
