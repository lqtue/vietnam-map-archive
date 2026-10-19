import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { readExploreMap } from '$lib/server/exploreMap';

export const GET: RequestHandler = async ({ locals, url }) => {
  const ref = url.searchParams.get('ref')?.trim();
  const direction = url.searchParams.get('direction') ?? '0';
  if (!ref || ref.length > 300 || !['-1', '0', '1'].includes(direction)) {
    throw error(400, 'A map reference and valid direction are required');
  }
  const role = await getRole(locals);
  try {
    const map = await readExploreMap(
      adminClient(),
      ref,
      role === 'admin' || role === 'mod',
      Number(direction) as -1 | 0 | 1
    );
    return json({ map }, { headers: { 'Cache-Control': 'private, no-store' } });
  } catch (err) {
    dbError(err, 'Map lookup failed');
  }
};
