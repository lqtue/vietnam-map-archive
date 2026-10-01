/**
 * POST /api/admin/maps/[id]/sync-allmaps — "fetch latest".
 *
 * Re-reads the annotation from allmaps.org (ignoring our stored copy), rewrites
 * and stores it. Use after editing the georeference in the Allmaps Editor. The
 * previous version stays at `annotations/{mapId}/{timestamp}.json`.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { assertUuid } from '$lib/server/http';
import { mirrorAnnotation } from '$lib/server/annotationMirror';

export const POST: RequestHandler = async ({ locals, params }) => {
  const { user } = await requireRole(locals);
  return json(
    await mirrorAnnotation(assertUuid(params.id, 'map id'), { fromAllmaps: true, userId: user.id })
  );
};
