import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { geometryKind, type FeatureType } from '$lib/data/maps/footprintTypes';
import { validRing } from '$lib/core/geo/simplifyRing';
import { readAllPages } from '$lib/data/supabase/footprints';
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

  try {
    const data = await readAllPages((from, to) =>
      adminClient()
        .from('footprints')
        .select(
          'id, map_id, iiif_canvas, pixel_polygon, feature_type, name, category, confidence, status:review_status, created_at'
        )
        .eq('map_id', mapId)
        .in('review_status', statuses)
        .order('confidence', { ascending: false })
        .order('id')
        .range(from, to)
    );
    return json(data);
  } catch (err) {
    dbError(err, 'Could not list footprints');
  }
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
  const {
    id,
    status,
    pixel_polygon,
    feature_type,
    name,
    category,
    review_tags,
    review_note,
    expected_pixel_polygon,
    expected_feature_type,
    expected_status,
  } = body as {
    id: string;
    status: string;
    pixel_polygon?: [number, number][];
    feature_type?: string;
    name?: string;
    category?: string;
    review_tags?: string[];
    review_note?: string;
    expected_pixel_polygon?: [number, number][];
    expected_feature_type?: string;
    expected_status?: string;
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

  const footprintId = assertUuid(id, 'footprint id');
  if (
    pixel_polygon !== undefined &&
    (!Array.isArray(pixel_polygon) ||
      pixel_polygon.length < 2 ||
      pixel_polygon.some((p) => !Array.isArray(p) || p.length !== 2 || !p.every(Number.isFinite)))
  ) {
    throw error(400, 'pixel_polygon must contain at least two finite coordinate pairs');
  }
  let targetType = feature_type ?? expected_feature_type;
  if (pixel_polygon !== undefined && targetType === undefined) {
    const { data: original, error: readError } = await adminClient()
      .from('footprints')
      .select('feature_type')
      .eq('id', footprintId)
      .maybeSingle();
    if (readError) dbError(readError, 'Could not resolve footprint type');
    if (!original) throw error(409, 'That footprint no longer exists');
    targetType = original.feature_type;
  }
  if (
    pixel_polygon !== undefined &&
    geometryKind(targetType as FeatureType, pixel_polygon) === 'Polygon' &&
    !validRing(pixel_polygon)
  ) {
    throw error(400, 'pixel_polygon must be a valid outline');
  }
  const args = {
    p_id: footprintId,
    p_status: status,
    p_user: user.id,
    p_pixel_polygon: pixel_polygon ?? undefined,
    p_feature_type: feature_type ?? undefined,
    p_name: name ?? undefined,
    p_category: category ?? undefined,
    p_review_tags: review_tags ?? undefined,
    p_review_note: review_note?.trim() || undefined,
  };
  const guarded = expected_pixel_polygon !== undefined;
  if (guarded && (!expected_feature_type || !expected_status))
    throw error(400, 'Expected type and status are required with the original outline');
  const { data, error: err } = guarded
    ? await adminClient().rpc('review_footprint_if_current', {
        ...args,
        p_expected_polygon: expected_pixel_polygon,
        p_expected_feature_type: expected_feature_type!,
        p_expected_status: expected_status!,
      })
    : await adminClient().rpc('set_footprint_status', args);
  if (err?.code === '40001')
    throw error(409, 'This footprint changed. Reload the sheet before reviewing.');
  if (guarded && err?.code === 'PGRST202')
    throw error(
      503,
      'Geometry review requires migration 121. Apply it before deploying this review tool.'
    );
  if (err) dbError(err, 'Could not update footprint');
  // The RPC only moves rows out of needs_review, and returns nothing otherwise.
  if (!data || (!guarded && !(data as { id: string | null }).id)) {
    throw error(409, 'That footprint is not awaiting review');
  }
  return json({ ok: true });
};
