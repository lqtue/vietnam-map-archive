/**
 * Recording a georeference version (migration 103).
 *
 * Every writer that stores `annotations/<map>/<stamp>.json` calls this with the
 * same stamp, right after that write and before the live file moves, so no
 * version goes live without a row. A database failure throws: a version the
 * table does not know about is exactly the drift the table exists to show.
 *
 * An annotation with no control points is not a georeference, so it gets no row
 * and does not block the mirror (mig 062 lets a map publish before a volunteer
 * has placed anything). Returns false then. `map_georef_current` keeps pointing
 * at the last real version until the next one with points.
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
): Promise<boolean> {
  let facts;
  try {
    facts = await describeAnnotation(annotation);
  } catch (e) {
    console.warn(`[georef_versions] ${mapId}/${stamp} not recorded: ${(e as Error).message}`);
    return false;
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
  return true;
}
