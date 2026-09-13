// Utility for fetching and calculating geographic bounds from Allmaps annotations
import { annotationUrlForSource } from '$lib/core/iiif/annotationUrl';
import { debounce } from '$lib/core/utils/debounce';
import { readJson, writeJson } from '$lib/core/utils/persistence/storage';

export type Bbox = [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]

// In-memory + localStorage cache. Persists across reloads AND across sessions
// so repeat /explore visits do zero network for the same catalogue. Allmaps
// annotations are immutable for a given image id, so cache invalidation is
// not a concern; we only ever cache success (bbox) or null (no GCPs / 404).
const boundsCache: Map<string, Bbox | null> = new Map();
const STORAGE_KEY = 'vma-bounds-cache-v2';

// Debounced — fetchMultipleBounds calls this many times in quick succession.
const persistCache = debounce(() => {
  writeJson(STORAGE_KEY, Object.fromEntries(boundsCache));
}, 250);

function saveToSessionCache(id: string, value: Bbox | null): void {
  boundsCache.set(id, value);
  persistCache();
}

for (const [k, v] of Object.entries(readJson<Record<string, Bbox | null>>(STORAGE_KEY, {}))) {
  boundsCache.set(k, v);
}

/** A `[minLon, minLat, maxLon, maxLat]` tuple with real, ordered numbers. */
export function looksValidBbox(bbox: unknown): bbox is Bbox {
  return (
    Array.isArray(bbox) &&
    bbox.length === 4 &&
    bbox.every((n) => typeof n === 'number' && Number.isFinite(n)) &&
    bbox[0] < bbox[2] &&
    bbox[1] < bbox[3]
  );
}

/**
 * The annotation source for a catalogue row: the R2/Supabase mirror URL
 * (`annotation_url`) wins over the bare Allmaps image id. Also the cache key
 * every bounds lookup uses — resolving the two inconsistently gave mirrored
 * maps two cache entries.
 */
export function annotationSourceFor(map: {
  allmaps_id?: string | null;
  annotation_url?: string | null;
}): string | null {
  return map.annotation_url ?? map.allmaps_id ?? null;
}

/**
 * The full bounds ladder: `bounds` (runtime enrichment) → `bbox` (DB column)
 * → the map's annotation (`annotation_url`, else `allmaps_id`).
 *
 * The single resolver for "where is this map?". Callers that skipped a rung
 * silently failed to zoom for whole classes of map (R2 mirrors had no
 * `allmaps_id`; most of the catalogue has no `bbox` backfilled).
 */
export async function resolveBounds(map: {
  bounds?: unknown;
  bbox?: unknown;
  allmaps_id?: string | null;
  annotation_url?: string | null;
}): Promise<Bbox | null> {
  if (looksValidBbox(map.bounds)) return map.bounds;
  if (looksValidBbox(map.bbox)) return map.bbox;
  const source = annotationSourceFor(map);
  return source ? await fetchAnnotationBounds(source) : null;
}

interface GroundControlPoint {
  world: [number, number];
  // Other fields exist but we only need world coordinates
}

/**
 * Fetches an Allmaps annotation and calculates its geographic bounding box
 * @param mapId - The Allmaps annotation ID
 * @returns Bounds as [minLon, minLat, maxLon, maxLat] or null if unavailable
 */
export async function fetchAnnotationBounds(mapId: string): Promise<Bbox | null> {
  // Check cache first
  if (boundsCache.has(mapId)) {
    return boundsCache.get(mapId) ?? null;
  }

  try {
    const response = await fetch(annotationUrlForSource(mapId));
    if (!response.ok) {
      // 404 is expected for un-georeferenced maps — cache null silently.
      boundsCache.set(mapId, null);
      saveToSessionCache(mapId, null);
      return null;
    }

    const annotation = await response.json();

    // Extract ground control points
    const gcps = extractGCPs(annotation);
    if (!gcps || gcps.length === 0) {
      // Some maps may not have GCPs - this is expected, cache null silently
      boundsCache.set(mapId, null);
      return null;
    }

    // Calculate bounding box from GCPs
    const lons = gcps.map((p) => p.world[0]);
    const lats = gcps.map((p) => p.world[1]);

    const bounds: Bbox = [
      Math.min(...lons),
      Math.min(...lats),
      Math.max(...lons),
      Math.max(...lats),
    ];

    // Cache and return
    boundsCache.set(mapId, bounds);
    saveToSessionCache(mapId, bounds);
    return bounds;
  } catch (error) {
    console.error(`Error fetching bounds for ${mapId}:`, error);
    boundsCache.set(mapId, null);
    saveToSessionCache(mapId, null);
    return null;
  }
}

/**
 * Extracts ground control points from an Allmaps annotation
 * Allmaps annotation structure can vary, this handles common formats
 */
