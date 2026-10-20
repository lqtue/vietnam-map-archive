/**
 * POST /api/review/[task]/undo — append the undo for this reviewer's last live verdict.
 *
 * Reply: { ok, undone: item_id | null }. An undo is an event whose verdicts are {"undone": true};
 * nothing is rewritten or deleted (review_events is insert-only). Staff only in v1.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { openTask, undoLast } from '$lib/server/reviewSession';

export const POST: RequestHandler = async ({ locals, params }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const sb = adminClient();
  const task = await openTask(sb, params.task);
  return json(await undoLast(sb, task, user.id));
};
