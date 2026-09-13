import { test, expect } from '@playwright/test';
import type { SupabaseClient } from '@supabase/supabase-js';
import {
  sheetStatus,
  tally,
  cellCamera,
  fetchSeriesSheets,
  type SeriesSheet,
} from '../src/lib/data/maps/seriesSheets';

// What a survey contains, read for display. Three of these four functions
// decide what a coverage page *claims* — how many sheets the archive holds,
// which of them are missing, and where the map opens for a sheet that has no
// scan. None of that fails loudly: a wrong status is a plausible badge, a
// dropped page of rows is a smaller denominator, and a bad camera is a map
// over the wrong ground. So they are pinned here rather than eyeballed.

const row = (over: Partial<SeriesSheet> = {}): SeriesSheet => ({
  series_key: 's',
  sheet_number: '6330-4',
  name: 'Sai Gon',
  bbox: null,
  source: null,
  source_ref: null,
  held_by: null,
  map_id: null,
  note: null,
  ...over,
});

test('a held sheet is held whether or not anyone recorded where the scan came from', () => {
  // The trap: `source` is provenance, not possession. A cell that reaches the
  // reader as mosaic pixels has no source URL and is still held.
  expect(sheetStatus({ held_by: 'raster:l7014', source: null })).toBe('held');
  expect(sheetStatus({ held_by: 'map', source: 'PCL' })).toBe('held');
});

test('an unheld sheet splits on whether a scan has been located at all', () => {
  expect(sheetStatus({ held_by: null, source: 'PCL' })).toBe('obtainable');
  expect(sheetStatus({ held_by: null, source: null })).toBe('no_scan');
});

test('the three statuses partition the survey', () => {
  // The coverage bar draws these as three segments of one whole and the prose
  // says "N of TOTAL". A row counted twice or not at all is a percentage that
  // is wrong by a plausible amount, which is the only symptom there would be.
  const sheets = [
    row({ held_by: 'map' }),
    row({ held_by: 'raster:l7014' }),
    row({ source: 'PCL' }),
    row({}),
  ].map((r) => ({ ...r, status: sheetStatus(r), heldAs: null }));
  const t = tally(sheets);
  expect(t).toEqual({ total: 4, held: 2, obtainable: 1, no_scan: 1 });
  expect(t.held + t.obtainable + t.no_scan).toBe(t.total);
});

test('a cell opens over its own centre', () => {
  const cam = cellCamera([106.5, 10.75, 106.75, 11.0]); // one 15' x 15' L7014 cell
  expect(cam.lng).toBeCloseTo(106.625, 6);
  expect(cam.lat).toBeCloseTo(10.875, 6);
});

test('a smaller cell asks for a closer camera, and neither end runs away', () => {
  const wide = cellCamera([100, 0, 110, 10]);
  const tight = cellCamera([106.5, 10.75, 106.75, 11.0]);
  expect(tight.zoom).toBeGreaterThan(wide.zoom);
  expect(wide.zoom).toBeGreaterThanOrEqual(4);
  expect(tight.zoom).toBeLessThanOrEqual(16);
});

test('a degenerate cell asks for a zoom a basemap has, not Infinity', () => {
  // A zero-area bbox is a bad import, not an impossible one, and `log2(360/0)`
  // is Infinity — which OL takes and renders nothing at.
  const cam = cellCamera([106.5, 10.75, 106.5, 10.75]);
  expect(Number.isFinite(cam.zoom)).toBe(true);
  expect(cam.zoom).toBe(16);
});

/** Enough of PostgREST's builder for `fetchSeriesSheets`, counting its pages. */
function stubDb(total: number, ranges: [number, number][]) {
  const q = {
    select: () => q,
    eq: () => q,
    range: (from: number, to: number) => {
      ranges.push([from, to]);
      const rows: SeriesSheet[] = [];
      for (let i = from; i <= Math.min(to, total - 1); i++) {
        rows.push(row({ sheet_number: String(i) }));
      }
      return Promise.resolve({ data: rows, error: null });
    },
  };
  return { from: () => q } as unknown as SupabaseClient;
}

test('a survey longer than one page is read whole', () => {
  // PostgREST caps an unbounded select at 1000 rows and says nothing about it.
  // L7014 is 627 today; Cochinchine's three series are 826 and the cap is the
  // kind of ceiling that is crossed by ingesting data, not by editing code.
  const ranges: [number, number][] = [];
  return fetchSeriesSheets(stubDb(1500, ranges), 's').then((sheets) => {
    expect(sheets).toHaveLength(1500);
    expect(ranges).toEqual([
      [0, 999],
      [1000, 1999],
    ]);
  });
});

test('a survey that exactly fills a page still stops', () => {
  // The off-by-one: a final page of exactly `page` rows is indistinguishable
  // from a full one, so the loop must ask once more and get nothing.
  const ranges: [number, number][] = [];
  return fetchSeriesSheets(stubDb(1000, ranges), 's').then((sheets) => {
    expect(sheets).toHaveLength(1000);
    expect(ranges).toHaveLength(2);
  });
});

test('sheets come back in the order a person reads them', () => {
  const ranges: [number, number][] = [];
  return fetchSeriesSheets(stubDb(12, ranges), 's').then((sheets) => {
    // Plain string order puts "10" before "9"; `numeric` collation is what the
    // sheet-number column needs, and 6329-4 must precede 6330-1.
    expect(sheets.map((s) => s.sheet_number).slice(-4)).toEqual(['8', '9', '10', '11']);
  });
});
