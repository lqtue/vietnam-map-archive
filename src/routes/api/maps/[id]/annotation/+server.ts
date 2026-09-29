import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { requireRole } from '$lib/server/auth';

/** Published annotations are public; draft annotations require a session. */
export const GET: RequestHandler = async ({ locals, params, url }) => {
  const mapId = assertUuid(params.id, 'map id');
  const admin = adminClient();
  const { data: map, error: readError } = await admin
    .from('maps')
    .select('status')
    .eq('id', mapId)
    .maybeSingle();
  if (readError) dbError(readError, 'Could not read map');
  if (!map) throw error(404, 'Annotation not found');

  const published = map.status === 'public' || map.status === 'featured';
  if (!published) {
    const { user } = await locals.safeGetSession();
    if (!user) throw error(404, 'Annotation not found');
  }

  const version = url.searchParams.get('version');
  if (version && !/^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z$/.test(version)) {
    throw error(400, 'Invalid annotation version');
  }
  if (version) {
    // History may include unpublished control points even for a public map.
    await requireRole(locals, ['admin', 'mod']);
  }
  const path = version ? `${mapId}/${version}.json` : `${mapId}.json`;
  const { data: blob, error: storageError } = await admin.storage
    .from('annotations')
    .download(path);
  if (storageError || !blob) throw error(404, 'Annotation not found');
  return new Response(blob, {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      'Cache-Control': published && !version ? 'public, max-age=300' : 'private, no-store',
      ...(published && !version ? { 'Access-Control-Allow-Origin': '*' } : {}),
    },
  });
};
