import { expect, test } from '@playwright/test';
import { isSheetLayer } from '../src/lib/map/stores/overlayKind';
import type { OverlayLayer } from '../src/lib/map/stores/layersStore';

/**
 * The overlay stack holds two different things since the AMS L7014 mosaic
 * arrived: catalogued sheets, and whole pre-warped raster series.
 *
 * Everything that says "this sheet" — the `?map=` param, the Info rail, story
 * playback, the arrow-key year scrubber — means a sheet. A raster series has no
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
    kind: 'raster',
    mapId: `raster:${key}`,
    key,
    name: key,
    bounds: [102, 8, 110, 24],
  },
  opacity: 1,
  visible: true,
});

/**
 * A live-warped series: one stack row standing for N catalogue sheets, warped
 * by Allmaps at read time rather than tiled into an archive in advance. It is
 * the third thing the stack holds and the second that is not a sheet — and the
 * one most likely to be mistaken for one, because unlike a raster archive its
 * sheets really do have catalogue rows. The row itself still does not.
 */
const sheetsSeries = (key: string): OverlayLayer => ({
  id: `layer-${key}`,
  ref: {
    kind: 'sheets',
    mapId: `sheets:${key}`,
    key,
    collection: `Collection ${key}`,
    name: key,
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
  // Not `'raster:l7014'`, which is what reaches the URL as `?map=` and 404s.
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

test('the two series kinds are told apart by their own key, not their kind', () => {
  // `hasSeriesOverlay` matches on `key` across both kinds, so two series must
  // never collide — and a series must never match a sheet, whose ref has no key.
  const keys = [series('l7014'), sheetsSeries('tonkin-25k'), sheet('abc')]
    .filter((o) => !isSheetLayer(o))
    .map((o) => (o.ref as { key: string }).key);
  expect(keys).toEqual(['l7014', 'tonkin-25k']);
});
