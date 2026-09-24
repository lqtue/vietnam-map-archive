// /api/admin/scout/[id] — approve, reject, or update a single candidate
import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import type { Database } from '$lib/data/supabase/types';

export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const candidateId = assertUuid(params.id, 'candidate id');
  const body = await request.json();
  const allowed = [
    'status',
    'category',
    'thumbnail',
    'title',
    'creator',
    'year',
    'language',
    'rights',
    // The reviewer's reason for the decision (mig 078). Optional, and blank
    // clears it — a reason that no longer applies should not outlive a revert.
    'review_note',
  ] as const;
  const patch: Database['public']['Tables']['scout_candidates']['Update'] = {};
  for (const k of allowed) {
    if (body[k] === undefined) continue;
    // `status` stays the request body's field name; the column is `review_status`.
    if (k === 'status') patch.review_status = body[k];
    else patch[k] = body[k];
  }
  if (patch.review_status && !['pending', 'approved', 'rejected'].includes(patch.review_status)) {
    throw error(400, 'invalid status (use ingest endpoint to mark ingested)');
  }
  if (patch.review_status) {
    patch.reviewed_by = user.id;
    patch.reviewed_at = new Date().toISOString();
  }
  const { data, error: err } = await adminClient()
    .from('scout_candidates')
    .update(patch)
    .eq('id', candidateId)
    .select('*, status:review_status')
    .single();
  if (err) dbError(err, 'Could not update scout candidate');
  return json(data);
};
