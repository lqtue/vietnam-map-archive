/**
 * GET /api/maps/[id]/legend-points
 *
 * Public. Returns the map's numbered-legend references placed on the ground.
 *
 * Two ways an entry gets a position, and the response says which:
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
import { getTransformer } from '$lib/server/transformer';
import { cellBox, cellCentre, cellSize, parseGrid } from '$lib/core/geo/mapGrid';
import type { SavedTriage } from '$lib/data/maps/triageTypes';

export const GET: RequestHandler = async ({ params }) => {
  const mapId = assertUuid(params.id, 'map id');
  const supabase = adminClient();

  const { data: map } = await supabase
    .from('maps')
    .select('allmaps_id, annotation_url, status, triage')
    .eq('id', mapId)
    .single();
  // Public route on the service-role client: never serve draft maps.
  if (!map || !['public', 'featured'].includes(map.status ?? ''))
    return json({ points: [], reason: 'not public' });
  if (!map.allmaps_id) return json({ points: [], reason: 'not georeferenced' });

  // Legend entries → number→name map + the legend box rect (shared tile bbox).
  // Skip rows a human rejected; prefer their corrected text over the raw model
  // output so HITL fixes actually reach the public map.
  const { data: entries } = await supabase
    .from('ocr_labels')
    .select('text, text_corrected, notes, tile_x, tile_y, tile_w, tile_h')
    .eq('map_id', mapId)
    .eq('category', 'legend_entry')
    .neq('review_status', 'rejected');

  const nameByN = new Map<number, { name: string; vn: string | null; grid: string | null }>();
  let rect: { x: number; y: number; w: number; h: number } | null = null;
  for (const e of entries ?? []) {
    const eText = e.text_corrected ?? e.text;
    const m = /^(\d+)\.\s*(.*)$/.exec(eText ?? '');
    const n = m ? parseInt(m[1], 10) : parseInt(/n=(\d+)/.exec(e.notes ?? '')?.[1] ?? '', 10);
    if (!Number.isFinite(n)) continue;
    const grid = /grid=([^;]+)/.exec(e.notes ?? '')?.[1]?.trim() ?? null;
    const vn = /vn=([^;]+)/.exec(e.notes ?? '')?.[1]?.trim() ?? null;
    nameByN.set(n, { name: m ? m[2] : (eText ?? ''), vn, grid });
    if (!rect && e.tile_w)
      rect = { x: e.tile_x ?? 0, y: e.tile_y ?? 0, w: e.tile_w, h: e.tile_h ?? 0 };
  }
  const maxN = nameByN.size ? Math.max(...nameByN.keys()) : 0;

  // Feature-reference numerals: bare digits sitting out on the map body. Gemini
  // tags them 'other'; the old Tesseract pass used 'legend_ref'. Either way the
  // digit + ≤maxN + outside-legend-box filters below isolate the real refs.
  const { data: refs } = await supabase
    .from('ocr_labels')
    .select('text, text_corrected, global_x, global_y, global_w, global_h')
    .eq('map_id', mapId)
    .in('category', ['legend_ref', 'other'])
    .neq('review_status', 'rejected');

  // Build the pixel→geo transformer from the stored annotation (mirror override
  // first, else the public Allmaps annotation).
  const resolved = await getTransformer(map.allmaps_id, map.annotation_url);
  if (!resolved) return json({ points: [], reason: 'no annotation' });
  const { transformer } = resolved;

  const inRect = (x: number, y: number) =>
    rect !== null && x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h;

  // Parsed before the numerals, because it is what decides whether to believe
  // them.
  const grid = parseGrid((map.triage as SavedTriage | null)?.grid);

  /**
   * Does this numeral land where its own index entry says it should?
   *
   * Tolerance is the stated cell inflated by a full cell on each side: the
   * index cell is itself approximate, and a feature near a boundary is often
   * catalogued one cell over. That still rejects a numeral kilometres away,
   * which is the failure this guards.
   */
  const agreesWithIndex = (n: number, px: number, py: number): boolean => {
    if (!grid) return true;
    const ref = nameByN.get(n)?.grid;
    if (!ref) return true; // nothing to check against
    const box = cellBox(grid, ref);
    const cell = cellSize(grid);
    if (!box || !cell) return true;
    return (
      px >= box[0] - cell.w &&
      px <= box[0] + box[2] + cell.w &&
      py >= box[1] - cell.h &&
      py <= box[1] + box[3] + cell.h
    );
  };

  type Point = {
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number;
    lat: number;
    src: 'numeral' | 'grid';
    accuracy_m?: number;
  };
  const byN = new Map<number, Point>();
  for (const r of refs ?? []) {
    const t = (r.text_corrected ?? r.text ?? '').trim();
    if (!/^\d+$/.test(t)) continue;
    const n = parseInt(t, 10);
    if (n < 1 || n > maxN) continue; // only numerals that name a legend entry
    if (r.global_x == null || r.global_y == null) continue;
    const cx = r.global_x + (r.global_w || 0) / 2;
    const cy = r.global_y + (r.global_h || 0) / 2;
    if (inRect(cx, cy)) continue; // drop legend-internal column numbers
    if (!agreesWithIndex(n, cx, cy)) continue; // a digit that is not this reference
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
      byN.set(n, { n, ...info, lng, lat, src: 'grid', ...(accuracy_m ? { accuracy_m } : {}) });
    }
  }

  const points = [...byN.values()].sort((a, b) => a.n - b.n);
  return json({ points });
};
