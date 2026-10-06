import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { textGroupsAvailable } from '$lib/server/textGroups';
import { warpFields } from '$lib/server/ocrReview';
import { OCR_CATEGORIES } from '$lib/features/contribute/shared/constants';

export const POST: RequestHandler = async ({ params, request, locals }) => {
  const { user } = await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const { ids, text, category } = await request.json();
  if (
    !Array.isArray(ids) ||
    ids.length < 2 ||
    ids.length > 100 ||
    new Set(ids).size !== ids.length
  ) {
    throw error(400, 'Select between 2 and 100 different boxes');
  }
  ids.forEach((id) => assertUuid(id, 'label id'));
  if (typeof text !== 'string' || !text.trim() || text.length > 2000)
    throw error(400, 'Enter the combined label text');
  if (!OCR_CATEGORIES.includes(category)) throw error(400, 'Choose a label category');
  const db = adminClient();
  if (!(await textGroupsAvailable(db)))
    throw error(503, 'Text grouping is not available until database migration 112 is applied');
  const { data: rows, error: readError } = await db
    .from('ocr_labels')
    .select('id, run_id, global_x, global_y, global_w, global_h, text_group_id, is_text_group')
    .eq('map_id', mapId)
    .in('id', ids);
  if (readError) dbError(readError, 'Could not read selected boxes');
  if (
    rows?.length !== ids.length ||
    rows.some(
      (r) =>
        r.is_text_group ||
        r.text_group_id ||
        ![r.global_x, r.global_y, r.global_w, r.global_h].every(Number.isFinite) ||
        !(r.global_w! > 0) ||
        !(r.global_h! > 0)
    )
  ) {
    throw error(409, 'Select original boxes that are not already grouped');
  }
  const x = Math.min(...rows.map((r) => r.global_x));
  const y = Math.min(...rows.map((r) => r.global_y));
  const w = Math.max(...rows.map((r) => r.global_x + r.global_w!)) - x;
  const h = Math.max(...rows.map((r) => r.global_y + r.global_h!)) - y;
  const geo = await warpFields(db, mapId, { global_x: x, global_y: y, global_w: w, global_h: h });
  const { data: id, error: groupError } = await db.rpc('group_text_boxes', {
    p_map_id: mapId,
    p_ids: ids,
    p_text: text.trim(),
    p_category: category,
    p_bounds: [x, y, w, h],
    p_geom: geo.geom,
    p_geom_src: geo.geom_src,
    p_geom_rmse: geo.geom_rmse,
    p_user: user.id,
  });
  if (groupError?.code === '22023') {
    const reasons: Record<string, string> = {
      'Boxes missing or already grouped':
        'A selected box was removed or already grouped. Reload and select the boxes again.',
      'Boxes changed; reload and try again':
        'A selected box moved while grouping. Reload and select the boxes again.',
      'Choose boxes from the same OCR run': 'Choose boxes from the same OCR run.',
      'Invalid group': 'Select at least two different boxes and enter the combined text.',
    };
    console.error('[api] Grouping rejected:', groupError.message);
    throw error(
      409,
      reasons[groupError.message] ?? 'Could not group this selection. Reload and try again.'
    );
  }
  if (groupError) dbError(groupError, 'Could not group text boxes');
  return json({ id });
};

export const DELETE: RequestHandler = async ({ params, request, locals }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const { id } = await request.json();
  assertUuid(id, 'group id');
  const db = adminClient();
  if (!(await textGroupsAvailable(db)))
    throw error(503, 'Text grouping is not available until database migration 112 is applied');
  const { error: err } = await db.rpc('ungroup_text_boxes', {
    p_map_id: mapId,
    p_id: id,
  });
  if (err?.code === '22023') throw error(404, 'Group not found');
  if (err) dbError(err, 'Could not ungroup text boxes');
  return json({ ok: true });
};
