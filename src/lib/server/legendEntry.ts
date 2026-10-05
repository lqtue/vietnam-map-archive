/** Existing OCR legend notes carry number, translation and grid references. */
export function legendNote(notes: string | null, key: string): string | null {
  return (
    notes
      ?.split(';')
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${key}=`))
      ?.slice(key.length + 1)
      .trim() || null
  );
}

export function legendNumber(text: string | null, notes: string | null): number | null {
  const match = /^(\d+)\.\s*/.exec(text ?? '');
  const number = Number(match?.[1] ?? legendNote(notes, 'n'));
  return Number.isSafeInteger(number) && number > 0 ? number : null;
}

function pair(raw: string | null): [number, number] | null {
  const parts = raw?.split(',') ?? [];
  if (parts.length !== 2 || parts.some((part) => !part.trim())) return null;
  const [a, b] = parts.map(Number);
  return Number.isFinite(a) && Number.isFinite(b) ? [a, b] : null;
}

/**
 * A staff-placed position, kept in image pixels (`px=x,y`) so it is a fact
 * about the sheet and follows any later re-georeference. `point=lng,lat` is the
 * pre-2026-10-05 form, read until `scripts/oneoff/legend_points_to_pixels.mjs`
 * has converted every row; a save rewrites it as `px=`.
 */
export function manualLegendPoint(
  notes: string | null
): { px: [number, number] } | { lngLat: [number, number] } | null {
  const px = pair(legendNote(notes, 'px'));
  if (px && px[0] >= 0 && px[1] >= 0) return { px };
  const ll = pair(legendNote(notes, 'point'));
  return ll && Math.abs(ll[0]) <= 180 && Math.abs(ll[1]) <= 90 ? { lngLat: ll } : null;
}

export type PixelRect = { x: number; y: number; w: number; h: number };

export function inRects(rects: readonly PixelRect[], x: number, y: number): boolean {
  return rects.some((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
}

/**
 * A body numeral that could name a legend entry: bare digits, 1..maxN, with a
 * pixel box, centred outside the legend box (a number inside it is a column of
 * the index itself). Returns its centre in image pixels, or null.
 */
export function numeralCandidate(
  row: {
    text: string | null;
    text_corrected: string | null;
    global_x: number | null;
    global_y: number | null;
    global_w: number | null;
    global_h: number | null;
  },
  maxN: number,
  rects: readonly PixelRect[]
): { n: number; x: number; y: number } | null {
  const t = (row.text_corrected ?? row.text ?? '').trim();
  if (!/^\d+$/.test(t)) return null;
  const n = parseInt(t, 10);
  if (n < 1 || n > maxN) return null;
  if (row.global_x == null || row.global_y == null) return null;
  const x = row.global_x + (row.global_w || 0) / 2;
  const y = row.global_y + (row.global_h || 0) / 2;
  return inRects(rects, x, y) ? null : { n, x, y };
}

/** Replace only the fields being edited; keep unrelated OCR/provenance notes. */
export function editLegendNotes(
  notes: string | null,
  fields: { vn: string | null; grid: string | null; px: [number, number] | null }
): string {
  const retained = (notes ?? '')
    .split(';')
    .map((part) => part.trim())
    .filter((part) => part && !/^(vn|grid|point|px)=/.test(part));
  if (fields.vn) retained.push(`vn=${fields.vn}`);
  if (fields.grid) retained.push(`grid=${fields.grid}`);
  if (fields.px) retained.push(`px=${fields.px.map((v) => Math.round(v)).join(',')}`);
  return retained.join('; ');
}
