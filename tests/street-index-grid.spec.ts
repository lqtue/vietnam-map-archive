/**
 * A printed grid reference becomes a rectangle twice, and that is the point of
 * this file.
 *
 * `cellBox` in `src/lib/core/geo/mapGrid.ts` does it for the browser and for
 * `/api/maps/[id]/legend-points`. `_cell_rect` in `work/ocr/scripts/ocr.py`
 * does it headless, because `ocr street-index` reads a sheet's printed street
 * directory and has to write each street's position at upsert time — the
 * `ocr_labels` box columns are NOT NULL, so there is nothing to defer.
 *
 * A drift between the two does not look like a bug. It looks like a street a
 * few hundred metres from where it belongs, on a map where everything is a few
 * hundred metres from something. So the Python side generates the fixture and
 * this asserts the TypeScript side reproduces it exactly.
 *
 * Regenerate with:
 *   python3 work/ocr/scripts/ocr.py street-index-fixture \
 *     --map-id <uuid> --out tests/fixtures/street-index-grid.json
 *
 * Browser-less pure checks, riding the Playwright runner like the rest.
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { cellBox, parseGrid } from '../src/lib/core/geo/mapGrid';

type Fixture = {
  map_id: string;
  grid: { bbox: [number, number, number, number]; rows: string[]; columns: string[] };
  cases: { ref: string; rect: [number, number, number, number] | null }[];
  ts_only: string[];
};

const fixture: Fixture = JSON.parse(
  readFileSync(new URL('./fixtures/street-index-grid.json', import.meta.url), 'utf8')
);

test('the fixture carries a grid this repo can parse', () => {
  const grid = parseGrid(fixture.grid);
  expect(grid).not.toBeNull();
  expect(grid!.rows.length).toBeGreaterThan(1);
  expect(grid!.columns.length).toBeGreaterThan(1);
  // Enough cases to cover both axes' ends, not just the middle.
  expect(fixture.cases.length).toBeGreaterThan(20);
});

test('cellBox agrees with the Python writer on every reference on the sheet', () => {
  const grid = parseGrid(fixture.grid)!;
  const disagreements: string[] = [];
  for (const { ref, rect } of fixture.cases) {
    const got = cellBox(grid, ref);
    if (rect === null) {
      // A reference naming a label the sheet does not print must place nothing
      // in both languages. This sheet's index says "J 2" and its rows stop at
      // I; guessing a row there would put a street off the bottom of the map.
      if (got !== null)
        disagreements.push(`${ref}: TS placed ${JSON.stringify(got)}, Python placed nothing`);
      continue;
    }
    if (got === null) {
      disagreements.push(`${ref}: TS placed nothing, Python placed ${JSON.stringify(rect)}`);
      continue;
    }
    for (let i = 0; i < 4; i++) {
      // Same arithmetic in both languages, so this is exact bar float printing.
      if (Math.abs(got[i] - rect[i]) > 1e-6) {
        disagreements.push(`${ref}: TS ${JSON.stringify(got)} vs Python ${JSON.stringify(rect)}`);
        break;
      }
    }
  }
  expect(disagreements, disagreements.join('\n')).toEqual([]);
});

test('a reference naming a run of cells is TypeScript-only, on purpose', () => {
  const grid = parseGrid(fixture.grid)!;
  // `cellBox` spans "G H 10"; `_cell_rect` in ocr.py reads one cell and returns
  // null. Only the browser needs the run — a street index states its two cells
  // in separate columns. Pinned here so the gap is a decision, not a surprise.
  for (const ref of fixture.ts_only) {
    expect(cellBox(grid, ref), `${ref} should still resolve in TS`).not.toBeNull();
  }
});

test('a reference outside the grid places nothing rather than clamping', () => {
  const grid = parseGrid(fixture.grid)!;
  const badRow = 'Z' + grid.columns[0];
  const badCol = grid.rows[0] + '99';
  expect(cellBox(grid, badRow)).toBeNull();
  expect(cellBox(grid, badCol)).toBeNull();
});
