import { test, expect } from '@playwright/test';
import {
  JOBS,
  jobOf,
  jobCounts,
  jobBox,
  isPrintedJob,
} from '../src/lib/features/contribute/ocr/jobs';
import type { LayoutRegion } from '../src/lib/data/maps/triageTypes';
import type { OcrExtraction } from '../src/lib/features/contribute/shared/types';

/**
 * The four reading jobs of /scan?mode=text.
 *
 * They are tabs with counts on them, which is a promise: a reviewer who clears
 * all four has cleared the sheet. That only holds if every row lands in exactly
 * one job — so the property under test is the partition, not the four rules.
 * A row that matched two jobs would be checked twice and a row that matched
 * none would never be seen at all, and neither shows up as an error anywhere:
 * the sheet just quietly finishes with work left on it.
 *
 * The regions are `maps.triage.regions` for 3a446d85 (1968 Sài Gòn 1:12,500),
 * the same sheet `ocr-regions.spec.ts` pins the axis itself against.
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

const row = (x: number, y: number, category: string): OcrExtraction =>
  ({
    id: `${x}_${y}_${category}`,
    global_x: x,
    global_y: y,
    global_w: 40,
    global_h: 30,
    category,
  }) as OcrExtraction;

test('each job gets the work it is named for', () => {
  const job = (x: number, y: number, c: string) => jobOf(row(x, y, c), REGIONS);

  // On the terrain.
  expect(job(5000, 5000, 'street')).toBe('names');
  expect(job(5000, 5000, 'hydrology')).toBe('names');
  expect(job(5000, 5000, 'institution')).toBe('names');

  // A numeral on the terrain is Numbers, not Names — `37` alone says nothing.
  expect(job(5000, 5000, 'legend_ref')).toBe('numbers');

  // The same numeral printed in the legend table is part of the table.
  expect(job(3000, 11500, 'legend_ref')).toBe('index');
  expect(job(8000, 10500, 'street')).toBe('index'); // a line of the name list

  // Furniture, off-sheet, and anything on the map that is none of the above.
  expect(job(5000, 200, 'title')).toBe('other');
  expect(job(3000, 12500, 'other')).toBe('other'); // scale bar
  expect(job(50, 50, 'street')).toBe('other'); // outside the neatline
  expect(job(5000, 5000, 'legend')).toBe('other');
});

test('every row lands in exactly one job, so the tab counts add up to the sheet', () => {
  const rows: OcrExtraction[] = [];
  const cats = [
    'street',
    'hydrology',
    'place',
    'building',
    'institution',
    'legend',
    'legend_entry',
    'legend_ref',
    'title',
    'other',
  ];
  // A coarse sweep of the whole sheet in every category: terrain, both name
  // lists, both legends, the scale bar, the title and the margin.
  for (let x = 0; x < 10816; x += 700)
    for (let y = 0; y < 13523; y += 700) for (const c of cats) rows.push(row(x, y, c));

  const counts = jobCounts(rows, REGIONS);
  const total = counts.names + counts.index + counts.numbers + counts.other;
  expect(total).toBe(rows.length);
  // And no job is a dead tab on this sheet.
  for (const j of JOBS) expect(counts[j.key]).toBeGreaterThan(0);
});

test('a sheet with no layout pass is all map, so nothing is filed as printed', () => {
  expect(jobOf(row(5000, 12000, 'street'), [])).toBe('names');
  expect(jobOf(row(5000, 12000, 'legend_ref'), [])).toBe('numbers');
  expect(jobCounts([row(1, 1, 'street')], []).index).toBe(0);
});

test('a reviewer’s category correction moves map work to its reviewed job', () => {
  const corrected = { ...row(5000, 5000, 'other'), category_validated: 'street' };
  expect(jobOf(corrected, REGIONS)).toBe('names');
});

test('a job frames the part of the sheet it reads', () => {
  // Index spans both legends and both name lists — one rectangle over the lot.
  const index = jobBox('index', REGIONS)!;
  expect(index[0]).toBe(2527);
  expect(index[1]).toBe(9871);
  expect(index[0] + index[2]).toBe(10316); // the right name list's right edge
  expect(index[1] + index[3]).toBe(13377);

  // Names and Numbers are the terrain; Other is everywhere, so it frames nothing.
  expect(jobBox('names', REGIONS)).toEqual([281, 311, 10015, 9533]);
  expect(jobBox('numbers', REGIONS)).toEqual([281, 311, 10015, 9533]);
  expect(jobBox('other', REGIONS)).toBeNull();

  // Only the table job reads as a table.
  expect(isPrintedJob('index')).toBe(true);
  expect(isPrintedJob('numbers')).toBe(false);
});
