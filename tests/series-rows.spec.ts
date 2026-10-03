import { test, expect } from '@playwright/test';
import { buildSeriesRows } from '../src/lib/features/explore/seriesRows';
import type { MapSeries } from '../src/lib/data/maps/types';

// The series list /explore offers: one row per survey, one layer per row — the `maps` rows of one
// collection, warped live. L7014 used to be two things folded into one row (a PMTiles mosaic ~470 m
// out, plus nine live sheets); it is the database series alone since 2026-10-03.

const series = (over: Partial<MapSeries> = {}): MapSeries => ({
  key: 'series-l7014-vietnam-1-50-000',
  collection: 'Series L7014 (Vietnam 1:50,000)',
  name: 'Series L7014 (Vietnam 1:50,000)',
  sheets: 519,
  publishedSheets: 519,
  surveySheets: 627,
  firstYear: 1963,
  lastYear: 1989,
  bounds: [102, 8, 110, 24],
  ...over,
});

test('a survey is one row holding one sheets part', () => {
  const [row] = buildSeriesRows([series()], false);
  expect(row.key).toBe('series-l7014-vietnam-1-50-000');
  expect(row.ref.mapId).toBe('series:series-l7014-vietnam-1-50-000');
  expect(row.ref.parts).toEqual([
    { kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' },
  ]);
  expect(row.ref.bounds).toEqual([102, 8, 110, 24]);
});

test('its count is the cells held against the survey', () => {
  expect(buildSeriesRows([series()], false)[0].label).toBe('519 of 627 sheets');
});

test('a survey with no imported index says nothing rather than "of 0"', () => {
  // A null denominator is "not counted", which is not the same as "contains none".
  const l909 = series({ key: 'l909', sheets: 3, publishedSheets: 3, surveySheets: undefined });
  expect(buildSeriesRows([l909], false)[0].label).toBe('3 sheets');
});

test('only a reader who can see drafts is told about them', () => {
  const withDrafts = [series({ sheets: 540, publishedSheets: 519 })];
  expect(buildSeriesRows(withDrafts, false)[0].note).toBe('1963–89');
  expect(buildSeriesRows(withDrafts, true)[0].note).toBe('1963–89 · 21 unpublished');
});

test('the coverage link is the survey key, and only where an index was imported', () => {
  expect(buildSeriesRows([series()], false)[0].seriesKey).toBe('series-l7014-vietnam-1-50-000');
  // `map_series` has a row for every survey with georeferenced sheets, but `series_cells` is seeded per
  // survey by hand — AMS L909 has three sheets and no index, so its page is a 404.
  const l909 = series({ key: 'l909', sheets: 3, publishedSheets: 3, surveySheets: undefined });
  expect(buildSeriesRows([l909], false)[0].seriesKey).toBeUndefined();
});

test('every survey gets its own row', () => {
  const tonkin = series({
    key: 'tonkin-25k',
    collection: 'Indochine 1:25,000',
    name: 'Indochine 1:25,000',
    sheets: 53,
    publishedSheets: 53,
    surveySheets: 76,
  });
  const rows = buildSeriesRows([series(), tonkin], false);
  expect(rows.map((r) => r.key)).toEqual(['series-l7014-vietnam-1-50-000', 'tonkin-25k']);
  expect(rows[1].label).toBe('53 of 76 sheets');
});
