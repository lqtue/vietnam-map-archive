import type { MapEditPayload } from '$lib/data/admin/mapEditPayload';
import type { Database } from '$lib/data/supabase/types';

export type MapRow = Database['public']['Tables']['maps']['Row'];

/**
 * Every admin endpoint answers a failure the same way — a JSON body with a
 * `message`, or nothing parseable at all. This turns that into a thrown Error
 * so callers only handle the happy path.
 *
 * `T = void` for endpoints whose body we ignore.
 */
async function apiFetch<T>(
  url: string,
  init?: RequestInit,
  fallbackMsg = 'Request failed'
): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.message || fallbackMsg);
  }
  return (await res.json().catch(() => undefined)) as T;
}

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export async function updateMap(id: string, data: Partial<MapEditPayload>): Promise<MapRow> {
  return apiFetch<MapRow>(`/api/admin/maps/${id}`, jsonInit('PATCH', data), 'Failed to update map');
}

export async function deleteMap(id: string): Promise<void> {
  await apiFetch<void>(`/api/admin/maps/${id}`, { method: 'DELETE' }, 'Failed to delete map');
}

export async function uploadMapImage(
  id: string,
  file: File
): Promise<{
  success: boolean;
  ia_identifier: string;
  ia_filename: string;
  iiif_url: string;
}> {
  const formData = new FormData();
  formData.append('image', file);

  return apiFetch(
    `/api/admin/maps/${id}/image`,
    { method: 'POST', body: formData },
    'Failed to upload image'
  );
}

// ---- IIIF Sources ----

export interface IIIFSourceRow {
  id: string;
  map_id: string;
  label?: string;
  source_type?: string;
  iiif_manifest?: string;
  iiif_image: string;
  is_primary: boolean;
  sort_order: number;
  created_at: string;
}

export async function fetchIIIFSources(mapId: string): Promise<IIIFSourceRow[]> {
  return apiFetch<IIIFSourceRow[]>(
    `/api/admin/maps/${mapId}/iiif-sources`,
    undefined,
    'Failed to fetch IIIF sources'
  );
}

export async function addIIIFSource(
  mapId: string,
  data: {
    label?: string;
    source_type?: string;
    iiif_manifest?: string;
    iiif_image: string;
    is_primary?: boolean;
  }
): Promise<void> {
  await apiFetch<void>(
    `/api/admin/maps/${mapId}/iiif-sources`,
    jsonInit('POST', data),
    'Failed to add IIIF source'
  );
}

export async function setPrimaryIIIFSource(mapId: string, sourceId: string): Promise<void> {
  await apiFetch<void>(
    `/api/admin/maps/${mapId}/iiif-sources/${sourceId}`,
    jsonInit('PATCH', { is_primary: true }),
    'Failed to set primary source'
  );
}

export async function deleteIIIFSource(mapId: string, sourceId: string): Promise<void> {
  await apiFetch<void>(
    `/api/admin/maps/${mapId}/iiif-sources/${sourceId}`,
    { method: 'DELETE' },
    'Failed to delete IIIF source'
  );
}

export interface MirrorR2Result {
  iiif_image: string;
  annotation_url: string;
  /** The timestamped copy kept as history — Storage has no versioning. */
  history_url: string;
  thumbnail: string;
  old_source_url: string | null;
  download_url: string | null;
  tile_command: string;
}

export async function mirrorToR2(mapId: string): Promise<MirrorR2Result> {
  return apiFetch<MirrorR2Result>(
    `/api/admin/maps/${mapId}/mirror-r2`,
    // Empty JSON body: hooks.server.ts refuses a write whose body is not JSON, and on
    // Cloudflare a body-less POST still arrives with a (zero-length) body stream.
    jsonInit('POST', {}),
    'Failed to mirror to R2'
  );
}

/**
 * Re-read the annotation from allmaps.org and store it again. Use after editing
 * the georeference upstream; `mirrorToR2` re-stores whatever we already have.
 */
export async function syncAllmaps(mapId: string): Promise<MirrorR2Result> {
  return apiFetch<MirrorR2Result>(
    `/api/admin/maps/${mapId}/sync-allmaps`,
    // Empty JSON body: hooks.server.ts refuses a write whose body is not JSON, and on
    // Cloudflare a body-less POST still arrives with a (zero-length) body stream.
    jsonInit('POST', {}),
    'Failed to fetch the latest annotation from Allmaps'
  );
}

export async function fetchIIIFMetadata(manifestUrl: string): Promise<{
  title?: string;
  creator?: string;
  date?: string;
  rights?: string;
  imageServiceUrl?: string;
  shelfmark?: string;
  language?: string;
  physicalDescription?: string;
  sourceUrl?: string;
  attribution?: string;
}> {
  return apiFetch(
    '/api/admin/maps/fetch-iiif-metadata',
    jsonInit('POST', { manifestUrl }),
    'Failed to fetch IIIF metadata'
  );
}

/**
 * Derives the Allmaps image ID for a IIIF image service URL and probes
 * annotations.allmaps.org to see whether a georeference already exists.
 */
export async function lookupAllmapsId(
  iiifImage: string
): Promise<{ allmapsId: string; hasAnnotation: boolean }> {
  return apiFetch(
    '/api/admin/maps/lookup-allmaps-id',
    jsonInit('POST', { iiifImage }),
    'Failed to look up Allmaps ID'
  );
}
