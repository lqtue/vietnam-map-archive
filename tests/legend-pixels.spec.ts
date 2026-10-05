/**
 * The pixel side of the legend tool: which body numerals can name an entry,
 * whether one agrees with the index cell, which entry is next and which numeral
 * Enter takes. The public ground-space GET and the staff pixel GET share the
 * first two, so one reading cannot drift from the other.
 */
import { test, expect } from '@playwright/test';
import { numeralCandidate } from '../src/lib/server/legendEntry';
import { cellAgreement } from '../src/lib/core/geo/mapGrid';
import {
  bestCandidate,
  nextUnplaced,
  type LegendRow,
} from '../src/lib/features/contribute/legend/legendStage';

const box = (text: string, x: number, y: number) => ({
  text,
  text_corrected: null,
  global_x: x,
  global_y: y,
  global_w: 10,
  global_h: 10,
});
const legendBox = [{ x: 0, y: 0, w: 100, h: 100 }];

test('a numeral is a bare number up to the legend size, outside the legend box', () => {
  expect(numeralCandidate(box('7', 500, 500), 20, legendBox)).toEqual({ n: 7, x: 505, y: 505 });
  expect(numeralCandidate(box('21', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('0', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('7a', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('7', 20, 20), 20, legendBox)).toBeNull();
  expect(numeralCandidate({ ...box('7', 500, 500), global_x: null }, 20, legendBox)).toBeNull();
});

test('a numeral agrees with its index cell within one cell, and says nothing without a grid', () => {
  const grid = {
    bbox: [0, 0, 400, 400] as [number, number, number, number],
    columns: ['1', '2', '3', '4'],
    rows: ['A', 'B', 'C', 'D'],
  };
  // "B 2" is the box x 100..200, y 100..200, with one cell of slack each side.
  expect(cellAgreement(grid, 'B 2', 150, 150)).toBe(true);
  expect(cellAgreement(grid, 'B 2', 290, 150)).toBe(true);
  expect(cellAgreement(grid, 'B 2', 350, 150)).toBe(false);
  expect(cellAgreement(null, 'B 2', 150, 150)).toBeNull();
  expect(cellAgreement(grid, null, 150, 150)).toBeNull();
  expect(cellAgreement(grid, 'Z 9', 150, 150)).toBeNull();
});

const row = (n: number, x: number | null): LegendRow => ({
  id: `id${n}`,
  n,
  name: `Name ${n}`,
  vn: null,
  grid: null,
  x,
  y: x,
  validated: false,
});

test('n walks to the next unplaced entry, wrapping; Enter never takes a disagreeing numeral', () => {
  const rows = [row(1, 5), row(2, null), row(3, 5), row(4, null)];
  expect(nextUnplaced(rows, null)?.n).toBe(2);
  expect(nextUnplaced(rows, 'id2')?.n).toBe(4);
  expect(nextUnplaced(rows, 'id4')?.n).toBe(2);
  expect(nextUnplaced([row(1, 5)], 'id1')).toBeNull();

  const c = (inCell: boolean | null, labelId: string) => ({ n: 2, x: 1, y: 1, inCell, labelId });
  expect(bestCandidate([c(null, 'a'), c(true, 'b')], 2)?.labelId).toBe('b');
  expect(bestCandidate([c(null, 'a')], 2)?.labelId).toBe('a');
  expect(bestCandidate([c(false, 'a')], 2)).toBeNull();
  expect(bestCandidate([c(true, 'a')], 3)).toBeNull();
});
