#!/usr/bin/env node
/**
 * allmaps_drift.mjs — has anyone edited a map we pushed to Allmaps?
 *
 *   node --env-file=.env scripts/allmaps_drift.mjs [<map-uuid> ...]
 *
 * For each map whose newest pushed version carries an `allmaps_map_id`
 * (`georef_versions`, mig 118), compare the GCPs, transformation and mask Allmaps serves
 * now with the live annotation we hold. Read-only, and it never adopts what it finds:
 * Allmaps is a push-only mirror, so a difference is for a person to judge, then the next
 * `georef_write.mjs --allmaps` PATCH puts our version back. Exit 3 when anything differs.
 */
import { serviceClient } from './lib/db.mjs';
import { parseAnnotation } from '@allmaps/annotation';
import { fetchMap, differences } from './lib/allmaps.mjs';

const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const db = serviceClient();

let q = db
  .from('georef_versions')
  .select('map_id, stamp, allmaps_map_id')
  .not('allmaps_map_id', 'is', null)
  .order('stamp', { ascending: false });
if (only.length) q = q.in('map_id', only);
const { data, error } = await q;
if (error) throw error;
// Newest pushed version per map.
const latest = [...new Map(data.map((r) => [r.map_id, r])).values()];

let drifted = 0;
for (const { map_id, allmaps_map_id } of latest) {
  const { data: file, error: dl } = await db.storage.from('annotations').download(`${map_id}.json`);
  if (dl) {
    console.log(`  ${map_id}  no live file here: ${dl.message}`);
    drifted++;
    continue;
  }
  const ours = parseAnnotation(JSON.parse(await file.text()))[0];
  const theirs = await fetchMap(allmaps_map_id);
  const diff = !theirs ? ['404 at Allmaps'] : differences(ours, theirs);
  console.log(
    `  ${map_id}  ${allmaps_map_id}  ${diff.length ? `DRIFT — ${diff.join('; ')}` : 'same'}`
  );
  if (diff.length) drifted++;
}
console.log(`\n${latest.length} pushed maps checked, ${drifted} differ`);
if (drifted) process.exitCode = 3;
