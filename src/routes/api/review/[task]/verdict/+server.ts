/**
 * POST /api/review/[task]/verdict — store one verdict as one `review_events` row.
 *
 * Body: { item_id, bound, relation, pick?, search_id?, note?, shown_at, decided_at, hidden_ms?,
 *         client_id, client? }  (stamps are epoch milliseconds from the page)
 *
 * The reviewer comes from the session, never the body. The arm is the server's own (recomputed from
 * the task seed). 409 when `bound` no longer matches the item (it changed since it was loaded); a
 * resend with the same `client_id` stores nothing twice and answers ok with `duplicate: true`.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { openTask, saveVerdict } from '$lib/server/reviewSession';
import { parseVerdictBody } from '$lib/server/reviewVerdict';

export const POST: RequestHandler = async ({ locals, params, request }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw error(400, 'Body is not JSON');
  }
  const parsed = parseVerdictBody(body);
  const sb = adminClient();
  const task = await openTask(sb, params.task);
  return json(await saveVerdict(sb, task, user.id, parsed));
};
