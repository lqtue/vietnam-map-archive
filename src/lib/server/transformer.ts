/**
 * Pixel → geo transformers built from an Allmaps annotation.
 *
 * `/api/export/footprints` and `/api/maps/[id]/legend-points` both need the
 * same three steps: fetch the annotation, `parseAnnotation`, then
 * `GcpTransformer.fromGeoreferencedMap`.
 */

import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';
import { fetchAnnotationJson } from './safeAnnotation';

export interface AnnotationTransform {
  transformer: GcpTransformer;
  /** IIIF Image service base URL from `items[0].target.source.id`, when present. */
  iiifBaseUrl: string | null;
}

/**
 * Public Allmaps annotation URL for a `maps.allmaps_id`.
 *
 * `/images/`, not `/maps/`. `allmaps_id` holds Allmaps' **image** id (the
 * 16-char hex derived by `deriveAllmapsId`), and the `/maps/` endpoint keys on
 * a different id entirely — measured 2026-09-04 it returned 404 for all 101
 * rows in the catalogue, while `/images/` returned 200 for exactly the 40 that
 * are georeferenced. This fallback had therefore never resolved once.
 * `annotationUrlForSource` in $lib/core/iiif had it right all along.
 */
export function allmapsAnnotationUrl(allmapsId: string): string {
  return `https://annotations.allmaps.org/images/${allmapsId}`;
}

/**
 * Resolve a transformer for a map. Prefers an explicit `annotationUrl`
 * (the self-hosted mirror override) and falls back to the public Allmaps
 * annotation for `allmapsId`. Returns null if anything along the way fails.
 */
export async function getTransformer(
  allmapsId: string | null | undefined,
  annotationUrl?: string | null
): Promise<AnnotationTransform | null> {
  const url = annotationUrl || (allmapsId ? allmapsAnnotationUrl(allmapsId) : null);
  if (!url) return null;

  try {
    const annotation = (await fetchAnnotationJson(url)) as any;
    const maps = parseAnnotation(annotation);
    if (!maps.length) return null;

    return {
      transformer: GcpTransformer.fromGeoreferencedMap(maps[0]),
      iiifBaseUrl: (annotation.items?.[0]?.target?.source?.id as string | undefined) ?? null,
    };
  } catch {
    return null;
  }
}
