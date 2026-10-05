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
 * Response: { points: [{ n, name, vn, grid, lng, lat, src, accuracy_m? }], reason? }
 */

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid } from '$lib/server/http';
import { getRole } from '$lib/server/auth';
import { readLegendEntries, readNumeralCandidates } from '$lib/server/legendRead';
import { getTransformer } from '$lib/server/transformer';
import { cellAgreement, cellCentre, cellSize, parseGrid } from '$lib/core/geo/mapGrid';
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

  type Point = {
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number;
    lat: number;
    src: 'numeral' | 'grid' | 'manual';
    accuracy_m?: number;
  };
  // A manual point is stored in image pixels; with no georeference only a
  // legacy lng/lat one can still be placed.
  const placeManual = (toGeo: ((px: [number, number]) => [number, number]) | null): Point[] =>
    [...nameByN].flatMap(([n, info]): Point[] => {
      const p = info.manualPoint;
      const ll = !p ? null : 'lngLat' in p ? p.lngLat : toGeo ? toGeo(p.px) : null;
      return ll
        ? [
            {
              n,
              name: info.name,
              vn: info.vn,
              grid: info.grid,
              lng: ll[0],
              lat: ll[1],
              src: 'manual',
            },
          ]
        : [];
    });
  function response(points: Point[], reason?: string) {
    return json(
      {
        points,
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
  if (!resolved) return response(placeManual(null), 'no annotation');
  const { transformer } = resolved;
  const manual = placeManual((px) => transformer.transformToGeo(px) as [number, number]);

  // Parsed before the numerals, because it is what decides whether to believe
  // them.
  const grid = parseGrid((map.triage as SavedTriage | null)?.grid);

  const byN = new Map<number, Point>(manual.map((point) => [point.n, point]));
  for (const { n, x: cx, y: cy } of candidates) {
    if (nameByN.get(n)?.manualPoint) continue;
    if (cellAgreement(grid, nameByN.get(n)?.grid, cx, cy) === false) continue; // not this reference
    const [lng, lat] = transformer.transformToGeo([cx, cy]);
    const info = nameByN.get(n);
    byN.set(n, {
      n,
      name: info?.name ?? null,
      vn: info?.vn ?? null,
      grid: info?.grid ?? null,
      lng,
      lat,
      src: 'numeral',
    });
  }

  // Fall back to the printed grid for entries no numeral was found for. This is
  // most of them: spotting small digits scattered over a city sheet is the hard
  // half, while the index already states a cell for every row it carries.
  if (grid) {
    const cell = cellSize(grid);
    for (const [n, info] of nameByN) {
      if (byN.has(n) || !info.grid) continue;
      const centre = cellCentre(grid, info.grid);
      if (!centre) continue;
      const [lng, lat] = transformer.transformToGeo(centre);
      // The error bar, in metres on the ground: half a cell diagonal, measured
      // through the same georeference rather than assumed from the scale bar.
      let accuracy_m: number | undefined;
      if (cell) {
        const [lng2, lat2] = transformer.transformToGeo([
          centre[0] + cell.w / 2,
          centre[1] + cell.h / 2,
        ]);
        const dx = (lng2 - lng) * 111320 * Math.cos((lat * Math.PI) / 180);
        const dy = (lat2 - lat) * 110574;
        accuracy_m = Math.round(Math.hypot(dx, dy));
      }
      byN.set(n, {
        n,
        name: info.name,
        vn: info.vn,
        grid: info.grid,
        lng,
        lat,
        src: 'grid',
        ...(accuracy_m ? { accuracy_m } : {}),
      });
    }
  }

  const points = [...byN.values()].sort((a, b) => a.n - b.n);
  return response(points);
};
