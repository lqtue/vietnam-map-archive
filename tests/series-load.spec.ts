import { expect, test } from '@playwright/test';
import { loadSeriesInView, type SeriesSheetSource } from '../src/lib/map/shell/warpedOverlay';

/**
 * How a whole sheet series loads, and how it reports on itself.
 *
 * One `WarpedMapLayer` carries every sheet in the series, which is the only
 * reason a live-warped series is affordable. Two properties hang off that.
 *
 * The first is the count. `addGeoreferenceAnnotationByUrl` resolves with
 * `(string | Error)[]` — one entry per georeferenced map in the annotation. A
 * sheet that fails to parse comes back as an `Error` *inside a fulfilled
 * promise*; only a fetch that throws rejects. Counting rejections alone reports
 * every series complete no matter how much of it is missing, and a half-drawn
 * series looks exactly like a series with gaps in the survey.
 *
 * The second is which sheets are asked for at all. The renderer draws only the
 * maps in the viewport, but it cannot know a sheet exists until its annotation
 * has been fetched — so the layer used to pay 56 round trips to draw the four
 * sheets on screen. `maps.bbox` answers that for nothing, and `loaded` is what
 * makes the same call safe to fire again on every `moveend`: a sheet already in
 * the layer is never asked for twice, however many times the reader pans back
 * over it.
 */

/** A layer that answers the way @allmaps/openlayers does, per scripted result. */
function fakeLayer(results: ((string | Error)[] | Error)[]) {
  let i = 0;
  const calls: string[] = [];
  return {
    calls,
    opacity: null as number | null,
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

/** What `annotationUrlForSource` makes of a bare id — the layer sees this, not the id. */
const ann = (id: string) => `https://annotations.allmaps.org/images/${id}`;

const fakeMap = () => ({
  renders: 0,
  render() {
    this.renders += 1;
  },
});

/** A sheet at a 1°×1° cell with its lower-left corner at (lon, lat). */
const sheet = (id: string, lon: number, lat: number): SeriesSheetSource => ({
  id,
  source: id,
  bbox: [lon, lat, lon + 1, lat + 1],
});

const state = (sheets: SeriesSheetSource[]) => ({ sheets, loaded: new Set<string>() });

const run = (
  layer: any,
  map: any,
  st: ReturnType<typeof state>,
  view: [number, number, number, number] | null = null,
  opacity = 0.8
) => loadSeriesInView(layer as never, map as never, st, view, opacity);

// ── Counting what arrived ────────────────────────────────────────

test('every sheet that loads is counted once', async () => {
  const layer = fakeLayer([['map-a'], ['map-b'], ['map-c']]);
  const map = fakeMap();
  const st = state([sheet('a', 0, 0), sheet('b', 0, 0), sheet('c', 0, 0)]);
  expect(await run(layer, map, st)).toEqual({ loaded: 3, failed: 0 });
  expect(map.renders).toBe(1); // repainted once at the end, not per sheet
});

test('an Error inside a fulfilled promise is a failed sheet, not a loaded one', async () => {
  // The whole point. Without this branch the series below reports 3 loaded.
  const layer = fakeLayer([['map-a'], [new Error('unparseable')], ['map-c']]);
  const st = state([sheet('a', 0, 0), sheet('b', 0, 0), sheet('c', 0, 0)]);
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 2, failed: 1 });
});

test('a rejected fetch is a failed sheet too', async () => {
  const layer = fakeLayer([['map-a'], new Error('404'), ['map-c']]);
  const st = state([sheet('a', 0, 0), sheet('b', 0, 0), sheet('c', 0, 0)]);
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 2, failed: 1 });
});

test('both failure shapes count together', async () => {
  const layer = fakeLayer([new Error('404'), [new Error('bad')], ['map-c']]);
  const st = state([sheet('a', 0, 0), sheet('b', 0, 0), sheet('c', 0, 0)]);
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 1, failed: 2 });
});

test('one annotation carrying several maps counts each of them', async () => {
  // A Georeference Annotation may hold more than one map, so the count is of
  // sheets drawn, not of URLs fetched — 56 rows can be more than 56 maps.
  const layer = fakeLayer([['map-a', 'map-b'], ['map-c']]);
  const st = state([sheet('a', 0, 0), sheet('b', 0, 0)]);
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 3, failed: 0 });
});

