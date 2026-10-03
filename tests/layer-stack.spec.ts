import { expect, test } from '@playwright/test';
import {
  foldLegacyOverlays,
  isSheetLayer,
  readOverlayRef,
} from '../src/lib/map/stores/overlayKind';
import type { OverlayLayer } from '../src/lib/map/stores/layersStore';

/**
 * The overlay stack holds two different things since the AMS L7014 mosaic
 * arrived: catalogued sheets, and whole surveys.
 *
 * Everything that says "this sheet" — the `?map=` param, the Info rail, story
 * playback, the arrow-key year scrubber — means a sheet. A series row has no
 * catalogue row, so letting one answer those questions writes a `?map=` that
 * resolves to nothing and a share link that opens an empty page. That failure is
 * silent: no error, just a map that does not come back. Hence this.
 */

const sheet = (id: string): OverlayLayer => ({
  id: `layer-${id}`,
  ref: { kind: 'historical', mapId: id, allmapsId: `a-${id}`, name: id },
  opacity: 1,
  visible: true,
});

const series = (key: string): OverlayLayer => ({
  id: `layer-${key}`,
  ref: {
    kind: 'series',
    mapId: `series:${key}`,
    key,
    name: key,
    parts: [{ kind: 'sheets', collection: key }],
    bounds: [102, 8, 110, 24],
  },
  opacity: 1,
  visible: true,
});

/**
 * A live-warped series: one stack row standing for N catalogue sheets, warped
 * by Allmaps at read time rather than tiled into an archive in advance. It is
 * the same `series` row as the mosaic with a different part in it — and the one
 * most likely to be mistaken for a sheet, because unlike a raster archive its
 * sheets really do have catalogue rows. The row itself still does not.
 */
const sheetsSeries = (key: string): OverlayLayer => ({
  id: `layer-${key}`,
  ref: {
    kind: 'series',
    mapId: `series:${key}`,
    key,
    name: key,
    parts: [{ kind: 'sheets', collection: `Collection ${key}` }],
    bounds: [105, 19, 107, 22],
  },
  opacity: 1,
  visible: true,
});

/** The rule `topOverlay` applies: the topmost entry that is actually a sheet. */
const topSheet = (overlays: OverlayLayer[]) => overlays.find(isSheetLayer)?.ref.mapId ?? null;

test('a raster series never answers for "the sheet on top"', () => {
  // The series sits above the sheet, which is the ordinary case once a reader
  // turns it on: newest addition goes to the top of the stack.
  expect(topSheet([series('l7014'), sheet('abc')])).toBe('abc');
  expect(topSheet([sheet('abc'), series('l7014')])).toBe('abc');
});

test('a stack of nothing but series has no sheet on top', () => {
  // Not `'series:l7014'`, which is what reaches the URL as `?map=` and 404s.
  expect(topSheet([series('l7014')])).toBeNull();
});

test('an empty stack has no sheet on top', () => {
  expect(topSheet([])).toBeNull();
});

test('isSheetLayer separates the two kinds', () => {
  expect(isSheetLayer(sheet('abc'))).toBe(true);
  expect(isSheetLayer(series('l7014'))).toBe(false);
});

test('a live-warped series never answers for "the sheet on top" either', () => {
  // The trap this closes: the sheets of this series *are* catalogue rows, so
  // it is tempting to let the row stand for one of them. It stands for 56, and
  // `sheets:tonkin-25k` is not a `maps.id` — as `?map=` it resolves to nothing.
  expect(topSheet([sheetsSeries('tonkin-25k'), sheet('abc')])).toBe('abc');
  expect(topSheet([sheetsSeries('tonkin-25k')])).toBeNull();
  expect(isSheetLayer(sheetsSeries('tonkin-25k'))).toBe(false);
});

test('a stack of both kinds of series still has no sheet on top', () => {
  expect(topSheet([series('l7014'), sheetsSeries('tonkin-25k')])).toBeNull();
});

test('two series are told apart by their own key', () => {
  // Both routes are one kind now, so `key` is the whole of a series' identity —
  // two of them must never collide, and a sheet, whose ref has no key, must
  // never match either.
  const keys = [series('l7014'), sheetsSeries('tonkin-25k'), sheet('abc')]
    .filter((o) => !isSheetLayer(o))
    .map((o) => (o.ref as { key: string }).key);
  expect(keys).toEqual(['l7014', 'tonkin-25k']);
});

/**
 * Reading a stack back out of localStorage.
 *
 * A survey was one stack row per route until Sept 2026 — `raster` for the
 * pre-tiled archive, `sheets` for the live-warped `maps` rows — so every reader
 * who had L7014 on the map has two saved rows for one survey, and a reader who
 * had the Indochine 1:25,000 has a `sheets` row. Those must still draw. The
 * failure this pins is silent in both directions: a ref that no longer parses
 * takes the layer off the map with no error, and one that parses into a
 * half-formed row hands OpenLayers a layer with nothing to draw.
 */
test('a saved sheet still reads back', () => {
  const ref = readOverlayRef({ kind: 'historical', mapId: 'abc', allmapsId: 'a-abc' });
  expect(ref?.kind).toBe('historical');
});

