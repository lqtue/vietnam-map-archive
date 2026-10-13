import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { getTransformer } from '$lib/server/transformer';

/**
 * A pixel read off another sheet, in this sheet's pixels: the legend tool's
 * "click on sheet" — a Cholon entry printed on the Saigon half is clicked on the
 * Saigon scan and stored against Cholon. Body `{ from: <map uuid>, x, y }`;
 * answers `{ x, y }`, which may lie past this scan's edge (or before its origin,
 * which the caller must refuse — legend `px=` is unsigned).
 */
export const POST: RequestHandler = async ({ params, request, locals }) => {
  await requireRole(locals, ['admin', 'mod']);
  const mapId = assertUuid(params.id, 'map id');
  const body = await request.json().catch(() => null);
  const from = assertUuid(typeof body?.from === 'string' ? body.from : '', 'source map id');
  if (![body?.x, body?.y].every((v) => typeof v === 'number' && Number.isFinite(v)))
    throw error(400, 'x and y must be numbers');

  const db = adminClient();
  const { data, error: readError } = await db
    .from('maps')
    .select('id, allmaps_id, annotation_url')
    .in('id', [mapId, from]);
  if (readError) dbError(readError, 'Could not read maps');
  const [here, there] = await Promise.all(
    [mapId, from].map((id) => {
      const m = data?.find((row) => row.id === id);
      return m ? getTransformer(m.allmaps_id, m.annotation_url) : null;
    })
  );
  if (!here || !there) throw error(409, 'Both sheets need a georeference');
  const [x, y] = here.transformer.transformToResource(
    there.transformer.transformToGeo([body.x, body.y])
  );
  return json({ x: Math.round(x), y: Math.round(y) });
};
