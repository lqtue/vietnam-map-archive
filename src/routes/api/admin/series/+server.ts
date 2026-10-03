import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { readAll } from '$lib/data/supabase/paged';

export const GET: RequestHandler = async ({ locals }) => {
  await requireRole(locals);
  const result = await readAll((from, to) =>
    adminClient()
      .from('series')
      .select('id,key,name,code,scale_denominator')
      .order('name')
      .order('id')
      .range(from, to)
  );
  if (result.error) throw error(500, 'Could not load series');
  return json(result.data ?? []);
};
