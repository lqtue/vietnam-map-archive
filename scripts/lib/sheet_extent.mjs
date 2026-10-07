/**
 * sheet_extent.mjs — the ground a sheet covers, computed the way the renderer does.
 *
 * Lifted out of `scripts/oneoff/backfill_map_bbox.mjs`, whose header has the
 * measurement behind it: the GCP hull under-states a sheet (by half its area on
 * `Đô thành Sài Gòn`), so `maps.bbox` is the resource mask warped through the
 * sheet's own transform. `scripts/georef_write.mjs` uses the same function, so
 * a pipeline-written bbox and a backfilled one agree.
 */
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';

/** Extent of a list of [lng, lat] pairs, or null when there is nothing to bound. */
export function extentOf(points) {
  if (!points.length) return null;
  const lng = points.map((p) => p[0]);
  const lat = points.map((p) => p[1]);
  return [Math.min(...lng), Math.min(...lat), Math.max(...lng), Math.max(...lat)];
}

/**
 * Subdivide each edge of a resource ring into `perEdge` segments.
 *
 * A mask is four corners, and under a Helmert or first-order polynomial a
 * straight resource edge stays straight, so the corners alone bound it. Under a
 * higher-order polynomial or a thin-plate spline the edge bows, and a bow that
 * leaves the corner box is invisible to a four-point extent. Densifying costs
 * one transform call per point and removes the question.
 */
function densify(ring, perEdge = 24) {
  const out = [];
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    for (let s = 0; s < perEdge; s++) {
      const t = s / perEdge;
      out.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]);
    }
  }
  return out;
}

/**
 * The ground a sheet covers: its resource mask warped through its own
 * transform. Falls back to the GCP hull when the annotation carries no usable
 * mask or the transform refuses it — an under-estimate, but better than null.
 * Returns `{ bbox, how, n }`, or null when there is nothing to bound.
 */
export function sheetExtent(annotation) {
  let maps = [];
  try {
    maps = parseAnnotation(annotation);
  } catch {
    return null;
  }
  if (!maps.length) return null;
  const map = maps[0];
  const gcps = map.gcps ?? [];
  if (gcps.length < 2) return null;

  const hull = extentOf(gcps.map((g) => g.geo));

  const mask = map.resourceMask;
  if (Array.isArray(mask) && mask.length >= 3) {
    try {
      const transformer = GcpTransformer.fromGeoreferencedMap(map);
      const warped = densify(mask).map((p) => transformer.transformToGeo(p));
      const usable = warped.filter(
        (p) => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])
      );
      const bbox = extentOf(usable);
      if (bbox) return { bbox, how: 'mask', n: gcps.length };
    } catch {
      // fall through to the hull
    }
  }
  return hull ? { bbox: hull, how: 'hull', n: gcps.length } : null;
}
