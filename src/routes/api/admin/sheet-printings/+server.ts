import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { readAll } from '$lib/data/supabase/paged';
import { pickSheetPrintingInsert } from '$lib/server/sheetPrintingFields';

export const GET: RequestHandler = async ({ locals, url }) => {
  await requireRole(locals);
  const seriesId = assertUuid(url.searchParams.get('series_id') ?? '', 'series id');
  const sheetNumber = url.searchParams.get('sheet_number')?.trim();
  if (!sheetNumber) throw error(400, 'sheet_number is required');
  const db = adminClient();
  const { data: cell } = await db
    .from('series_cells')
    .select('id')
    .eq('series_id', seriesId)
    .eq('sheet_number', sheetNumber)
    .maybeSingle();
  if (!cell) return json({ printings: [], items: [] });

  const printings = await readAll((from, to) =>
    db.from('sheet_printings').select('*').eq('cell_id', cell.id).order('id').range(from, to)
  );
  if (printings.error) throw error(500, 'Could not read sheet printings');
  const items = await readAll((from, to) =>
    db
      .from('cell_printings')
      .select('id,institution,title,source_ref,url,year,edition,part,printing_id')
      .eq('series_id', seriesId)
      .eq('sheet_number', sheetNumber)
      .order('id')
      .range(from, to)
  );
  if (items.error) throw error(500, 'Could not read institutional source items');
  return json({ printings: printings.data, items: items.data });
};

export const POST: RequestHandler = async ({ locals, request }) => {
  await requireRole(locals);
  const body = await request.json();
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw error(400, 'Expected an object');
  }
  const seriesId = assertUuid(body.series_id, 'series id');
  const sheetNumber = typeof body.sheet_number === 'string' ? body.sheet_number.trim() : '';
  if (!sheetNumber) throw error(400, 'sheet_number is required');
  const db = adminClient();
  const { data: cell } = await db
    .from('series_cells')
    .select('id')
    .eq('series_id', seriesId)
    .eq('sheet_number', sheetNumber)
    .maybeSingle();
  if (!cell) throw error(400, 'No cell matches this series and sheet number');
  const values = pickSheetPrintingInsert(body);
  const { data, error: err } = await db
    .from('sheet_printings')
    .insert({ ...values, cell_id: cell.id })
    .select()
    .single();
  if (err) throw error(400, 'Could not create sheet printing');
  return json(data, { status: 201 });
};
