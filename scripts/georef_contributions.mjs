#!/usr/bin/env node
// Report where the georeference on Allmaps and the copy this site serves disagree.
//
// Georeferences are edited on Allmaps (annotations.allmaps.org). The site shows its own stored
// copy, `annotations/<map uuid>.json` in the private Supabase bucket, which changes only when
// someone runs a sync. So two things go unnoticed: a contributor georeferences a queue map on
// Allmaps, and a published map's Allmaps annotation drifts from our copy. Anyone can edit an
// Allmaps annotation, which is why this is a report and not a sync: **this is the review step
// before any sync.** Read the table, look at the displaced points, then decide. It never writes
// to the database, to storage, or to disk.
//
//   node --env-file=.env scripts/georef_contributions.mjs             # grouped table
//   node --env-file=.env scripts/georef_contributions.mjs --json      # machine output
//   node --env-file=.env scripts/georef_contributions.mjs --all       # also list in-sync rows
//   node scripts/georef_contributions.mjs --selftest                  # offline, pins the diff
//
// For every map with a non-null `maps.allmaps_id`:
//   upstream  GET annotations.allmaps.org/images/<allmaps_id>, Cache-Control: no-cache. 404 = nothing there.
//   ours      the bucket object `<map uuid>.json`, fetched with the service key. The public
//             storage URL does not work: the bucket is private (migration 097).
//
// Classes:
//   new contribution  upstream exists, ours does not (never synced)
//   drifted           both exist and the GCPs, transformation or mask differ
//   in sync           same
//   upstream missing  ours exists, Allmaps 404. Normal for maps the pipeline made. Counted only.
//   nothing yet       an allmaps_id, but nothing on Allmaps and no copy of ours (queue maps). Counted only.
//   error             a request failed twice; the row says which side
//
// A drifted row carries the GCP counts (ours -> upstream), the modified dates, the transformation
// change, points added and removed, and for points matched by ground coordinate (lon/lat equal to
// 1e-6) the displacement in pixels. A source width/height mismatch is flagged loudly: that is a
// different scan, and syncing it would move every point.
//
// Sync commands are printed for the actionable rows. They use sync_district4_annotations.mjs,
// which works for any map despite its name; it is a dry run unless given --apply.
//
// Politeness: at most 4 requests in flight to Allmaps, one retry each.

import { serviceClient } from './lib/db.mjs';
import { flag } from './lib/cli.mjs';
import assert from 'node:assert/strict';

const ALLMAPS = 'https://annotations.allmaps.org/images';
const BUCKET = 'annotations';
const CONCURRENCY = 4;
const PX_EPS = 1e-6; // a GCP that "did not move"
const SYNC = 'node --env-file=.env scripts/oneoff/sync_district4_annotations.mjs';

// ---------- the diff: pure, so --selftest can pin it ----------

/**
 * One AnnotationPage (or a bare Annotation) flattened to what a georeference is.
 * @param {any} ann
 */
export function summarise(ann) {
  const items = ann?.type === 'Annotation' ? [ann] : (ann?.items ?? ann?.maps ?? []);
  const gcps = [];
  const transformations = new Set();
  const masks = [];
  let modified = null;
  let size = null;
  for (const item of items) {
    for (const f of item?.body?.features ?? []) {
      const px = f?.properties?.resourceCoords;
      const ll = f?.geometry?.coordinates;
      if (Array.isArray(px) && Array.isArray(ll)) {
        gcps.push({ x: +px[0], y: +px[1], lon: +ll[0], lat: +ll[1] });
      }
    }
    const t = item?.body?.transformation;
    if (t) transformations.add(`${t.type ?? '?'}${t.options?.order ? `/${t.options.order}` : ''}`);
    const mask = item?.target?.selector?.value;
    if (mask) masks.push(String(mask));
    if (item?.modified && (!modified || item.modified > modified)) modified = item.modified;
    const s = item?.target?.source;
    if (!size && typeof s?.width === 'number' && typeof s?.height === 'number') {
      size = { width: s.width, height: s.height };
    }
  }
  return {
    gcps,
    transformation: [...transformations].sort().join('+') || null,
    // Compared as the SVG path string Allmaps stores, whitespace-normalised.
    mask: masks.map((m) => m.replace(/\s+/g, ' ').trim()).join('|') || null,
    modified,
    size,
  };
}

