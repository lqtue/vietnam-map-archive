/**
 * Public, read-only snapshot of CartoMundi's Indochina series that may cover
 * Vietnam and the Nakala items VMA has actually checked. The snapshot is built
 * by scripts/cartomundi_rights_index.mjs; a zero item count means unchecked,
 * never that a series has no scans.
 */
import snapshot from './cartomundiIndex.json';

export type CartomundiSeries = (typeof snapshot.series)[number];
export type CartomundiItem = (typeof snapshot.items)[number];
export interface CartomundiSheetRecord {
  seriesId: string;
  fkey: string | number | null;
  number: string | null;
  title: string | null;
  year: number | null;
  bbox: (string | null)[] | null;
}
export type CartomundiSheet = CartomundiSheetRecord & {
  linkedItems: Pick<CartomundiItem, 'doi' | 'license'>[];
};

export function cartomundiSeries(): CartomundiSeries[] {
  return snapshot.series;
}

export function cartomundiSummary() {
  return snapshot.summary;
}

export function cartomundiSeriesById(id: string): CartomundiSeries | null {
  return snapshot.series.find((series) => series.id === id) ?? null;
}

export function cartomundiItemsBySeries(id: string): CartomundiItem[] {
  return snapshot.items.filter((item) => item.seriesId === id);
}

export function cartomundiSheetsBySeries(id: string): CartomundiSheet[] {
  const itemsByKey = new Map<string, Pick<CartomundiItem, 'doi' | 'license'>[]>();
  for (const item of snapshot.items) {
    if (item.seriesId !== id || !item.fkey) continue;
    const linked = itemsByKey.get(item.fkey) ?? [];
    linked.push({ doi: item.doi, license: item.license });
    itemsByKey.set(item.fkey, linked);
  }
  return (snapshot.sheets as CartomundiSheetRecord[])
    .filter((sheet) => sheet.seriesId === id)
    .map((sheet) => ({ ...sheet, linkedItems: itemsByKey.get(String(sheet.fkey)) ?? [] }));
}
