/**
 * Shared write paths for OCR review.
 *
 * Since migration 054 the transitions themselves live in Postgres
 * (`set_extraction_status`, `revert_recent_validations`) — the `validated_at` /
 * `validated_by` stamping is applied there, so a worker or a future direct
 * client write cannot skip it. What is left here is argument shaping.
 */

import { textGroupsAvailable } from './textGroups';
import { adminClient } from './supabaseAdmin';
import { bboxCentre, pointEwkt, resolveMapWarp, type MapWarp } from './warp';

export const OCR_REVIEW_STATUSES = ['validated', 'rejected', 'pending'] as const;
export type OcrReviewStatus = (typeof OCR_REVIEW_STATUSES)[number];

export function isOcrReviewStatus(v: unknown): v is OcrReviewStatus {
  return OCR_REVIEW_STATUSES.includes(v as OcrReviewStatus);
}

/** ISO timestamp `windowMins` ago — the cut-off for "recently validated". */
export function revertThreshold(windowMins: number): string {
  return new Date(Date.now() - windowMins * 60 * 1000).toISOString();
}

/**
 * Status change for a map's extractions, scoped either to explicit `ids` or to
 * a whole `runId`. The caller is responsible for requiring one of them.
 */
export async function bulkSetStatus(opts: {
  mapId: string;
  status: OcrReviewStatus;
  userId: string;
  ids?: string[] | null;
  runId?: string | null;
}) {
  return await adminClient().rpc('set_extraction_status', {
    p_status: opts.status,
    p_user: opts.userId,
    p_ids: opts.ids?.length ? opts.ids : undefined,
    p_map_id: opts.mapId,
    p_run_id: opts.ids?.length ? undefined : (opts.runId ?? undefined),
  });
}

/** Rows this user validated on this map inside the window. */
async function recentQuery(mapId: string, userId: string, threshold: string) {
  const db = adminClient();
  const available = await textGroupsAvailable(db);
  let q = db
    .from('ocr_labels')
    .select('id', { count: 'exact' })
    .eq('map_id', mapId)
    .eq('review_status', 'validated')
    .eq('reviewed_by', userId)
    .gt('reviewed_at', threshold);
  if (available) q = q.is('text_group_id', null);
  return await q;
}

/** How many of this user's validations on this map fall inside the window. */
export async function countRecentValidations(mapId: string, userId: string, windowMins: number) {
  const threshold = revertThreshold(windowMins);
  const { error, count } = await recentQuery(mapId, userId, threshold);
  return { error, count: count ?? 0, threshold };
}

/** Revert this user's validations on this map inside the window back to pending. */
export async function revertRecentValidations(mapId: string, userId: string, windowMins: number) {
  const { data, error } = await adminClient().rpc('revert_recent_validations', {
    p_map_id: mapId,
    p_user: userId,
    p_window_mins: windowMins,
  });

  return { error, count: data ?? 0, threshold: revertThreshold(windowMins) };
}

/**
 * The bbox centre warped into the place-time index (migration 066). Shared by
 * the manual-box POST and the coordinate-editing PATCH, because a box that is
 * dragged somewhere else is somewhere else on the ground too.
 */
export async function warpFields(
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
