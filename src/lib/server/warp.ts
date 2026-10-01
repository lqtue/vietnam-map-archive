/**
 * warp.ts — pixel → geography, for the place-time index.
 *
 * Design: `docs/platform-design.md` §0. Pixel coordinates are the master; the
 * `geom` columns are derived. This module is what the writers use to fill them,
 * and what the `warp` job uses to refill them after a re-georeference.
 *
 * Three things travel with every warp:
 *   geom      — the warped geography, as EWKT (PostGIS parses it on insert)
 *   geom_src  — a short hash of the GCP set used, so a stale row is queryable
 *   geom_rmse — that map's own GCP residual in metres
 */

import type { GcpTransformer } from '@allmaps/transform';
import { getTransformer } from './transformer';
import { gcpRmseMetres, gcpSrcHash } from '$lib/core/georef/version';

export interface MapWarp {
  transformer: GcpTransformer;
  /** Short hash of the GCP set — changes exactly when the georeference does. */
  src: string;
  /** RMS of the GCP residuals, in metres. Null when it cannot be computed. */
  rmse: number | null;
}

/** Resolve a map's transformer plus the two provenance fields. Null if it has no usable annotation. */
export async function resolveMapWarp(
  allmapsId: string | null | undefined,
  annotationUrl?: string | null
): Promise<MapWarp | null> {
  const resolved = await getTransformer(allmapsId, annotationUrl);
  if (!resolved) return null;
  const { transformer } = resolved;
  return { transformer, src: await gcpSrcHash(transformer), rmse: gcpRmseMetres(transformer) };
}

function coord(lng: number, lat: number): string {
  return `${lng.toFixed(8)} ${lat.toFixed(8)}`;
}

/**
 * EWKT point for a pixel coordinate, or null when the transform refuses it.
 *
 * ponytail: EWKT text rather than a geometry object, because PostgREST hands a
 * string straight to the geography input function and there is nothing to
 * install. If a writer ever needs the numbers back, use `transformToGeo`
 * directly instead of parsing this.
 */
export function pointEwkt(warp: MapWarp, pixel: [number, number]): string | null {
  try {
    const [lng, lat] = warp.transformer.transformToGeo(pixel);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
    return `SRID=4326;POINT(${coord(lng, lat)})`;
  } catch {
    return null;
  }
}

/**
 * EWKT polygon for a pixel ring. Closes the ring, and refuses anything that
 * cannot make one (fewer than three distinct points, or an unwarpable vertex) —
 * a line trace has no polygon, and inventing one would put a fake area in the
 * index.
 */
export function polygonEwkt(warp: MapWarp, ring: [number, number][]): string | null {
  if (!Array.isArray(ring) || ring.length < 3) return null;
  const out: string[] = [];
  for (const p of ring) {
    if (!Array.isArray(p) || p.length < 2) return null;
    try {
      const [lng, lat] = warp.transformer.transformToGeo([p[0], p[1]]);
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
      out.push(coord(lng, lat));
    } catch {
      return null;
    }
  }
  if (out[0] !== out[out.length - 1]) out.push(out[0]);
  if (new Set(out).size < 3) return null;
  return `SRID=4326;POLYGON((${out.join(', ')}))`;
}

/** The centre of an extraction's full-image bbox, which is what gets indexed. */
export function bboxCentre(row: {
  global_x?: number | null;
  global_y?: number | null;
  global_w?: number | null;
  global_h?: number | null;
}): [number, number] | null {
  if (row.global_x == null || row.global_y == null) return null;
  return [row.global_x + (row.global_w ?? 0) / 2, row.global_y + (row.global_h ?? 0) / 2];
}
