/**
 * GET /api/pipeline/review-events?task=<key>&after=<id>&limit=<n> — the events of one task, for
 * the export (`review_sync.py pull`, which writes them back as review_record lines).
 *
 * Ordered by event id, which is the order they arrived. Paged by id: pass the previous page's
 * `next_after` as `after` until it is null. `limit` is 1-1000, default 1000.
 *
 * Reply: { events: [...], reviewers: { <uuid>: <display_name | null> }, next_after: number | null }
 * `reviewers` covers the reviewers on this page only; the client turns uuids into handles
 * (the rule is in review_sync.py). `client` (viewport, user agent) is not returned: the export
 * does not use it.
 *
 * Worker token, scoped to the `review` kind. Events are insert-only, so nothing here can change
 * what a reviewer decided.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireWorker } from '$lib/server/workerAuth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { TASK_KEY_RE } from '$lib/server/reviewUpload';

const MAX_LIMIT = 1000;

export const GET: RequestHandler = async ({ request, url }) => {
  await requireWorker(request, 'review');

  const task = url.searchParams.get('task') ?? '';
  if (!TASK_KEY_RE.test(task)) throw error(400, 'task is required');
  const after = Number(url.searchParams.get('after') ?? 0);
  if (!Number.isSafeInteger(after) || after < 0)
    throw error(400, 'after must be a non-negative integer');
  const limit = Number(url.searchParams.get('limit') ?? MAX_LIMIT);
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_LIMIT)
    throw error(400, `limit must be 1-${MAX_LIMIT}`);

  const supabase = adminClient();
  const { data: found, error: taskErr } = await supabase
    .from('review_tasks')
    .select('key')
    .eq('key', task)
    .maybeSingle();
  if (taskErr) dbError(taskErr, 'Could not read the task');
  if (!found) throw error(404, 'No such task');

  const { data: events, error: err } = await supabase
    .from('review_events')
    .select(
      'id, task, item_id, bound, reviewer, order_idx, shown_at, decided_at, received_at, proposal_shown, verdicts, readings, note, client_id'
    )
    .eq('task', task)
    .gt('id', after)
    .order('id', { ascending: true })
    .limit(limit);
  if (err) dbError(err, 'Could not read the events');

  const ids = [...new Set((events ?? []).map((e) => e.reviewer).filter((r): r is string => !!r))];
  const reviewers: Record<string, string | null> = {};
  if (ids.length) {
    const { data: profiles, error: profErr } = await supabase
      .from('profiles')
      .select('id, display_name')
      .in('id', ids);
    if (profErr) dbError(profErr, 'Could not read the reviewers');
    for (const id of ids) reviewers[id] = null;
    for (const p of profiles ?? []) reviewers[p.id] = p.display_name;
  }

  const last = events && events.length === limit ? events[events.length - 1].id : null;
  return json({ events: events ?? [], reviewers, next_after: last });
};
