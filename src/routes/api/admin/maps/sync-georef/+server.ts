import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { probeAllmapsAnnotation } from '$lib/server/allmaps';

/**
 * POST — probe the Allmaps annotation server for every map with allmaps_id
 * set and is_georeferenced=false, and flip is_georeferenced=true on hits. Idempotent;
 * safe to run on a cron or as a button click. Returns { checked, flipped, ids }.
 *
 * Optional body: { mapId?: string } to probe a single row.
 */
export const POST: RequestHandler = async ({ locals, request }) => {
  await requireRole(locals);
  const supabase = adminClient();

  let mapId: string | undefined;
  try {
    ({ mapId } = (await request.json()) as { mapId?: string });
  } catch {
    /* empty body ok */
  }

  let q = supabase
    .from('maps')
    .select('id, name, allmaps_id')
    .not('allmaps_id', 'is', null)
    .eq('is_georeferenced', false);
  if (mapId) q = q.eq('id', mapId);

  const { data: rows, error: err } = await q;
  if (err) dbError(err, 'Could not list maps to sync');

  const flippedIds: string[] = [];
  for (const r of rows ?? []) {
    if (await probeAllmapsAnnotation(r.allmaps_id!, 'HEAD')) {
      const { error: updErr } = await supabase
        .from('maps')
        .update({ is_georeferenced: true })
        .eq('id', r.id);
      if (!updErr) flippedIds.push(r.id);
    }
  }

  return json({ checked: rows?.length ?? 0, flipped: flippedIds.length, ids: flippedIds });
};
