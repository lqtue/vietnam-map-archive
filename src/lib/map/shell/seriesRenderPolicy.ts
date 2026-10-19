import type { SeriesSheetSource } from './warpedOverlay';

type Extent = [number, number, number, number];
export type SeriesRenderingMode = 'overview' | 'detail';
export type SeriesRenderingChoice = {
  mode: SeriesRenderingMode;
  /** Empty in overview: footprints replace image annotations at that scale. */
  sources: SeriesSheetSource[];
  /** Known sources intersecting the actual viewport, excluding unknown bounds. */
  visibleCount: number;
  unknownCount: number;
};

export function seriesRenderingBudget(mobile: boolean): number {
  return mobile ? 24 : 64;
}

/** Call with only series intersecting this map's viewport; allocations never exceed its budget. */
export function allocateSeriesBudgets(visibleSeriesCount: number, mobile: boolean): number[] {
  if (!Number.isFinite(visibleSeriesCount) || visibleSeriesCount <= 0) return [];
  const count = Math.floor(visibleSeriesCount);
  const budget = seriesRenderingBudget(mobile);
  const base = Math.floor(budget / count);
  const extra = budget % count;
  return Array.from({ length: count }, (_, index) => base + (index < extra ? 1 : 0));
}

function validExtent(value: Extent | undefined | null): value is Extent {
  return !!value && value.every(Number.isFinite) && value[0] <= value[2] && value[1] <= value[3];
}
function intersects(a: Extent, b: Extent): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

/**
 * Rendering is complete or explicitly an overview, never a truncated survey.
 * Unknown bounds consume detail capacity because excluding them could hide visible imagery.
 * Padding is optional prefetch, so only its nearest sources fill the remaining capacity.
 */
export function chooseSeriesRendering(
  sheets: readonly SeriesSheetSource[],
  view: Extent | null,
  allocation: number,
  previousMode?: SeriesRenderingMode
): SeriesRenderingChoice {
  if (!validExtent(view))
    return { mode: 'overview', sources: [], visibleCount: 0, unknownCount: 0 };
  const limit = Number.isFinite(allocation) ? Math.max(0, Math.floor(allocation)) : 0;
  const dx = (view[2] - view[0]) / 4;
  const dy = (view[3] - view[1]) / 4;
  const padded: Extent = [view[0] - dx, view[1] - dy, view[2] + dx, view[3] + dy];
  const cx = (view[0] + view[2]) / 2;
  const cy = (view[1] + view[3]) / 2;
  const width = Math.max(view[2] - view[0], Number.EPSILON);
  const height = Math.max(view[3] - view[1], Number.EPSILON);
  type Candidate = { sheet: SeriesSheetSource; priority: number; distance: number };
  const candidates = new Map<string, Candidate>();
  for (const sheet of sheets) {
    const bbox = sheet.bbox;
    const unknown = !validExtent(bbox);
    const priority = unknown ? 0 : intersects(bbox, view) ? 1 : intersects(bbox, padded) ? 2 : 3;
    if (priority === 3) continue;
    const distance = unknown
      ? 0
      : ((bbox[0] + bbox[2]) / 2 - cx) ** 2 / width ** 2 +
        ((bbox[1] + bbox[3]) / 2 - cy) ** 2 / height ** 2;
    const previous = candidates.get(sheet.source);
    if (
      !previous ||
      priority < previous.priority ||
      (priority === previous.priority && distance < previous.distance)
    )
      candidates.set(sheet.source, {
        sheet: unknown ? { ...sheet, bbox: undefined } : sheet,
        priority,
        distance,
      });
  }
  const values = [...candidates.values()];
  const required = values.filter((candidate) => candidate.priority < 2);
  const unknownCount = required.filter((candidate) => candidate.priority === 0).length;
  const visibleCount = required.length - unknownCount;
  // Enter overview above capacity; leave only with spare room to avoid repeated transitions
  // around a sheet boundary. Small allocations keep their useful single-sheet capacity.
  const resumeLimit = previousMode === 'overview' && limit >= 5 ? Math.floor(limit * 0.8) : limit;
  if (!limit || required.length > resumeLimit)
    return { mode: 'overview', sources: [], visibleCount, unknownCount };
  const nearby = values
    .filter((candidate) => candidate.priority === 2)
    .sort((a, b) => a.distance - b.distance || a.sheet.source.localeCompare(b.sheet.source));
  return {
    mode: 'detail',
    sources: [...required, ...nearby.slice(0, limit - required.length)].map(
      (candidate) => candidate.sheet
    ),
    visibleCount,
    unknownCount,
  };
}
