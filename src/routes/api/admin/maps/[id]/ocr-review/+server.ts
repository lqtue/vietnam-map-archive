import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { bboxCentre, pointEwkt, resolveMapWarp, type MapWarp } from '$lib/server/warp';

/**
 * The bbox centre warped into the place-time index (migration 066). Shared by
 * the manual-box POST and the coordinate-editing PATCH, because a box that is
 * dragged somewhere else is somewhere else on the ground too.
 */
async function warpFields(
  supabase: ReturnType<typeof adminClient>,
  mapId: string,
  coords: {
    global_x?: number | null;
    global_y?: number | null;
    global_w?: number | null;
    global_h?: number | null;
  }
): Promise<{ geom: string | null; geom_src: string | null; geom_rmse: number | null }> {
  const centre = bboxCentre(coords);
  if (!centre) return { geom: null, geom_src: null, geom_rmse: null };
  const { data: map } = await supabase
    .from('maps')
    .select('allmaps_id, annotation_url')
    .eq('id', mapId)
    .single();
  const warp: MapWarp | null = map
    ? await resolveMapWarp(map.allmaps_id, map.annotation_url)
    : null;
  const geom = warp ? pointEwkt(warp, centre) : null;
  return {
    geom,
    geom_src: geom ? warp!.src : null,
    geom_rmse: geom ? warp!.rmse : null,
  };
}
import { bulkSetStatus, isOcrReviewStatus } from '$lib/server/ocrReview';
import type { Database } from '$lib/data/supabase/types';

/**
 * PostgREST answers with at most 1000 rows however wide a range is asked for,
 * and says so only in the Content-Range header. A sheet with more extractions
 * than that silently lost its tail — and, worse, every count derived from the
 * same query: the 1882 cadastral plan reported 0 validated rows out of 1099,
 * because all 43 of them sorted past the cap. Page until a short page arrives.
 */
async function pageAll<T>(
  query: (
    from: number,
    to: number
  ) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>,
  limit: number,
  failure: string
): Promise<T[]> {
  const PAGE = 1000;
  const out: T[] = [];
  while (out.length < limit) {
    const want = Math.min(PAGE, limit - out.length);
    const { data, error: err } = await query(out.length, out.length + want - 1);
    if (err) dbError(err, failure);
    if (!data?.length) break;
    out.push(...data);
    if (data.length < want) break;
  }
  return out;
}

/** GET /api/admin/maps/[id]/ocr-review
 *  Query params: run_id (optional), status (optional), limit (default 200), offset (default 0)
 *  Returns extractions for the map ordered by category, confidence desc.
 */
export const GET: RequestHandler = async ({ params, url, locals }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const supabase = adminClient();
  const runId = url.searchParams.get('run_id');
  const status = url.searchParams.get('status');
  const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '200'), 2000);
  const offset = parseInt(url.searchParams.get('offset') ?? '0');

  const rows = await pageAll(
    (from, to) => {
      let q = supabase
        .from('ocr_labels')
        .select(
          // Client-side field names stay `text_validated`/`category_validated`/
          // `status`/`validated_at` (the OCR review UI's own vocabulary) — only
          // the columns they read from renamed (mig 095).
          'id, run_id, tile_x, tile_y, tile_w, tile_h, global_x, global_y, global_w, global_h, category, text, text_validated:text_corrected, category_validated:category_corrected, confidence, rotation_deg, label_w, label_h, notes, status:review_status, validated_at:reviewed_at, model, prompt'
        )
        .eq('map_id', mapId)
        .order('category', { ascending: true })
        .order('confidence', { ascending: false })
        // Category and confidence both tie in bulk — every row of a run tends to
        // carry confidence 1 — and a tie that resolves differently between two
        // pages would drop rows and repeat others. id is the stable tiebreak.
        .order('id', { ascending: true })
        .range(offset + from, offset + to);
      if (runId) q = q.eq('run_id', runId);
      if (status) q = q.eq('review_status', status);
      return q;
    },
    limit,
    'Could not read OCR extractions'
  );

  // Counts and run ids describe the whole sheet, so they need every row, not the
  // page above. Two small columns, paged the same way.
  const meta = await pageAll(
    (from, to) =>
      supabase
        .from('ocr_labels')
        .select('status:review_status, run_id')
        .eq('map_id', mapId)
        .range(from, to),
    Infinity,
    'Could not count OCR extractions'
  );

  const statusCounts: Record<string, number> = {};
  for (const row of meta) statusCounts[row.status] = (statusCounts[row.status] ?? 0) + 1;

  const runIds = [...new Set(meta.map((r) => r.run_id))].sort();

  return json({ extractions: rows, total: meta.length, statusCounts, runIds });
};

/** POST /api/admin/maps/[id]/ocr-review
 *  Body: { run_id, global_x, global_y, global_w, global_h, category?, text?, tile_x?, tile_y?, tile_w?, tile_h? }
 *  Creates a new blank extraction row with status=pending.
 */
