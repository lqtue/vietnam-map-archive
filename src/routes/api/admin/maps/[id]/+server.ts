import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { pickMapFields } from '$lib/server/mapFields';
import { deriveAllmapsId } from '$lib/core/iiif/allmapsId';

/** PATCH — update map fields */
export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const supabase = adminClient();

  const body = await request.json();
  const updateData = pickMapFields(body);

  // Every field the caller sent was dropped by the allow-list — an unknown
  // column, or a value the coercion refused (a string where `asObject` wants an
  // object). PostgREST answers an empty update with a 500, which reads as a
  // server fault for what is squarely a bad request.
  if (Object.keys(updateData).length === 0) {
    throw error(400, 'No writable map fields in the request');
  }

  const { data: current, error: currentError } = await supabase
    .from('maps')
    .select('series_id,sheet_number,printing_id,status,duplicate_of_map_id,archive_reason')
    .eq('id', mapId)
    .single();
  if (currentError || !current) throw error(404, 'Map not found');
  const effective = { ...current, ...updateData };
  const publishing = effective.status === 'public' || effective.status === 'featured';
  if (effective.status === 'archived' && !String(effective.archive_reason ?? '').trim()) {
    throw error(400, 'An archive reason is required');
  }
  if (effective.duplicate_of_map_id) {
    if (effective.status !== 'archived' || !String(effective.archive_reason ?? '').trim()) {
      throw error(400, 'A duplicate target requires an explicitly archived map and reason');
    }
    if (effective.duplicate_of_map_id === mapId) throw error(400, 'A map cannot duplicate itself');
    const { data: survivor } = await supabase
      .from('maps')
      .select('status,printing_id')
      .eq('id', effective.duplicate_of_map_id)
      .maybeSingle();
    if (!survivor || !['public', 'featured'].includes(survivor.status)) {
      throw error(400, 'Duplicate target must be a public surviving map');
    }
    if (!effective.printing_id || survivor.printing_id !== effective.printing_id) {
      throw error(400, 'A duplicate redirect requires the same verified printing on both maps');
    }
    const { data: duplicatePrinting } = await supabase
      .from('sheet_printings')
      .select('review_status')
      .eq('id', effective.printing_id)
      .maybeSingle();
    if (duplicatePrinting?.review_status !== 'verified') {
      throw error(400, 'A duplicate redirect requires a verified printing identity');
    }
  }
  if (effective.series_id && !effective.sheet_number) {
    throw error(400, 'A resolved series link requires a sheet number');
  }
  if (effective.series_id && effective.sheet_number) {
    const { data: cell } = await supabase
      .from('series_cells')
      .select('id')
      .eq('series_id', effective.series_id)
      .eq('sheet_number', effective.sheet_number)
      .maybeSingle();
    if (
      !cell &&
      (publishing || updateData.series_id !== undefined || updateData.sheet_number !== undefined)
    ) {
      throw error(400, 'Resolved series and sheet number must identify an existing series cell');
    }
    if (effective.printing_id) {
      const { data: printing } = await supabase
        .from('sheet_printings')
        .select('cell_id,review_status')
        .eq('id', effective.printing_id)
        .maybeSingle();
      if (!cell || !printing || printing.cell_id !== cell.id) {
        throw error(400, 'Printing must belong to the map’s resolved series cell');
      }
      if (publishing && printing.review_status !== 'verified') {
        throw error(400, 'A public map requires a verified printing identity');
      }
    }
  } else if (effective.printing_id) {
    throw error(400, 'A printing link requires a resolved series and sheet number');
  }

  // Auto-derive allmaps_id when iiif_image is being set and caller didn't
  // provide an explicit allmaps_id. Look up the existing row to see whether
  // we already have one — never overwrite a present value silently.
  if (updateData.iiif_image && body.allmaps_id === undefined) {
    const { data: existing } = await supabase
      .from('maps')
      .select('allmaps_id')
      .eq('id', mapId)
      .single();
    if (!existing?.allmaps_id) {
      try {
        updateData.allmaps_id = await deriveAllmapsId(updateData.iiif_image as string);
      } catch (e) {
        console.error('[admin/maps PATCH] deriveAllmapsId failed:', e);
      }
    }
  }

  const { data, error: err } = await supabase
    .from('maps')
    .update(updateData)
    .eq('id', mapId)
    .select()
    .single();

  if (err) dbError(err, 'Could not update map');
  return json(data);
};

/** DELETE — retained for the existing authorized admin workflow. */
export const DELETE: RequestHandler = async ({ locals, params }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const { error: err } = await adminClient().from('maps').delete().eq('id', mapId);
  if (err) dbError(err, 'Could not delete map');
  return json({ success: true });
};