function extractGCPs(annotation: unknown): GroundControlPoint[] {
  if (!annotation || typeof annotation !== 'object') {
    return [];
  }

  let ann = annotation as Record<string, unknown>;

  // Allmaps API returns an AnnotationPage with items array
  // Unwrap to the first Annotation item
  if (ann.items && Array.isArray(ann.items) && ann.items.length > 0) {
    ann = ann.items[0] as Record<string, unknown>;
  }

  // Try to find resourceCoords (Georeference Annotation format)
  if (ann.body && typeof ann.body === 'object') {
    const body = ann.body as Record<string, unknown>;

    // Look for geometry in body
    if (body.features && Array.isArray(body.features)) {
      const gcps: GroundControlPoint[] = [];
      for (const feature of body.features) {
        if (
          feature &&
          typeof feature === 'object' &&
          'geometry' in feature &&
          feature.geometry &&
          typeof feature.geometry === 'object'
        ) {
          const geom = feature.geometry as Record<string, unknown>;
          if (geom.coordinates && Array.isArray(geom.coordinates)) {
            // Coordinates in [lon, lat] format
            const coords = geom.coordinates as number[];
            if (
              coords.length >= 2 &&
              typeof coords[0] === 'number' &&
              typeof coords[1] === 'number'
            ) {
              gcps.push({
                world: [coords[0], coords[1]],
              });
            }
          }
        }
      }
      if (gcps.length > 0) {
        return gcps;
      }
    }

    // Alternative: look for transformation or gcps array
    if (body.transformation && typeof body.transformation === 'object') {
      const transformation = body.transformation as Record<string, unknown>;
      if (transformation.gcps && Array.isArray(transformation.gcps)) {
        return transformation.gcps
          .filter((gcp): gcp is Record<string, unknown> => gcp !== null && typeof gcp === 'object')
          .filter((gcp) => {
            const world = gcp.world as unknown;
            return Array.isArray(world) && world.length >= 2;
          })
          .map((gcp) => {
            const world = gcp.world as number[];
            return {
              world: [world[0], world[1]],
            };
          });
      }
    }
  }

  // Fallback: try to find any coordinate-like structure
  // This is a last resort for unexpected formats
  if (ann.gcps && Array.isArray(ann.gcps)) {
    return ann.gcps
      .filter((gcp): gcp is Record<string, unknown> => gcp !== null && typeof gcp === 'object')
      .filter((gcp) => {
        const world = gcp.world as unknown;
        return Array.isArray(world) && world.length >= 2;
      })
      .map((gcp) => {
        const world = gcp.world as number[];
        return {
          world: [world[0], world[1]],
        };
      });
  }

  return [];
}

/**
 * Fetches bounds for multiple maps with concurrency control
 * @param mapIds - Array of map IDs to fetch
 * @param concurrency - Maximum concurrent requests
 */
export async function fetchMultipleBounds(
  mapIds: string[],
  concurrency: number = 12
): Promise<Map<string, Bbox | null>> {
  const results = new Map<string, Bbox | null>();

  // Drain via a sliding window of N workers — keeps `concurrency`
  // requests in flight at all times instead of waiting for the slowest
  // of each batch (the old code paused the whole batch on its tail
  // latency, costing ~3-5× wall time on slow maps).
  let cursor = 0;
  async function worker() {
    while (cursor < mapIds.length) {
      const i = cursor++;
      const id = mapIds[i];
      const bounds = await fetchAnnotationBounds(id);
      results.set(id, bounds);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, mapIds.length) }, worker));

  return results;
}

/**
 * The maps that still need their bounds fetched from an annotation.
 *
 * The ladder in `resolveBounds` is per map; this is the same ladder asked of a
 * whole catalogue at once, so a caller can probe the gaps and nothing else. It
 * lives here rather than beside its first caller because two of them are in
 * `map/` and `features/`, and a feature may not be imported from the shell.
 *
 * Three rungs, each of which was once missing and cost a page load:
 *   - a map with a `bbox` is already answered — today that is the entire
 *     corpus (103 of 103), so skipping this rung fetched 102 annotations on
 *     every cold /explore load to learn what the catalogue row already said;
 *   - a map with no annotation at all can only 404;
 *   - a draft is not probed unless the caller can see drafts.
 */
export function unresolvedBoundsSources(
  mapList: Array<{
    status?: string;
    georef_done?: boolean | null;
    bbox?: unknown;
    bounds?: unknown;
    allmaps_id?: string | null;
    annotation_url?: string | null;
  }>,
  includeDrafts = false
): string[] {
  return mapList
    .filter(
      (m) =>
        (includeDrafts || m.status === 'public' || m.status === 'featured') &&
        // A map with no annotation cannot yield a bbox, so asking for one is
        // 61 guaranteed 404s at annotations.allmaps.org on every page load.
        // `annotation_url` overrides the flag: having a mirror means it is
        // georeferenced whatever `georef_done` happens to say.
        !(m.georef_done === false && !m.annotation_url) &&
        !looksValidBbox(m.bbox) &&
        !looksValidBbox(m.bounds)
    )
    .map(annotationSourceFor)
    .filter((src): src is string => !!src);
}
