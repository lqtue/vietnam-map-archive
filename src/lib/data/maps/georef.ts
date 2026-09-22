// ---- /contribute/georef data + Allmaps Editor links ----

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { PUBLIC_SUPABASE_URL } from '$env/static/public';
import { allmapsEditorSourceUrl, annotationUrlForSource } from '$lib/core/iiif/annotationUrl';

export interface GeorefMapItem {
  id: string;
  name: string;
  allmaps_id: string | null;
  iiif_image: string | null;
  iiif_manifest: string | null;
  georef_done: boolean;
  year: number | null;
}

/** A georeferenced map together with the editor link that reopens its control points. */
export interface GeorefFixItem {
  id: string;
  name: string;
  year: number | null;
  status: string;
  /** '' when the map carries nothing the Allmaps Editor can open (R2-only, no manifest). */
  editorUrl: string;
}

const EDITOR = 'https://editor.allmaps.org/#/collection?url=';

/** The annotation URL a map's GCPs actually live at — override first, else the bare id. */
export function effectiveAnnotationUrl(map: {
  annotation_url?: string | null;
  allmaps_id?: string | null;
}): string | null {
  const source = map.annotation_url || map.allmaps_id;
  return source ? annotationUrlForSource(source) : null;
}

/**
 * What the live annotation is actually fit to — `target.source.id` — so the
 * editor link can be verified against ground truth instead of guessed from
 * `source_type`. Null on any failure; callers fall back to the sourceless
 * heuristic in `allmapsEditorSourceUrl`.
 */
export async function fetchAnnotationSourceId(annotationUrl: string): Promise<string | null> {
  try {
    const res = await fetch(annotationUrl);
    if (!res.ok) return null;
    const json = await res.json();
    return json.items?.[0]?.target?.source?.id ?? null;
  } catch {
    return null;
  }
}

/**
 * Every georeferenced map, published or not, with the link that reopens its
 * existing control points — the same link the share page builds, so nobody has
 * to find a map id to correct a georeference. Sources come along because an
 * R2 mirror must not be handed to the editor *unless* the annotation itself
 * says otherwise — see `allmapsEditorSourceUrl`; the whole District 4 series
 * is the exception, so this list verifies against the live annotation rather
 * than trusting `source_type` alone.
 */
export async function fetchGeorefFixList(
  supabase: SupabaseClient<Database>
): Promise<GeorefFixItem[]> {
  const { data, error } = await supabase
    .from('maps')
    .select(
      'id, name, year, status, iiif_manifest, annotation_url, allmaps_id, map_iiif_sources(iiif_image, source_type)'
    )
    .eq('georef_done', true)
    .order('name');

  if (error) {
    console.error('fetchGeorefFixList:', error);
    return [];
  }
  return Promise.all(
    (data ?? []).map(async (m) => {
      const annotationUrl = effectiveAnnotationUrl(m);
      const verifiedSourceId = annotationUrl ? await fetchAnnotationSourceId(annotationUrl) : null;
      const source = allmapsEditorSourceUrl(m, m.map_iiif_sources ?? [], verifiedSourceId);
      return {
        id: m.id,
        name: m.name,
        year: m.year,
        status: m.status ?? 'draft',
        editorUrl: source ? EDITOR + encodeURIComponent(source) : '',
      };
    })
  );
}

/** The georeferencing queue: maps not yet published, highest priority first. */
export async function fetchGeorefQueue(
  supabase: SupabaseClient<Database>
): Promise<GeorefMapItem[]> {
  const { data, error } = await supabase
    .from('maps')
    .select('id, name, allmaps_id, iiif_image, iiif_manifest, georef_done, year')
    .eq('status', 'draft')
    .order('priority', { ascending: false })
    .order('name');

  if (error) {
    console.error('fetchGeorefQueue:', error);
    return [];
  }
  return (data ?? []) as GeorefMapItem[];
}

function withInfoJson(url: string): string {
  return /\.json($|\?)/.test(url) ? url : `${url.replace(/\/$/, '')}/info.json`;
}

/** Where a mirrored annotation lives once an admin has run mirror-r2. */
export function annotationStorageUrl(allmapsId: string): string {
  if (allmapsId.startsWith('http')) return allmapsId;
  return `${PUBLIC_SUPABASE_URL}/storage/v1/object/public/annotations/${allmapsId}.json`;
}

/**
 * Deep-link into the Allmaps Editor. Prefers the manifest (multi-image
 * collections), then the image service, then an existing annotation.
 */
export function allmapsEditorUrl(map: GeorefMapItem): string {
  const base = 'https://editor.allmaps.org/#/collection?url=';
  if (map.iiif_manifest) return base + encodeURIComponent(map.iiif_manifest);
  if (map.iiif_image) return base + encodeURIComponent(withInfoJson(map.iiif_image));
  if (map.allmaps_id) return base + encodeURIComponent(annotationStorageUrl(map.allmaps_id));
  return 'https://editor.allmaps.org/';
}
