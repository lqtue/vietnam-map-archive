/**
 * POST /api/contribute/footprints — submit a hand-traced polygon.
 *
 * Decision 4 in docs/architecture-target.md: shared writes go through /api, not
 * straight from the browser. That is what makes a rate limit and a
 * server-stamped `user_id` possible; RLS alone can enforce neither.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireUser, assertUnderRateLimit } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { polygonEwkt, resolveMapWarp } from '$lib/server/warp';
import { assertUuid, dbError } from '$lib/server/http';

/** Generous enough for a good tracing session, low enough to stop a script. */
const MAX_PER_HOUR = 300;

const FEATURE_TYPES = ['building', 'land_plot', 'road', 'waterway', 'block', 'other'];

export const POST: RequestHandler = async ({ locals, request }) => {
  const { user } = await requireUser(locals);
  const body = await request.json().catch(() => ({}));

  const mapId = assertUuid(body.map_id, 'map_id');
  const polygon = body.pixel_polygon;
  if (!Array.isArray(polygon) || polygon.length < 2) {
    throw error(400, 'pixel_polygon must have at least two points');
  }
  if (body.feature_type && !FEATURE_TYPES.includes(body.feature_type)) {
    throw error(400, `feature_type must be one of ${FEATURE_TYPES.join(', ')}`);
  }

  await assertUnderRateLimit('footprints', user.id, MAX_PER_HOUR);

  const admin = adminClient();

  // Warp into the place-time index on the way in (migration 066). A line trace
  // has no polygon and a map with no annotation has no position; both write a
  // null geom rather than a fabricated one.
  const { data: map } = await admin
    .from('maps')
    .select('allmaps_id, annotation_url')
    .eq('id', mapId)
    .single();
  const warp = map ? await resolveMapWarp(map.allmaps_id, map.annotation_url) : null;
  const geom = warp ? polygonEwkt(warp, polygon) : null;

  const { data, error: err } = await admin
    .from('footprints')
    .insert({
      map_id: mapId,
      user_id: user.id, // from the session, never from the body
      pixel_polygon: polygon,
      geom,
      geom_src: geom ? warp!.src : null,
      geom_rmse: geom ? warp!.rmse : null,
      name: body.name ?? null,
      category: body.category ?? null,
      feature_type: body.feature_type ?? 'building',
      review_status: 'submitted',
      source: 'volunteer',
    })
    .select('id')
    .single();

  if (err) dbError(err, 'Could not save the footprint');
  return json({ id: data!.id }, { status: 201 });
};
