import { test, expect } from '@playwright/test';
import { buildSeriesRows, type RasterSeries } from '../src/lib/features/explore/seriesRows';
import type { MapSeries } from '../src/lib/data/maps/types';

// The series list /explore offers, where one row is one layer with up to two
// parts in it.
//
// L7014 is held two ways — 452 cells pre-tiled into a raster archive, 9 as
// `maps` rows warped live — and they are complementary, not alternative: the
// mosaic has a hole exactly over Saigon and the city sheets are what fills it.
// A row that adds only one half draws a survey with a hole in it, which reads
// as a broken layer rather than as a partial pick, and nothing about it looks
// like an error. That is the property here.

const mosaic: RasterSeries = {
  key: 'l7014',
  name: 'AMS L7014 1:50,000',
  bounds: [102, 8, 110, 24],
  halfOf: 'series-l7014-vietnam-1-50-000',
  sheets: 452,
  note: '1963–89 · 1:50,000',
};

const series = (over: Partial<MapSeries> = {}): MapSeries => ({
  key: 'series-l7014-vietnam-1-50-000',
  collection: 'Series L7014 (Vietnam 1:50,000)',
  name: 'Series L7014 (Vietnam 1:50,000)',
  sheets: 9,
  publishedSheets: 9,
  surveySheets: 627,
  firstYear: 1966,
  lastYear: 1984,
  bounds: [106, 10, 108, 21],
  ...over,
});

test('the two halves of one survey are a single row', () => {
  const rows = buildSeriesRows([series()], false, [mosaic]);
  expect(rows).toHaveLength(1);
  expect(rows[0].name).toBe('AMS L7014 1:50,000');
});

test('that row is one layer holding both halves, mosaic first', () => {
  // `parts` is bottom-up: the warped city sheets must draw ABOVE the pixels
  // they are filling in for. One row means one opacity slider, one eye, one ×
  // and one of the ten stack slots for the whole survey.
  const [row] = buildSeriesRows([series()], false, [mosaic]);
  expect(row.ref.mapId).toBe('series:l7014');
  expect(row.ref.parts).toEqual([
    { kind: 'raster', key: 'l7014' },
    { kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' },
  ]);
});

test('the row reaches the whole survey, not one half of it', () => {
  // Tapping the name zooms to the layer, and the layer is both halves — so the
  // box is their union. The mosaic's alone would cut off any city sheet that
  // reaches past it, and the sheets' alone is a corner of the country.
  const [row] = buildSeriesRows([series()], false, [mosaic]);
  expect(row.ref.bounds).toEqual([102, 8, 110, 24]);
});

test('its count is both halves against the survey, not one half', () => {
  const [row] = buildSeriesRows([series()], false, [mosaic]);
  expect(row.label).toBe('461 of 627 sheets');
});

test('a database series nothing claims stands on its own', () => {
  const tonkin = series({
    key: 'tonkin-25k',
    collection: 'Indochine 1:25,000',
    name: 'Indochine 1:25,000',
    sheets: 53,
    publishedSheets: 53,
    surveySheets: 76,
  });
  const rows = buildSeriesRows([series(), tonkin], false, [mosaic]);
  expect(rows.map((r) => r.key)).toEqual(['l7014', 'tonkin-25k']);
  expect(rows[1].ref.parts).toEqual([{ kind: 'sheets', collection: 'Indochine 1:25,000' }]);
  expect(rows[1].label).toBe('53 of 76 sheets');
});

test('a survey with no imported index says nothing rather than "of 0"', () => {
  // A null denominator is "not counted", which is not the same as "contains
  // none" — printing "3 of 0 sheets" would be worse than printing no ratio.
  const l909 = series({ key: 'l909', sheets: 3, publishedSheets: 3, surveySheets: undefined });
  const [row] = buildSeriesRows([l909], false, []);
  expect(row.label).toBe('3 sheets');
});

test('the mosaic still offers itself when its other half is not visible', () => {
  // An anonymous reader sees no `map_series` row for a wholly-draft survey, and
  // the pre-tiled half is public regardless — it must not vanish with it.
  const [row] = buildSeriesRows([], false, [mosaic]);
  expect(row.ref.parts).toEqual([{ kind: 'raster', key: 'l7014' }]);
  expect(row.label).toBe('452 sheets');
});

test('only a reader who can see drafts is told about them', () => {
  const withDrafts = [series({ sheets: 31, publishedSheets: 9 })];
  expect(buildSeriesRows(withDrafts, false, [mosaic])[0].note).toBe('1963–89 · 1:50,000');
  expect(buildSeriesRows(withDrafts, true, [mosaic])[0].note).toBe(
    '1963–89 · 1:50,000 · 22 unpublished'
  );
});

test('a merged row prints one year span, not two', () => {
  // The mosaic's 1963–89 already contains the sheets' 1966–84; printing both
  // reads as two different things on one row.
  const [row] = buildSeriesRows([series()], true, [mosaic]);
  expect(row.note).toBe('1963–89 · 1:50,000');
});

test('the coverage link points at the database series, not the raster archive', () => {
  // `row.key` for a folded row is the ARCHIVE's key (`l7014`), because the row
  // is named and toggled by the archive. The coverage page lives in
  // `series_cells`, which is keyed by `series_key` — so a link built from
  // `row.key` would 404 on exactly the survey that needs the page most.
  const [row] = buildSeriesRows([series()], false, [mosaic]);
  expect(row.key).toBe('l7014');
  expect(row.seriesKey).toBe('series-l7014-vietnam-1-50-000');
});

test('a standalone survey links to itself', () => {
  const [row] = buildSeriesRows([series({ key: 'indochine' })], false, []);
  expect(row.seriesKey).toBe('indochine');
});

test('an archive that is half of nothing offers no coverage page', () => {
  // Its index is not in `series_cells` — there is no page to link to, and a
  // link to one would be a 404 offered from a row that works.
  const orphan: RasterSeries = { ...mosaic, halfOf: undefined };
  const [row] = buildSeriesRows([], false, [orphan]);
  expect(row.seriesKey).toBeUndefined();
});

test('a survey with no imported index offers no coverage link', () => {
  // `map_series` has a row for every survey with georeferenced sheets, but
  // `series_cells` is seeded per survey by hand — AMS L909 has three sheets
  // and no index, so /catalog/series/<key> is a 404 for it. A link offered
  // from a row that otherwise works is worse than no link at all.
  const l909 = series({ key: 'l909', sheets: 3, publishedSheets: 3, surveySheets: undefined });
  const [row] = buildSeriesRows([l909], false, []);
  expect(row.seriesKey).toBeUndefined();
});
