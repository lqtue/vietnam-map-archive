/**
 * Recording a georeference version (migration 103).
 *
 * Every writer that stores `annotations/<map>/<stamp>.json` calls this with the
 * same stamp, right after that write and before the live file moves, so no
 * version goes live without a row. A failure throws: a version the table does
 * not know about is exactly the drift the table exists to show.
 */

import { error } from '@sveltejs/kit';
import { adminClient } from './supabaseAdmin';
import { describeAnnotation } from '$lib/core/georef/version';

export type GeorefOrigin = 'allmaps' | 'mirror' | 'neatline' | 'script' | 'pipeline' | 'unrecorded';

export async function recordGeorefVersion(
  mapId: string,
  stamp: string,
  annotation: unknown,
  origin: GeorefOrigin,
  { allmapsId = null, userId = null }: { allmapsId?: string | null; userId?: string | null } = {}
): Promise<void> {
  let facts;
  try {
    facts = await describeAnnotation(annotation);
  } catch (e) {
    throw error(422, `Annotation is not a usable georeference: ${(e as Error).message}`);
  }
  const { error: dbErr } = await adminClient()
    .from('georef_versions')
    .upsert(
      { map_id: mapId, stamp, origin, allmaps_id: allmapsId, user_id: userId, ...facts },
      { onConflict: 'map_id,stamp', ignoreDuplicates: true }
    );
  if (dbErr) {
    console.error('[georef_versions] insert failed:', dbErr.message);
    throw error(500, 'Could not record the georeference version');
  }
}
