/**
 * The two reads a legend needs, shared by the public ground-space GET and the
 * staff pixel-space GET: the numbered entries (with the box they were printed
 * in) and the body numerals that might mark them. Those reads are pixels;
 * `warpLegend` is the one place they become points on the ground.
 */
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { readAll } from '$lib/data/supabase/paged';
import {
  extraLegendPoints,
  legendNote,
  manualLegendPoint,
  numeralCandidate,
  type PixelRect,
} from '$lib/server/legendEntry';
import { getTransformer, type AnnotationTransform } from '$lib/server/transformer';
import {
  cellAgreement,
  cellCentre,
  cellSize,
  parseGrid,
  type MapGrid,
} from '$lib/core/geo/mapGrid';
import type { SavedTriage } from '$lib/data/maps/triageTypes';

export type LegendInfo = {
  id: string;
  name: string;
  vn: string | null;
  grid: string | null;
  manualPoint: ReturnType<typeof manualLegendPoint>;
  /** Further pixel positions of the same entry; see `extraLegendPoints`. */
  more: [number, number][];
  validated: boolean;
};

export async function readLegendEntries(
  supabase: ReturnType<typeof adminClient>,
  mapId: string
): Promise<{ nameByN: Map<number, LegendInfo>; rects: PixelRect[]; maxN: number }> {
  // Skip rows a human rejected; prefer their corrected text over the raw model
  // output so HITL fixes actually reach the map.
  const { data: entries, error: entryError } = await readAll((from, to) =>
    supabase
      .from('ocr_labels')
      .select(
        'id,run_id,text,text_corrected,notes,review_status,tile_x,tile_y,tile_w,tile_h,global_x,global_y,global_w,global_h'
      )
      .eq('map_id', mapId)
      .eq('category', 'legend_entry')
      .neq('review_status', 'rejected')
      .order('id')
      .range(from, to)
  );
  if (entryError) dbError(entryError, 'Could not read legend entries');

  const nameByN = new Map<number, LegendInfo>();
  const legendBounds = new Map<
    string,
    { minX: number; minY: number; maxX: number; maxY: number }
  >();
  for (const e of entries ?? []) {
    const eText = e.text_corrected ?? e.text;
    const m = /^(\d+)\.\s*(.*)$/.exec(eText ?? '');
    const n = m ? parseInt(m[1], 10) : parseInt(/n=(\d+)/.exec(e.notes ?? '')?.[1] ?? '', 10);
    if (!Number.isFinite(n)) continue;
    const grid = legendNote(e.notes, 'grid');
    const vn = legendNote(e.notes, 'vn');
    if (!nameByN.get(n)?.validated || e.review_status === 'validated')
      nameByN.set(n, {
        id: e.id,
        name: m ? m[2] : (eText ?? ''),
        vn,
        grid,
        manualPoint: e.review_status === 'validated' ? manualLegendPoint(e.notes) : null,
        more: e.review_status === 'validated' ? extraLegendPoints(e.notes) : [],
        validated: e.review_status === 'validated',
      });
    if (e.global_x != null && e.global_y != null) {
      const key = e.run_id ?? 'default';
      const x = e.global_x;
      const y = e.global_y;
      const maxX = x + (e.global_w ?? 0);
      const maxY = y + (e.global_h ?? 0);
      const bounds = legendBounds.get(key);
      if (bounds) {
        bounds.minX = Math.min(bounds.minX, x);
        bounds.minY = Math.min(bounds.minY, y);
        bounds.maxX = Math.max(bounds.maxX, maxX);
        bounds.maxY = Math.max(bounds.maxY, maxY);
      } else {
        legendBounds.set(key, { minX: x, minY: y, maxX, maxY });
      }
    } else if (e.tile_w && e.tile_h) {
      // Old extractions may not have per-label pixel bounds. Their tile rect
      // is a coarse fallback for the printed index region.
      const key = e.run_id ?? 'default';
      const x = e.tile_x ?? 0;
      const y = e.tile_y ?? 0;
      const bounds = legendBounds.get(key);
      if (bounds) {
        bounds.minX = Math.min(bounds.minX, x);
        bounds.minY = Math.min(bounds.minY, y);
        bounds.maxX = Math.max(bounds.maxX, x + e.tile_w);
        bounds.maxY = Math.max(bounds.maxY, y + e.tile_h);
      } else {
        legendBounds.set(key, { minX: x, minY: y, maxX: x + e.tile_w, maxY: y + e.tile_h });
      }
    }
  }
  const rects = [...legendBounds.values()].map((bounds) => ({
    x: bounds.minX,
    y: bounds.minY,
    w: bounds.maxX - bounds.minX,
    h: bounds.maxY - bounds.minY,
  }));
  const maxN = nameByN.size ? Math.max(...nameByN.keys()) : 0;
  return { nameByN, rects, maxN };
}

