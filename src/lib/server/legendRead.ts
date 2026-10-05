/**
 * The two reads a legend needs, shared by the public ground-space GET and the
 * staff pixel-space GET: the numbered entries (with the box they were printed
 * in) and the body numerals that might mark them. Everything here is pixels.
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
