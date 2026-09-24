#!/usr/bin/env node
// Queue a `layout` job for every georeferenced map, so we learn what each sheet
// is made of before deciding what to read.
//
//   node --env-file=.env scripts/enqueue_layout_all.mjs [--dry] [--force]
//                                                       [--limit N] [--model NAME]
//
// The layout pass (migration 070) asks the model, once per sheet at low
// resolution, where the main map, title block, legend, name list, inset and
// furniture are, and writes the answer to `maps.triage.regions`. It is the only
// way to answer questions of the form "which sheets have a printed index of
// street names?" — nothing else in the schema knows.
//
// Cheap: one call per sheet on the multi-scale path, cents for the whole
// corpus. Drain it the usual way, with `layout` in the worker's kinds (it is,
// by default):
//
//   source work/ocr/.venv/bin/activate
//   python work/worker/vma_worker.py --worker $(hostname)
//
// By default it skips sheets that already carry regions; `--force` re-runs
// them. Re-running is safe — `/api/pipeline/results` merges regions into the
// triage rather than replacing the object, so a hand-drawn neatline survives —
// but it does overwrite regions a person corrected, so it is not the default.

import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const force = args.includes('--force');
const limitIdx = args.indexOf('--limit');
const limit = limitIdx > -1 ? Number(args[limitIdx + 1]) : Infinity;
const modelIdx = args.indexOf('--model');
const model = modelIdx > -1 ? args[modelIdx + 1] : null;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: maps, error } = await db
  .from('maps')
  .select('id, name, year, iiif_image, triage')
  .eq('is_georeferenced', true)
  .not('iiif_image', 'is', null)
  .order('year');
if (error) throw error;

// One live job per (kind, map) is enforced by a partial unique index, but
// asking first turns a duplicate into a clear line rather than a caught error.
const { data: live } = await db
  .from('pipeline_jobs')
  .select('map_id')
  .eq('kind', 'layout')
  .in('status', ['queued', 'claimed', 'running']);
const inFlight = new Set((live ?? []).map((r) => r.map_id));

const hasRegions = (m) => Boolean(m.triage?.regions?.length);

const todo = maps.filter((m) => !inFlight.has(m.id) && (force || !hasRegions(m))).slice(0, limit);

console.log(
  `${maps.length} georeferenced · ${maps.filter(hasRegions).length} already mapped out · ` +
    `${inFlight.size} in flight → ${todo.length} to queue${dry ? ' (dry run)' : ''}`
);

let queued = 0;
for (const m of todo) {
  console.log(`  ${m.year ?? '????'}  ${m.name}`);
  if (dry) continue;
  const run_id = `layout-${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}-${m.id.slice(0, 8)}`;
  const { error: insErr } = await db.from('pipeline_jobs').insert({
    kind: 'layout',
    map_id: m.id,
    // 2048 for the same reason OVERVIEW_WIDTH is: below it the density read
    // inverts, and a model looking for a legend needs to see that it is ruled.
    payload: { run_id, render_size: 2048, ...(model ? { model } : {}) },
  });
  if (insErr && insErr.code !== '23505') throw insErr; // 23505 = one-live-job index
  if (!insErr) queued++;
}
if (!dry) console.log(`queued ${queued}`);