/**
 * Feature-reference numerals: bare digits sitting out on the map body. Gemini
 * tags them 'other'; the old Tesseract pass used 'legend_ref'. Either way the
 * digit + ≤maxN + outside-legend-box filters isolate the real refs.
 */
export async function readNumeralCandidates(
  supabase: ReturnType<typeof adminClient>,
  mapId: string,
  maxN: number,
  rects: PixelRect[]
): Promise<{ n: number; x: number; y: number; labelId: string }[]> {
  const { data: refs, error: refError } = await readAll((from, to) =>
    supabase
      .from('ocr_labels')
      .select('id, text, text_corrected, global_x, global_y, global_w, global_h')
      .eq('map_id', mapId)
      .in('category', ['legend_ref', 'other'])
      .neq('review_status', 'rejected')
      .order('id')
      .range(from, to)
  );
  if (refError) dbError(refError, 'Could not read legend references');
  return (refs ?? []).flatMap((r) => {
    const c = numeralCandidate(r, maxN, rects);
    return c ? [{ ...c, labelId: r.id }] : [];
  });
}

export type LegendPoint = {
  n: number;
  name: string | null;
  vn: string | null;
  grid: string | null;
  lng: number;
  lat: number;
  src: 'numeral' | 'grid' | 'manual';
  accuracy_m?: number;
};

/**
 * Entries + numerals → points on the ground, one per number (`points`), plus the
 * further plots of a multi-plot entry (`more`). Reviewed manual position wins,
 * then an agreeing numeral, then the printed grid cell. With no transformer only
 * a legacy lng/lat manual point can still be placed.
 */
export function warpLegend(
  nameByN: Map<number, LegendInfo>,
  candidates: { n: number; x: number; y: number }[],
  grid: MapGrid | null,
  transformer: AnnotationTransform['transformer'] | null
): { points: LegendPoint[]; more: LegendPoint[] } {
  const toGeo = transformer
    ? (px: [number, number]) => transformer.transformToGeo(px) as [number, number]
    : null;
  // A manual point is stored in image pixels; with no georeference only a
  // legacy lng/lat one can still be placed.
  const manual = [...nameByN].flatMap(([n, info]): LegendPoint[] => {
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
  if (!transformer || !toGeo) return { points: manual, more: [] };

  // Further positions of an entry that has a reviewed first one (pixels → ground).
  const more = [...nameByN].flatMap(([n, info]) =>
    info.manualPoint
      ? info.more.map((px): LegendPoint => {
          const [lng, lat] = toGeo(px);
          return { n, name: info.name, vn: info.vn, grid: info.grid, lng, lat, src: 'manual' };
        })
      : []
  );

  const byN = new Map<number, LegendPoint>(manual.map((point) => [point.n, point]));
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
  return { points: [...byN.values()].sort((a, b) => a.n - b.n), more };
}

/** The ids, among `mapIds`, of maps that carry at least one live legend entry. */
export async function mapsWithLegend(
  supabase: ReturnType<typeof adminClient>,
  mapIds: string[]
): Promise<Set<string>> {
  if (!mapIds.length) return new Set();
  const { data, error } = await readAll((from, to) =>
    supabase
      .from('ocr_labels')
      .select('id, map_id')
      .in('map_id', mapIds)
      .eq('category', 'legend_entry')
      .neq('review_status', 'rejected')
      .order('id')
      .range(from, to)
  );
  if (error) dbError(error, 'Could not read legend entries');
  return new Set(data.map((row) => row.map_id));
}

/** One map's legend on the ground: every read, the transformer, `warpLegend`. */
export async function readWarpedLegend(
  supabase: ReturnType<typeof adminClient>,
  map: { id: string; allmaps_id: string | null; annotation_url: string | null; triage: unknown }
): Promise<LegendPoint[]> {
  const { nameByN, rects, maxN } = await readLegendEntries(supabase, map.id);
  if (!nameByN.size) return [];
  const [candidates, resolved] = await Promise.all([
    readNumeralCandidates(supabase, map.id, maxN, rects),
    getTransformer(map.allmaps_id, map.annotation_url),
  ]);
  if (!resolved) return [];
  const grid = parseGrid((map.triage as SavedTriage | null)?.grid);
  const { points, more } = warpLegend(nameByN, candidates, grid, resolved.transformer);
  return [...points, ...more];
}
