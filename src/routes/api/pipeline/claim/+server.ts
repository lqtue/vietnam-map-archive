/**
 * POST /api/pipeline/claim — hand one queued job to a worker.
 *
 * Body: { kinds: string[], worker: string }
 * Returns the claimed job, or `{ job: null }` when the queue is empty.
 *
 * The FOR UPDATE SKIP LOCKED select lives in the `claim_job` RPC, so two
 * workers polling at the same instant get different jobs (or nothing).
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireWorker } from '$lib/server/workerAuth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';

export const POST: RequestHandler = async ({ request }) => {
  const worker = await requireWorker(request);
  const body = await request.json().catch(() => ({}));

  const kinds: string[] = Array.isArray(body.kinds) ? body.kinds.filter(Boolean) : [];
  if (!kinds.length) throw error(400, 'kinds must be a non-empty array');

  // A key scoped to certain kinds cannot widen its reach by asking for more.
  const allowed = worker.kinds.length ? kinds.filter((k) => worker.kinds.includes(k)) : kinds;
  if (!allowed.length) throw error(403, 'This worker key may not claim any of those kinds');

  const name: string = typeof body.worker === 'string' && body.worker ? body.worker : worker.name;

  const { data, error: err } = await adminClient().rpc('claim_job', {
    p_kinds: allowed,
    p_worker: name,
    p_worker_key_id: worker.id,
  });
  if (err) dbError(err, 'Could not claim a job');

  // The RPC returns a row of nulls rather than no row when nothing is queued.
  const job = data && (data as { id: string | null }).id ? data : null;
  return json({ job });
};
