import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { pickSheetPrintingFields } from '$lib/server/sheetPrintingFields';

export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const id = assertUuid(params.id, 'printing id');
  const body = await request.json();
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw error(400, 'Expected an object');
  }
  const db = adminClient();
  const { data: existing, error: readError } = await db
    .from('sheet_printings')
    .select('evidence,review_status')
    .eq('id', id)
    .maybeSingle();
  if (readError || !existing) throw error(404, 'Printing not found');
  const update = pickSheetPrintingFields(body, existing);
  if (Object.keys(update).length === 0) throw error(400, 'No writable printing fields');
  const { data, error: err } = await db
    .from('sheet_printings')
    .update(update)
    .eq('id', id)
    .select()
    .single();
  if (err) throw error(400, 'Could not update sheet printing');
  return json(data);
};
