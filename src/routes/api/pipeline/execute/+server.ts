/**
 * POST /api/pipeline/execute — run a job whose work belongs on the server.
 *
 * Body: { job_id }
 *
 * `mirror_annotation`, `sync_allmaps` and `warp` are fetch-rewrite-store: no
 * GPU, no venv, and they need the service key, which a worker deliberately does
 * not have. So the worker claims them like any other job and then asks us to do the
 * work. Kinds with real compute behind them (ocr, seg, tile_to_r2) run on the
 * worker itself and report through /api/pipeline/results instead.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireClaimedJob } from '$lib/server/workerJob';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { mirrorAnnotation } from '$lib/server/annotationMirror';
import { rewarpMap } from '$lib/server/rewarp';

const SERVER_KINDS = ['mirror_annotation', 'sync_allmaps', 'warp'] as const;

export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json().catch(() => ({}));
  const jobId = assertUuid(body.job_id, 'job_id');

  const { worker, job } = await requireClaimedJob(request, jobId);
  if (job.status !== 'claimed') throw error(409, 'Job has already started');
  const supabase = adminClient();

  if (!SERVER_KINDS.includes(job.kind as (typeof SERVER_KINDS)[number])) {
    throw error(
      400,
      `${job.kind} runs on the worker, not here — report it to /api/pipeline/results`
    );
  }
  if (!job.map_id) throw error(400, `${job.kind} job has no map_id`);

  const { data: started, error: startError } = await supabase.rpc('finish_job', {
    p_id: job.id,
    p_status: 'running',
    p_worker_key_id: worker.id,
    p_result: {},
  });
  if (startError) dbError(startError, 'Could not start job');
  if (!started) throw error(409, 'Job claim expired');

  try {
    if (job.kind === 'warp') {
      const result = await rewarpMap(job.map_id);
      await supabase.rpc('finish_job', {
        p_id: job.id,
        p_status: 'done',
        p_worker_key_id: worker.id,
        p_result: { ...result },
      });
      return json({ ok: true, job_id: job.id, result });
    }

    const result = await mirrorAnnotation(job.map_id, {
      fromAllmaps: job.kind === 'sync_allmaps',
    });
    // The georeference just moved (or arrived), so every warped row on this map
    // is stale. One job; 23505 is the one-live-job index saying there is
    // already one queued, which is the intended outcome. Anything else is a
    // real failure and must not vanish behind a job that reports done.
    const { error: qErr } = await supabase
      .from('pipeline_jobs')
      .insert({ kind: 'warp', map_id: job.map_id, payload: { after: job.kind } });
    if (qErr && qErr.code !== '23505') {
      console.error('could not enqueue the warp job:', qErr.message);
    }
    await supabase.rpc('finish_job', {
      p_id: job.id,
      p_status: 'done',
      p_worker_key_id: worker.id,
      p_result: { annotation_url: result.annotation_url, history_url: result.history_url },
    });
    return json({ ok: true, job_id: job.id, result });
  } catch (e) {
    // A failed mirror is usually a 502 from upstream; let finish_job decide
    // whether that is a retry or the end of the road.
    const message = e instanceof Error ? e.message : String(e);
    await supabase.rpc('finish_job', {
      p_id: job.id,
      p_status: 'failed',
      p_worker_key_id: worker.id,
      p_result: {},
      p_error: message.slice(0, 2000),
    });
    throw error(502, `Job failed: ${message}`);
  }
};
