/**
 * GET /api/review/tasks — the open review tasks for this reviewer, each with how many items they
 * have left. Staff (admin/mod) only in v1. Reads only this reviewer's own events.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { listTasks } from '$lib/server/reviewSession';

export const GET: RequestHandler = async ({ locals }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  return json({ tasks: await listTasks(adminClient(), user.id) });
};
