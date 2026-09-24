/**
 * Turning a printed index reference into a position. Getting this wrong puts
 * every point one cell out, which looks plausible on a map and is wrong by a
 * few hundred metres — the failure mode worth a test.
 *
 * Browser-less pure checks, riding the Playwright runner like the rest.
 */
import { test, expect } from '@playwright/test';
import {
  parseGridRef,
  parseGrid,
  cellBox,
  cellCentre,
  cellSize,
  type MapGrid,
} from '../src/lib/core/geo/mapGrid';

/** Letters across the top: 10x10 over 1000x1000 px, one cell is 100x100. */
const grid: MapGrid = {
  bbox: [0, 0, 1000, 1000],
  columns: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K'], // note: no I
  rows: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
};

/**
 * The other convention, and the one the real 1968 Saigon sheet uses: columns
 * numbered 1-13 across, rows lettered A-O down. Same reference strings, axes
 * the other way round. Assuming letters are always columns resolved all 244 of
 * that sheet's index entries to nothing.
 */
const saigon1968: MapGrid = {
  bbox: [281, 338, 10123, 11819],
  columns: Array.from({ length: 13 }, (_, i) => String(i + 1)),
  rows: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'],
};

test('a plain reference lands in the middle of its own cell', () => {
  // J is the 9th printed column (index 8) precisely because I is skipped.
  expect(cellCentre(grid, 'J 6')).toEqual([850, 550]);
  expect(cellBox(grid, 'J 6')).toEqual([800, 500, 100, 100]);
});

test('skipping I is why the printed labels are stored, not derived', () => {
  // Deriving columns from the alphabet would put J at index 9 and every point
  // from J onward one cell to the right.
  expect(cellCentre(grid, 'K 1')).toEqual([950, 50]);
  expect(cellCentre(grid, 'I 1')).toBeNull();
});

test('a reference spanning rows covers both, and centres between them', () => {
  // "J 5,6" on the real 1968 sheet: Chợ Rẫy Hospital straddles the boundary.
  expect(cellBox(grid, 'J 5,6')).toEqual([800, 400, 100, 200]);
  expect(cellCentre(grid, 'J 5,6')).toEqual([850, 500]);
});

test('a reference spanning columns does the same sideways', () => {
  // "G H 10" — Grall's Hospital.
  expect(cellBox(grid, 'G H 10')).toEqual([600, 900, 200, 100]);
  expect(cellCentre(grid, 'G H 10')).toEqual([700, 950]);
});

test('spacing and case in the reference do not matter', () => {
  const c = cellCentre(grid, 'J 6');
  for (const ref of ['J6', 'j 6', ' J  6 ', 'J/6', 'J;6']) {
    expect(cellCentre(grid, ref)).toEqual(c);
  }
});

test('a reference the grid does not contain is null, not a guess', () => {
  expect(cellCentre(grid, 'Z 3')).toBeNull();
  expect(cellCentre(grid, 'A 99')).toBeNull();
  expect(cellCentre(grid, '')).toBeNull();
  expect(cellCentre(grid, 'nonsense')).toBeNull();
});

test('an offset grid is not assumed to start at the sheet origin', () => {
  // The gridded area is inside the neatline, which is inside the paper.
  const offset: MapGrid = { ...grid, bbox: [500, 300, 1000, 1000] };
  expect(cellCentre(offset, 'A 1')).toEqual([550, 350]);
});

test('cell size is the error bar a caller should surface', () => {
  expect(cellSize(grid)).toEqual({ w: 100, h: 100 });
  expect(cellSize({ bbox: [0, 0, 100, 100], columns: [], rows: [] })).toBeNull();
});

test('parseGridRef returns the tokens and does not decide their axis', () => {
  expect(parseGridRef('G H 10')).toEqual(['G', 'H', '10']);
  expect(parseGridRef('J 5,6')).toEqual(['J', '5', '6']);
  expect(parseGridRef('')).toEqual([]);
});

test('the real sheet letters its ROWS, and the same code reads it', () => {
  const cw = 10123 / 13;
  const ch = 11819 / 15;
  // "J 6" = row J (index 9), column 6 (index 5).
  const [cx, cy] = cellCentre(saigon1968, 'J 6')!;
  expect(cx).toBeCloseTo(281 + 5 * cw + cw / 2, 3);
  expect(cy).toBeCloseTo(338 + 9 * ch + ch / 2, 3);
});

test('a run resolves on whichever axis carries those labels', () => {
  const ch = 11819 / 15;
  // "G H 10" — Grall's Hospital: rows G-H at column 10, not columns G-H.
  const box = cellBox(saigon1968, 'G H 10')!;
  expect(box[3]).toBeCloseTo(2 * ch, 3); // two rows tall
  expect(box[2]).toBeCloseTo(10123 / 13, 3); // one column wide

  // "J 5,6" — Chợ Rẫy: one row, two columns. The mirror image.
  const box2 = cellBox(saigon1968, 'J 5,6')!;
  expect(box2[2]).toBeCloseTo((2 * 10123) / 13, 3);
  expect(box2[3]).toBeCloseTo(ch, 3);
});

test('every reference in the real index resolves', () => {
  // Sampled verbatim from the 244 rows already in ocr_labels. A parser
  // that returns null for these is the bug this file exists to catch.
  for (const ref of ['J 6', 'H 8', 'K 7', 'J 5,6', 'G H 10', 'A 1', 'O 13']) {
    expect(cellCentre(saigon1968, ref), ref).not.toBeNull();
  }
});

test('a grid off the wire is validated, not trusted', () => {
  expect(
    parseGrid({ bbox: [0, 0, 100, 100], columns: ['A', 'B'], rows: ['1', '2'] })
  ).not.toBeNull();
  // A one-column "grid" is the model failing to read the margin.
  expect(parseGrid({ bbox: [0, 0, 100, 100], columns: ['A'], rows: ['1', '2'] })).toBeNull();
  expect(parseGrid({ bbox: [0, 0, 0, 100], columns: ['A', 'B'], rows: ['1', '2'] })).toBeNull();
  expect(
    parseGrid({ bbox: [0, 0, 100, Number.NaN], columns: ['A', 'B'], rows: ['1', '2'] })
  ).toBeNull();
  expect(parseGrid(null)).toBeNull();
});
