/**
 * POST /api/admin/maps/[id]/triage — write part of `maps.triage`, one key at a time.
 *
 * The triage is assembled by several hands: the `layout` job writes `regions`
 * and adopts `main_map` as the crop, the `grid` pass writes the printed
 * reference grid, and a person adjusts the crop and the tile priorities. Until
 * this route existed the page saved it by PATCHing `maps` with a whole `triage`
 * object built from local state, which silently dropped every key that state
 * did not know about — `grid`, `grid_at`, `neatline_src`, and now
 * `validated_at`. Each key here goes through the `set_triage_key` RPC, which is
 * a single `jsonb_set`, so a save can only ever change what it names.
 *
 * `{ validate: true }` is the Accept action: the crop can now be proposed
 * end-to-end without a human, so `validated_at` is what separates "a machine
 * suggested this" from "a person agreed", and it is what
 * `enqueue_ocr_all.mjs` gates OCR spending on.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { parseRegion, triageState, type SavedTriage } from '$lib/data/maps/triageTypes';

/** Keys a person's save may set. `regions_at`/`grid_at` belong to the passes. */
const WRITABLE = [
  'neatline',
  'neatline_src',
  'tile_size',
  'overlap',
  'tile_overrides',
  'regions',
  'legend',
] as const;

const isBox = (v: unknown): boolean =>
  Array.isArray(v) && v.length === 4 && v.every((n) => Number.isFinite(Number(n)));

export const POST: RequestHandler = async ({ locals, params, request }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const mapId = assertUuid(params.id, 'map id');
  const body = await request.json().catch(() => ({}));
  const supabase = adminClient();

  const writes: [string, unknown][] = [];

  for (const key of WRITABLE) {
    if (!(key in body)) continue;
    const value = body[key];

    if (key === 'neatline') {
      if (!isBox(value)) throw error(400, 'neatline must be [x, y, w, h]');
      writes.push(['neatline', (value as unknown[]).map(Number)]);
      // A crop that arrives through this route came from a person, unless they
      // said otherwise — that is what stops a later layout run replacing it.
      if (!('neatline_src' in body)) writes.push(['neatline_src', 'human']);
      continue;
    }
    if (key === 'neatline_src') {
      if (value !== 'human' && value !== 'main_map') {
        throw error(400, "neatline_src must be 'human' or 'main_map'");
      }
      writes.push([key, value]);
      continue;
    }
    if (key === 'legend') {
      // null removes the key: "this sheet has no legend" is withdrawn.
      if (value !== 'none' && value !== null) throw error(400, "legend must be 'none' or null");
      writes.push([key, value]);
      continue;
    }
    if (key === 'regions') {
      if (!Array.isArray(value)) throw error(400, 'regions must be an array');
      const parsed = value.map(parseRegion).filter((r) => r !== null);
      writes.push(['regions', parsed]);
      writes.push(['regions_at', new Date().toISOString()]);
      continue;
    }
    if (key === 'tile_size' || key === 'overlap') {
      const n = Number(value);
      if (!Number.isFinite(n) || n <= 0) throw error(400, `${key} must be a positive number`);
      writes.push([key, Math.round(n)]);
      continue;
    }
    // tile_overrides: a flat map of tile key → priority. Anything else is a
    // typo that would silently never match a tile.
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      for (const v of Object.values(value as Record<string, unknown>)) {
        if (v !== 'skip' && v !== 'low_res') {
          throw error(400, "tile_overrides values must be 'skip' or 'low_res'");
        }
      }
      writes.push([key, value]);
    }
  }

  if (body.validate === true) {
    writes.push(['validated_at', new Date().toISOString()]);
    writes.push(['validated_by', user.id]);
  } else if (body.validate === false) {
    // Withdrawing an acceptance takes the sheet back out of the OCR queue.
    writes.push(['validated_at', null]);
    writes.push(['validated_by', null]);
  }

  if (!writes.length) throw error(400, 'Nothing to write');

  for (const [key, value] of writes) {
    const { error: err } = await supabase.rpc('set_triage_key', {
      p_map_id: mapId,
      p_key: key,
      p_value: value as never,
    });
    if (err) dbError(err, `Could not write triage.${key}`);
  }

  const { data: row, error: readErr } = await supabase
    .from('maps')
    .select('triage')
    .eq('id', mapId)
    .single();
  if (readErr) dbError(readErr, 'Could not read the triage back');

  const triage = (row?.triage ?? {}) as SavedTriage;
  return json({ triage, state: triageState(triage), wrote: writes.map(([k]) => k) });
};
