#!/usr/bin/env node
// Is every map in the archive where it claims to be?
//
//   node --env-file=.env scripts/geo_audit.mjs [--key l7014-20260913] [--quiet]
//
// Exits 1 on any FAIL. Run it before publishing a sheet and after any mosaic
// rebuild.
//
// Why this exists. Every position in the archive is asserted by exactly one
// authority: a warped sheet is where its annotation says, a mosaic cell was
// where its GeoPDF's CRS said. Nothing cross-examined either, so in Sept 2026
// 285 of 437 mosaic sheets shipped ~470 m off with the warp reporting success
// and the one check that looked relevant returning 2e-12 -- it read the sheet's
// control points into the sheet's OWN datum and compared them with the
// graticule the sheet itself prints, which is self-consistency wearing the
// costume of a check.
//
// So every check here compares two things that should agree and were arrived
// at independently. None of them needs a person to say what is true.
//
// ponytail: no adjacency/seam check. The generic version needs sheet-neighbour
// topology the database does not carry, and `l7014_mosaic.py fit` already
// covers the one series where seams found the bug. Add it when a second
// lattice-less survey exists.

import { readFileSync, existsSync } from 'node:fs';
import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const arg = (n, d) => {
  const i = args.indexOf(n);
  return i > -1 ? args[i + 1] : d;
};
const quiet = args.includes('--quiet');
const KEY = arg('--key', 'l7014-20260913');

// Generous box around Vietnam. A sheet outside it means the transform put the
// paper somewhere Vietnam is not -- which is what an axis-order slip or a
// wholly wrong datum looks like, and neither throws on the way past.
const VIETNAM = [100, 5, 112, 25];
// A sheet may sit this far from its printed cell. The datum fault is ~470 m and
// the lattice is good to ~15 m, so anything in between is a safe line.
const CELL_TOL = 150;
// maps.bbox is derived from the annotation, so this is staleness, not truth.
const BBOX_TOL = 50;

// Lazy: --self-test runs the geometry with no database and no network, and a
// client built at import time would demand credentials before it got there.
const db = () =>
  createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
    auth: { persistSession: false },
  });

const findings = [];
const say = (level, check, subject, detail) => findings.push({ level, check, subject, detail });

// ── geometry ────────────────────────────────────────────────────────────────

const metres = (a, b) =>
  Math.hypot((a[0] - b[0]) * 111320 * Math.cos((a[1] * Math.PI) / 180), (a[1] - b[1]) * 110540);

/** Corners of a [w,s,e,n] box, NW NE SE SW — the order lattice.json uses. */
const boxCorners = (b) => [
  [b[0], b[3]],
  [b[2], b[3]],
  [b[2], b[1]],
  [b[0], b[1]],
];

const bounds = (pts) => [
  Math.min(...pts.map((p) => p[0])),
  Math.min(...pts.map((p) => p[1])),
  Math.max(...pts.map((p) => p[0])),
  Math.max(...pts.map((p) => p[1])),
];

/** Mirrors annotationUrlForSource() in $lib/core/iiif/annotationUrl.ts. */
function annotationUrl(source) {
  const s = (source ?? '').trim();
  try {
    const u = new URL(s);
    if (u.protocol === 'http:' || u.protocol === 'https:') return s;
  } catch {
    /* bare Allmaps image id */
  }
  return `https://annotations.allmaps.org/images/${s}`;
}

/** Least-squares affine pixel -> ground, from an annotation's control points. */
function affine(pts) {
  const solve = (target) => {
    const M = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
      ],
      r = [0, 0, 0];
    for (const p of pts) {
      const row = [p.px, p.py, 1];
      for (let j = 0; j < 3; j++) {
        for (let k = 0; k < 3; k++) M[j][k] += row[j] * row[k];
        r[j] += row[j] * target(p);
      }
    }
    for (let i = 0; i < 3; i++) {
      let piv = i;
      for (let j = i + 1; j < 3; j++) if (Math.abs(M[j][i]) > Math.abs(M[piv][i])) piv = j;
      [M[i], M[piv]] = [M[piv], M[i]];
      [r[i], r[piv]] = [r[piv], r[i]];
      if (!M[i][i]) return null;
      for (let j = i + 1; j < 3; j++) {
        const f = M[j][i] / M[i][i];
        for (let k = i; k < 3; k++) M[j][k] -= f * M[i][k];
        r[j] -= f * r[i];
      }
    }
    const x = [0, 0, 0];
    for (let i = 2; i >= 0; i--) {
      let s = r[i];
      for (let k = i + 1; k < 3; k++) s -= M[i][k] * x[k];
      x[i] = s / M[i][i];
    }
    return x;
  };
  const X = solve((p) => p.lon),
    Y = solve((p) => p.lat);
  return X && Y ? (px, py) => [X[0] * px + X[1] * py + X[2], Y[0] * px + Y[1] * py + Y[2]] : null;
}

