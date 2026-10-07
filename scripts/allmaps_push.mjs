#!/usr/bin/env node
/**
 * allmaps_push.mjs — push what is already stored to Allmaps, writing no new version.
 *
 *   node --env-file=.env scripts/allmaps_push.mjs [--apply] <map-uuid> ...
 *
 * `georef_write.mjs --allmaps` records a new version with a method; this is for sheets
 * whose stored georef has no method to claim (L909). Reads the live annotation, POSTs
 * (PATCHes when the newest version row already carries an id), stores the id on that
 * row, reads back. Needs a `georef_versions` row: run backfill_georef_versions.mjs first.
 */
import { serviceClient } from './lib/db.mjs';
import { willApply } from './lib/cli.mjs';
import { toAllmapsMap, push, fetchMap, differences } from './lib/allmaps.mjs';

const apply = willApply();
const ids = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const db = serviceClient();
let failed = 0;
for (const id of ids) {
  const { data: v, error } = await db
    .from('georef_versions')
    .select('stamp, allmaps_map_id')
    .eq('map_id', id)
    .order('stamp', { ascending: false })
    .limit(1);
  if (error) throw error;
  if (!v?.length) {
    console.log(`  ${id} no georef_versions row — SKIP`);
    failed++;
    continue;
  }
  const { data: blob, error: dl } = await db.storage.from('annotations').download(`${id}.json`);
  if (dl) throw new Error(`${id}: ${dl.message}`);
  const ours = toAllmapsMap(JSON.parse(await blob.text()));
  const known = v[0].allmaps_map_id;
  if (!apply) {
    console.log(`  ${id} would ${known ? 'PATCH ' + known : 'POST'} (${ours.gcps.length} gcp)`);
    continue;
  }
  const am = await push(ours, known);
  const { error: e } = await db
    .from('georef_versions')
    .update({ allmaps_map_id: am })
    .eq('map_id', id)
    .eq('stamp', v[0].stamp);
  if (e) throw new Error(`pushed ${id} as ${am} but could not record it: ${e.message}`);
  console.log(`  ${id} ${known ? 'PATCH' : 'POST'} ${am}`);
}
if (failed) process.exitCode = 3;
