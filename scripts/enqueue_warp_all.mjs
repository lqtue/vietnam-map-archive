#!/usr/bin/env node
// Queue a `warp` job for every georeferenced map whose derived geometry is
// missing or stale.
//
//   node --env-file=.env scripts/enqueue_warp_all.mjs [--dry] [--all] [--limit N]
//
// The writers warp on the way in, so this is for rows that predate the index
// (migration 066) — which is most of the corpus — and for maps whose
// georeference has moved since. A map is queued when it has rows with no
// geometry at all; --all queues every georeferenced map regardless, which is
// what you want after changing the warp itself.
//
// The job runs server-side (it needs the service key), so a worker claims it
// and hands it to /api/pipeline/execute:
//
//   python work/worker/vma_worker.py --kinds warp --worker $(hostname)
//
// The one-live-job index makes a duplicate a skipped row, never a second job.

import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const all = args.includes('--all');
const limitIdx = args.indexOf('--limit');
const limit = limitIdx > -1 ? Number(args[limitIdx + 1]) : Infinity;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: maps, error } = await db
  .from('maps')
  .select('id, name, year')
  .eq('is_georeferenced', true)
  .order('year');
if (error) throw error;

const { data: live } = await db
  .from('pipeline_jobs')
  .select('map_id')
  .eq('kind', 'warp')
  .in('status', ['queued', 'claimed', 'running']);
const inFlight = new Set((live ?? []).map((r) => r.map_id));

/** Maps holding at least one row with no geometry yet. */
async function needsWarp(mapId) {
  for (const table of ['ocr_labels', 'footprints']) {
    const { count } = await db
      .from(table)
      .select('id', { count: 'exact', head: true })
      .eq('map_id', mapId)
      .is('geom', null);
    if ((count ?? 0) > 0) return count;
  }
  return 0;
}

const todo = [];
for (const m of maps) {
  if (inFlight.has(m.id)) continue;
  const pending = all ? null : await needsWarp(m.id);
  if (all || pending > 0) todo.push({ ...m, pending });
  if (todo.length >= limit) break;
}

console.log(
  `${maps.length} georeferenced · ${inFlight.size} already in flight → ${todo.length} to queue${dry ? ' (dry run)' : ''}`
);

let queued = 0;
for (const m of todo) {
  const detail = m.pending == null ? '' : `  (${m.pending}+ rows unwarped)`;
  console.log(`  ${m.year ?? '????'}  ${m.name}${detail}`);
  if (dry) continue;
  const { error: insErr } = await db
    .from('pipeline_jobs')
    .insert({ kind: 'warp', map_id: m.id, payload: { reason: all ? 'rewarp-all' : 'backfill' } });
  // 23505 is the one-live-job index: already queued, which is fine.
  if (insErr && insErr.code !== '23505') throw insErr;
  if (!insErr) queued++;
}
if (!dry) console.log(`queued ${queued}`);