const groundKey = (g) => `${g.lon.toFixed(6)},${g.lat.toFixed(6)}`;

/**
 * Match points by ground coordinate. A key seen twice pairs in order. Rounding to 1e-6 can put
 * two points that are 1e-6 apart in different keys, which reads as one removed and one added;
 * that is the safe direction to be wrong in.
 */
function matchPoints(ours, theirs) {
  const pool = new Map();
  for (const g of theirs) {
    const k = groundKey(g);
    if (!pool.has(k)) pool.set(k, []);
    pool.get(k).push(g);
  }
  const matched = [];
  const removed = [];
  for (const g of ours) {
    const hit = pool.get(groundKey(g))?.shift();
    if (hit) matched.push({ ours: g, theirs: hit });
    else removed.push(g);
  }
  const added = [...pool.values()].flat();
  return { matched, added, removed };
}

/**
 * @param {ReturnType<typeof summarise> | null} ours  null = no stored copy
 * @param {ReturnType<typeof summarise> | null} theirs null = Allmaps 404
 */
export function classify(ours, theirs) {
  if (!ours && !theirs) return { cls: 'nothing yet' };
  if (!theirs) return { cls: 'upstream missing', ours: ours.gcps.length };
  if (!ours) {
    return {
      cls: 'new contribution',
      theirs: theirs.gcps.length,
      transformation: theirs.transformation,
      modified: theirs.modified,
    };
  }
  const { matched, added, removed } = matchPoints(ours.gcps, theirs.gcps);
  const moved = matched
    .map(({ ours: a, theirs: b }) => ({
      lon: a.lon,
      lat: a.lat,
      from: [a.x, a.y],
      to: [b.x, b.y],
      px: Math.hypot(b.x - a.x, b.y - a.y),
    }))
    .filter((m) => m.px > PX_EPS)
    .sort((a, b) => b.px - a.px);
  const transformationChanged = ours.transformation !== theirs.transformation;
  const maskChanged = ours.mask !== theirs.mask;
  const sizeMismatch =
    ours.size &&
    theirs.size &&
    (ours.size.width !== theirs.size.width || ours.size.height !== theirs.size.height)
      ? { ours: ours.size, theirs: theirs.size }
      : null;
  const drifted =
    moved.length > 0 ||
    added.length > 0 ||
    removed.length > 0 ||
    transformationChanged ||
    maskChanged;
  const base = {
    cls: drifted ? 'drifted' : 'in sync',
    ours: ours.gcps.length,
    theirs: theirs.gcps.length,
    transformation: theirs.transformation,
  };
  if (!drifted) return base;
  return {
    ...base,
    oursModified: ours.modified,
    theirsModified: theirs.modified,
    transformationChange: transformationChanged
      ? { ours: ours.transformation, theirs: theirs.transformation }
      : null,
    maskChanged,
    added: added.length,
    removed: removed.length,
    moved: moved.length,
    maxMovePx: moved[0]?.px ?? 0,
    worst: moved.slice(0, 3),
    sizeMismatch,
  };
}

// ---------- fetching ----------

/** fetch with one retry on a network error or a 5xx/429. A 4xx is an answer. */
async function fetchRetry(url, init) {
  let last;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(url, init);
      if (res.status < 500 && res.status !== 429) return res;
      last = new Error(`HTTP ${res.status}`);
    } catch (e) {
      last = e;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw last;
}

