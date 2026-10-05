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
