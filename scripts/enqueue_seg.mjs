#!/usr/bin/env node
// Queue one `seg` job — MapSAM2 inference over a sheet's tiles.
//
//   node --env-file=.env scripts/enqueue_seg.mjs --map-id <uuid> [--dry]
//                                               [--ocr-run-id <id>] [--automatic]
//                                               [--device cuda|mps|cpu] [--encoder vit_s]
//
// This is the piece that was missing: the Segmentation panel only ever *printed*
// a command for a human to paste into Colab, so nothing in the tree could
// actually enqueue this kind. Now a GPU machine running
//
//   python work/worker/vma_worker.py --kinds seg --worker colab
//
// has something to claim. `seg` is opt-in in the worker's default kinds, so a
// laptop worker will not pick this up by accident.
//
// Prompted by default. With a validated OCR run the model is seeded from those
// label boxes and writes polygons with the toponym already attached, which is
// the whole point of running the two passes in this order; without one it falls
// back to automatic mode and returns unnamed blobs. So the newest run holding
// validated labels for the map is looked up and used unless --automatic says
// otherwise.
//
// `checkpoint` and `mapsam2_dir` are deliberately NOT in the payload: they
// describe the machine, and the worker reads MAPSAM2_CHECKPOINT / MAPSAM2_DIR
// from its own environment. Pass them per-job only to override one machine.

import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const flag = (name) => {
  const i = args.indexOf(name);
  return i > -1 ? args[i + 1] : undefined;
};

const mapId = flag('--map-id');
const dry = args.includes('--dry');
const automatic = args.includes('--automatic');
const device = flag('--device') ?? 'cuda';
const encoder = flag('--encoder') ?? 'vit_s';
let ocrRunId = flag('--ocr-run-id');

if (!mapId) {
  console.error('usage: node --env-file=.env scripts/enqueue_seg.mjs --map-id <uuid> [--dry]');
  process.exit(1);
}

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: map, error: mapErr } = await db
  .from('maps')
  .select('id, name, year')
  .eq('id', mapId)
  .single();
if (mapErr) throw mapErr;

// The one-live-job index would refuse a duplicate, but a clear message beats a
// unique-violation stack trace.
const { data: live } = await db
  .from('pipeline_jobs')
  .select('id, status')
  .eq('kind', 'seg')
  .eq('map_id', mapId)
  .in('status', ['queued', 'claimed', 'running']);
if (live?.length) {
  console.error(`a seg job is already ${live[0].status} for this map (${live[0].id})`);
  process.exit(1);
}

// The validated OCR run with the MOST labels — not the newest. These boxes are
// seed prompts, so more of them is strictly better, and the newest run on this
// corpus is often a two-label spot check. Tallied client-side because PostgREST
// has no group-by; the validated set is small by construction.
let runTally = {};
if (!ocrRunId && !automatic) {
  const { data: rows } = await db
    .from('ocr_labels')
    .select('run_id')
    .eq('map_id', mapId)
    .eq('review_status', 'validated');
  for (const r of rows ?? []) runTally[r.run_id] = (runTally[r.run_id] ?? 0) + 1;
  const best = Object.entries(runTally).sort((a, b) => b[1] - a[1])[0];
  ocrRunId = best?.[0];
}

const runId = `seg-${new Date().toISOString().slice(0, 16).replace(/[-:]/g, '').replace('T', 'T')}-${mapId.slice(0, 8)}`;
const payload = {
  run_id: runId,
  encoder,
  device,
  tile_size: 1024,
  overlap: 128,
  text_mask: true,
  watershed: true,
  ...(ocrRunId ? { ocr_run_id: ocrRunId } : {}),
};

console.log(`${map.year ?? '????'} ${map.name}`);
const seeds = runTally[ocrRunId];
console.log(
  `  mode      ${
    ocrRunId
      ? `prompted off OCR run "${ocrRunId}"${seeds ? ` (${seeds} validated labels)` : ''}`
      : 'automatic (no validated OCR run)'
  }`
);
if (Object.keys(runTally).length > 1)
  console.log(
    `  other runs ${Object.entries(runTally)
      .filter(([r]) => r !== ocrRunId)
      .map(([r, n]) => `${r}:${n}`)
      .join(', ')}`
  );
console.log(`  run_id    ${runId}`);
console.log(`  device    ${device}   encoder ${encoder}`);

if (dry) {
  console.log('\n--dry: nothing enqueued. Payload would be:');
  console.log(JSON.stringify(payload, null, 2));
  process.exit(0);
}

const { data: job, error } = await db
  .from('pipeline_jobs')
  .insert({ kind: 'seg', map_id: mapId, payload })
  .select('id')
  .single();
if (error) throw error;

console.log(`\nqueued seg job ${job.id}`);
console.log('claim it with:  python work/worker/vma_worker.py --kinds seg --worker <name>');
