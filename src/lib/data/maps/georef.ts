// ---- /contribute/georef data + Allmaps Editor links ----

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { PUBLIC_SUPABASE_URL } from '$env/static/public';
import { allmapsEditorSourceUrl, verifiedEditorSourceId } from '$lib/core/iiif/annotationUrl';

export interface GeorefMapItem {
  id: string;
  name: string;
  allmaps_id: string | null;
  iiif_image: string | null;
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

/**
 * Every georeferenced map, published or not, with the link that reopens its
 * existing control points — the same link the share page builds, so nobody has
 * to find a map id to correct a georeference. Sources come along because an
 * R2 mirror must not be handed to the editor *unless* it's the one
 * `allmaps_id` is actually keyed to — see `verifiedEditorSourceId` and
 * `allmapsEditorSourceUrl`.
 */
export async function fetchGeorefFixList(
  supabase: SupabaseClient<Database>
): Promise<GeorefFixItem[]> {
  const { data, error } = await supabase
    .from('maps')
    .select(
      'id, name, year, status, annotation_url, allmaps_id, map_images(iiif_image, iiif_manifest, source_type)'
    )
    .eq('is_georeferenced', true)
    .order('name');

  if (error) {
    console.error('fetchGeorefFixList:', error);
    return [];
  }
  return Promise.all(
    (data ?? []).map(async (m) => {
      const verifiedSourceId = await verifiedEditorSourceId(m, m.map_images ?? []);
      const source = allmapsEditorSourceUrl(m, m.map_images ?? [], verifiedSourceId);
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
    // `georef_done` stays the field name below (this module's own vocabulary);
    // only the column read from renamed (mig 095).
    .select('id, name, allmaps_id, iiif_image, georef_done:is_georeferenced, year')
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
 * Deep-link into the Allmaps Editor. Prefers the image service, then an
 * existing annotation. (`maps.iiif_manifest` was dropped, mig 095 — dead,
 * duplicated by the per-source manifest on `map_images` — and this queue
 * never carried one anyway: it is unpublished, self-hosted scans.)
 */
export function allmapsEditorUrl(map: GeorefMapItem): string {
  const base = 'https://editor.allmaps.org/#/collection?url=';
  if (map.iiif_image) return base + encodeURIComponent(withInfoJson(map.iiif_image));
  if (map.allmaps_id) return base + encodeURIComponent(annotationStorageUrl(map.allmaps_id));
  return 'https://editor.allmaps.org/';
}
