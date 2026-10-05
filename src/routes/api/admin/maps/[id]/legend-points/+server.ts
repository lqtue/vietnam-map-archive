import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { editLegendNotes, legendNumber } from '$lib/server/legendEntry';
import { bulkSetStatus } from '$lib/server/ocrReview';
import { getTransformer } from '$lib/server/transformer';

type LegendEdit = {
  id: string;
  name: string;
  vn: string | null;
  grid: string | null;
  /** Image pixels as sent, or ground lng/lat to be taken back to pixels. */
  point: { px: [number, number] } | { lngLat: [number, number] } | null;
};

function noteText(value: unknown, label: string): string | null {
  if (value === null || value === '') return null;
  if (typeof value !== 'string' || value.length > 1000 || /[;\r\n]/.test(value))
    throw error(400, `${label} must be text without semicolons or line breaks`);
  return value.trim() || null;
}

function parseEdit(body: unknown): LegendEdit {
  if (!body || typeof body !== 'object' || Array.isArray(body))
    throw error(400, 'Invalid legend entry');
  const value = body as Record<string, unknown>;
  const id = assertUuid(typeof value.id === 'string' ? value.id : '', 'entry id');
  if (typeof value.name !== 'string' || !value.name.trim() || value.name.length > 1000)
    throw error(400, 'Enter a legend name of up to 1000 characters');
  let point: LegendEdit['point'] = null;
  if (value.x != null || value.y != null) {
    if (
      typeof value.x !== 'number' ||
      typeof value.y !== 'number' ||
      !Number.isFinite(value.x) ||
      !Number.isFinite(value.y) ||
      value.x < 0 ||
      value.y < 0
    )
      throw error(400, 'Enter valid image x and y, or reset both');
    point = { px: [value.x, value.y] };
  } else if (value.lng != null || value.lat != null) {
    if (
      typeof value.lng !== 'number' ||
      typeof value.lat !== 'number' ||
      !Number.isFinite(value.lng) ||
      !Number.isFinite(value.lat) ||
      Math.abs(value.lng) > 180 ||
      Math.abs(value.lat) > 90
    )
      throw error(400, 'Enter valid longitude and latitude, or reset both');
    point = { lngLat: [value.lng, value.lat] };
  }
  return {
    id,
    name: value.name.trim(),
    vn: noteText(value.vn, 'Vietnamese name'),
    grid: noteText(value.grid, 'Grid reference'),
    point,
  };
}

/** Save one legend correction or a batch of staged corrections. */
export const PATCH: RequestHandler = async ({ params, request, locals }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const mapId = assertUuid(params.id, 'map id');
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    throw error(400, 'Invalid JSON');
  }
  if (!body || typeof body !== 'object' || Array.isArray(body))
    throw error(400, 'Invalid legend entry');
  const entries = body.entries;
  const batch = Array.isArray(entries);
  if (batch && (!entries.length || entries.length > 200))
    throw error(400, 'Save between 1 and 200 legend entries at once');
  const edits = (batch ? entries : [body]).map(parseEdit);
  if (new Set(edits.map((edit) => edit.id)).size !== edits.length)
    throw error(400, 'A legend entry appears more than once');

  const db = adminClient();
  const { data: rows, error: readError } = await db
    .from('ocr_labels')
    .select('id,text,text_corrected,notes,review_status')
    .eq('map_id', mapId)
    .eq('category', 'legend_entry')
    .in(
      'id',
      edits.map((edit) => edit.id)
    );
  if (readError) dbError(readError, 'Could not read legend entries');
  const byId = new Map((rows ?? []).map((row) => [row.id, row]));

  // A position is stored in image pixels, so a click on the warped map goes back
  // through this map's own georeference before it is saved.
  let transformer: Awaited<ReturnType<typeof getTransformer>> = null;
  if (edits.some((edit) => edit.point && 'lngLat' in edit.point)) {
    const { data: map, error: mapError } = await db
      .from('maps')
      .select('allmaps_id, annotation_url')
      .eq('id', mapId)
      .single();
    if (mapError) dbError(mapError, 'Could not read map');
    transformer = await getTransformer(map?.allmaps_id, map?.annotation_url);
    if (!transformer) throw error(409, 'This map has no georeference to place a point through');
  }
  const pixel = (point: LegendEdit['point']): [number, number] | null =>
    !point
      ? null
      : 'px' in point
        ? point.px
        : transformer!.transformer.transformToResource(point.lngLat);

  for (const edit of edits) {
    const row = byId.get(edit.id);
    if (!row || row.review_status === 'rejected') throw error(404, 'Legend entry not found');
    if (!legendNumber(row.text_corrected ?? row.text, row.notes))
      throw error(400, 'A selected entry has no legend number');
  }

  const updates = await Promise.all(
    edits.map(async (edit) => {
      const row = byId.get(edit.id)!;
      const n = legendNumber(row.text_corrected ?? row.text, row.notes)!;
      const { error: saveError } = await db
        .from('ocr_labels')
        .update({
          text_corrected: `${n}. ${edit.name}`,
          notes: editLegendNotes(row.notes, {
            vn: edit.vn,
            grid: edit.grid,
            px: pixel(edit.point),
          }),
        })
        .eq('id', edit.id)
        .eq('map_id', mapId)
        .eq('category', 'legend_entry');
      return { id: edit.id, error: saveError };
    })
  );
  const saved = updates.filter((result) => !result.error).map((result) => result.id);
  const failed: { id: string; message: string }[] = updates
    .filter((result) => result.error)
    .map(({ id }) => ({ id, message: 'Could not save this entry.' }));
  if (saved.length) {
    const { error: statusError } = await bulkSetStatus({
      mapId,
      ids: saved,
      status: 'validated',
      userId: user.id,
    });
    if (statusError) {
      for (const id of saved)
        failed.push({ id, message: 'Could not record review for this entry.' });
      saved.length = 0;
    }
  }

  if (!batch && failed.length) throw error(500, failed[0].message);
  if (!batch) return json({ id: saved[0] });
  return json({ saved, failed });
};
