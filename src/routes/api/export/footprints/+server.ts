/**
 * GET /api/export/footprints
 *
 * Exports volunteer-traced and SAM-generated building footprints.
 *
 * Query params:
 *   map_id   — one uuid or a comma-separated list. Required for coco format.
 *   status   — default 'approved'. A reviewed polygon is the only kind an
 *              anonymous consumer should be handed; pass status=submitted
 *              explicitly when you want the raw queue.
 *   year     — 'from-to' (e.g. 1878-1968) filtering on the source map's year
 *   bbox     — 'minLng,minLat,maxLng,maxLat', applied AFTER the warp, so it
 *              selects by where the feature is on the ground (the District 4
 *              study area is one such box). Features that could not be warped
 *              are dropped when bbox is given, since they have no position.
 *   format   — 'geojson' (default) | 'coco'
 *   limit    — row cap, default 5000, max 20000. Without map_id this endpoint
 *              would otherwise stream the whole archive on one request.
 *   pad      — COCO only: pixel padding around each crop bbox (default 128)
 *   size     — COCO only: IIIF output size for image crops (default 1024)
 *
 * COCO format returns a complete dataset ready for segmentation training:
 *   images[]      — one entry per footprint with IIIF crop URL + dimensions
 *   annotations[] — polygon segmentation relative to each crop
 *   categories[]  — feature_type classes
 *
 * Usage in Colab:
 *   coco = requests.get('.../api/export/footprints?format=coco&map_id=<uuid>').json()
 *   # Each image has coco['images'][i]['iiif_url'] — fetch it to get the image crop
 *   # Polygon is already crop-relative in coco['annotations'][i]['segmentation']
 */

import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { createClient } from '@supabase/supabase-js';
import type { GcpTransformer } from '@allmaps/transform';
import { PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY } from '$env/static/public';
import { allmapsAnnotationUrl, getTransformer } from '$lib/server/transformer';
import { assertUuid, dbError } from '$lib/server/http';

/** `1878-1968` → inclusive bounds. Null when absent or unparseable. */
function parseYearRange(raw: string | null): { from: number; to: number } | null {
  if (!raw) return null;
  const [from, to] = raw.split('-').map((s) => parseInt(s, 10));
  if (!Number.isFinite(from) || !Number.isFinite(to) || from > to) return null;
  return { from, to };
}

/** `minLng,minLat,maxLng,maxLat` → tuple. Null when absent or unparseable. */
function parseBbox(raw: string | null): [number, number, number, number] | null {
  if (!raw) return null;
  const p = raw.split(',').map(Number);
  if (p.length !== 4 || p.some((n) => !Number.isFinite(n))) return null;
  const [minLng, minLat, maxLng, maxLat] = p;
  if (minLng > maxLng || minLat > maxLat) return null;
  if (Math.abs(minLat) > 90 || Math.abs(maxLat) > 90) return null;
  return [minLng, minLat, maxLng, maxLat];
}

/**
 * Envelope overlap, not true intersection.
 *
 * ponytail: a polygon whose bounding box clips the study area but whose ring
 * does not is included. For an AOI query that is the generous, safe direction —
 * the notebook clips precisely anyway. Swap in a real predicate only if an
 * export ever has to be exact without post-processing.
 */
function ringIntersectsBbox(
  ring: [number, number][],
  [minLng, minLat, maxLng, maxLat]: [number, number, number, number]
): boolean {
  let loMinLng = Infinity,
    loMinLat = Infinity,
    loMaxLng = -Infinity,
    loMaxLat = -Infinity;
  for (const [lng, lat] of ring) {
    if (lng < loMinLng) loMinLng = lng;
    if (lng > loMaxLng) loMaxLng = lng;
    if (lat < loMinLat) loMinLat = lat;
    if (lat > loMaxLat) loMaxLat = lat;
  }
  return loMinLng <= maxLng && loMaxLng >= minLng && loMinLat <= maxLat && loMaxLat >= minLat;
}

interface AnnotationData {
  transformer: GcpTransformer;
  /** IIIF image service base URL. Needed for COCO crops; null is fine for GeoJSON. */
  iiifBaseUrl: string | null;
}

type AnnotationCache = Map<string, AnnotationData>;

/**
 * Resolve a map's transformer, mirror first.
 *
 * Two bugs lived here, and together they meant this endpoint had never warped
 * a single footprint — every export was pixel coordinates with
 * `geo_converted: false`, which reads downstream as "nobody has traced this
 * area yet" rather than "the warp is broken":
 *
 * 1. It called `getTransformer(allmapsId)` and dropped `annotation_url`, so it
 *    only ever tried the public Allmaps endpoint. Every georeferenced map here
 *    is self-hosted, and the mirror is the copy that resolves.
 * 2. It bailed on a missing `iiifBaseUrl`. That URL builds COCO crop requests;
 *    GeoJSON warping does not need it, so requiring it threw away a working
 *    transformer. COCO checks for it separately, where it actually matters.
 *
 * Cache is per-request: module scope is shared across concurrent requests in a
 * CF isolate. Keyed on the URL actually used, so a mirror and a public
 * annotation cannot collide.
 */
