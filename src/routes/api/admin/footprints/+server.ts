import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { isReviewTag, REVIEW_NOTE_MAX } from '$lib/core/reviewTags';

/**
 * GET /api/admin/footprints?map_id=&status=
 *
 * `status` takes a comma-separated list. The default is the whole review queue,
 * which is two states and not one: MapSAM2 writes `needs_review`, a volunteer's
 * trace lands in `submitted`, and a reviewer has to see both.
 */
export const GET: RequestHandler = async ({ locals, url }) => {
  await requireRole(locals);

  const mapId = assertUuid(url.searchParams.get('map_id') ?? undefined, 'map_id');
  const statuses = (url.searchParams.get('status') ?? 'needs_review,submitted')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  if (!statuses.length) throw error(400, 'status must name at least one state');

  const { data, error: err } = await adminClient()
    .from('footprint_submissions')
    .select(
      'id, map_id, iiif_canvas, pixel_polygon, feature_type, name, category, confidence, status, created_at'
    )
    .eq('map_id', mapId)
    .in('status', statuses)
    .order('confidence', { ascending: false });

  if (err) dbError(err, 'Could not list footprints');
  return json(data);
};

/**
 * PATCH /api/admin/footprints  { id, status: 'approved' | 'rejected' }
 *
 * The transition (and the `sam-corrected` marking that comes with an edited
 * polygon) lives in the `set_footprint_status` RPC — migrations 054 and 090.
 *
 * `submitted` used to be accepted here as the approving verdict, which left
 * a row in the state it was already in and meant nothing could ever reach
 * `approved` — the state /api/export/footprints filters on by default.
 */
export const PATCH: RequestHandler = async ({ locals, request }) => {
  const { user } = await requireRole(locals);

  const body = await request.json();
  const { id, status, pixel_polygon, feature_type, name, category, review_tags, review_note } =
    body as {
      id: string;
      status: string;
      pixel_polygon?: [number, number][];
      feature_type?: string;
      name?: string;
      category?: string;
      review_tags?: string[];
      review_note?: string;
    };

  if (!id || !status) throw error(400, 'id and status are required');
  if (!['approved', 'rejected'].includes(status)) {
    throw error(400, 'status must be approved or rejected');
  }
  if (
    review_tags !== undefined &&
    (!Array.isArray(review_tags) || !review_tags.every(isReviewTag))
  ) {
    throw error(400, 'review_tags contains an unknown diagnosis');
  }
  if (
    review_note !== undefined &&
    (typeof review_note !== 'string' || review_note.length > REVIEW_NOTE_MAX)
  ) {
    throw error(400, `review_note must be a string of at most ${REVIEW_NOTE_MAX} characters`);
  }

  const { data, error: err } = await adminClient().rpc('set_footprint_status', {
    p_id: assertUuid(id, 'footprint id'),
    p_status: status,
    p_user: user.id,
    p_pixel_polygon: pixel_polygon ?? undefined,
    p_feature_type: feature_type ?? undefined,
    p_name: name ?? undefined,
    p_category: category ?? undefined,
    p_review_tags: review_tags ?? undefined,
    p_review_note: review_note?.trim() || undefined,
  });

  if (err) dbError(err, 'Could not update footprint');
  // The RPC only moves rows out of needs_review, and returns nothing otherwise.
  if (!data || !(data as { id: string | null }).id) {
    throw error(409, 'That footprint is not awaiting review');
  }
  return json({ ok: true });
};
