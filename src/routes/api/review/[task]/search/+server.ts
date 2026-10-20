/**
 * GET /api/review/[task]/search?item=<id>&q=<text> — places within 300 m of the item, by name.
 *
 * Reply: { hits: [{ id, name, source, dist_m, wikidata }] }, at most 8, nearest first. Same on
 * every arm: the reply never marks or ranks the machine's candidates. Staff only in v1.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { openTask, searchItem } from '$lib/server/reviewSession';

export const GET: RequestHandler = async ({ locals, params, url }) => {
  await requireRole(locals, ['admin', 'mod']);
  const item = url.searchParams.get('item') ?? '';
  const q = url.searchParams.get('q') ?? '';
  if (!item || item.length > 200) throw error(400, 'item is required');
  if (q.length > 200) throw error(400, 'q is too long');
  const sb = adminClient();
  const task = await openTask(sb, params.task);
  return json({ hits: await searchItem(sb, task.key, item, q) });
};
