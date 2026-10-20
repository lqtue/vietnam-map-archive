/**
 * GET /api/review/[task]/next — the next item for this reviewer.
 *
 * Reply: { task: { key, title, question }, done, total, item: null | { item_id, bound, payload, proposal } }. `proposal` is the
 * machine's candidates on this reviewer's shown arm and [] otherwise, and `payload.pool` (what
 * search reads) is never sent: the blind arm must not see the machine's answer (plan §2.3). The
 * reply never says which arm the reviewer is on. Staff only in v1.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { nextItem, openTask } from '$lib/server/reviewSession';

export const GET: RequestHandler = async ({ locals, params }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const sb = adminClient();
  const task = await openTask(sb, params.task);
  return json(await nextItem(sb, task, user.id), { headers: { 'cache-control': 'no-store' } });
};
