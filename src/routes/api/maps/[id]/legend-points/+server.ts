/**
 * GET /api/maps/[id]/legend-points
 *
 * Public. Returns the map's numbered-legend references placed on the ground.
 *
 * Three ways an entry gets a position, and the response says which:
 *   src: 'manual' — a reviewed position explicitly placed by staff. Wins over OCR/grid.
 *
 *   src: 'numeral' — a body numeral (category 'legend_ref') warped to lng/lat.
 *     Exact, but only for numerals the OCR pass actually spotted.
 *   src: 'grid' — the cell the printed index names ("J 6") turned into a point
 *     via `maps.triage.grid`. Covers every entry that carries a reference and
 *     costs no OCR, but it is the middle of a cell: `accuracy_m` says how big.
 *
 * A numeral wins over a grid cell for the same number — but only if the two
 * agree. On the 1968 Saigon sheet this rejects nothing today: all 15 numerals
 * fall within a cell of where the index puts them, median 384 m against a 704 m
 * half-cell. It is here for the numerals pass to come. Spotting small digits
 * across a city sheet produces false positives by nature, and an index that
 * independently states a cell for every entry is the only cheap check on them
 * — the two readings are unrelated, so agreement is evidence and a numeral
 * kilometres outside its stated cell is a misread, not a discovery.
 *
 * Legend-internal numbers (those inside the legend box) are dropped — only
 * numerals out on the map body count.
 *
 * Response: { points: [{ n, name, vn, grid, lng, lat, src, accuracy_m? }], more, reason? }
 *
 * `points` is one per number — the list and the fly-to rely on that. `more`
 * is the further positions of a number printed on several plots (same shape,
 * `src: 'manual'`), for the map's pins only.
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { getRole } from '$lib/server/auth';
import {
  readLegendEntries,
  readNumeralCandidates,
  warpLegend,
  type LegendPoint,
} from '$lib/server/legendRead';
import { getTransformer } from '$lib/server/transformer';
import { parseGrid } from '$lib/core/geo/mapGrid';
import type { SavedTriage } from '$lib/data/maps/triageTypes';

export const GET: RequestHandler = async ({ params, locals }) => {
  const mapId = assertUuid(params.id, 'map id');
  const supabase = adminClient();
  const role = await getRole(locals);
  const canEdit = role === 'admin' || role === 'mod';

  const { data: map } = await supabase
    .from('maps')
    .select('allmaps_id, annotation_url, status, triage')
    .eq('id', mapId)
    .single();
  // Public route on the service-role client: never serve draft maps.
  if (!map || !['public', 'featured'].includes(map.status ?? ''))
    return json({ points: [], reason: 'not public' });
  // Either source counts: pipeline-made georeferences (the Indochine 1:100,000
  // halves) carry an `annotation_url` and no `allmaps_id` — Allmaps never held them.

  // Legend entries → number→name map + the legend box rect (shared tile bbox),
  // and the numerals out on the map body that might mark them.
  const { nameByN, rects, maxN } = await readLegendEntries(supabase, mapId);
  const candidates = await readNumeralCandidates(supabase, mapId, maxN, rects);

  function response(points: LegendPoint[], reason?: string, more: LegendPoint[] = []) {
    return json(
      {
        points,
        more,
        reason,
        canEdit,
        ...(canEdit
          ? {
              entries: [...nameByN]
                .map(([n, info]) => {
                  const point = points.find((item) => item.n === n);
                  return {
                    id: info.id,
                    n,
                    name: info.name,
                    vn: info.vn,
                    grid: info.grid,
                    lng: point?.lng ?? null,
                    lat: point?.lat ?? null,
                    src: point?.src ?? null,
                  };
                })
                .sort((a, b) => a.n - b.n),
            }
          : {}),
      },
      { headers: { 'Cache-Control': 'private, no-store' } }
    );
  }

  // Build the pixel→geo transformer from the stored annotation (mirror override
  // first, else the public Allmaps annotation).
  const resolved = await getTransformer(map.allmaps_id, map.annotation_url);
  const grid = parseGrid((map.triage as SavedTriage | null)?.grid);
  const { points, more } = warpLegend(nameByN, candidates, grid, resolved?.transformer ?? null);
  return response(points, resolved ? undefined : 'no annotation', more);
};
