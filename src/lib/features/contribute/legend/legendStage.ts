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
