/**
 * Pure checks for the catalog's drawn slice and the two-page read. No browser, no network.
 *
 * They exist because `catalog-list-speed` draws the first 100 rows and the rest on scroll: a slice
 * that cut a group's count, dropped a group heading, or a read that lost the second page would look
 * like a smaller archive rather than like a bug.
 */
import { test, expect } from '@playwright/test';
import { sliceGroups } from '../src/lib/features/catalog/sliceGroups';
import { readAllParallel } from '../src/lib/data/supabase/paged';

test('sliceGroups cuts across groups, keeps each group full count', () => {
  const groups = [
    { label: 'a', rows: [1, 2, 3] },
    { label: 'b', rows: [4, 5, 6, 7] },
    { label: 'c', rows: [8] },
  ];
  const s = sliceGroups(groups, 5);
  expect(s.map((g) => [g.label, g.rows, g.count])).toEqual([
    ['a', [1, 2, 3], 3],
    ['b', [4, 5], 4],
  ]);
  expect(sliceGroups(groups, 99).flatMap((g) => g.rows)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  // The ungrouped table is one group with a null label.
  expect(sliceGroups([{ label: null, rows: [1, 2, 3] }], 2)[0].rows).toEqual([1, 2]);
});

test('readAllParallel returns every row for 0, 1, 2 and 3 pages, and passes an error through', async () => {
  const table = (n: number) => Array.from({ length: n }, (_, i) => i);
  const pager = (n: number) => async (from: number, to: number) => ({
    data: table(n).slice(from, to + 1),
    error: null as unknown,
  });
  for (const n of [0, 999, 1000, 1001, 2000, 2500]) {
    const { data, error } = await readAllParallel(pager(n));
    expect(error).toBeNull();
    expect(data).toEqual(table(n));
  }
  const bad = await readAllParallel(async () => ({ data: null, error: new Error('x') }));
  expect(bad.error).toBeTruthy();
});
