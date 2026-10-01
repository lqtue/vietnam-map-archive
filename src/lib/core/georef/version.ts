/**
 * What one stored georeference is, read off its annotation JSON.
 *
 * One implementation for every writer: the Pages Functions import it through
 * `$lib`, and the Node scripts import this file by path (Node strips the types),
 * so `geom_src` cannot come out differently depending on who wrote the version.
 * That is the whole point of the `georef_versions` table (migration 103): its
 * `geom_src` is compared with the copy on every label and polygon, and a hash
 * computed two ways would mark everything stale, or nothing.
 *
 * Keep this file to package imports and erasable TypeScript, or the scripts
 * stop being able to load it.
 */

import { parseAnnotation } from '@allmaps/annotation';
import { GcpTransformer } from '@allmaps/transform';

/** Names the RMSE measure, per `evidence-chain-plan.md` invariant 8. */
export const RMSE_METHOD = 'gcp-roundtrip-rms';

const EARTH_RADIUS_M = 6_371_008.8;

/** Great-circle metres between two lng/lat pairs. */
function distanceMetres([lng1, lat1]: number[], [lng2, lat2]: number[]): number {
  const toRad = Math.PI / 180;
  const dLat = (lat2 - lat1) * toRad;
  const dLng = (lng2 - lng1) * toRad;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
}

/**
 * Warp error, measured the only way the library allows: push each GCP's own
 * resource coordinate through the transform and compare with where the GCP
 * says it belongs. `@allmaps/transform` keeps its residuals private, but it
 * exposes the GCPs, and a handful of round trips is cheap.
 *
 * A thin-plate spline interpolates its control points exactly, so this reads
 * ~0 for RBF-type transforms. It is honest about polynomial and Helmert fits,
 * which is where the large errors actually live.
 */
export function gcpRmseMetres(transformer: GcpTransformer): number | null {
  const gcps = transformer.gcps;
  if (!gcps?.length) return null;
  let sum = 0;
  let n = 0;
  for (const gcp of gcps) {
    try {
      const got = transformer.transformToGeo(gcp.resource as [number, number]);
      sum += distanceMetres(got, gcp.geo) ** 2;
      n++;
    } catch {
      /* a GCP the transform cannot round-trip tells us nothing; skip it */
    }
  }
  return n ? Math.sqrt(sum / n) : null;
}

/**
 * Identity of the georeference a warp was computed against. Rounded to ~1e-7°
 * (about a centimetre) so floating-point noise does not invent a new version.
 *
 * ponytail: hashes the GCPs only, so a change of transformation type with the
 * same points keeps the same hash and leaves derived rows looking fresh. Adding
 * the type would re-mark every warped row in the corpus stale at once; do it
 * together with `rewarp-on-sync`, which can absorb that.
 */
export async function gcpSrcHash(transformer: Pick<GcpTransformer, 'gcps'>): Promise<string> {
  const gcps = transformer.gcps ?? [];
  const canonical = gcps
    .map(
      (g) =>
        `${Math.round(g.resource[0])},${Math.round(g.resource[1])}:` +
        `${g.geo[0].toFixed(7)},${g.geo[1].toFixed(7)}`
    )
    .sort()
    .join('|');
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical));
  return Array.from(new Uint8Array(digest))
    .slice(0, 8)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** The columns of a `georef_versions` row that come from the annotation itself. */
export interface GeorefVersionFacts {
  geom_src: string;
  transformation: string;
  gcp_count: number;
  rmse_m: number | null;
  rmse_method: string;
  source_id: string | null;
  source_width: number | null;
  source_height: number | null;
}

/**
 * Read one annotation. Throws when it does not parse: an annotation the app
 * cannot turn into a transformer is not a georeference anyone can see, and
 * storing it as a version would only hide that.
 */
export async function describeAnnotation(annotation: unknown): Promise<GeorefVersionFacts> {
  const [map] = parseAnnotation(annotation);
  if (!map) throw new Error('annotation holds no georeferenced map');
  const transformer = GcpTransformer.fromGeoreferencedMap(map);
  const t = map.transformation;
  const order = (t?.options as { order?: number } | undefined)?.order;
  // `polynomial2`/`polynomial3` are Allmaps' own names for the higher orders.
  const transformation =
    t?.type === 'polynomial' && order && order > 1
      ? `polynomial${order}`
      : (t?.type ?? 'polynomial');
  return {
    geom_src: await gcpSrcHash(transformer),
    transformation,
    gcp_count: map.gcps.length,
    rmse_m: gcpRmseMetres(transformer),
    rmse_method: RMSE_METHOD,
    source_id: map.resource.id ?? null,
    source_width: map.resource.width ?? null,
    source_height: map.resource.height ?? null,
  };
}

/** `2026-10-01T06-10-18-123Z` (the history path key) → an ISO timestamp. */
export function stampToIso(stamp: string): string {
  const m = stamp.match(/^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})-(\d{3})Z$/);
  if (!m) throw new Error(`not a history stamp: ${stamp}`);
  return `${m[1]}T${m[2]}:${m[3]}:${m[4]}.${m[5]}Z`;
}

/** The inverse: an instant → the key every writer uses for `annotations/<map>/<stamp>.json`. */
export function isoToStamp(iso: string | Date): string {
  return new Date(iso).toISOString().replace(/[:.]/g, '-');
}
