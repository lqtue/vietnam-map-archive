import { expect, test } from '@playwright/test';
import { loadSeriesByUrls } from '../src/lib/map/shell/warpedOverlay';

/**
 * How a whole sheet series reports on itself.
 *
 * One `WarpedMapLayer` carries every sheet in the series, which is the only
 * reason a live-warped series is affordable — but it means the load is 56
 * fetches behind one call, and the caller has to be told what actually arrived.
 *
 * The trap, and the reason this file exists: `addGeoreferenceAnnotationByUrl`
 * resolves with `(string | Error)[]` — one entry per georeferenced map in the
 * annotation. A sheet that fails to parse comes back as an `Error` *inside a
 * fulfilled promise*; only a fetch that throws rejects. Counting rejections
 * alone reports every series complete no matter how much of it is missing, and
 * a half-drawn series looks exactly like a series with gaps in the survey.
 */

/** A layer that answers the way @allmaps/openlayers does, per scripted result. */
function fakeLayer(results: ((string | Error)[] | Error)[]) {
  let i = 0;
  const calls: string[] = [];
  return {
    calls,
    cleared: 0,
    opacity: null as number | null,
    clear() {
      this.cleared += 1;
    },
    setOpacity(o: number) {
      this.opacity = o;
    },
    async addGeoreferenceAnnotationByUrl(url: string) {
      calls.push(url);
      const r = results[i++];
      if (r instanceof Error) throw r; // the fetch itself failed
      return r;
    },
  };
}

const fakeMap = () => ({
  renders: 0,
  render() {
    this.renders += 1;
  },
});

const run = (layer: any, map: any, sources: string[], opacity = 0.8) =>
  loadSeriesByUrls(layer as never, map as never, sources, opacity);

test('every sheet that loads is counted once', async () => {
  const layer = fakeLayer([['map-a'], ['map-b'], ['map-c']]);
  const map = fakeMap();
  expect(await run(layer, map, ['a', 'b', 'c'])).toEqual({ loaded: 3, failed: 0 });
  expect(layer.cleared).toBe(1); // the layer is emptied before the series goes in
  expect(map.renders).toBe(1); // and repainted once at the end, not per sheet
});

test('an Error inside a fulfilled promise is a failed sheet, not a loaded one', async () => {
  // The whole point. Without this branch the series below reports 3 loaded.
  const layer = fakeLayer([['map-a'], [new Error('unparseable')], ['map-c']]);
  expect(await run(layer, fakeMap(), ['a', 'b', 'c'])).toEqual({ loaded: 2, failed: 1 });
});

test('a rejected fetch is a failed sheet too', async () => {
  const layer = fakeLayer([['map-a'], new Error('404'), ['map-c']]);
  expect(await run(layer, fakeMap(), ['a', 'b', 'c'])).toEqual({ loaded: 2, failed: 1 });
});

test('both failure shapes count together', async () => {
  const layer = fakeLayer([new Error('404'), [new Error('bad')], ['map-c']]);
  expect(await run(layer, fakeMap(), ['a', 'b', 'c'])).toEqual({ loaded: 1, failed: 2 });
});

test('one annotation carrying several maps counts each of them', async () => {
  // A Georeference Annotation may hold more than one map, so the count is of
  // sheets drawn, not of URLs fetched — 56 rows can be more than 56 maps.
  const layer = fakeLayer([['map-a', 'map-b'], ['map-c']]);
  expect(await run(layer, fakeMap(), ['a', 'b'])).toEqual({ loaded: 3, failed: 0 });
});

test('an empty series is a no-op, not a crash', async () => {
  const layer = fakeLayer([]);
  const map = fakeMap();
  expect(await run(layer, map, [])).toEqual({ loaded: 0, failed: 0 });
  expect(layer.calls).toEqual([]);
  // Still cleared: turning a series off has to leave the layer empty.
  expect(layer.cleared).toBe(1);
});

test('the requested opacity reaches the layer', async () => {
  const layer = fakeLayer([['map-a']]);
  await run(layer, fakeMap(), ['a'], 0.42);
  expect(layer.opacity).toBe(0.42);
});