export const POST: RequestHandler = async ({ params, request, locals }) => {
  await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const body = await request.json();

  const { run_id, global_x, global_y, global_w, global_h } = body;
  if (!run_id) throw error(400, 'Missing run_id');
  if (global_x == null || global_y == null || global_w == null || global_h == null) {
    throw error(400, 'Missing bbox coords');
  }

  // The unique key is (map_id, run_id, tile_x, tile_y, text). Manual boxes
  // usually have empty text, so keying tile_x/y off the drawn location keeps
  // two blank boxes from colliding on (…,0,0,''). Two boxes at the exact same
  // pixel with the same text still collapse — same-spot dup, acceptable.
  const row = {
    map_id: mapId,
    run_id,
    tile_x: body.tile_x ?? Math.round(global_x),
    tile_y: body.tile_y ?? Math.round(global_y),
    tile_w: body.tile_w ?? 0,
    tile_h: body.tile_h ?? 0,
    global_x,
    global_y,
    global_w,
    global_h,
    // A drawn box is upright and is its own label rectangle.
    rotation_deg: Number.isFinite(body.rotation_deg) ? body.rotation_deg : 0,
    label_w: Number.isFinite(body.label_w) ? body.label_w : global_w,
    label_h: Number.isFinite(body.label_h) ? body.label_h : global_h,
    category: body.category ?? 'other',
    text: body.text ?? '',
    confidence: 1.0,
    review_status: 'pending',
    model: 'manual',
    prompt: 'manual',
  };

  const supabase = adminClient();
  const { data, error: err } = await supabase
    .from('ocr_labels')
    .insert({ ...row, ...(await warpFields(supabase, mapId, row)) })
    .select('id')
    .single();

  if (err) dbError(err, 'Could not create extraction');
  return json({ ok: true, id: data!.id });
};

/** PATCH /api/admin/maps/[id]/ocr-review
 *  Body: { id: string, text?: string, category?: string, notes?: string, status: 'validated'|'rejected'|'pending' }
 *  Updates the extraction and records who validated it.
 */
export const PATCH: RequestHandler = async ({ params, request, locals }) => {
  const { user } = await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const body = await request.json();

  const {
    id: extractionId,
    text,
    category,
    notes,
    status,
    global_x,
    global_y,
    global_w,
    global_h,
    rotation_deg,
    label_w,
    label_h,
  } = body;
  if (!extractionId) throw error(400, 'Missing extraction id');
  for (const [name, value] of [
    ['rotation_deg', rotation_deg],
    ['label_w', label_w],
    ['label_h', label_h],
  ] as const) {
    if (value !== undefined && value !== null && !Number.isFinite(value)) {
      throw error(400, `${name} must be a number or null`);
    }
  }
  if (status !== undefined && !isOcrReviewStatus(status)) {
    throw error(400, 'status must be validated, rejected, or pending');
  }

  // Corrections are plain column writes; the status transition is not, because
  // it carries the reviewed_at/reviewed_by stamp — that lives in the RPC.
  const update: Database['public']['Tables']['ocr_labels']['Update'] = {};
  if (text !== undefined) update.text_corrected = text;
  if (category !== undefined) update.category_corrected = category;
  if (notes !== undefined) update.notes = notes;
  if (global_x !== undefined) update.global_x = global_x;
  if (global_y !== undefined) update.global_y = global_y;
  if (global_w !== undefined) update.global_w = global_w;
  if (global_h !== undefined) update.global_h = global_h;
  // The label's own rectangle (mig 076). `global_*` is the box around it and
  // arrives in the same PATCH, so there is nothing to recompute server-side.
  if (rotation_deg !== undefined) update.rotation_deg = rotation_deg;
  if (label_w !== undefined) update.label_w = label_w;
  if (label_h !== undefined) update.label_h = label_h;
  if (!Object.keys(update).length && status === undefined) {
    throw error(400, 'No fields to update');
  }

  const supabase = adminClient();

  // A moved box is a moved place. Re-warp from the row as it will be, so a
  // PATCH that changes only x still gets a geom built from the stored y.
  if (
    global_x !== undefined ||
    global_y !== undefined ||
    global_w !== undefined ||
    global_h !== undefined
  ) {
    const { data: current } = await supabase
      .from('ocr_labels')
      .select('global_x, global_y, global_w, global_h')
      .eq('id', extractionId)
      .eq('map_id', mapId)
      .single();
    Object.assign(update, await warpFields(supabase, mapId, { ...current, ...update }));
  }

  if (Object.keys(update).length) {
    const { error: err } = await supabase
      .from('ocr_labels')
      .update(update)
      .eq('id', extractionId)
      .eq('map_id', mapId);
    if (err) dbError(err, 'Could not update extraction');
  }

  if (status !== undefined) {
    const { error: err } = await bulkSetStatus({
      mapId,
      status,
      userId: user.id,
      ids: [extractionId],
    });
    if (err) dbError(err, 'Could not update extraction status');
  }

  return json({ ok: true });
};

/** PUT /api/admin/maps/[id]/ocr-review  (batch)
 *  Body: { ids: string[], status: 'validated'|'rejected'|'pending' }
 *  Bulk-update status for multiple extractions (e.g. validate all confirmed-tier items).
 */
export const PUT: RequestHandler = async ({ params, request, locals }) => {
  const { user } = await requireRole(locals);
  const mapId = assertUuid(params.id, 'map id');
  const { ids, status, run_id } = await request.json();

  if (!isOcrReviewStatus(status)) {
    throw error(400, 'status must be validated, rejected, or pending');
  }
  if (!ids?.length && !run_id) throw error(400, 'Provide ids[] or run_id');

  const { error: err, data: count } = await bulkSetStatus({
    mapId,
    status,
    userId: user.id,
    ids,
    runId: run_id,
  });

  if (err) dbError(err, 'Could not update extractions');
  return json({ ok: true, count });
};
