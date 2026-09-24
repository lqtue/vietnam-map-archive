import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import type { Database } from '$lib/data/supabase/types';

/** PATCH — update a source (e.g. set is_primary, change label) */
export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const sourceId = assertUuid(params.sourceId, 'source id');
  const supabase = adminClient();
  const body = await request.json();

  const updateData: Database['public']['Tables']['map_images']['Update'] = {};
  if (body.label !== undefined) updateData.label = body.label;
  if (body.source_type !== undefined) updateData.source_type = body.source_type;
  if (body.iiif_manifest !== undefined) updateData.iiif_manifest = body.iiif_manifest;
  if (body.iiif_image !== undefined) updateData.iiif_image = body.iiif_image;
  if (body.is_primary !== undefined) updateData.is_primary = body.is_primary;
  if (body.sort_order !== undefined) updateData.sort_order = body.sort_order;

  // Setting a new primary: clear the existing one first to avoid the partial
  // unique index violation on (map_id) WHERE is_primary = true.
  // The trigger would do this too, but it runs AFTER the constraint check.
  if (updateData.is_primary === true) {
    const { error: clearErr } = await supabase
      .from('map_images')
      .update({ is_primary: false })
      .eq('map_id', mapId)
      .eq('is_primary', true)
      .neq('id', sourceId);
    if (clearErr) dbError(clearErr, 'Could not demote the existing primary source');
  }

  const { data, error: err } = await supabase
    .from('map_images')
    .update(updateData)
    .eq('id', sourceId)
    .eq('map_id', mapId)
    .select()
    .single();

  if (err) dbError(err, 'Could not update IIIF source');
  return json(data);
};

/** DELETE — remove a source (cannot delete the only primary) */
export const DELETE: RequestHandler = async ({ locals, params }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const sourceId = assertUuid(params.sourceId, 'source id');
  const supabase = adminClient();

  // Guard: don't delete the primary if it's the only source
  const { data: sources } = await supabase
    .from('map_images')
    .select('id, is_primary')
    .eq('map_id', mapId);

  const target = sources?.find((s) => s.id === sourceId);

  if (target?.is_primary && (sources?.length ?? 0) <= 1) {
    throw error(400, 'Cannot delete the only IIIF source for a map');
  }

  const { error: err } = await supabase
    .from('map_images')
    .delete()
    .eq('id', sourceId)
    .eq('map_id', mapId);

  if (err) dbError(err, 'Could not delete IIIF source');
  return json({ success: true });
};
