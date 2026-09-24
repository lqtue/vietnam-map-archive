/**
 * rewarp.ts — refill a map's derived geometry after its georeference moves.
 *
 * The writers warp on the way in (`$lib/server/warp.ts`), which covers every
 * row written while a map's GCPs stand still. Re-georeferencing invalidates all
 * of them at once, and enqueuing one `warp` job is cheaper and more honest than
 * trying to patch rows from the editor. This is that job's body; it is also
 * what backfills a map whose rows were written before it was georeferenced at
 * all, which is most of the corpus.
 *
 * Batched deliberately. A real sheet holds well over a thousand extractions,
 * and this runs inside a Pages Function, which gets a few dozen subrequests per
 * request — not a few thousand. So both sides page through their rows and write
 * back through `set_extraction_geom` / `set_footprint_geom` (migration 068),
 * which take up to 1000 rows per call. One map is a handful of round trips.
 */

import { adminClient } from './supabaseAdmin';
import { bboxCentre, pointEwkt, polygonEwkt, resolveMapWarp, type MapWarp } from './warp';

/** Rows fetched per page, and rows sent per write. The RPC's own cap is 1000. */
const PAGE = 500;

export interface RewarpResult {
  map_id: string;
  geom_src: string | null;
  geom_rmse: number | null;
  labels: number;
  footprints: number;
  /** Rows the transform refused: a line trace, or a point outside the GCP hull. */
  skipped: number;
  /** Rows already warped against this same georeference, so left alone. */
  unchanged: number;
  reason?: string;
}

interface GeomWrite {
  id: string;
  geom: string | null;
  geom_src: string;
  geom_rmse: number | null;
}

export async function rewarpMap(mapId: string): Promise<RewarpResult> {
  const supabase = adminClient();
  const empty: RewarpResult = {
    map_id: mapId,
    geom_src: null,
    geom_rmse: null,
    labels: 0,
    footprints: 0,
    skipped: 0,
    unchanged: 0,
  };

  const { data: map } = await supabase
    .from('maps')
    .select('allmaps_id, annotation_url')
    .eq('id', mapId)
    .single();
  if (!map) return { ...empty, reason: 'no such map' };

  const resolved = await resolveMapWarp(map.allmaps_id, map.annotation_url);
  if (!resolved) return { ...empty, reason: 'no usable annotation' };
  // Bound to a const the closures below can narrow.
  const warp: MapWarp = resolved;

  const counts = { written: 0, skipped: 0, unchanged: 0 };

  /**
   * Walk one table a page at a time, turning each page into one RPC call.
   *
   * Paging is by `id` rather than by offset: `range()` over an unordered set is
   * unstable, and an offset walk over rows this pass is itself updating can miss
   * some. `id` is a uuid, so the order is arbitrary but total and stable.
   */
  async function pass<T extends { id: string; geom_src: string | null }>(
    table: 'ocr_labels' | 'footprints',
    columns: string,
    rpc: 'set_extraction_geom' | 'set_footprint_geom',
    toEwkt: (row: T, w: MapWarp) => string | null
  ): Promise<number> {
    let written = 0;
    let after = '';
    for (;;) {
      let q = supabase.from(table).select(columns).eq('map_id', mapId).order('id').limit(PAGE);
      if (after) q = q.gt('id', after);

      const { data, error } = await q;
      if (error || !data?.length) break;

      const rows = data as unknown as T[];
      after = rows[rows.length - 1].id;

      const writes: GeomWrite[] = [];
      for (const row of rows) {
        // Already warped against this exact georeference: nothing to do.
        if (row.geom_src === warp.src) {
          counts.unchanged++;
          continue;
        }
        const geom = toEwkt(row, warp);
        if (!geom) {
          counts.skipped++;
          continue;
        }
        writes.push({ id: row.id, geom, geom_src: warp.src, geom_rmse: warp.rmse });
      }

      if (writes.length) {
        const { data: n, error: rpcErr } = await supabase.rpc(rpc, {
          p_rows: writes as unknown as never,
        });
        if (rpcErr) counts.skipped += writes.length;
        else written += (n as number | null) ?? writes.length;
      }

      if (rows.length < PAGE) break;
    }
    return written;
  }

  const labels = await pass<{
    id: string;
    geom_src: string | null;
    global_x: number | null;
    global_y: number | null;
    global_w: number | null;
    global_h: number | null;
  }>(
    'ocr_labels',
    'id, geom_src, global_x, global_y, global_w, global_h',
    'set_extraction_geom',
    (row, w) => {
      const centre = bboxCentre(row);
      return centre ? pointEwkt(w, centre) : null;
    }
  );

  const footprints = await pass<{
    id: string;
    geom_src: string | null;
    pixel_polygon: unknown;
  }>('footprints', 'id, geom_src, pixel_polygon', 'set_footprint_geom', (row, w) => {
    const ring = row.pixel_polygon as [number, number][] | null;
    return ring ? polygonEwkt(w, ring) : null;
  });

  return {
    map_id: mapId,
    geom_src: warp.src,
    geom_rmse: warp.rmse,
    labels,
    footprints,
    skipped: counts.skipped,
    unchanged: counts.unchanged,
  };
}
