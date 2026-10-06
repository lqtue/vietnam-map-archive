/**
 * Which part of the sheet a row was read from.
 *
 * The layout pass already answers "where is the terrain, where is the printed
 * matter" and saves it in `maps.triage.regions`. That is a better axis to
 * review along than the OCR category: a reviewer checking the numbered legend
 * is doing one job (number ↔ name ↔ place) and a reviewer checking street
 * names is doing another, and the category vocabulary cuts across both — the
 * printed index alone contributed 719 `street` and 630 `institution` rows on
 * the 1942 sheet, none of them marks on the map.
 *
 * Pure functions over rows the sidebar already holds. `tests/ocr-regions.spec.ts`
 * is the check. The centre test is the twin of `in_rects` in
 * `work/ocr/scripts/ocr.py` — the same rule decides what the pipeline writes
 * and what the review table groups.
 */

import type { LayoutRegion } from '$lib/data/maps/triageTypes';
import type { OcrExtraction } from '../shared/types';

export type RegionKey = 'map' | 'legend' | 'names' | 'title' | 'off';

export const REGION_LABELS: Record<RegionKey, string> = {
  map: 'Map',
  legend: 'Legend',
  names: 'Names',
  title: 'Title',
  off: 'Outside map body',
};

/** The layout categories each pill answers to. `map` is the fallback, not a list. */
const PRINTED: { key: RegionKey; cats: string[] }[] = [
  { key: 'legend', cats: ['legend'] },
  { key: 'names', cats: ['name_list'] },
  { key: 'title', cats: ['title', 'scale_bar', 'north_arrow', 'stamp'] },
];

function centreIn(bbox: number[] | undefined, cx: number, cy: number): boolean {
  if (!bbox || bbox.length !== 4) return false;
  const [x, y, w, h] = bbox;
  return cx >= x && cx < x + w && cy >= y && cy < y + h;
}

/**
 * Which pill a row belongs to.
 *
 * A printed block wins over `main_map`, always: the legend on this sheet is
 * printed *inside* the neatline, so "inside the map" is true of it too. That is
 * the same precedence `tilingCrop` uses and the same reason the tile pass had
 * to be told to skip these blocks.
 */
export function regionOf(row: OcrExtraction, regions: LayoutRegion[]): RegionKey {
  const cx = row.global_x + (row.global_w ?? 0) / 2;
  const cy = row.global_y + (row.global_h ?? 0) / 2;
  for (const { key, cats } of PRINTED) {
    if (regions.some((r) => cats.includes(r.category) && centreIn(r.bbox, cx, cy))) return key;
  }
  const main = regions.find((r) => r.category === 'main_map');
  if (main) return centreIn(main.bbox, cx, cy) ? 'map' : 'off';
  // No layout pass has run: everything is "the map", because nothing yet says
  // otherwise. Better than calling the whole sheet off-sheet.
  return 'map';
}

/** Row counts per pill, in a fixed order so the pills do not reshuffle. */
export function regionCounts(
  rows: OcrExtraction[],
  regions: LayoutRegion[]
): { key: RegionKey; count: number }[] {
  const tally = new Map<RegionKey, number>();
  for (const row of rows) {
    const key = regionOf(row, regions);
    tally.set(key, (tally.get(key) ?? 0) + 1);
  }
  const order: RegionKey[] = ['map', 'legend', 'names', 'title', 'off'];
  return order.filter((k) => tally.get(k)).map((key) => ({ key, count: tally.get(key)! }));
}

/** True for the parts that are printed matter rather than terrain. */
export function isPrinted(key: RegionKey | ''): boolean {
  return key === 'legend' || key === 'names' || key === 'title';
}

/**
 * The rectangle a pill covers — the union when a sheet prints the same kind of
 * block more than once, which every one of these sheets does (two name lists,
 * two legends). Null for `off`, which is everywhere else by definition, and for
 * a part the sheet has no region for.
 */
export function regionBox(
  key: RegionKey | '',
  regions: LayoutRegion[]
): [number, number, number, number] | null {
  if (!key || key === 'off') return null;
  const cats = key === 'map' ? ['main_map'] : (PRINTED.find((p) => p.key === key)?.cats ?? []);
  const boxes = regions.filter((r) => cats.includes(r.category) && r.bbox?.length === 4);
  if (!boxes.length) return null;
  const x = Math.min(...boxes.map((r) => r.bbox[0]));
  const y = Math.min(...boxes.map((r) => r.bbox[1]));
  const right = Math.max(...boxes.map((r) => r.bbox[0] + r.bbox[2]));
  const bottom = Math.max(...boxes.map((r) => r.bbox[1] + r.bbox[3]));
  return [x, y, right - x, bottom - y];
}