test('a retired raster row, or a raster part, is dropped rather than read', () => {
  // L7014's PMTiles mosaic was retired 2026-10-03; nothing renders a raster part any more.
  expect(
    readOverlayRef({
      kind: 'raster',
      mapId: 'raster:l7014',
      key: 'l7014',
      name: 'mosaic',
      bounds: [102, 8, 110, 24],
    })
  ).toBeNull();
  expect(
    readOverlayRef({
      kind: 'series',
      mapId: 'series:l7014',
      key: 'l7014',
      name: 'L7014',
      bounds: [102, 8, 110, 24],
      parts: [{ kind: 'raster', key: 'l7014' }],
    })
  ).toBeNull();
  // Both halves saved: the series survives with only the sheets part.
  expect(
    readOverlayRef({
      kind: 'series',
      mapId: 'series:l7014',
      key: 'l7014',
      name: 'L7014',
      bounds: [102, 8, 110, 24],
      parts: [
        { kind: 'raster', key: 'l7014' },
        { kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' },
      ],
    })
  ).toMatchObject({ parts: [{ kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' }] });
});

test('a pre-`series` sheets row keeps its collection', () => {
  const ref = readOverlayRef({
    kind: 'sheets',
    mapId: 'sheets:tonkin-25k',
    key: 'tonkin-25k',
    name: 'Indochine 1:25,000',
    collection: 'Indochine 1:25,000',
    bounds: [105, 19, 107, 22],
  });
  // Without the collection the row resolves to no sheets at all, which draws an
  // empty layer rather than an error — so it is the one field worth checking.
  expect(ref).toMatchObject({
    kind: 'series',
    mapId: 'sheets:tonkin-25k',
    parts: [{ kind: 'sheets', collection: 'Indochine 1:25,000' }],
  });
});

test('an unreadable row is dropped rather than half-built', () => {
  // Each of these reached OpenLayers as a layer that could never draw.
  expect(readOverlayRef(null)).toBeNull();
  expect(readOverlayRef({ kind: 'historical', mapId: 'abc' })).toBeNull(); // no annotation
  expect(
    readOverlayRef({ kind: 'sheets', mapId: 's:x', key: 'x', name: 'x', bounds: [1, 2, 3, 4] })
  ).toBeNull(); // no collection
  expect(
    readOverlayRef({
      kind: 'series',
      mapId: 's:x',
      key: 'x',
      name: 'x',
      bounds: [1, 2, 3, 4],
      parts: [],
    })
  ).toBeNull();
  expect(readOverlayRef({ kind: 'raster', mapId: 'raster:x', key: 'x', name: 'x' })).toBeNull(); // no bounds
});

/**
 * Folding a restored stack back into one row per survey.
 *
 * The real input: what a reader who had L7014 on the map in Sept 2026 has in
 * localStorage — the warped city sheets on top, the mosaic under them at
 * whatever opacity they left it. Two rows, two sliders, two eyes, two of the
 * ten stack slots, for one survey.
 */
const savedSheetsHalf = {
  id: 'layer-a',
  ref: readOverlayRef({
    kind: 'sheets',
    mapId: 'sheets:series-l7014-vietnam-1-50-000',
    key: 'series-l7014-vietnam-1-50-000',
    name: 'Series L7014 (Vietnam 1:50,000)',
    collection: 'Series L7014 (Vietnam 1:50,000)',
    bounds: [106, 10, 108, 21],
  })!,
  opacity: 1,
  visible: true,
} as OverlayLayer;

test('a stack saved with the mosaic row loses it and keeps the sheets', () => {
  // The raster half cannot be read any more, so it never reaches the fold.
  const raster = readOverlayRef({
    kind: 'raster',
    mapId: 'raster:l7014',
    key: 'l7014',
    name: 'mosaic',
    bounds: [102, 8, 110, 24],
  });
  expect(raster).toBeNull();
  const [row, ...rest] = foldLegacyOverlays([savedSheetsHalf]);
  expect(rest).toHaveLength(0);
  expect(row.ref).toMatchObject({
    mapId: 'series:series-l7014-vietnam-1-50-000',
    parts: [{ kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' }],
  });
  expect(row.id).toBe('layer-a');
});

test('a row saved under the retired archive key becomes the survey the list offers', () => {
  const old = {
    id: 'layer-z',
    ref: {
      kind: 'series',
      mapId: 'series:l7014',
      key: 'l7014',
      name: 'AMS L7014 1:50,000',
      bounds: [102, 8, 110, 24],
      parts: [{ kind: 'sheets', collection: 'Series L7014 (Vietnam 1:50,000)' }],
    },
    opacity: 0.7,
    visible: true,
  } as OverlayLayer;
  const [row] = foldLegacyOverlays([old]);
  expect(row.ref).toMatchObject({
    mapId: 'series:series-l7014-vietnam-1-50-000',
    key: 'series-l7014-vietnam-1-50-000',
  });
  expect(row.opacity).toBe(0.7);
});

test('a survey no archive claims is left alone but renamed to its own id', () => {
  const saved = {
    id: 'layer-c',
    ref: readOverlayRef({
      kind: 'sheets',
      mapId: 'sheets:tonkin-25k',
      key: 'tonkin-25k',
      name: 'Indochine 1:25,000',
      collection: 'Indochine 1:25,000',
      bounds: [105, 19, 107, 22],
    })!,
    opacity: 0.8,
    visible: false,
  } as OverlayLayer;
  const [row] = foldLegacyOverlays([saved]);
  expect(row.ref).toMatchObject({
    mapId: 'series:tonkin-25k',
    name: 'Indochine 1:25,000',
    parts: [{ kind: 'sheets', collection: 'Indochine 1:25,000' }],
  });
  expect(row.visible).toBe(false);
});

test('sheets are left where they are, and folding twice changes nothing', () => {
  const once = foldLegacyOverlays([sheet('abc'), savedSheetsHalf, sheet('def')]);
  expect(once.map((o) => o.ref.mapId)).toEqual([
    'abc',
    'series:series-l7014-vietnam-1-50-000',
    'def',
  ]);
  expect(foldLegacyOverlays(once)).toEqual(once);
});
