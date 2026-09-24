import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { pickMapFields } from '$lib/server/mapFields';
import { deriveAllmapsId } from '$lib/core/iiif/allmapsId';

/** POST — create a new map */
export const POST: RequestHandler = async ({ locals, request }) => {
  await requireRole(locals);

  const body = await request.json();
  const { name, allmaps_id, iiif_image } = body;

  if (!name) throw error(400, 'name is required');

  // Auto-derive allmaps_id from iiif_image when caller didn't supply one.
  let resolvedAllmapsId = allmaps_id || null;
  if (!resolvedAllmapsId && iiif_image) {
    try {
      resolvedAllmapsId = await deriveAllmapsId(iiif_image);
    } catch (e) {
      console.error('[admin/maps POST] deriveAllmapsId failed:', e);
    }
  }

  const insertData = {
    ...pickMapFields(body),
    // Always present on create, even when the caller omitted them.
    name,
    allmaps_id: resolvedAllmapsId,
    annotation_url: body.annotation_url || null,
    location: body.location || null,
    year: body.year ? Number(body.year) : null,
    description: body.description || null,
  };

  const { data, error: err } = await adminClient()
    .from('maps')
    .insert(insertData)
    .select()
    .single();

  if (err) dbError(err, 'Could not create map');
  return json(data, { status: 201 });
};
