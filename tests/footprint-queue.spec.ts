import { test, expect } from '@playwright/test';
import { readAllPages } from '../src/lib/data/supabase/footprints';

// The review queue read an unbounded select, so a sheet with more than 1000
// proposals showed the first 1000 and no error. The 1882 colour run has 1,443.

function pages(total: number, ranges: [number, number][]) {
  return (from: number, to: number) => {
    ranges.push([from, to]);
    const rows = [];
    for (let i = from; i <= Math.min(to, total - 1); i++) rows.push(i);
    return Promise.resolve({ data: rows, error: null });
  };
}

test('a queue longer than one page is read whole', async () => {
  const ranges: [number, number][] = [];
  const rows = await readAllPages(pages(1443, ranges));
  expect(rows).toHaveLength(1443);
  expect(ranges).toEqual([
    [0, 999],
    [1000, 1999],
  ]);
});

test('a queue that exactly fills a page still stops', async () => {
  const ranges: [number, number][] = [];
  expect(await readAllPages(pages(1000, ranges))).toHaveLength(1000);
  expect(ranges).toHaveLength(2);
});

test('a failing page throws instead of returning a short queue', async () => {
  await expect(
    readAllPages(() => Promise.resolve({ data: null, error: { message: 'boom' } }))
  ).rejects.toThrow('boom');
});
