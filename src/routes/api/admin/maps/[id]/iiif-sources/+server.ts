import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';

/** GET — list all IIIF sources for a map */
export const GET: RequestHandler = async ({ locals, params }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');

  const { data, error: err } = await adminClient()
    .from('map_images')
    .select('*')
    .eq('map_id', mapId)
    .order('sort_order');

  if (err) dbError(err, 'Could not list IIIF sources');
  return json(data);
};

/** POST — add a IIIF source to a map */
export const POST: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const body = await request.json();

  const { label, source_type, iiif_manifest, iiif_image, is_primary, sort_order } = body;
  if (!iiif_image) throw error(400, 'iiif_image is required');

  // If making this primary, the DB trigger handles demoting others
  const { data, error: err } = await adminClient()
    .from('map_images')
    .insert({
      map_id: mapId,
      label: label || null,
      source_type: source_type || null,
      iiif_manifest: iiif_manifest || null,
      iiif_image,
      is_primary: is_primary ?? false,
      sort_order: sort_order ?? 0,
    })
    .select()
    .single();

  if (err) dbError(err, 'Could not add IIIF source');
  return json(data, { status: 201 });
};