/**
 * What an annotation actually puts on the map.
 *
 * `hull` is the control points' own extent — the same thing `maps.bbox` holds.
 * `drawn` is the georeference mask pushed through those control points, which
 * is the paper the reader sees; on a sheet with three interior GCPs the two
 * differ by hundreds of kilometres, so which one a check means has to be said.
 */
function drawnExtent(doc) {
  const anno = (doc?.type === 'AnnotationPage' ? doc.items?.[0] : doc) ?? null;
  if (!anno) return null;
  const pts = [];
  for (const f of anno.body?.features ?? []) {
    const rc = f?.properties?.resourceCoords,
      g = f?.geometry?.coordinates;
    if (Array.isArray(rc) && Array.isArray(g))
      pts.push({ px: +rc[0], py: +rc[1], lon: +g[0], lat: +g[1] });
  }
  if (pts.length < 3) return { gcps: pts.length, hull: null, drawn: null };
  const hull = bounds(pts.map((p) => [p.lon, p.lat]));
  const sel = anno.target?.selector?.value ?? '';
  const mask = /points="([^"]+)"/.exec(sel);
  const fwd = mask && affine(pts);
  const drawn = fwd
    ? bounds(
        mask[1]
          .trim()
          .split(/\s+/)
          .map((s) => {
            const [px, py] = s.split(',').map(Number);
            return fwd(px, py);
          })
      )
    : hull;
  return { gcps: pts.length, hull, drawn, hasMask: Boolean(mask) };
}

// ── A. every published map's annotation resolves and lands in Vietnam ───────

async function checkAnnotations(maps) {
  const extents = new Map();
  await Promise.all(
    maps.map(async (m) => {
      const published = m.status !== 'draft';
      const level = published ? 'FAIL' : 'WARN';
      const source = m.annotation_url || m.allmaps_id;
      const where = `${m.name} [${m.status}]`;
      if (!source) return say(level, 'annotation', where, 'no annotation_url and no allmaps_id');
      let doc;
      try {
        const res = await fetch(annotationUrl(source));
        if (!res.ok) return say(level, 'annotation', where, `annotation HTTP ${res.status}`);
        doc = await res.json();
      } catch (e) {
        return say(level, 'annotation', where, `annotation unreachable: ${e.message}`);
      }

      const ext = drawnExtent(doc);
      if (!ext) return say(level, 'annotation', where, 'annotation carries no map');
      if (!ext.hull) return say(level, 'annotation', where, `${ext.gcps} control points, needs 3`);
      extents.set(m.id, ext);

      // The third party: a box round the country. Cheap, and the only thing here
      // that catches a transform that went somewhere else entirely.
      const [w, s, e, n] = ext.drawn;
      if (w < VIETNAM[0] || s < VIETNAM[1] || e > VIETNAM[2] || n > VIETNAM[3])
        say(
          'FAIL',
          'annotation',
          where,
          `drawn outside Vietnam: [${ext.drawn.map((v) => v.toFixed(3))}]`
        );

      // Copy against its source, so staleness only — bbox is computed FROM the
      // annotation (scripts/oneoff/backfill_map_bbox.mjs) and is the GCP hull.
      if (Array.isArray(m.bbox) && m.bbox.length === 4) {
        const off = Math.max(
          ...boxCorners(m.bbox).map((p, i) => metres(p, boxCorners(ext.hull)[i]))
        );
        if (off > BBOX_TOL)
          say(
            'WARN',
            'bbox',
            where,
            `maps.bbox is ${(off / 1000).toFixed(1)} km from the annotation's control-point hull — re-georeferenced since the backfill?`
          );
      }
    })
  );
  return extents;
}

// ── B. sheets of an indexed series sit on their printed cell ────────────────

