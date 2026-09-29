import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { uploadJson } from '$lib/server/storage';
import { fetchAnnotationJson } from '$lib/server/safeAnnotation';

interface GCP {
  resourceCoords: [number, number];
  geo: [number, number];
}

/**
 * PATCH — update GCPs in a self-hosted annotation JSON stored in Supabase Storage.
 * Body: { gcps: [{resourceCoords:[x,y], geo:[lon,lat]}, ...] }
 * Order: NW, NE, SE, SW
 */
export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');

  const body = await request.json();
  const gcps: GCP[] = body.gcps;

  if (!Array.isArray(gcps) || gcps.length !== 4) {
    throw error(400, 'Expected exactly 4 GCPs');
  }

  // Fetch map to get allmaps_id (must be a URL for self-hosted)
  const { data: map } = await adminClient()
    .from('maps')
    .select('allmaps_id')
    .eq('id', mapId)
    .single();

  if (!map) throw error(404, 'Map not found');

  const annotationUrl = map.allmaps_id;
  if (!annotationUrl?.startsWith('http')) {
    throw error(400, 'This map does not use a self-hosted annotation URL');
  }

  let annotation: any;
  try {
    annotation = await fetchAnnotationJson(annotationUrl);
  } catch {
    throw error(502, 'Failed to fetch annotation');
  }

  // Extract source info for SVG dimensions
  const item = annotation.items?.[0];
  if (!item) throw error(400, 'No annotation items found');

  const target = item.target;
  const source = typeof target === 'string' ? { id: target } : (target.source ?? target);
  const sourceId = typeof source === 'string' ? source : source.id;
  const imgWidth: number = source.width ?? 0;
  const imgHeight: number = source.height ?? 0;

  // Rebuild the neatline polygon from GCP resource coords (NW, NE, SE, SW)
  const points = gcps.map((g) => `${g.resourceCoords[0]},${g.resourceCoords[1]}`).join(' ');

  const svgValue = `<svg width="${imgWidth}" height="${imgHeight}"><polygon points="${points}" /></svg>`;

  // Rebuild GCP features
  const features = gcps.map((g) => ({
    type: 'Feature',
    properties: {
      resourceCoords: g.resourceCoords,
    },
    geometry: {
      type: 'Point',
      coordinates: g.geo,
    },
  }));

  // Update annotation in place
  item.body = {
    type: 'FeatureCollection',
    features,
  };

  if (typeof target === 'string') {
    item.target = {
      type: 'SpecificResource',
      source: sourceId,
      selector: {
        type: 'SvgSelector',
        value: svgValue,
      },
    };
  } else {
    target.selector = {
      type: 'SvgSelector',
      value: svgValue,
    };
  }

  // Extract Supabase Storage bucket + path from the URL.
  // Strip query params first, then parse:
  // https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
  const cleanUrl = annotationUrl.split('?')[0];
  const storageMarker = '/object/public/';
  const markerIdx = cleanUrl.indexOf(storageMarker);
  if (markerIdx === -1) {
    throw error(400, 'Cannot determine storage path from annotation URL');
  }
  const storagePath = cleanUrl.slice(markerIdx + storageMarker.length);
  const bucketEnd = storagePath.indexOf('/');
  if (bucketEnd === -1) throw error(400, 'Cannot parse bucket from storage path');

  await uploadJson(storagePath.slice(0, bucketEnd), storagePath.slice(bucketEnd + 1), annotation);

  return json({ success: true });
};
