#!/usr/bin/env node
// Given a point, ask context_at (mig 066/068) for everything within radius
// across every covering year, then dedupe: the RPC returns one row per
// (label|footprint) observation, so the same real-world thing on N sheets is
// N rows. This collapses those into one thread per thing.
//
// Labels dedupe by placeKey (same folding as place_key(), mig 067, and
// scripts/dedupe_ocr.mjs) — "Rue de Khánh-Hội" 1923 and "Khanh Hoi" 1959 fold
// to the same key. Footprints have no name to key on, so they dedupe by
// spatial proximity: greedy-cluster centroids within --thresh metres of each
// other (haversine, same fn as scripts/sheet_align.mjs). ponytail: greedy
// single-link, not real clustering — fine at D4 sheet density, revisit if a
// cluster ever needs splitting by feature_type as well as distance.
//
// Usage:
//   node --env-file=.env scripts/spot_history.mjs --lng 106.7064 --lat 10.7753
//   node --env-file=.env scripts/spot_history.mjs --candidate cand-1
//   node --env-file=.env scripts/spot_history.mjs --candidate cand-1 --radius 300 --thresh 25 --all
//   node scripts/spot_history.mjs --selftest
//
// Needs PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_KEY (context_at is
// service_role-only — mig 066 revokes public/anon/authenticated).

import { readFileSync } from 'node:fs';

const argv = process.argv.slice(2);
const opt = (n, d) => (argv.indexOf(n) > -1 ? argv[argv.indexOf(n) + 1] : d);
const flag = (n) => argv.includes(n);

const placeKey = (s) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

function haversineM([lon1, lat1], [lon2, lat2]) {
  const R = 6371008.8;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// GeoJSON Polygon (or MultiPolygon) → centroid of its outer ring's vertices.
// Not area-weighted — fine for clustering, this is not the export path.
function centroid(geometry) {
  const ring =
    geometry.type === 'Polygon' ? geometry.coordinates[0] : geometry.coordinates[0][0];
  let x = 0,
    y = 0,
    n = 0;
  for (const [lon, lat] of ring.slice(0, -1)) {
    x += lon;
    y += lat;
    n += 1;
  }
  return [x / n, y / n];
}

function clusterFootprints(footprints, threshM) {
  const clusters = []; // [{ centroid, items: [] }]
  for (const f of footprints) {
    const c = centroid(f.geometry);
    let target = clusters.find((cl) => haversineM(cl.centroid, c) <= threshM);
    if (!target) {
      target = { centroid: c, items: [] };
      clusters.push(target);
    }
    target.items.push({ ...f, centroid: c });
  }
  return clusters;
}

function groupLabels(labels) {
  const byKey = new Map();
  for (const l of labels) {
    const key = placeKey(l.text) || '(blank)';
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(l);
  }
  return byKey;
}

function report({ at, radius_m, labels, footprints, maps }) {
  console.log(`\nspot ${at[0]}, ${at[1]} — radius ${radius_m} m — ${maps.length} covering sheet(s)`);
  console.log(maps.map((m) => `  ${m.year ?? '?'} · ${m.name}`).join('\n'));

  const byKey = groupLabels(labels);
  console.log(`\n${byKey.size} label thread(s) from ${labels.length} observation(s):`);
  for (const [key, obs] of [...byKey.entries()].sort((a, b) => b[1].length - a[1].length)) {
    obs.sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
    const years = obs.map((o) => `${o.year ?? '?'}:"${o.text}"@${o.distance_m}m`).join('  ');
    console.log(`  [${key}] × ${obs.length} — ${years}`);
  }

  const clusters = clusterFootprints(footprints, Number(opt('--thresh', 25)));
  console.log(`\n${clusters.length} footprint thread(s) from ${footprints.length} observation(s):`);
  for (const cl of clusters.sort((a, b) => b.items.length - a.items.length)) {
    cl.items.sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
    const years = cl.items
      .map((it) => `${it.year ?? '?'}:${it.feature_type}${it.name ? ` "${it.name}"` : ''}`)
      .join('  ');
    console.log(`  cluster @${cl.centroid[0].toFixed(5)},${cl.centroid[1].toFixed(5)} × ${cl.items.length} — ${years}`);
  }
}

async function main() {
  for (const line of readFileSync('.env', 'utf8').split('\n')) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
  }
  const URL_ = process.env.PUBLIC_SUPABASE_URL;
  const KEY = process.env.SUPABASE_SERVICE_KEY;
  if (!URL_ || !KEY) throw new Error('PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY missing');

  let lng = opt('--lng', null);
  let lat = opt('--lat', null);
  const candidate = opt('--candidate', null);
  if (candidate) {
    const rows = JSON.parse(readFileSync('work/analysis/district4/landmarks.json', 'utf8'));
    const row = rows.find((r) => r.id === candidate);
    if (!row) throw new Error(`no candidate "${candidate}" in landmarks.json`);
    lng = row.lon;
    lat = row.lat;
    console.log(`candidate ${candidate}: ${row.note}`);
  }
  if (lng == null || lat == null) throw new Error('need --lng/--lat or --candidate <id>');

  const body = {
    p_lng: Number(lng),
    p_lat: Number(lat),
    p_radius_m: Number(opt('--radius', 150)),
    p_year_from: opt('--from', null) ? Number(opt('--from')) : null,
    p_year_to: opt('--to', null) ? Number(opt('--to')) : null,
    p_public_only: !flag('--all'),
    p_limit: Number(opt('--limit', 200)),
  };
  const res = await fetch(`${URL_}/rest/v1/rpc/context_at`, {
    method: 'POST',
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`context_at ${res.status}: ${await res.text()}`);
  report(await res.json());
}

function selftest() {
  console.assert(placeKey('Rue de Khánh-Hội') === placeKey('Rue de Khanh Hoi'), 'placeKey folds accents+case+punct');
  console.assert(placeKey('Đường') === 'duong', `placeKey đ: ${placeKey('Đường')}`);
  const d = haversineM([106.7, 10.77], [106.7, 10.77 + 1 / 111]);
  console.assert(Math.abs(d - 1000) < 20, `haversine off: ${d}`);
  const clusters = clusterFootprints(
    [
      { year: 1923, feature_type: 'building', geometry: { type: 'Polygon', coordinates: [[[0, 0], [0, 0.0001], [0.0001, 0.0001], [0.0001, 0], [0, 0]]] } },
      { year: 1942, feature_type: 'building', geometry: { type: 'Polygon', coordinates: [[[0.00002, 0], [0.00002, 0.0001], [0.00012, 0.0001], [0.00012, 0], [0.00002, 0]]] } },
      { year: 1959, feature_type: 'building', geometry: { type: 'Polygon', coordinates: [[[1, 1], [1, 1.0001], [1.0001, 1.0001], [1.0001, 1], [1, 1]]] } },
    ],
    25
  );
  console.assert(clusters.length === 2, `expected 2 clusters, got ${clusters.length}`);
  console.log('self-check ok — placeKey, haversine, clusterFootprints');
}

if (flag('--selftest')) selftest();
else main().catch((e) => (console.error(e), process.exit(1)));
