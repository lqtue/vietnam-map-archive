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

  // Fetch the stored mirror, never an arbitrary URL supplied by the caller.
  const { data: map } = await adminClient()
    .from('maps')
    .select('allmaps_id, annotation_url')
    .eq('id', mapId)
    .single();

  if (!map) throw error(404, 'Map not found');

  const annotationUrl =
    map.annotation_url ?? (map.allmaps_id?.startsWith('http') ? map.allmaps_id : null);
  if (!annotationUrl) {
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

  await uploadJson('annotations', `${mapId}.json`, annotation);
  await adminClient()
    .from('maps')
    .update({ annotation_url: `https://maparchive.vn/api/maps/${mapId}/annotation` })
    .eq('id', mapId);

  return json({ success: true });
};
