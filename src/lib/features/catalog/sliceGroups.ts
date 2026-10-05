/**
 * The first `n` rows across the groups, in order. Sliced after grouping, so a group is never
 * split from its heading and its count stays honest: `count` is the group's full size, `rows` is
 * what is drawn.
 */
export function sliceGroups<T>(
  groups: { label: string | null; rows: T[] }[],
  n: number
): { label: string | null; rows: T[]; count: number }[] {
  const out: { label: string | null; rows: T[]; count: number }[] = [];
  let left = n;
  for (const g of groups) {
    if (left <= 0) break;
    out.push({ label: g.label, rows: g.rows.slice(0, left), count: g.rows.length });
    left -= g.rows.length;
  }
  return out;
}
