import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { uploadToIA } from '$lib/server/ia';

/** Historical scans run large; the client only asks for `image/*`. */
const MAX_IMAGE_BYTES = 200 * 1024 * 1024;

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/tiff', 'image/webp'];

/**
 * POST — Upload a replacement image for a map.
 * Uploads to Internet Archive S3 and returns the resulting IIIF image URL;
 * the caller decides whether to persist it on the map row.
 */
export const POST: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');

  const { data: map } = await adminClient()
    .from('maps')
    .select('name, allmaps_id')
    .eq('id', mapId)
    .single();

  if (!map) throw error(404, 'Map not found');

  const formData = await request.formData();
  const image = formData.get('image');
  if (!(image instanceof File)) throw error(400, 'No image file provided');
  if (!ALLOWED_IMAGE_TYPES.includes(image.type)) {
    throw error(400, `Unsupported image type: ${image.type || 'unknown'}`);
  }
  if (image.size > MAX_IMAGE_BYTES) {
    throw error(413, `Image exceeds the ${MAX_IMAGE_BYTES / (1024 * 1024)} MB limit`);
  }

  const upload = await uploadToIA(image, `vma-map-${mapId}`, map.name);

  return json({
    success: true,
    ia_identifier: upload.identifier,
    ia_filename: upload.filename,
    iiif_url: upload.iiifUrl,
  });
};
