/**
 * GET   /api/admin/stories?status=submitted — the moderation queue
 * PATCH /api/admin/stories  { id, status }  — a review decision
 *
 * Same shape as /api/admin/footprints: contributions are open, so every shared
 * kind gets one staff-gated review endpoint backed by a status RPC (mig 059).
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';

const REVIEW_STATUSES = ['approved', 'rejected', 'draft'];

export const GET: RequestHandler = async ({ locals, url }) => {
  await requireRole(locals, ['admin', 'mod']);
  const status = url.searchParams.get('status') ?? 'submitted';

  const { data, error: err } = await adminClient()
    .from('stories')
    .select(
      'id, title, description, mode, status:review_status, user_id, created_at, updated_at, story_points(id)'
    )
    .eq('review_status', status)
    .order('updated_at', { ascending: false });

  if (err) dbError(err, 'Could not list stories');

  // The count is what a reviewer actually wants to see, not the ids.
  return json(
    (data ?? []).map(({ story_points, ...story }) => ({
      ...story,
      point_count: story_points?.length ?? 0,
    }))
  );
};

export const PATCH: RequestHandler = async ({ locals, request }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const body = await request.json().catch(() => ({}));

  if (!REVIEW_STATUSES.includes(body.status)) {
    throw error(400, `status must be one of ${REVIEW_STATUSES.join(', ')}`);
  }

  const { data, error: err } = await adminClient().rpc('set_story_status', {
    p_id: assertUuid(body.id, 'story id'),
    p_status: body.status,
    p_user: user.id,
  });
  if (err) dbError(err, 'Could not update the story');
  if (!data || !(data as { id: string | null }).id) throw error(404, 'No such story');

  return json({ ok: true, story: data });
};
