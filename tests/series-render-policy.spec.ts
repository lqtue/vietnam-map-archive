import { expect, test } from '@playwright/test';
import {
  allocateSeriesBudgets,
  chooseSeriesRendering,
  seriesRenderingBudget,
} from '../src/lib/map/shell/seriesRenderPolicy';
import type { SeriesSheetSource } from '../src/lib/map/shell/warpedOverlay';

const sheet = (i: number): SeriesSheetSource => ({
  id: `${i}`,
  source: `${i}`,
  bbox: [i * 2, 0, i * 2 + 1, 1],
});
const sheets = Array.from({ length: 5000 }, (_, i) => sheet(i));

test('a 5000-sheet overview schedules no image annotations', () => {
  const result = chooseSeriesRendering(sheets, [0, 0, 10000, 1], 64);
  expect(result.mode).toBe('overview');
  expect(result.sources).toEqual([]);
  expect(result.visibleCount).toBe(5000);
});

test('zooming to detail includes every visible source', () => {
  const result = chooseSeriesRendering(sheets, [4.2, 0.2, 8.8, 0.8], 4);
  expect(result.mode).toBe('detail');
  expect(result.sources.map((value) => value.source)).toEqual(
    expect.arrayContaining(['2', '3', '4'])
  );
  expect(result.sources.length).toBeLessThanOrEqual(4);
});

test('unknown or invalid bounds consume capacity rather than disappearing', () => {
  const unknown = { id: 'unknown', source: 'unknown' };
  const invalid = {
    id: 'invalid',
    source: 'invalid',
    bbox: [NaN, 0, 1, 1] as [number, number, number, number],
  };
  const detail = chooseSeriesRendering([sheet(0), unknown, invalid], [0, 0, 1, 1], 3);
  expect(detail.mode).toBe('detail');
  expect(detail.unknownCount).toBe(2);
  expect(detail.sources).toHaveLength(3);
  expect(chooseSeriesRendering([sheet(0), unknown, invalid], [0, 0, 1, 1], 2).mode).toBe(
    'overview'
  );
});

test('padding stays within allocation and favors the nearest sources', () => {
  const near: SeriesSheetSource = { id: 'near', source: 'near', bbox: [4.5, 0, 5.5, 1] };
  const far: SeriesSheetSource = { id: 'far', source: 'far', bbox: [9, 0, 9.1, 1] };
  const result = chooseSeriesRendering([sheet(0), far, near], [0, 0, 4, 1], 2);
  expect(result.mode).toBe('detail');
  expect(result.sources.map((value) => value.source)).toEqual(['0', 'near']);
});

test('absent viewport or invalid allocation cannot request the whole archive', () => {
  expect(chooseSeriesRendering(sheets, null, 64)).toMatchObject({ mode: 'overview', sources: [] });
  for (const allocation of [0, -1, NaN, Infinity])
    expect(chooseSeriesRendering(sheets, [0, 0, 1, 1], allocation)).toMatchObject({
      mode: 'overview',
      sources: [],
    });
});

test('multiple visible series share one desktop or mobile annotation budget', () => {
  for (const mobile of [false, true]) {
    for (const count of [1, 2, 3, 5, 30, 100]) {
      const allocations = allocateSeriesBudgets(count, mobile);
      expect(allocations).toHaveLength(count);
      expect(allocations.reduce((sum, value) => sum + value, 0)).toBe(
        seriesRenderingBudget(mobile)
      );
      expect(Math.max(...allocations) - Math.min(...allocations)).toBeLessThanOrEqual(1);
      const details = allocations.map((allocation) =>
        chooseSeriesRendering(sheets, [0, 0, 1, 1], allocation)
      );
      expect(details.reduce((sum, choice) => sum + choice.sources.length, 0)).toBeLessThanOrEqual(
        seriesRenderingBudget(mobile)
      );
    }
  }
});

test('hysteresis avoids alternating overview and detail at capacity', () => {
  // Stacked printings of one cell: many sources, each wide enough to read.
  const stack = (n: number) =>
    Array.from({ length: n }, (_, i): SeriesSheetSource => ({
      id: `${i}`,
      source: `${i}`,
      bbox: [0, 0, 5, 1],
    }));
  expect(chooseSeriesRendering(stack(10), [0, 0, 20, 1], 10, 'detail').mode).toBe('detail');
  expect(chooseSeriesRendering(stack(10), [0, 0, 20, 1], 10, 'overview').mode).toBe('overview');
  expect(chooseSeriesRendering(stack(8), [0, 0, 20, 1], 10, 'overview').mode).toBe('detail');
});

test('sheets too small for the viewport show footprints whatever the series size', () => {
  // The same rule for a 3-sheet series as for a 5000-sheet one.
  const few = [sheet(0), sheet(2), sheet(4)];
  expect(chooseSeriesRendering(few, [0, 0, 10, 1], 64).mode).toBe('overview');
  expect(chooseSeriesRendering(few, [0, 0, 5, 1], 64).mode).toBe('detail');
  // Leaving overview needs a little more than entering detail does.
  expect(chooseSeriesRendering(few, [0, 0, 5, 1], 64, 'overview').mode).toBe('overview');
  expect(chooseSeriesRendering(few, [0, 0, 4, 1], 64, 'overview').mode).toBe('detail');
});

test('duplicate annotation sources count once and retain their visible representative', () => {
  const result = chooseSeriesRendering(
    [
      { ...sheet(100), source: 'same' },
      { ...sheet(0), source: 'same' },
    ],
    [0, 0, 1, 1],
    1
  );
  expect(result.mode).toBe('detail');
  expect(result.visibleCount).toBe(1);
  expect(result.sources).toHaveLength(1);
  expect(result.sources[0].bbox).toEqual([0, 0, 1, 1]);
});
