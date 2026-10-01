/**
 * POST /api/admin/maps/[id]/mirror-r2 — self-host this map's annotation.
 *
 * The work lives in `$lib/server/annotationMirror.ts`, because the
 * `mirror_annotation` and `sync_allmaps` jobs run exactly the same thing.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { assertUuid } from '$lib/server/http';
import { mirrorAnnotation } from '$lib/server/annotationMirror';

export const POST: RequestHandler = async ({ locals, params }) => {
  const { user } = await requireRole(locals);
  return json(await mirrorAnnotation(assertUuid(params.id, 'map id'), { userId: user.id }));
};
