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

export function manualLegendPoint(notes: string | null): [number, number] | null {
  const raw = legendNote(notes, 'point');
  if (!raw) return null;
  const parts = raw.split(',');
  if (parts.length !== 2 || parts.some((part) => !part.trim())) return null;
  const [lng, lat] = parts.map(Number);
  return Number.isFinite(lng) && Number.isFinite(lat) && Math.abs(lng) <= 180 && Math.abs(lat) <= 90
    ? [lng, lat]
    : null;
}

/** Replace only the fields being edited; keep unrelated OCR/provenance notes. */
export function editLegendNotes(
  notes: string | null,
  fields: { vn: string | null; grid: string | null; point: [number, number] | null }
): string {
  const retained = (notes ?? '')
    .split(';')
    .map((part) => part.trim())
    .filter((part) => part && !/^(vn|grid|point)=/.test(part));
  if (fields.vn) retained.push(`vn=${fields.vn}`);
  if (fields.grid) retained.push(`grid=${fields.grid}`);
  if (fields.point) retained.push(`point=${fields.point.join(',')}`);
  return retained.join('; ');
}
