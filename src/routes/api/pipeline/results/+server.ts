/**
 * POST /api/pipeline/results — everything a worker writes back.
 *
 * Body (all parts optional, applied in this order):
 *   extractions:     ocr_extractions rows to upsert (max 500 per request)
 *   map_id + triage_regions: the layout pass's answer, merged into maps.triage
 *   map_id + triage_grid:    the sheet's printed reference grid, likewise merged
 *   footprints:      footprint_submissions rows to insert (max 500 per request)
 *   job_id + status: closes the job out via finish_job (done | failed | running)
 *
 * Bundling them means a worker can report "rows written, job done" in one round
 * trip. The worker holds a `worker_keys` token, so this is the only surface it
 * can write through — it never sees the service key.
 *
 * There is deliberately no stage field: since migration 056 the pipeline stage
 * is a view over `pipeline_jobs`, so closing the job *is* advancing the stage.
 *
 * Extractions are warped into the place-time index on the way in (migration
 * 066): the bbox centre becomes `geom`, stamped with the georeference it used.
 * A map with no usable annotation writes a null `geom`, which is a legitimate
 * state — the `warp` job fills it in once the map is georeferenced.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireWorker } from '$lib/server/workerAuth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { bboxCentre, pointEwkt, resolveMapWarp, type MapWarp } from '$lib/server/warp';
import { parseRegion, type SavedTriage } from '$lib/data/maps/triageTypes';
import { parseGrid } from '$lib/core/geo/mapGrid';

const MAX_ROWS = 500;

// Must match the unique index ocr_extractions_upsert_key (migration 077) and
// `_CONFLICT_COLS` in work/ocr/scripts/supabase_client.py. global_xi/global_yi
// are generated round(global_x/y) columns that exist only to be nameable here —
// PostgREST cannot reference an expression index in on_conflict.
const UPSERT_KEY = 'map_id,run_id,tile_x,tile_y,text,global_xi,global_yi';
const JOB_STATUSES = ['running', 'done', 'failed'];

export const POST: RequestHandler = async ({ request }) => {
  await requireWorker(request);
  const body = await request.json().catch(() => ({}));
  const supabase = adminClient();
  const applied: Record<string, unknown> = {};

  if (Array.isArray(body.extractions) && body.extractions.length) {
    const rows = body.extractions;
    if (rows.length > MAX_ROWS) throw error(413, `At most ${MAX_ROWS} extractions per request`);
    for (const row of rows) {
      assertUuid(row.map_id, 'extraction map_id');
      if (!row.run_id) throw error(400, 'Every extraction needs a run_id');
    }
    // Warp per map, not per row: a batch is normally one map's tiles, and
    // resolving the annotation is a network fetch.
    const warps = new Map<string, MapWarp | null>();
    for (const row of rows) {
      if (warps.has(row.map_id)) continue;
      const { data: map } = await supabase
        .from('maps')
        .select('allmaps_id, annotation_url')
        .eq('id', row.map_id)
        .single();
      warps.set(row.map_id, map ? await resolveMapWarp(map.allmaps_id, map.annotation_url) : null);
    }
    for (const row of rows) {
      const warp = warps.get(row.map_id);
      const centre = warp ? bboxCentre(row) : null;
      const geom = warp && centre ? pointEwkt(warp, centre) : null;
      row.geom = geom;
      row.geom_src = geom ? warp!.src : null;
      row.geom_rmse = geom ? warp!.rmse : null;
    }

    const { error: err, count } = await supabase
      .from('ocr_extractions')
      .upsert(rows, { onConflict: UPSERT_KEY, count: 'exact' });
    if (err) dbError(err, 'Could not write extractions');
    // Report what the database accepted *and* what was offered. They differed
    // silently before migration 077: the key was (map_id, run_id, tile_x,
    // tile_y, text), so 18 of a 337-row merge collapsed into each other and the
    // count came back 319 with nothing to compare it against.
    applied.extractions = count ?? rows.length;
    if (count != null && count < rows.length) applied.extractions_offered = rows.length;
  }

  // The layout job's output. Merged, not replaced: the neatline and tile grid
  // beside it belong to whoever drew them, and a re-run of the layout pass must
  // not silently discard a person's triage.
  if (Array.isArray(body.triage_regions)) {
    const mapId = assertUuid(body.map_id, 'map_id');
    const regions = body.triage_regions
      .map(parseRegion)
      .filter((r: ReturnType<typeof parseRegion>) => r !== null);

    const { data: row, error: readErr } = await supabase
      .from('maps')
      .select('triage')
      .eq('id', mapId)
      .single();
    if (readErr) dbError(readErr, 'Could not read the triage');
    if (!row) throw error(404, 'No such map');

    // Keep what a person decided. `LayoutRegion.source` has recorded who put a
    // region there since migration 069 — the canvas stamps 'human' on every
    // drag, category change and add — and this used to replace the whole array
    // anyway, so pressing Detect a second time silently discarded every
    // correction. The model's proposals are the only thing a re-run may replace.
    const kept = ((row.triage as SavedTriage)?.regions ?? []).filter((r) => r.source === 'human');
    const merged = [...kept, ...regions];

    const { error: writeErr } = await supabase.rpc('set_triage_key', {
      p_map_id: mapId,
      p_key: 'regions',
      p_value: merged,
    });
    if (writeErr) dbError(writeErr, 'Could not write the triage');
    await supabase.rpc('set_triage_key', {
      p_map_id: mapId,
      p_key: 'regions_at',
      p_value: new Date().toISOString(),
    });
    applied.regions = merged.length;
    if (kept.length) applied.regions_kept_human = kept.length;

    // Adopt the layout pass's `main_map` as the crop, so a sheet becomes
    // OCR-able without anyone drawing a neatline. `tilingCrop()` prefers
    // main_map to a neatline anyway, and across the corpus 37 sheets had one
    // while *no* sheet had a neatline — which is why the fleet script's default
    // mode used to queue nothing. A crop a person drew is never overwritten.
    if (Array.isArray(body.triage_neatline) && body.triage_neatline.length === 4) {
      const existing = row.triage as SavedTriage | null;
      if (existing?.neatline_src === 'human') {
        applied.neatline = 'kept the human crop';
      } else {
        const box = body.triage_neatline.map(Number);
        if (box.every((n: number) => Number.isFinite(n))) {
          await supabase.rpc('set_triage_key', {
            p_map_id: mapId,
            p_key: 'neatline',
            p_value: box,
          });
          await supabase.rpc('set_triage_key', {
            p_map_id: mapId,
            p_key: 'neatline_src',
            p_value: 'main_map',
          });
          applied.neatline = box;
        }
      }
    }
  }

  // The sheet's printed reference grid. Merged for the same reason the regions
  // are: everything else in the triage belongs to whoever put it there.
  if (body.triage_grid) {
    const mapId = assertUuid(body.map_id, 'map_id');
    const grid = parseGrid(body.triage_grid);
    if (!grid) throw error(400, 'triage_grid needs a bbox and at least two columns and rows');

    const { data: row, error: readErr } = await supabase
      .from('maps')
      .select('triage')
      .eq('id', mapId)
      .single();
    if (readErr) dbError(readErr, 'Could not read the triage');
    if (!row) throw error(404, 'No such map');

    const { error: writeErr } = await supabase.rpc('set_triage_key', {
      p_map_id: mapId,
      p_key: 'grid',
      p_value: grid,
    });
    if (writeErr) dbError(writeErr, 'Could not write the triage');
    await supabase.rpc('set_triage_key', {
      p_map_id: mapId,
      p_key: 'grid_at',
      p_value: new Date().toISOString(),
    });
    applied.grid = `${grid.columns.length}x${grid.rows.length}`;
  }

  // MapSAM2's polygons. They used to go straight to PostgREST from the GPU
  // machine, which meant a Colab session needed SUPABASE_SERVICE_KEY — the one
  // thing this endpoint exists so a worker never holds. Migration 089 had
  // already dropped the publishable key's INSERT policy, so the anon key cannot
  // stand in: without this branch the seg path had no key it was allowed to use.
  if (Array.isArray(body.footprints) && body.footprints.length) {
    const rows = body.footprints;
    if (rows.length > MAX_ROWS) throw error(413, `At most ${MAX_ROWS} footprints per request`);

    const insert = rows.map((row: Record<string, unknown>) => {
      assertUuid(row.map_id as string, 'footprint map_id');
      const ring = row.pixel_polygon;
      if (!Array.isArray(ring) || ring.length < 3) {
        throw error(400, 'pixel_polygon must be a ring of at least three points');
      }
      for (const pt of ring) {
        if (!Array.isArray(pt) || pt.length < 2 || !pt.slice(0, 2).every(Number.isFinite)) {
          throw error(400, 'pixel_polygon points must be [x, y] numbers');
        }
      }
      return {
        map_id: row.map_id as string,
        pixel_polygon: ring,
        feature_type: (row.feature_type as string) ?? 'building',
        source: (row.source as string) ?? 'sam-auto',
        // Not the worker's to choose. A machine's output enters the review
        // queue; letting a job name its own status would let it write straight
        // to `approved` and skip the person the queue exists for.
        status: 'needs_review',
        confidence: typeof row.confidence === 'number' ? row.confidence : null,
        run_id: (row.run_id as string) ?? null,
        name: (row.name as string) ?? null,
        category: (row.category as string) ?? null,
      };
    });

    // `geom` is deliberately left null: warping a ring is the `warp` job's
    // work, and it already does footprints (migration 066). Publishing a
    // polygon here with no ground geometry is the same state the 46 volunteer
    // traces were in before their warp ran.
    const { error: err } = await supabase.from('footprint_submissions').insert(insert);
    if (err) dbError(err, 'Could not write the footprints');
    applied.footprints = insert.length;
  }

  if (body.job_id) {
    const jobId = assertUuid(body.job_id, 'job_id');
    if (!JOB_STATUSES.includes(body.status)) {
      throw error(400, `status must be one of ${JOB_STATUSES.join(', ')}`);
    }
    const { data, error: err } = await supabase.rpc('finish_job', {
      p_id: jobId,
      p_status: body.status,
      p_result: body.result ?? {},
      p_error: body.error ?? null,
    });
    if (err) dbError(err, 'Could not update the job');
    if (!data || !(data as { id: string | null }).id) throw error(404, 'No such job');
    applied.job = (data as { status: string }).status;
  }

  return json({ ok: true, applied });
};
