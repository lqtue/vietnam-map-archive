import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { assertUuid } from '$lib/server/http';
import { adminClient } from '$lib/server/supabaseAdmin';

export const PATCH: RequestHandler = async ({ locals, params, request }) => {
  await requireRole(locals);
  const id = assertUuid(params.id, 'source item id');
  const body = await request.json();
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw error(400, 'Expected an object');
  }
  const printingId = body.printing_id === null ? null : assertUuid(body.printing_id, 'printing id');
  const db = adminClient();
  const { data: item, error: itemError } = await db
    .from('cell_printings')
    .select('id,series_id,sheet_number')
    .eq('id', id)
    .maybeSingle();
  if (itemError || !item) throw error(404, 'Institution item not found');

  if (printingId) {
    if (!item.series_id) throw error(400, 'Institution item is not linked to a canonical series');
    const { data: cell, error: cellError } = await db
      .from('series_cells')
      .select('id')
      .eq('series_id', item.series_id)
      .eq('sheet_number', item.sheet_number)
      .maybeSingle();
    if (cellError || !cell) throw error(400, 'Institution item has no matching series cell');
    const { data: printing, error: printingError } = await db
      .from('sheet_printings')
      .select('id,cell_id')
      .eq('id', printingId)
      .maybeSingle();
    if (printingError || !printing) throw error(400, 'Printing not found');
    if (printing.cell_id !== cell.id)
      throw error(400, 'Printing must belong to the same series cell');
  }

  const { data, error: updateError } = await db
    .from('cell_printings')
    .update({ printing_id: printingId })
    .eq('id', id)
    .select('id,printing_id')
    .single();
  if (updateError) throw error(400, 'Could not update institution item link');
  return json(data);
};
