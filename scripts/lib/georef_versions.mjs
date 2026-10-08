/**
 * georef_versions.mjs — the scripts' half of migration 103.
 *
 * Imports the same `describeAnnotation` the Pages Functions use, by path (Node
 * strips the types), so a script-written version hashes exactly like a
 * route-written one. Call it right after writing `annotations/<map>/<stamp>.json`
 * and before moving the live file, as `$lib/server/georefVersions.ts` does.
 */
import { describeAnnotation } from '../../src/lib/core/georef/version.ts';

/**
 * @param {import('@supabase/supabase-js').SupabaseClient} db service-role client
 * @param {string} mapId
 * @param {string} stamp the history file's key
 * @param {unknown} annotation
 * @param {'allmaps'|'mirror'|'neatline'|'script'|'pipeline'|'unrecorded'} origin
 * @param {{ allmapsId?: string | null, method?: string | null, methodRef?: string | null,
 *          datum?: string | null, derivedFrom?: string | null }} [opts] provenance (mig 118)
 */
export async function recordGeorefVersion(db, mapId, stamp, annotation, origin, opts = {}) {
  const facts = await describeAnnotation(annotation);
  const { error } = await db.from('georef_versions').upsert(
    {
      map_id: mapId,
      stamp,
      origin,
      allmaps_id: opts.allmapsId ?? null,
      // Only when given: the other callers must keep working against a database that has
      // not had migration 118 pushed yet.
      ...(opts.method && {
        method: opts.method,
        method_ref: opts.methodRef ?? null,
        datum: opts.datum ?? null,
        derived_from: opts.derivedFrom ?? null,
      }),
      ...facts,
    },
    { onConflict: 'map_id,stamp', ignoreDuplicates: true }
  );
  if (error)
    throw new Error(`georef_versions insert failed for ${mapId}/${stamp}: ${error.message}`);
  return facts;
}
