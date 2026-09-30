import { error } from '@sveltejs/kit';
import { adminClient } from './supabaseAdmin';
import { requireWorker } from './workerAuth';
import { assertUuid, dbError } from './http';

/** A claim belongs to the bearer key, not the caller-supplied worker name. */
export async function requireClaimedJob(request: Request, jobId: string) {
  const worker = await requireWorker(request);
  const { data: job, error: readError } = await adminClient()
    .from('pipeline_jobs')
    .select('id, kind, map_id, payload, status, worker_key_id')
    .eq('id', assertUuid(jobId, 'job_id'))
    .maybeSingle();
  if (readError) dbError(readError, 'Could not read job');
  if (!job) throw error(404, 'No such job');
  if (worker.kinds.length && !worker.kinds.includes(job.kind)) {
    throw error(403, 'Worker key may not handle this job kind');
  }
  if (job.worker_key_id !== worker.id || !['claimed', 'running'].includes(job.status)) {
    throw error(403, 'Job is not claimed by this worker key');
  }
  return { worker, job };
}
