import { test, expect } from '@playwright/test';
import {
  regionOf,
  regionCounts,
  regionBox,
  isPrinted,
  type RegionKey,
} from '../src/lib/features/contribute/ocr/regionFilter';
import { indexGaps, printedLine } from '../src/lib/features/contribute/ocr/legendIndex';
import type { LayoutRegion } from '../src/lib/data/maps/triageTypes';
import type { OcrExtraction } from '../src/lib/features/contribute/shared/types';

/**
 * Reviewing a sheet one printed part at a time only works if "which part" is
 * decided the same way the pipeline decides what to read. Both use the row's
 * centre, and a printed block beats `main_map` — the legend on these sheets is
 * printed inside the neatline, so "inside the map" is true of it as well.
 *
 * The regions are `maps.triage.regions` for 3a446d85 (1968 Sài Gòn 1:12,500),
 * copied verbatim: `main_map` is the neatline, and the two `name_list` blocks,
 * two `legend` blocks and the scale bar all sit below and inside the sheet.
 */
const REGIONS: LayoutRegion[] = [
  { category: 'sheet', bbox: [0, 0, 10816, 13523], source: 'human' },
  { category: 'title', bbox: [4921, 121, 973, 189], source: 'model' },
  { category: 'main_map', bbox: [281, 311, 10015, 9533], source: 'model' },
  { category: 'name_list', bbox: [7571, 9871, 2745, 3262], source: 'human' },
  { category: 'name_list', bbox: [4218, 9871, 3271, 3506], source: 'human' },
  { category: 'legend', bbox: [2527, 11022, 1596, 1142], source: 'human' },
  { category: 'scale_bar', bbox: [2316, 12212, 1901, 1054], source: 'human' },
  { category: 'legend', bbox: [3166, 10478, 699, 510], source: 'human' },
] as LayoutRegion[];

const row = (x: number, y: number, w = 40, h = 30): OcrExtraction =>
  ({ id: `${x}_${y}`, global_x: x, global_y: y, global_w: w, global_h: h }) as OcrExtraction;

test('a row is placed by its centre, and a printed block beats the map', () => {
  const where = (x: number, y: number, w?: number, h?: number): RegionKey =>
    regionOf(row(x, y, w, h), REGIONS);

  expect(where(5000, 5000)).toBe('map');
  expect(where(5000, 200)).toBe('title');
  expect(where(8000, 10500)).toBe('names');
  expect(where(3000, 11500)).toBe('legend');
  expect(where(3000, 12500)).toBe('title'); // scale bar is furniture, not terrain
  expect(where(50, 50)).toBe('off'); // inside the sheet, outside the neatline

  // The small legend at (3166,10478,699,510) overlaps neither name_list; it is
  // below `main_map`'s bottom edge (311 + 9533 = 9844) but must still resolve
  // as legend rather than off-sheet.
  expect(where(3400, 10700)).toBe('legend');

  // The centre decides, not the corner: a box whose origin is in the legend but
  // whose bulk is not belongs to where its middle lands.
  expect(where(2400, 10950, 400, 300)).toBe('legend');
  expect(where(2100, 10700, 400, 300)).toBe('off');
});

test('no layout pass means the whole sheet is the map', () => {
  expect(regionOf(row(5000, 12000), [])).toBe('map');
  expect(regionCounts([row(1, 1), row(2, 2)], [])).toEqual([{ key: 'map', count: 2 }]);
});

test('counts keep a fixed order and drop the parts with nothing in them', () => {
  const rows = [row(5000, 5000), row(5001, 5000), row(3000, 11500), row(5000, 200)];
  expect(regionCounts(rows, REGIONS)).toEqual([
    { key: 'map', count: 2 },
    { key: 'legend', count: 1 },
    { key: 'title', count: 1 },
  ]);
});

test('a pill covers the union of its blocks, and only the printed ones are printed', () => {
  // Two name lists side by side: the pill has to frame both or picking it
  // shows half the table and hides the rest off screen.
  expect(regionBox('names', REGIONS)).toEqual([4218, 9871, 6098, 3506]);
  expect(regionBox('legend', REGIONS)).toEqual([2527, 10478, 1596, 1686]);
  expect(regionBox('map', REGIONS)).toEqual([281, 311, 10015, 9533]);
  expect(regionBox('off', REGIONS)).toBeNull();
  expect(regionBox('', REGIONS)).toBeNull();
  expect(regionBox('legend', [])).toBeNull();

  expect([isPrinted('legend'), isPrinted('names'), isPrinted('title')]).toEqual([true, true, true]);
  expect([isPrinted('map'), isPrinted('off'), isPrinted('')]).toEqual([false, false, false]);
});

/**
 * The 1942 Saigon–Cho Lon legend, as it stands in the table: 235 rows carrying
 * `n=` in their notes, numbered 1..236 with 22 the only hole. One line of
 * report that 235 rows of review never produces.
 */
test('the printed index reports its own holes and repeats', () => {
  const entry = (n: number, i = n) =>
    ({
      id: `e${i}`,
      category: 'legend_entry',
      notes: `n=${n}; grid=B10`,
      text: `${n}. Something`,
    }) as OcrExtraction;

  const full = Array.from({ length: 236 }, (_, i) => entry(i + 1)).filter(
    (r) => r.notes !== 'n=22; grid=B10'
  );
  expect(indexGaps(full)).toEqual({ min: 1, max: 236, missing: [22], repeated: [] });

  // A line read twice is a repeat; both are reported, neither is guessed at.
  expect(indexGaps([entry(1), entry(2), entry(2, 99), entry(4)])).toEqual({
    min: 1,
    max: 4,
    missing: [3],
    repeated: [2],
  });

  // No legend read at all: nothing to report, and nothing invented.
  expect(indexGaps([])).toBeNull();
  expect(
    indexGaps([{ id: 'x', category: 'street', text: 'Rue', notes: null } as OcrExtraction])
  ).toBeNull();
});

/**
 * Both printed blocks put their position in `notes`, because `ocr_labels`
 * has no column for a grid cell — the legend writes `n=37; grid=B10` and the
 * street index `street index; grid=K6→K8; cells=2`. Reading both back is what
 * lets the review table show either as the table it is, ordered the way the
 * paper orders it: the legend by number, the street index alphabetically.
 *
 * The notes here are copied from real rows on the 1942 and 1968 sheets.
 */
test('a printed row reports its cell, and its number when the paper prints one', () => {
  const withNotes = (notes: string | null) => ({ id: 'r', notes }) as OcrExtraction;

  expect(printedLine(withNotes('n=37; grid=B10'))).toEqual({ n: 37, grid: 'B10' });
  expect(printedLine(withNotes('n=232; grid=J1; vn=Sở Cảnh Sát'))).toEqual({ n: 232, grid: 'J1' });

  // The street index numbers nothing — it is alphabetical — so `n` is null and
  // the row still places itself.
  expect(printedLine(withNotes('street index; grid=K6→K8; cells=2'))).toEqual({
    n: null,
    grid: 'K6→K8',
  });

  // A directory line the pass could not place carries no grid, and is not a
  // printed line as far as the table is concerned.
  expect(printedLine(withNotes('n=12; grid='))).toBeNull();
  expect(printedLine(withNotes('index key'))).toBeNull();
  expect(printedLine(withNotes(null))).toBeNull();
});