async function getAnnotationData(
  allmapsId: string | null,
  annotationUrl: string | null,
  annotationCache: AnnotationCache
): Promise<AnnotationData | null> {
  const key = annotationUrl || (allmapsId ? allmapsAnnotationUrl(allmapsId) : null);
  if (!key) return null;
  const cached = annotationCache.get(key);
  if (cached) return cached;

  const resolved = await getTransformer(allmapsId, annotationUrl);
  if (!resolved) return null;

  const data: AnnotationData = {
    transformer: resolved.transformer,
    iiifBaseUrl: resolved.iiifBaseUrl,
  };
  annotationCache.set(key, data);
  return data;
}

const CATEGORY_IDS: Record<string, number> = {
  building: 1,
  land_plot: 2,
  road: 3,
  waterway: 4,
  green_space: 5,
  water_body: 6,
  other: 7,
};

export const GET: RequestHandler = async ({ url }) => {
  const annotationCache: AnnotationCache = new Map();
  const mapIds = (url.searchParams.get('map_id') ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const status = url.searchParams.get('status') || 'approved';
  const format = url.searchParams.get('format') || 'geojson';
  const pad = parseInt(url.searchParams.get('pad') ?? '128', 10);
  const cropSize = parseInt(url.searchParams.get('size') ?? '1024', 10);
  const rowLimit = Math.min(
    Math.max(parseInt(url.searchParams.get('limit') ?? '5000', 10) || 5000, 1),
    20000
  );
  const years = parseYearRange(url.searchParams.get('year'));
  const bbox = parseBbox(url.searchParams.get('bbox'));

  if (format === 'coco' && mapIds.length !== 1) {
    throw error(400, 'coco format needs exactly one map_id');
  }
  for (const id of mapIds) assertUuid(id, 'map_id');

  // Deliberately the anon key, not $lib/server/supabaseAdmin: this endpoint is
  // public and unauthenticated, so it must stay behind RLS.
  const supabase = createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY);

  let fpQuery = supabase
    .from('footprints')
    // `annotation_url` is the self-hosted mirror, and for this catalogue it is
    // the only annotation that resolves — see `getAnnotationData`.
    .select('*, maps(allmaps_id, annotation_url, name, year)')
    .eq('review_status', status);

  if (mapIds.length === 1) fpQuery = fpQuery.eq('map_id', mapIds[0]);
  else if (mapIds.length > 1) fpQuery = fpQuery.in('map_id', mapIds);
  fpQuery = fpQuery.limit(rowLimit);

  const { data: allRows, error: err } = await fpQuery;
  if (err) dbError(err, 'Could not load footprints');

  // The map's year is the year the feature was *observed*, which is the only
  // temporal claim a single sheet supports. Filtering here rather than in the
  // query keeps the join shape simple and the row count is small.
  const rows = (allRows ?? []).filter((r) => {
    if (!years) return true;
    const y = (r as { maps?: { year?: number | null } }).maps?.year;
    return y != null && y >= years.from && y <= years.to;
  });

  // ── GeoJSON ──────────────────────────────────────────────────────────────

  if (format === 'geojson') {
    const features: GeoJSON.Feature[] = [];

    for (const row of rows as any[]) {
      const resolvedAllmapsId = (row.maps as any)?.allmaps_id ?? null;
      const resolvedAnnotationUrl = (row.maps as any)?.annotation_url ?? null;
      if (!resolvedAllmapsId && !resolvedAnnotationUrl) continue;

      const annData = await getAnnotationData(
        resolvedAllmapsId,
        resolvedAnnotationUrl,
        annotationCache
      );
      const pixelRing: [number, number][] = row.pixel_polygon;
      let coordinates: [number, number][];

      if (annData) {
        coordinates = pixelRing.map(([px, py]) => {
          const [lng, lat] = annData.transformer.transformToGeo([px, py]);
          return [lng, lat] as [number, number];
        });
        if (coordinates.length > 0) coordinates.push(coordinates[0]);
      } else {
        coordinates = pixelRing.map(([x, y]) => [x, y] as [number, number]);
      }

      // bbox selects on the ground, so an unwarped ring cannot satisfy it.
      if (bbox) {
        if (!annData) continue;
        if (!ringIntersectsBbox(coordinates, bbox)) continue;
      }

      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [coordinates] },
        properties: {
          id: row.id,
          map_id: row.map_id,
          map_name: (row.maps as any)?.name ?? null,
          year: (row.maps as any)?.year ?? null,
          allmaps_id: resolvedAllmapsId,
          name: row.name,
          category: row.category,
          feature_type: row.feature_type,
          source: row.source,
          valid_from: row.valid_from,
          confidence: row.confidence,
          status: row.review_status,
          pixel_polygon: pixelRing,
          // The source map's GCP residual in metres, when the row has been
          // warped. The analysis notebook reports it beside every figure.
          geom_rmse: row.geom_rmse ?? null,
          geo_converted: !!annData,
          created_at: row.created_at,
        },
      });
    }

    return new Response(JSON.stringify({ type: 'FeatureCollection', features }, null, 2), {
      headers: {
        'Content-Type': 'application/geo+json',
        'Content-Disposition': 'attachment; filename="vma-footprints.geojson"',
        // Reviewed polygons change when a reviewer acts, not by the minute, and
        // /explore's fabric layer refetches this on every toggle.
        'Cache-Control': 'public, max-age=300',
      },
    });
  }

  // ── COCO ─────────────────────────────────────────────────────────────────

  const cocoImages: any[] = [];
  const cocoAnnotations: any[] = [];
  let annId = 1;

  for (const row of rows as any[]) {
    const resolvedAllmapsId = (row.maps as any)?.allmaps_id ?? null;
    const resolvedAnnotationUrl = (row.maps as any)?.annotation_url ?? null;
    if (!resolvedAllmapsId && !resolvedAnnotationUrl) continue;

    const annData = await getAnnotationData(
      resolvedAllmapsId,
      resolvedAnnotationUrl,
      annotationCache
    );
    // COCO is where the IIIF base actually matters — every row carries a crop
    // URL built from it. GeoJSON does not need it and no longer demands it.
    if (!annData?.iiifBaseUrl) continue;

    const pixelRing: [number, number][] = row.pixel_polygon;
    if (!pixelRing?.length) continue;

    // Bounding box in IIIF pixel space
    const xs = pixelRing.map(([x]) => x);
    const ys = pixelRing.map(([, y]) => y);
    const xMin = Math.min(...xs),
      yMin = Math.min(...ys);
    const xMax = Math.max(...xs),
      yMax = Math.max(...ys);

    // Crop region with padding (clamped to non-negative)
    const cropX = Math.max(0, Math.round(xMin - pad));
    const cropY = Math.max(0, Math.round(yMin - pad));
    const cropW = Math.round(xMax - xMin + 2 * pad);
    const cropH = Math.round(yMax - yMin + 2 * pad);

    // IIIF Image API v2: {base}/{x,y,w,h}/{size},/0/default.jpg
    const iiifUrl = `${annData.iiifBaseUrl}/${cropX},${cropY},${cropW},${cropH}/${cropSize},/0/default.jpg`;

    const imageId = annId; // 1:1 image per annotation for simplicity

    cocoImages.push({
      id: imageId,
      footprint_id: row.id,
      map_id: row.map_id,
      allmaps_id: resolvedAllmapsId,
      iiif_url: iiifUrl,
      iiif_base: annData.iiifBaseUrl,
      // Actual rendered dimensions (IIIF scales width to cropSize, height proportional)
      width: cropSize,
      height: Math.round((cropH / cropW) * cropSize),
      // Crop origin in original IIIF pixel space (needed to map back to geo)
      crop_x: cropX,
      crop_y: cropY,
      crop_w: cropW,
      crop_h: cropH,
      feature_type: row.feature_type,
      name: row.name,
      category: row.category,
      source: row.source,
      confidence: row.confidence,
      valid_from: row.valid_from,
    });

    // Scale factor: original crop pixels → rendered image pixels
    const scale = cropSize / cropW;

    // Segmentation polygon relative to crop, scaled to rendered size
    const relSeg = pixelRing.flatMap(([x, y]) => [
      Math.round((x - cropX) * scale),
      Math.round((y - cropY) * scale),
    ]);

    // Bbox relative to crop, scaled
    const relBbox = [
      Math.round((xMin - cropX) * scale),
      Math.round((yMin - cropY) * scale),
      Math.round((xMax - xMin) * scale),
      Math.round((yMax - yMin) * scale),
    ];

    const catId = CATEGORY_IDS[row.feature_type ?? 'building'] ?? 1;

    cocoAnnotations.push({
      id: annId,
      image_id: imageId,
      category_id: catId,
      segmentation: [relSeg],
      bbox: relBbox,
      area: relBbox[2] * relBbox[3],
      iscrowd: 0,
    });

    annId++;
  }

  return json({
    info: {
      description: 'Vietnam Map Archive — Building Footprints (segmentation training)',
      version: '1.0',
      year: new Date().getFullYear(),
      contributor: 'VMA Community',
      url: 'https://vietnammaps.org',
      export_params: { status, pad, crop_size: cropSize, map_id: mapIds[0] },
    },
    categories: [
      { id: 1, name: 'building', supercategory: 'structure' },
      { id: 2, name: 'land_plot', supercategory: 'structure' },
      { id: 3, name: 'road', supercategory: 'infrastructure' },
      { id: 4, name: 'waterway', supercategory: 'infrastructure' },
      { id: 5, name: 'green_space', supercategory: 'open_land' },
      { id: 6, name: 'water_body', supercategory: 'open_land' },
      { id: 7, name: 'other', supercategory: 'other' },
    ],
    images: cocoImages,
    annotations: cocoAnnotations,
  });
};
