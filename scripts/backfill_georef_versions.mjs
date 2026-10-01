#!/usr/bin/env node
// Reconcile `georef_versions` (migration 103) with what is in Storage.
//
//   node --env-file=.env scripts/backfill_georef_versions.mjs [--map <id>] [--apply]
//
// Two jobs, both idempotent, so this is also the catch-up for writers that do
// not record their own rows yet (the Python georef scripts):
//
// 1. Every history file `annotations/<map>/<stamp>.json` without a row gets one,
//    origin `unrecorded` — nobody wrote down who placed those points.
// 2. A live `annotations/<map>.json` that matches no history file was written by
//    a path that keeps no history. It is copied to a history file first (stamped
//    from its own updated_at, and never earlier than the newest history file, so
//    it sorts as current) and then recorded. Without the copy its row would have
//    no file behind it and `?version=` could not serve it.
//
// Default is a dry run; --apply writes. Ends with the plan's exit query for 1882.

import { serviceClient } from './lib/db.mjs';
import { willApply, opt, dryNotice } from './lib/cli.mjs';
import { recordGeorefVersion } from './lib/georef_versions.mjs';
import { describeAnnotation, isoToStamp, stampToIso } from '../src/lib/core/georef/version.ts';

const apply = willApply();
const onlyMap = opt('--map');
const db = serviceClient();
const bucket = db.storage.from('annotations');
const MAP_1882 = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const STAMP = /^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z)\.json$/;

/** Every entry under a prefix; Storage pages at 100 by default. */
async function listAll(prefix) {
  const out = [];
  for (let offset = 0; ; offset += 1000) {
    const { data, error } = await bucket.list(prefix, { limit: 1000, offset });
    if (error) throw error;
    out.push(...data);
    if (data.length < 1000) return out;
  }
}

async function readJson(path) {
  const { data, error } = await bucket.download(path);
  if (error) throw new Error(`${path}: ${error.message}`);
  return JSON.parse(await data.text());
}

/** Content identity, independent of whitespace. */
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const root = await listAll('');
const liveFiles = new Map(
  root
    .filter((e) => e.id && e.name.endsWith('.json') && UUID.test(e.name.slice(0, -5)))
    .map((e) => [e.name.slice(0, -5), e])
);
const mapIds = onlyMap
  ? [onlyMap]
  : [
      ...new Set([
        ...liveFiles.keys(),
        ...root.filter((e) => !e.id && UUID.test(e.name)).map((e) => e.name),
      ]),
    ];

const exists = new Set();
for (let i = 0; i < mapIds.length; i += 200) {
  const { data, error } = await db
    .from('maps')
    .select('id')
    .in('id', mapIds.slice(i, i + 200));
  if (error) throw error;
  data.forEach((m) => exists.add(m.id));
}

const totals = { maps: 0, history: 0, recorded: 0, liveCopied: 0, unparseable: 0, orphan: 0 };

for (const mapId of mapIds) {
  if (!exists.has(mapId)) {
    totals.orphan++;
    continue;
  }
  totals.maps++;
  const { data: rows, error } = await db
    .from('georef_versions')
    .select('stamp')
    .eq('map_id', mapId);
  // A dry run may precede `db push`: no table yet means nothing recorded yet.
  if (error && (apply || error.code !== 'PGRST205')) throw error;
  const recorded = new Set((rows ?? []).map((r) => r.stamp));

  const stamps = (await listAll(mapId))
    .map((e) => e.name.match(STAMP)?.[1])
    .filter(Boolean)
    .sort();
  totals.history += stamps.length;

  for (const stamp of stamps) {
    if (recorded.has(stamp)) continue;
    const annotation = await readJson(`${mapId}/${stamp}.json`);
    try {
      if (apply) await recordGeorefVersion(db, mapId, stamp, annotation, 'unrecorded');
      else await describeAnnotation(annotation);
      totals.recorded++;
    } catch (e) {
      totals.unparseable++;
      console.log(`  ${mapId}/${stamp}: ${e.message}`);
    }
  }

  const live = liveFiles.get(mapId);
  if (!live) continue;
  const liveJson = await readJson(`${mapId}.json`);
  const newest = stamps.at(-1);
  if (newest && same(liveJson, await readJson(`${mapId}/${newest}.json`))) continue;

  // Live matches no newest history file: give it one, after everything already there.
  let stamp = isoToStamp(live.updated_at ?? live.created_at);
  if (newest && stamp <= newest) stamp = isoToStamp(new Date(Date.parse(stampToIso(newest)) + 1));
  try {
    await describeAnnotation(liveJson);
  } catch (e) {
    totals.unparseable++;
    console.log(`  ${mapId}.json (live): ${e.message}`);
    continue;
  }
  console.log(`  ${mapId}: live file has no history copy → ${stamp}`);
  totals.liveCopied++;
  if (!apply) continue;
  const { error: upErr } = await bucket.upload(
    `${mapId}/${stamp}.json`,
    JSON.stringify(liveJson, null, 2),
    {
      contentType: 'application/json',
      upsert: false,
    }
  );
  if (upErr) throw new Error(`${mapId}/${stamp}: ${upErr.message}`);
  await recordGeorefVersion(db, mapId, stamp, liveJson, 'unrecorded');
}

console.log(
  `\n${totals.maps} maps · ${totals.history} history files · ${totals.recorded} rows ${apply ? 'written' : 'to write'} · ` +
    `${totals.liveCopied} live files without history · ${totals.unparseable} unparseable · ${totals.orphan} storage folders with no map row`
);

if (!apply) {
  dryNotice('Rows and history copies were only counted.');
  process.exit(0);
}

// The plan's exit test: every 1882 version, and the labels/polygons warped against an older one.
const { data: v1882 } = await db
  .from('georef_versions')
  .select('stamp, origin, gcp_count, rmse_m, rmse_method, geom_src')
  .eq('map_id', MAP_1882)
  .order('stamp');
console.log('\n1882 versions:');
for (const v of v1882 ?? [])
  console.log(
    `  ${v.stamp}  ${v.origin.padEnd(10)} ${v.gcp_count} GCPs  ${v.rmse_m?.toFixed(1) ?? '—'} m (${v.rmse_method})  ${v.geom_src}`
  );

const { data: cur } = await db.from('map_georef_current').select('map_id, geom_src');
let stale = 0;
for (const { map_id, geom_src } of cur ?? []) {
  for (const table of ['ocr_labels', 'footprints']) {
    const { count } = await db
      .from(table)
      .select('id', { count: 'exact', head: true })
      .eq('map_id', map_id)
      .not('geom_src', 'is', null)
      .neq('geom_src', geom_src);
    if (count) console.log(`  stale: ${map_id} ${table} ${count}`);
    stale += count ?? 0;
  }
}
console.log(`\n${stale} label/polygon rows warped against a version that is not current.`);