function checkLattice(maps, extents, lattice) {
  let checked = 0,
    unmasked = 0;
  for (const m of maps) {
    const sheet = m.extra_metadata?.sheet_number;
    const cell = sheet && lattice[sheet];
    const ext = extents.get(m.id);
    if (!cell || !ext?.drawn) continue;
    // Without a mask there is no paper edge to compare, only the control
    // points' own extent — and on a sheet with three interior GCPs that sits
    // kilometres inside the cell while being perfectly correct. Checking it
    // anyway would fail every sparsely-pinned sheet in the archive, so say
    // what is missing instead of inventing a verdict.
    if (!ext.hasMask) {
      unmasked++;
      say(
        'WARN',
        'cell',
        `${m.name} [${m.status}]`,
        `no georeference mask, so cell ${sheet} cannot be checked — add one in Allmaps Editor`
      );
      continue;
    }
    checked++;
    // Nearest drawn corner to each cell corner: the paper is a little larger
    // than the cell and a little rotated, so pairing by index overstates.
    const drawn = boxCorners(ext.drawn);
    const miss = cell.map((c) => Math.min(...drawn.map((d) => metres(d, c))));
    const mean = miss.reduce((a, b) => a + b, 0) / miss.length;
    if (mean > CELL_TOL)
      say(
        m.status === 'draft' ? 'WARN' : 'FAIL',
        'cell',
        `${m.name} [${m.status}]`,
        `${mean.toFixed(0)} m from printed cell ${sheet}`
      );
  }
  return { checked, unmasked };
}

// ── C. a cell held twice must agree with itself ─────────────────────────────

function checkDoubleHeld(maps, extents, mosaic) {
  let pairs = 0;
  for (const m of maps) {
    const sheet = m.extra_metadata?.sheet_number;
    const outline = sheet && mosaic.get(sheet);
    const ext = extents.get(m.id);
    if (!outline || !ext?.drawn || !ext.hasMask) continue;
    pairs++;
    const drawn = boxCorners(ext.drawn);
    const miss = boxCorners(outline).map((c) => Math.min(...drawn.map((d) => metres(d, c))));
    const mean = miss.reduce((a, b) => a + b, 0) / miss.length;
    if (mean > CELL_TOL)
      say(
        'FAIL',
        'double-held',
        `${m.name} [${m.status}]`,
        `warped sheet and mosaic cell ${sheet} disagree by ${mean.toFixed(0)} m — one of the two is wrong`
      );
  }
  return pairs;
}

// ── self-test ───────────────────────────────────────────────────────────────

/**
 * Proof that each check can reject something. The fault this whole script
 * exists for shipped past a check that returned ~0 by construction, so the
 * geometry here is exercised against inputs it must refuse -- not just against
 * the archive, which on a good day says nothing either way.
 *
 *   node scripts/geo_audit.mjs --self-test      (no database, no network)
 */
