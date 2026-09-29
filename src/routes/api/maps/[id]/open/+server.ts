import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';

/** Public tally, with publication and hourly caps enforced atomically in SQL. */
export const POST: RequestHandler = async ({ params }) => {
  const mapId = assertUuid(params.id, 'map id');
  const { data, error } = await adminClient().rpc('record_map_view', { p_map_id: mapId });
  if (error) dbError(error, 'Could not record map view');
  return json({ recorded: data === true });
};
