#!/usr/bin/env node
/**
 * georef_write.mjs — the one way a script stores a georeference.
 *
 *   node --env-file=.env scripts/georef_write.mjs [--apply] [--replace-public]
 *        [--origin script|pipeline] <map-uuid>.json ...
 *
 * Every series pipeline (Tonkin, Indochine 100k, L7014, L909, the 1971 grid) ends
 * the same way: an annotation JSON per sheet, named for its map id, built by
 * `scripts/lib/georef_annotation.py`. This stores it. Until 2026-10-07 each
 * pipeline stored it itself, five copies that disagreed: two guarded against
 * overwriting a public sheet and three did not, two wrote `bbox` from the GCP
 * corners, one wrote none, and none kept a history file or a `georef_versions`
 * row — so a script's re-placement overwrote the only copy of what it replaced,
 * which is the gap migration 103's header names ("the Python pipeline until it
 * records its own").
 *
 * Per file, in order, the same sequence the admin PATCH route uses:
 *   1. refuse an annotation that will not parse, has fewer than 3 GCPs or no mask,
 *      points at a IIIF base other than the row's `iiif_image`, or declares a
 *      pixel size that base does not serve (the Allmaps id / rescan traps);
 *   2. `annotations/<map>/<stamp>.json` (history) + its `georef_versions` row;
 *   3. `annotations/<map>.json` (live), read back and compared;
 *   4. `maps`: `annotation_url` = the app route (the bucket is private, mig 097),
 *      `is_georeferenced` = true, `bbox` = the warped mask extent (sheet_extent.mjs).
 *
 * Never touches `status`: publishing is a person's call, after a look in /explore.
 * A non-draft row that already has a georeference (`annotation_url`) is refused
 * unless `--replace-public`; a public row with none has nothing to overwrite. The
 * history file keeps what a replacement overwrites either way.
 */
import { readFile } from 'node:fs/promises';
import { basename } from 'node:path';
import { serviceClient } from './lib/db.mjs';
import { willApply, flag, opt, dryNotice } from './lib/cli.mjs';
import { recordGeorefVersion } from './lib/georef_versions.mjs';
import { sheetExtent } from './lib/sheet_extent.mjs';
import { isoToStamp } from '../src/lib/core/georef/version.ts';
import { sourceSizeMismatch } from '../src/lib/core/iiif/sourceSize.ts';
import { parseAnnotation } from '@allmaps/annotation';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const apply = willApply();
const replacePublic = flag('--replace-public');
const origin = opt('--origin') ?? 'script';
if (!['script', 'pipeline'].includes(origin)) {
  console.error(`--origin is script or pipeline, not ${origin}`);
  process.exit(2);
}
const files = process.argv
  .slice(2)
  .filter((a, i, all) => a.endsWith('.json') && all[i - 1] !== '--origin');
if (!files.length) {
  console.error(
    'usage: georef_write.mjs [--apply] [--replace-public] [--origin script|pipeline] <map-uuid>.json ...'
  );
  process.exit(2);
}

const db = serviceClient();
const bucket = db.storage.from('annotations');
const stripSlash = (s) => String(s ?? '').replace(/\/+$/, '');

/** Why this annotation must not be stored, or null. */
async function refusal(mapId, ann, row) {
  if (!row) return 'no maps row with this id';
  if (row.status !== 'draft' && row.annotation_url && !replacePublic)
    return `row is ${row.status} and already georeferenced (pass --replace-public)`;
  let map;
  try {
    [map] = parseAnnotation(ann);
  } catch (e) {
    return `does not parse: ${e.message}`;
  }
  if (!map) return 'holds no georeferenced map';
  if ((map.gcps ?? []).length < 3) return `${map.gcps?.length ?? 0} GCPs, need at least 3`;
  if (!Array.isArray(map.resourceMask) || map.resourceMask.length < 3) return 'no resource mask';
  const source = stripSlash(map.resource.id);
  if (source !== stripSlash(row.iiif_image))
    return `source ${source} is not the row's iiif_image ${row.iiif_image}`;
  return sourceSizeMismatch(ann, source);
}

let stored = 0;
let refused = 0;
for (const file of files) {
  const mapId = basename(file, '.json');
  if (!UUID.test(mapId)) {
    console.log(`  ${file}: name is not a map uuid — SKIP`);
    refused++;
    continue;
  }
  const body = await readFile(file, 'utf8');
  const ann = JSON.parse(body);
  const { data: row, error } = await db
    .from('maps')
    .select('name, status, iiif_image, annotation_url')
    .eq('id', mapId)
    .maybeSingle();
  if (error) throw error;

  const why = await refusal(mapId, ann, row);
  const extent = why ? null : sheetExtent(ann);
  const bbox = extent?.bbox.map((n) => +n.toFixed(6));
  const label = `${(row?.name ?? mapId).slice(0, 36).padEnd(36)}`;
  if (why || !bbox || !(bbox[0] < bbox[2] && bbox[1] < bbox[3])) {
    console.log(`  ${label} REFUSED — ${why ?? 'degenerate extent'}`);
    refused++;
    continue;
  }
  console.log(`  ${label} ${row.status.padEnd(7)} ${extent.n} gcp  bbox [${bbox}]`);
  if (!apply) continue;

  const stamp = isoToStamp(new Date());
  const put = async (path) => {
    const { error: e } = await bucket.upload(path, body, {
      upsert: true,
      contentType: 'application/json',
    });
    if (e) throw new Error(`storage ${path}: ${e.message}`);
  };
  await put(`${mapId}/${stamp}.json`);
  await recordGeorefVersion(db, mapId, stamp, ann, origin);
  await put(`${mapId}.json`);
  const { data: back, error: readErr } = await bucket.download(`${mapId}.json`);
  if (readErr || (await back.text()) !== body)
    throw new Error(`${mapId}: live file read-back differs — the row was not updated`);

  let q = db
    .from('maps')
    .update({
      annotation_url: `https://maparchive.vn/api/maps/${mapId}/annotation`,
      is_georeferenced: true,
      bbox,
    })
    .eq('id', mapId);
  if (!replacePublic) q = q.or('status.eq.draft,annotation_url.is.null');
  const { error: upErr } = await q;
  if (upErr) throw upErr;
  stored++;
}

console.log(
  `\n${apply ? `${stored} stored` : `${files.length - refused} ready`}, ${refused} refused`
);
if (!apply)
  dryNotice(
    'Each ready file would get a history copy, a georef_versions row, the live file and its maps row.'
  );
// 3, not 1: a refusal is a verdict on a file, and 1 is what an exception exits with.
if (refused) process.exitCode = 3;
