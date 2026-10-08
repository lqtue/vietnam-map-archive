import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import {
  editLegendNotes,
  extraLegendPoints,
  legendNumber,
  MAX_EXTRA_POINTS,
} from '$lib/server/legendEntry';
import { readLegendEntries, readNumeralCandidates } from '$lib/server/legendRead';
import { cellAgreement, parseGrid } from '$lib/core/geo/mapGrid';
import type { SavedTriage } from '$lib/data/maps/triageTypes';
import { bulkSetStatus } from '$lib/server/ocrReview';
import { getTransformer } from '$lib/server/transformer';

type LegendEdit = {
  id: string;
  name: string;
  vn: string | null;
  grid: string | null;
  /** Image pixels as sent, or ground lng/lat to be taken back to pixels. */
  point: { px: [number, number] } | { lngLat: [number, number] } | null;
  /** Further image-pixel positions of this entry; undefined keeps the stored ones
   *  (the map-mode editor does not know about them and never sends the field). */
  more?: [number, number][];
  /** The place search that led to a map-placed point, kept in `legend_finds` (mig 119). */
  find: LegendFind | null;
};

type LegendFind = {
  query: string;
  osmType: 'node' | 'way' | 'relation' | null;
  osmId: number | null;
  osmName: string | null;
  lng: number;
  lat: number;
};

/** A search is ground truth for the gazetteer, so a malformed one is refused, not trimmed. */
function parseFind(value: unknown): LegendFind | null {
  if (value == null) return null;
  const f = value as Record<string, unknown>;
  const osmType = f.osmType ?? null;
  const osmId = f.osmId ?? null;
  const osmName = f.osmName ?? null;
  if (
    typeof f !== 'object' ||
    Array.isArray(f) ||
    typeof f.query !== 'string' ||
    !f.query.trim() ||
    f.query.length > 500 ||
    (osmType !== null && !['node', 'way', 'relation'].includes(osmType as string)) ||
    (osmId !== null && (!Number.isSafeInteger(osmId) || (osmId as number) <= 0)) ||
    (osmType === null) !== (osmId === null) ||
    (osmName !== null && (typeof osmName !== 'string' || osmName.length > 1000)) ||
    typeof f.lng !== 'number' ||
    typeof f.lat !== 'number' ||
    !(Math.abs(f.lng) <= 180) ||
    !(Math.abs(f.lat) <= 90)
  )
    throw error(400, 'Invalid place search');
  return {
    query: f.query.trim(),
    osmType: osmType as LegendFind['osmType'],
    osmId: osmId as number | null,
    osmName: osmName as string | null,
    lng: f.lng,
    lat: f.lat,
  };
}

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
  let more: [number, number][] | undefined;
  if (value.more != null) {
    more = [];
    if (!Array.isArray(value.more) || value.more.length > MAX_EXTRA_POINTS)
      throw error(400, `Give at most ${MAX_EXTRA_POINTS} extra points`);
    for (const p of value.more) {
      if (
        !Array.isArray(p) ||
        p.length !== 2 ||
        p.some((v) => typeof v !== 'number' || !Number.isFinite(v) || v < 0)
      )
        throw error(400, 'Extra points are image x and y');
      more.push([p[0], p[1]]);
    }
  }
  return {
    id,
    name: value.name.trim(),
    vn: noteText(value.vn, 'Vietnamese name'),
    grid: noteText(value.grid, 'Grid reference'),
    point,
    more,
    // Only a point placed on the map can have been found by a search.
    find: point && 'lngLat' in point ? parseFind(value.find) : null,
  };
}

/**
 * The legend in image pixels, for the staff legend tool. No georeference is
 * read, so a draft or an ungeoreferenced sheet works. `x`/`y` are a reviewed
 * manual position (`px=`); a legacy ground `point=` has no pixel and reads as
 * unplaced. A candidate's `inCell` is whether it agrees with its entry's grid
 * reference (null: nothing to check against).
 */
export const GET: RequestHandler = async ({ params, locals }) => {
  await requireRole(locals, ['admin', 'mod']);
  const mapId = assertUuid(params.id, 'map id');
  const db = adminClient();
  const { data: map, error: mapError } = await db
    .from('maps')
    .select('triage')
    .eq('id', mapId)
    .single();
  if (mapError || !map) throw error(404, 'Map not found');
  const grid = parseGrid((map.triage as SavedTriage | null)?.grid);
  const { nameByN, rects, maxN } = await readLegendEntries(db, mapId);
  const found = await readNumeralCandidates(db, mapId, maxN, rects);
  return json(
    {
      entries: [...nameByN]
        .map(([n, info]) => {
          const px = info.manualPoint && 'px' in info.manualPoint ? info.manualPoint.px : null;
          return {
            id: info.id,
            n,
            name: info.name,
            vn: info.vn,
            grid: info.grid,
            x: px?.[0] ?? null,
            y: px?.[1] ?? null,
            src: px ? 'manual' : null,
            more: px ? info.more : [],
            validated: info.validated,
          };
        })
        .sort((a, b) => a.n - b.n),
      candidates: found.map(({ n, x, y, labelId }) => ({
        n,
        x,
        y,
        inCell: cellAgreement(grid, nameByN.get(n)?.grid, x, y),
        labelId,
      })),
      grid,
      legendRects: rects,
    },
    { headers: { 'Cache-Control': 'private, no-store' } }
  );
};

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
            more: edit.more ?? extraLegendPoints(row.notes),
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

  // The searches behind the saved points. The entries are already saved, so a
  // failure here is a warning, not a failed save.
  let warning: string | undefined;
  const savedIds = new Set(saved);
  const finds = edits
    .filter((edit) => edit.find && savedIds.has(edit.id))
    .map(({ id, find }) => ({
      label_id: id,
      map_id: mapId,
      query: find!.query,
      osm_type: find!.osmType,
      osm_id: find!.osmId,
      osm_name: find!.osmName,
      osm_lng: find!.lng,
      osm_lat: find!.lat,
      created_by: user.id,
    }));
  if (finds.length) {
    const { error: findError } = await db.from('legend_finds').insert(finds);
    if (findError) {
      console.error('legend_finds insert', findError.message);
      warning = 'The place searches were not recorded.';
    }
  }

  if (!batch && failed.length) throw error(500, failed[0].message);
  if (!batch) return json({ id: saved[0] });
  return json({ saved, failed, ...(warning ? { warning } : {}) });
};
