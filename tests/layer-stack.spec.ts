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
