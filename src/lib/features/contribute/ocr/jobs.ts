/**
 * jobs.ts — the four reading jobs of /scan?mode=text.
 *
 * A reviewer does one of four things, and they are four different jobs:
 *
 *   Names    the names printed on the terrain — streets, places, water,
 *            institutions. Read the ink, fix the spelling.
 *   Index    the sheet's own printed tables: the numbered legend and the name
 *            list. Read a table, not a map, and the rows are ordered the way
 *            the paper orders them.
 *   Numbers  the numerals printed on the map. Nothing about `37` is checkable
 *            on its own — the index is the answer key, and `suspectRefs` is
 *            what the index disagrees with.
 *   Other    the title block, the scale bar, the stamp, whatever fell off the
 *            sheet — plus anything on the map that is none of the above.
 *
 * They were one table with a category chip per OCR class, which cuts across all
 * four: the 1942 sheet's printed index alone contributed 719 `street` and 630
 * `institution` rows, none of them marks on the map, all of them sitting in the
 * same chip as the street names a reviewer was trying to check.
 *
 * The four **partition** the loaded rows — every row lands in exactly one, and
 * `other` is the fallback, so the tab counts add up to the sheet. That is the
 * property `tests/ocr-jobs.spec.ts` holds.
 */

import type { LayoutRegion } from '$lib/data/maps/triageTypes';
import type { OcrExtraction } from '../shared/types';
import { reviewedCategory } from '../shared/ocrApi';
import { regionOf, regionBox, type RegionKey } from './regionFilter';

export type JobKey = 'names' | 'index' | 'numbers' | 'other';

export type Job = {
  key: JobKey;
  label: string;
  /** What the reviewer is being asked to check, in the bar under the tabs. */
  hint: string;
  /** The categories the chips start on. A refinement, not the job's definition. */
  cats: string[];
  /** How the table starts out sorted — the order the job is naturally done in. */
  sort: { key: 'text' | 'category' | 'confidence' | 'cell' | 'n'; asc: boolean };
};

/** Names on the terrain. `legend_ref` is a numeral, not a name — that is Numbers. */
const NAME_CATS = ['street', 'place', 'hydrology', 'institution', 'building'];

export const JOBS: Job[] = [
  {
    key: 'names',
    label: 'Names',
    hint: 'Names printed on the map — streets, places, water, institutions.',
    cats: NAME_CATS,
    sort: { key: 'confidence', asc: false },
  },
  {
    key: 'index',
    label: 'Index',
    hint: "The sheet's own printed tables: the numbered legend and the name list.",
    cats: ['legend', 'legend_entry', 'legend_ref', 'street', 'institution', 'place', 'other'],
    sort: { key: 'n', asc: true },
  },
  {
    key: 'numbers',
    label: 'Numbers',
    hint: 'Numerals on the map, against the index that explains them.',
    cats: ['legend_ref'],
    sort: { key: 'n', asc: true },
  },
  {
    key: 'other',
    label: 'Other',
    hint: 'Title block, scale bar, stamp — and anything on the map that is none of the above.',
    cats: ['title', 'legend', 'legend_entry', 'other'],
    sort: { key: 'confidence', asc: false },
  },
];

/** Which job a row belongs to. Exactly one, always. */
export function jobOf(row: OcrExtraction, regions: LayoutRegion[]): JobKey {
  const where = regionOf(row, regions);
  if (where === 'legend' || where === 'names') return 'index';
  if (where === 'map') {
    const category = reviewedCategory(row);
    if (category === 'legend_ref') return 'numbers';
    if (NAME_CATS.includes(category)) return 'names';
  }
  return 'other';
}

/** Row counts per tab, in `JOBS` order so the tabs never reshuffle. */
export function jobCounts(rows: OcrExtraction[], regions: LayoutRegion[]): Record<JobKey, number> {
  const tally: Record<JobKey, number> = { names: 0, index: 0, numbers: 0, other: 0 };
  for (const row of rows) tally[jobOf(row, regions)]++;
  return tally;
}

/**
 * The rectangle to frame when a job is picked, or null for "the whole sheet".
 *
 * Index is the reason this exists: a printed table at whole-sheet zoom is
 * unreadable, and the boxes over it are worse than useless — 235 rows of the
 * 1942 index share six rectangles, because the pipeline stamps every line of a
 * band with the band's own crop.
 */
export function jobBox(
  key: JobKey,
  regions: LayoutRegion[]
): [number, number, number, number] | null {
  const parts: RegionKey[] = key === 'index' ? ['legend', 'names'] : key === 'other' ? [] : ['map'];
  const boxes = parts
    .map((p) => regionBox(p, regions))
    .filter((b): b is [number, number, number, number] => !!b);
  if (!boxes.length) return null;
  const x = Math.min(...boxes.map((b) => b[0]));
  const y = Math.min(...boxes.map((b) => b[1]));
  const right = Math.max(...boxes.map((b) => b[0] + b[2]));
  const bottom = Math.max(...boxes.map((b) => b[1] + b[3]));
  return [x, y, right - x, bottom - y];
}

/** True where the rows are lines of a printed table rather than marks on terrain. */
export function isPrintedJob(key: JobKey): boolean {
  return key === 'index';
}
