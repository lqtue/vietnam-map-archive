/**
 * POST /api/pipeline/review-items — a review task and its items, from the offline pipeline.
 *
 * Body: { task: { key, title, question, question_vi?, method, seed, blind_frac?, audience?, status? },
 *         items: [{ item_id, bound, payload, proposal?, gold?, active? }, ...] }   (≤ 200 items)
 *
 * Upserts the task row, then the items (key: task + item_id). Idempotent: send it again to
 * change a title, a status or an item's proposal. A bigger task goes in several calls, each
 * carrying the same task row (`review_sync.py push` does this).
 *
 * Worker token (`/api/pipeline/*`), scoped to the `review` kind: a key limited to `ocr` or `seg`
 * cannot write review items. Python still makes the machine's proposals and the crops; this is
 * the only way they reach the page (docs/plans/review-page-plan.md §2.9).
 *
 * Once a task has events, its `seed`, `blind_frac` and `method` are frozen (409): they decide who
 * saw a proposal, and changing them under a running sitting is exactly the drift the offline
 * session.json refuses. An item's `bound` may change; that is how a verdict goes stale.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireWorker } from '$lib/server/workerAuth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { MAX_BODY_BYTES, parseUpload } from '$lib/server/reviewUpload';

export const POST: RequestHandler = async ({ request }) => {
  await requireWorker(request, 'review');

  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) throw error(413, `Body over ${MAX_BODY_BYTES} bytes`);
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    throw error(400, 'Body is not JSON');
  }
  const { task, items } = parseUpload(body);

  const supabase = adminClient();

  const { data: existing, error: readErr } = await supabase
    .from('review_tasks')
    .select('seed, blind_frac, method')
    .eq('key', task.key)
    .maybeSingle();
  if (readErr) dbError(readErr, 'Could not read the task');
  if (
    existing &&
    (existing.seed !== task.seed ||
      Math.abs(existing.blind_frac - task.blind_frac) > 1e-6 ||
      existing.method !== task.method)
  ) {
    const { count, error: countErr } = await supabase
      .from('review_events')
      .select('id', { count: 'exact', head: true })
      .eq('task', task.key);
    if (countErr) dbError(countErr, 'Could not read the task events');
    if (count) throw error(409, 'Task has events: seed, blind_frac and method are frozen');
  }

  const { error: taskErr } = await supabase
    .from('review_tasks')
    .upsert(task, { onConflict: 'key' });
  if (taskErr) dbError(taskErr, 'Could not write the task');

  const rows = items.map((item) => ({ ...item, task: task.key }));
  const { error: itemErr } = await supabase
    .from('review_items')
    .upsert(rows, { onConflict: 'task,item_id' });
  if (itemErr) dbError(itemErr, 'Could not write the items');

  return json({ ok: true, task: task.key, items: rows.length });
};