test('an empty series is a no-op, not a crash', async () => {
  const layer = fakeLayer([]);
  const map = fakeMap();
  expect(await run(layer, map, state([]))).toEqual({ loaded: 0, failed: 0 });
  expect(layer.calls).toEqual([]);
  expect(map.renders).toBe(0); // nothing changed, so nothing is repainted
});

test('the requested opacity reaches the layer even when nothing loads', async () => {
  // Opacity is the reader dragging a slider, which is the common case and never
  // fetches anything. It has to apply before the early return, not after it.
  const layer = fakeLayer([]);
  await run(layer, fakeMap(), state([]), null, 0.42);
  expect(layer.opacity).toBe(0.42);
});

// ── Which sheets are asked for ───────────────────────────────────

test('only the sheets in view are fetched', async () => {
  const layer = fakeLayer([['near']]);
  const st = state([sheet('near', 0, 0), sheet('far', 50, 50)]);
  expect(await run(layer, fakeMap(), st, [0, 0, 0.5, 0.5])).toEqual({ loaded: 1, failed: 0 });
  expect(layer.calls).toEqual([ann('near')]);
});

test('a pan fetches what has newly come into view and nothing else', async () => {
  const layer = fakeLayer([['a'], ['b']]);
  const st = state([sheet('a', 0, 0), sheet('b', 10, 0)]);
  await run(layer, fakeMap(), st, [0.2, 0.2, 0.4, 0.4]);
  await run(layer, fakeMap(), st, [10.2, 0.2, 10.4, 0.4]);
  expect(layer.calls).toEqual([ann('a'), ann('b')]);
});

test('panning back over a loaded sheet fetches nothing', async () => {
  // The property that makes this safe to call on every moveend.
  const layer = fakeLayer([['a']]);
  const st = state([sheet('a', 0, 0)]);
  await run(layer, fakeMap(), st, [0.2, 0.2, 0.4, 0.4]);
  const again = await run(layer, fakeMap(), st, [0.2, 0.2, 0.4, 0.4]);
  expect(again).toEqual({ loaded: 0, failed: 0 });
  expect(layer.calls).toEqual([ann('a')]);
});

test('the viewport is padded, so a sheet just off screen is already loaded', async () => {
  // A sheet that only becomes visible after the pan has finished is a sheet the
  // reader watches arrive. The pad is what buys the half-screen of warning.
  const layer = fakeLayer([['next']]);
  const st = state([sheet('next', 1, 0)]);
  // The view is 0..1 in x; the sheet starts at 1. Unpadded they only touch.
  expect(await run(layer, fakeMap(), st, [0, 0, 0.9, 1])).toEqual({ loaded: 1, failed: 0 });
});

test('a sheet with no bbox is always loaded', async () => {
  // Not knowing where something is is not a reason to hide it.
  const layer = fakeLayer([['nowhere']]);
  const st = state([{ id: 'nowhere', source: 'nowhere' }]);
  expect(await run(layer, fakeMap(), st, [50, 50, 51, 51])).toEqual({ loaded: 1, failed: 0 });
});

test('no viewport means the whole series, which is what a headless caller gets', async () => {
  const layer = fakeLayer([['a'], ['b']]);
  const st = state([sheet('a', 0, 0), sheet('b', 50, 50)]);
  expect(await run(layer, fakeMap(), st, null)).toEqual({ loaded: 2, failed: 0 });
});

test('a sheet is claimed before its fetch, so two calls in flight do not double it', async () => {
  // moveend fires again inside the round trip. Without claiming up front the
  // second call sees an unloaded sheet and asks for it a second time — which is
  // the same fault, at one sheet a pan, that cost the series four whole loads.
  const layer = fakeLayer([['a'], ['a']]);
  const st = state([sheet('a', 0, 0)]);
  const view: [number, number, number, number] = [0.2, 0.2, 0.4, 0.4];
  await Promise.all([run(layer, fakeMap(), st, view), run(layer, fakeMap(), st, view)]);
  expect(layer.calls).toEqual([ann('a')]);
});
