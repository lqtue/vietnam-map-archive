/**
 * pipelineQueue.ts — jobs that start themselves.
 *
 * Ingest queues `layout` for a new draft sheet (`enqueueLayout`); when that job
 * finishes, `/api/pipeline/results` calls `queueOcrAfterLayout`, which queues `ocr`
 * with the crop and the printed blocks the layout pass just saved. Georeferencing
 * is not chained: it stays the one human gate.
 *
 * The chain is opt-in per job (`payload.then === 'ocr'`), the way `warp` carries
 * `payload.after`. A person pressing Detect in /scan?mode=prepare enqueues a plain
 * layout job and must still get to correct the regions before any tile is paid for.
 *
 * ponytail: `/api/admin/maps/[id]/layout` and `scripts/enqueue_layout_all.mjs` still
 * build their own layout payload; they enqueue for a person, not for a chain, and
 * folding them in would touch two working paths for no behaviour change.
 */

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { tilingCrop, type SavedTriage } from '$lib/data/maps/triageTypes';

type Db = SupabaseClient<Database>;

/** Printed text *about* the map, not the map: the tile pass must not read it as terrain.
 *  Same set as `PRINTED_BLOCKS` in scripts/enqueue_ocr_all.mjs (plain .mjs, cannot import this). */
const PRINTED_BLOCKS = new Set(['legend', 'name_list']);

const stamp = () => new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);

/** Queue a `layout` job whose completion queues `ocr`. A job already in flight is left alone. */
export async function enqueueLayout(supabase: Db, mapId: string): Promise<void> {
  const { error } = await supabase.from('pipeline_jobs').insert({
    kind: 'layout',
    map_id: mapId,
    // 2048 for the same reason OVERVIEW_WIDTH is: below it the density read inverts.
    payload: { run_id: `layout-${stamp()}-${mapId.slice(0, 8)}`, render_size: 2048, then: 'ocr' },
  });
  // 23505 = idx_pipeline_jobs_one_live: one is already queued, which is the outcome wanted.
  if (error && error.code !== '23505') throw new Error(error.message);
}

/**
 * Called when a layout job has finished. Queues `ocr` only if the job asked for it
 * and the layout pass found a crop; a sheet with no `main_map` is left for a person,
 * as `scripts/enqueue_ocr_all.mjs` does. Returns a short note for the results reply.
 */
export async function queueOcrAfterLayout(
  supabase: Db,
  job: { map_id: string; payload: unknown }
): Promise<string | null> {
  const p = job.payload as { then?: string } | null;
  if (p?.then !== 'ocr') return null;

  const { data: map } = await supabase.from('maps').select('triage').eq('id', job.map_id).single();
  const triage = (map?.triage ?? null) as SavedTriage | null;
  const crop = tilingCrop(triage);
  if (!crop) return 'ocr not queued: layout found no main_map';

  const exclude = (triage?.regions ?? [])
    .filter((r) => PRINTED_BLOCKS.has(r.category))
    .map((r) => r.bbox);
  const { error } = await supabase.from('pipeline_jobs').insert({
    kind: 'ocr',
    map_id: job.map_id,
    // The worker owns every other default (`_ocr_batch_argv`), as in the admin route.
    payload: {
      run_id: `${stamp()}-${job.map_id.slice(0, 8)}`,
      auto: true,
      auto_priority: true,
      neatline: crop,
      ...(exclude.length ? { exclude } : {}),
    },
  });
  if (error && error.code !== '23505') {
    console.error('could not enqueue the ocr job:', error.message);
    return 'ocr not queued: insert failed';
  }
  return 'ocr queued';
}
