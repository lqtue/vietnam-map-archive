import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { cached } from '$lib/server/edgeCache';
import { cachedExploreMaps } from '$lib/server/exploreMapsCache';
import { dbError } from '$lib/server/http';
import { exploreMapsParameters, shapeExploreMaps } from '$lib/server/exploreMaps';

export const GET: RequestHandler = async ({ url, locals, platform }) => {
  const role = await getRole(locals);
  let args;
  try {
    args = exploreMapsParameters(url.searchParams, role === 'admin' || role === 'mod');
  } catch {
    throw error(400, 'Invalid Explore search parameters');
  }
  // RPC privileges restrict this explicit visibility parameter to the trusted server.
  const payload = await cachedExploreMaps(
    platform,
    role === null,
    args,
    async () => {
      const { data, error: failure } = await (adminClient().rpc as any)('explore_maps_page', args);
      if (failure) dbError(failure, 'Explore search failed');
      return shapeExploreMaps(data);
    },
    cached
  );
  return json(payload, { headers: { 'Cache-Control': 'private, no-store' } });
};