async function fetchUpstream(allmapsId) {
  const res = await fetchRetry(`${ALLMAPS}/${allmapsId}`, {
    headers: { Accept: 'application/json', 'Cache-Control': 'no-cache' },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Allmaps HTTP ${res.status}`);
  return res.json();
}

async function fetchOurs(mapId) {
  const key = process.env.SUPABASE_SERVICE_KEY;
  const res = await fetchRetry(
    `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/${BUCKET}/${mapId}.json`,
    { headers: { apikey: key, Authorization: `Bearer ${key}`, 'Cache-Control': 'no-cache' } }
  );
  if (res.ok) return res.json();
  // Supabase answers a missing object with 400 or 404 depending on version.
  const body = await res.text().catch(() => '');
  if (res.status === 404 || (res.status === 400 && /not.?found/i.test(body))) return null;
  throw new Error(`storage HTTP ${res.status} ${body.slice(0, 120)}`);
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        out[i] = await fn(items[i]);
      }
    })
  );
  return out;
}

async function inspect(map) {
  let theirsRaw;
  try {
    theirsRaw = await fetchUpstream(map.allmaps_id);
  } catch (e) {
    return { ...map, cls: 'error', error: `upstream: ${e.message}` };
  }
  let oursRaw;
  try {
    oursRaw = await fetchOurs(map.id);
  } catch (e) {
    return { ...map, cls: 'error', error: `ours: ${e.message}` };
  }
  const result = classify(
    oursRaw ? summarise(oursRaw) : null,
    theirsRaw ? summarise(theirsRaw) : null
  );
  return { ...map, ...result };
}

// ---------- output ----------

const ORDER = [
  'new contribution',
  'drifted',
  'error',
  'in sync',
  'upstream missing',
  'nothing yet',
];
const day = (s) => (s ? String(s).slice(0, 10) : '?');

function describe(r) {
  if (r.cls === 'new contribution') {
    return `${r.theirs} GCPs, ${r.transformation ?? 'no transformation'}, modified ${day(r.modified)}${r.theirs === 0 ? '  (no GCPs: mask only?)' : ''}`;
  }
  if (r.cls === 'drifted') {
    const parts = [
      `GCPs ${r.ours} -> ${r.theirs}`,
      `modified ${day(r.oursModified)} -> ${day(r.theirsModified)}`,
    ];
    if (r.transformationChange) {
      parts.push(
        `transformation ${r.transformationChange.ours} -> ${r.transformationChange.theirs}`
      );
    }
    parts.push(`+${r.added} added, -${r.removed} removed, ${r.moved} moved`);
    if (r.moved) parts.push(`max shift ${r.maxMovePx.toFixed(1)} px`);
    if (r.maskChanged) parts.push('mask changed');
    return parts.join('; ');
  }
  if (r.cls === 'error') return r.error;
  return `${r.ours ?? '?'} GCPs, ${r.transformation ?? 'no transformation'}`;
}

function printReport(rows, showAll) {
  const by = Object.fromEntries(ORDER.map((c) => [c, rows.filter((r) => r.cls === c)]));
  console.log(`Georef contributions: ${rows.length} maps with an allmaps_id\n`);
  for (const c of ORDER) {
    console.log(`  ${c.padEnd(18)} ${by[c].length}`);
  }
  for (const c of ['new contribution', 'drifted', 'error']) {
    if (!by[c].length) continue;
    console.log(`\n== ${c} (${by[c].length}) ==`);
    for (const r of by[c]) {
      console.log(`\n${r.name ?? '(unnamed)'}  [${r.status ?? '?'}]  ${r.id}`);
      console.log(`  allmaps: ${r.allmaps_id}   ${describe(r)}`);
      if (r.sizeMismatch) {
        const { ours: o, theirs: t } = r.sizeMismatch;
        console.log(
          `  !! DIFFERENT SCAN: ours ${o.width}x${o.height}, Allmaps ${t.width}x${t.height}. Syncing would move every point.`
        );
      }
      for (const w of r.worst ?? []) {
        console.log(
          `  moved ${w.px.toFixed(1)} px  (${w.lon.toFixed(6)}, ${w.lat.toFixed(6)})  [${w.from.map((v) => v.toFixed(0))}] -> [${w.to.map((v) => v.toFixed(0))}]`
        );
      }
      if (c !== 'error') {
        console.log(`  dry run: ${SYNC} --map ${r.id}`);
        console.log(`  apply:   ${SYNC} --apply --map ${r.id}`);
      }
    }
  }
  if (showAll && by['in sync'].length) {
    console.log(`\n== in sync (${by['in sync'].length}) ==`);
    for (const r of by['in sync'])
      console.log(`  ${r.name ?? '(unnamed)'}  ${r.id}  ${describe(r)}`);
  }
  console.log('\nReview before syncing: anyone can edit an Allmaps annotation.');
}

// ---------- selftest ----------

function selftest() {
  const feature = (x, y, lon, lat) => ({
    type: 'Feature',
    properties: { resourceCoords: [x, y] },
    geometry: { type: 'Point', coordinates: [lon, lat] },
  });
  const page = (
    features,
    { size = [4000, 3000], t = 'polynomial', modified = '2026-09-01T00:00:00Z', order } = {}
  ) => ({
    type: 'AnnotationPage',
    items: [
      {
        type: 'Annotation',
        modified,
        target: {
          source: { id: 'x', width: size[0], height: size[1] },
          selector: { value: '<svg><polygon points="0,0 1,1"/></svg>' },
        },
        body: { transformation: { type: t, ...(order ? { options: { order } } : {}) }, features },
      },
    ],
  });
  const base = () => [
    feature(10, 10, 106.7, 10.77),
    feature(200, 10, 106.71, 10.77),
    feature(200, 300, 106.71, 10.76),
  ];
  const run = (o, t) => classify(o ? summarise(o) : null, t ? summarise(t) : null);

  // in sync, including a different point order
  const same = run(page(base()), page([...base()].reverse()));
  assert.equal(same.cls, 'in sync');
  assert.equal(same.ours, 3);

  // drifted: one point moved 5 px, and the date differs
  const movedF = base();
  movedF[1] = feature(203, 14, 106.71, 10.77);
  const d = run(page(base()), page(movedF, { modified: '2026-09-30T00:00:00Z' }));
  assert.equal(d.cls, 'drifted');
  assert.equal(d.moved, 1);
  assert.equal(d.added, 0);
  assert.equal(d.removed, 0);
  assert.equal(d.maxMovePx, 5);
  assert.equal(d.theirsModified, '2026-09-30T00:00:00Z');
  assert.equal(d.sizeMismatch, null);

  // a sub-1e-6 ground wobble still matches (and is not a move of 0 px reported as added+removed)
  const wob = base();
  wob[0] = feature(10, 10, 106.7 + 1e-8, 10.77);
  assert.equal(run(page(base()), page(wob)).cls, 'in sync');

  // added point
  const add = run(page(base()), page([...base(), feature(50, 50, 106.72, 10.78)]));
  assert.equal(add.cls, 'drifted');
  assert.equal(add.added, 1);
  assert.equal(add.removed, 0);
  assert.equal(add.theirs, 4);

  // removed point + transformation change
  const rem = run(page(base()), page(base().slice(1), { t: 'thinPlateSpline' }));
  assert.equal(rem.cls, 'drifted');
  assert.equal(rem.removed, 1);
  assert.deepEqual(rem.transformationChange, { ours: 'polynomial', theirs: 'thinPlateSpline' });

  // polynomial order is part of the transformation
  const ord = run(page(base(), { order: 1 }), page(base(), { order: 2 }));
  assert.equal(ord.cls, 'drifted');
  assert.equal(ord.moved, 0);

  // new contribution
  const nc = run(null, page(base()));
  assert.equal(nc.cls, 'new contribution');
  assert.equal(nc.theirs, 3);

  // upstream missing, and neither
  assert.equal(run(page(base()), null).cls, 'upstream missing');
  assert.equal(run(null, null).cls, 'nothing yet');

  // size mismatch is flagged on a drifted row
  const sz = run(page(base()), page(movedF, { size: [8000, 6000] }));
  assert.equal(sz.cls, 'drifted');
  assert.deepEqual(sz.sizeMismatch, {
    ours: { width: 4000, height: 3000 },
    theirs: { width: 8000, height: 6000 },
  });

  // a bare Annotation (not a page) reads the same
  assert.equal(summarise(page(base()).items[0]).gcps.length, 3);

  console.log('selftest ok');
}

// ---------- main ----------

async function main() {
  const db = serviceClient();
  const maps = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await db
      .from('maps')
      .select('id, name, allmaps_id, status')
      .not('allmaps_id', 'is', null)
      .order('id')
      .range(from, from + 999);
    if (error) throw error;
    maps.push(...data);
    if (data.length < 1000) break;
  }
  const todo = maps.filter((m) => m.allmaps_id && m.allmaps_id.trim());
  if (!flag('--json')) console.error(`Checking ${todo.length} maps...`);
  const rows = await pool(todo, CONCURRENCY, inspect);
  if (flag('--json')) {
    const counts = {};
    for (const r of rows) counts[r.cls] = (counts[r.cls] ?? 0) + 1;
    console.log(JSON.stringify({ total: rows.length, counts, maps: rows }, null, 2));
  } else {
    printReport(rows, flag('--all'));
  }
}

if (flag('--selftest')) selftest();
else await main();
