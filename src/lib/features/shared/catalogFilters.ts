/**
 * catalogFilters.ts — the pure row tests behind the catalog's facets, apart from
 * `catalogSearch` (which imports `$app` and so cannot run in the browser-less checks).
 *
 * A facet is a test on one row. Every group's selection lives in one `Selected` record, and the
 * year range is two strings under `year` — `[from, to]`, either of which may be empty.
 */
export type Row = Record<string, any>;
export type Selected = Record<string, string[]>;

/** A survey sheet carries a series key; a city plan or a one-off does not. */
export const isSurvey = (r: Row) => !!r.series_key;

/** Area is `maps.region` — the province, derived from the bbox (mig 109). `location` is the
 *  hand-written place and is filled on the one-off plans only, so it filters nothing on a survey. */
export const passArea = (r: Row, sel: Selected) =>
  !sel.area?.length || sel.area.includes(String(r.region ?? ''));
export const passType = (r: Row, sel: Selected) =>
  !sel.type?.length || sel.type.includes(String(r.map_type ?? ''));
export const passInstitution = (r: Row, sel: Selected) =>
  !sel.institution?.length || sel.institution.includes(String(r.holding_institution ?? ''));

/** `kind` is `surveys` or `plans` (everything that is not a survey sheet); empty means both. */
export const passKind = (r: Row, sel: Selected) => {
  const k = sel.kind?.[0];
  return !k || (k === 'surveys' ? isSurvey(r) : !isSurvey(r));
};

/** The selected range as numbers, open ends as ±Infinity; null when no range is set. */
export function yearRange(sel: Selected): [number, number] | null {
  const [a, b] = sel.year ?? [];
  const from = a ? Number(a) : -Infinity;
  const to = b ? Number(b) : Infinity;
  if (Number.isNaN(from) || Number.isNaN(to)) return null;
  return from === -Infinity && to === Infinity ? null : [from, to];
}

/** A row with no year cannot be inside a range, so a range excludes it. */
export const passYear = (r: Row, sel: Selected) => {
  const range = yearRange(sel);
  if (!range) return true;
  return r.year != null && r.year >= range[0] && r.year <= range[1];
};

/** Rows per decade, oldest first — the histogram under the year range. Decades with none are kept
 *  between the first and last, so a gap in the archive shows as a gap. */
export function decadeBins(rows: Row[]): { decade: number; count: number }[] {
  const counts = new Map<number, number>();
  for (const r of rows) {
    if (r.year == null) continue;
    const d = Math.floor(r.year / 10) * 10;
    counts.set(d, (counts.get(d) ?? 0) + 1);
  }
  if (!counts.size) return [];
  const ds = [...counts.keys()];
  const out: { decade: number; count: number }[] = [];
  for (let d = Math.min(...ds); d <= Math.max(...ds); d += 10)
    out.push({ decade: d, count: counts.get(d) ?? 0 });
  return out;
}
