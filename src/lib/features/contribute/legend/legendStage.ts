/** Pure helpers for the legend tool: which entry is next, which numeral to accept. */

export type LegendRow = {
  id: string;
  n: number;
  name: string;
  vn: string | null;
  grid: string | null;
  x: number | null;
  y: number | null;
  validated: boolean;
};

export type LegendCandidate = {
  n: number;
  x: number;
  y: number;
  inCell: boolean | null;
  labelId: string;
};

/** The next row after `afterId` (wrapping) that has no position; null when all are placed. */
export function nextUnplaced(rows: readonly LegendRow[], afterId: string | null): LegendRow | null {
  const from = rows.findIndex((row) => row.id === afterId);
  for (let i = 1; i <= rows.length; i++) {
    const row = rows[(from + i + rows.length) % rows.length];
    if (row.x == null) return row;
  }
  return null;
}

/**
 * The numeral Enter accepts for entry `n`: one that agrees with the index cell
 * wins over one with nothing to check against. A numeral that disagrees is
 * never taken without a click.
 */
export function bestCandidate(
  candidates: readonly LegendCandidate[],
  n: number
): LegendCandidate | null {
  const mine = candidates.filter((c) => c.n === n && c.inCell !== false);
  return mine.find((c) => c.inCell === true) ?? mine[0] ?? null;
}

/** Per-map progress: entries read off the legend, and how many have a point. */
export type LegendStats = Record<string, { total: number; placed: number }>;
export type MapStatus = 'todo' | 'doing' | 'done' | 'none';

export function mapStatus(s: { total: number; placed: number } | undefined): MapStatus {
  if (!s || !s.total) return 'none';
  return s.placed === 0 ? 'todo' : s.placed >= s.total ? 'done' : 'doing';
}

export type RowFilter = 'all' | 'unplaced' | 'placed' | 'edited';
export type RowSort = 'n' | 'name' | 'grid' | 'unplaced';

const plain = (text: string | null) =>
  (text ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

/**
 * The legend list as shown: filtered, searched (number, name, Vietnamese name,
 * grid; accents ignored), then sorted. The `keepId` row always stays so the
 * entry being edited does not vanish under its own edit.
 */
export function visibleRows(
  rows: readonly LegendRow[],
  opts: {
    filter: RowFilter;
    sort: RowSort;
    query: string;
    staged: ReadonlySet<string>;
    keepId: string | null;
  }
): LegendRow[] {
  const q = plain(opts.query.trim());
  const kept = rows.filter((row) => {
    if (row.id === opts.keepId) return true;
    if (opts.filter === 'unplaced' && row.x != null) return false;
    if (opts.filter === 'placed' && row.x == null) return false;
    if (opts.filter === 'edited' && !opts.staged.has(row.id)) return false;
    return !q || plain(`${row.n} ${row.name} ${row.vn ?? ''} ${row.grid ?? ''}`).includes(q);
  });
  const text = (a: string | null, b: string | null) =>
    (a ?? '').localeCompare(b ?? '', undefined, { numeric: true });
  const by: Record<RowSort, (a: LegendRow, b: LegendRow) => number> = {
    n: (a, b) => a.n - b.n,
    name: (a, b) => text(a.name, b.name),
    // An entry with no grid reference sorts last, not first.
    grid: (a, b) => (a.grid ? 0 : 1) - (b.grid ? 0 : 1) || text(a.grid, b.grid) || a.n - b.n,
    unplaced: (a, b) => (a.x == null ? 0 : 1) - (b.x == null ? 0 : 1) || a.n - b.n,
  };
  return [...kept].sort(by[opts.sort]);
}