function selfTest() {
  let failed = 0;
  const ok = (cond, what) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${what}`);
    if (!cond) failed++;
  };

  // A Luoi's cell, and the same cell with the Indian 1960 datum shift skipped
  // -- the exact ~470 m the mosaic shipped with.
  const cell = [
    [106.9958138, 16.5016347],
    [107.2457818, 16.5016397],
    [107.2457872, 16.2516607],
    [106.9958192, 16.2516558],
  ];
  const unshifted = cell.map(([x, y]) => [x + 0.0041862, y - 0.0016347]);
  const meanMiss = (drawn) =>
    cell.map((c) => Math.min(...drawn.map((d) => metres(d, c)))).reduce((a, b) => a + b, 0) / 4;

  ok(meanMiss(cell) < 1, 'a sheet on its cell measures ~0 m');
  const skipped = meanMiss(unshifted);
  ok(
    skipped > CELL_TOL,
    `the skipped datum shift is rejected (${skipped.toFixed(0)} m > ${CELL_TOL} m)`
  );

  // An affine recovered from three points must reproduce a fourth.
  const truth = (px, py) => [106.5 + px * 1e-4 + py * 2e-6, 10.8 - py * 1e-4 + px * 1e-6];
  const pts = [
    [0, 0],
    [1000, 0],
    [0, 1000],
  ].map(([px, py]) => {
    const [lon, lat] = truth(px, py);
    return { px, py, lon, lat };
  });
  const fwd = affine(pts);
  const [gx, gy] = fwd(1000, 1000);
  ok(metres([gx, gy], truth(1000, 1000)) < 0.5, 'affine from 3 control points reproduces a 4th');
  ok(
    affine([
      { px: 0, py: 0, lon: 1, lat: 1 },
      { px: 1, py: 1, lon: 2, lat: 2 },
      { px: 2, py: 2, lon: 3, lat: 3 },
    ]) === null,
    'collinear control points are refused, not fitted'
  );

  // The country box, which is what catches a transform that went elsewhere.
  const inVietnam = (b) =>
    !(b[0] < VIETNAM[0] || b[1] < VIETNAM[1] || b[2] > VIETNAM[2] || b[3] > VIETNAM[3]);
  ok(inVietnam([106.5, 10.7, 106.8, 10.9]), 'Saigon is inside the country box');
  ok(!inVietnam([-0.2, 5.5, 0.2, 5.9]), 'a lon/lat axis swap landing off West Africa is rejected');

  // The mask/hull distinction the cell check turns on.
  const sparse = {
    type: 'Annotation',
    body: {
      features: [
        [500, 500],
        [600, 520],
        [520, 600],
      ].map(([px, py]) => {
        const [lon, lat] = truth(px, py);
        return { properties: { resourceCoords: [px, py] }, geometry: { coordinates: [lon, lat] } };
      }),
    },
    target: { selector: { value: '<svg><polygon points="0,0 2000,0 2000,2000 0,2000" /></svg>' } },
  };
  const ext = drawnExtent(sparse);
  ok(
    ext.hasMask && metres([ext.drawn[0], ext.drawn[1]], [ext.hull[0], ext.hull[1]]) > 1000,
    'the drawn paper is distinguished from the control-point hull'
  );

  console.log(`\nself-test: ${failed ? `${failed} failed` : 'all passed'}`);
  process.exit(failed ? 1 : 0);
}

if (args.includes('--self-test')) selfTest();

// ── run ─────────────────────────────────────────────────────────────────────

const { data: maps, error } = await db()
  .from('maps')
  .select('id,name,status,collection,bbox,allmaps_id,annotation_url,extra_metadata');
if (error) {
  console.error(`maps: ${error.message}`);
  process.exit(2);
}

const latticePath = 'work/l7014/lattice.json';
const mosaicPath = `work/l7014/build/${KEY}.geojson`;
const lattice = existsSync(latticePath)
  ? JSON.parse(readFileSync(latticePath, 'utf8')).cells
  : null;
const mosaic = new Map();
if (existsSync(mosaicPath)) {
  for (const f of JSON.parse(readFileSync(mosaicPath, 'utf8')).features) {
    const g = f.geometry;
    const ring = (g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates]).flatMap((p) => p[0]);
    mosaic.set(f.properties.sheet, bounds(ring));
  }
}

const extents = await checkAnnotations(maps);
const onCell = lattice ? checkLattice(maps, extents, lattice) : null;
const pairs = mosaic.size ? checkDoubleHeld(maps, extents, mosaic) : null;

const rank = { FAIL: 0, WARN: 1 };
findings.sort((a, b) => rank[a.level] - rank[b.level] || a.check.localeCompare(b.check));
const fails = findings.filter((f) => f.level === 'FAIL');
if (!quiet || fails.length) {
  for (const f of findings)
    console.log(
      `  ${f.level}  ${f.check.padEnd(12)} ${f.subject.slice(0, 46).padEnd(46)} ${f.detail}`
    );
  if (findings.length) console.log('');
}
console.log(`geo_audit: ${maps.length} maps, ${extents.size} with usable control points`);
if (lattice)
  console.log(
    `  ${onCell.checked} checked against their printed cell` +
      `${onCell.unmasked ? `, ${onCell.unmasked} skipped for want of a mask` : ''}` +
      ` (${Object.keys(lattice).length} cells in the index)`
  );
else
  console.log(
    `  no ${latticePath} — run \`l7014_mosaic.py corners\` to check sheets against their cell`
  );
if (mosaic.size)
  console.log(`  ${pairs} held both as a warped sheet and as mosaic pixels, cross-checked`);
else console.log(`  no ${mosaicPath} — nothing to cross-check the mosaic against`);
console.log(`  ${fails.length} fail, ${findings.length - fails.length} warn`);
process.exit(fails.length ? 1 : 0);
