import { expect, test } from '@playwright/test';
import {
  clearOverlay,
  destroyWarpedLayer,
  loadSeriesInView,
  retainSeriesSources,
  SERIES_REQUEST_LIMIT,
  SERIES_CACHE_LIMIT,
  type SeriesSheetSource,
} from '../src/lib/map/shell/warpedOverlay';

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

/** Hold requests until released so concurrency and stale work are observable. */
function heldLayer() {
  const calls: string[] = [];
  const releases: (() => void)[] = [];
  const removed: string[] = [];
  return {
    calls,
    releases,
    removed,
    setOpacity() {},
    setMap() {},
    clear() {},
    removeGeoreferencedMapById(id: string) {
      removed.push(id);
    },
    addGeoreferenceAnnotationByUrl(url: string): Promise<string[]> {
      calls.push(url);
      return new Promise((resolve) => releases.push(() => resolve([url])));
    },
  };
}
const tick = () => new Promise<void>((resolve) => setImmediate(resolve));
const manySheets = (count: number, prefix = 'sheet', lon = 0) =>
  Array.from({ length: count }, (_, i) => sheet(`${prefix}-${i}`, lon, 0));

test('a large series and a second layer share one request budget', async () => {
  const first = heldLayer();
  const second = heldLayer();
  const a = run(first, fakeMap(), state(manySheets(20)));
  const b = run(second, fakeMap(), state(manySheets(10, 'other')));
  expect(first.calls.length + second.calls.length).toBe(SERIES_REQUEST_LIMIT);
  let peak = 0;
  for (let round = 0; round < 30; round += 1) {
    const active = first.releases.length + second.releases.length;
    peak = Math.max(peak, active);
    if (!active) break;
    first.releases.splice(0).forEach((release) => release());
    second.releases.splice(0).forEach((release) => release());
    await tick();
  }
  expect(await a).toEqual({ loaded: 20, failed: 0 });
  expect(await b).toEqual({ loaded: 10, failed: 0 });
  expect(peak).toBe(SERIES_REQUEST_LIMIT);
});

test('rapid panning drops queued old-view sheets and loads the new viewport', async () => {
  const layer = heldLayer();
  const st = state([...manySheets(20), sheet('new-view', 50, 0)]);
  const first = run(layer, fakeMap(), st, [0, 0, 1, 1]);
  const second = run(layer, fakeMap(), st, [50, 0, 51, 1]);
  layer.releases.splice(0).forEach((release) => release());
  await tick();
  expect(layer.calls).toHaveLength(SERIES_REQUEST_LIMIT + 1);
  expect(layer.calls.at(-1)).toBe(ann('new-view'));
  layer.releases.splice(0).forEach((release) => release());
  expect(await first).toEqual({ loaded: SERIES_REQUEST_LIMIT, failed: 0 });
  expect(await second).toEqual({ loaded: 1, failed: 0 });
  expect(st.loaded.has('sheet-19')).toBe(false);
});

test('duplicate sources within one series only fetch once', async () => {
  const layer = fakeLayer([['map']]);
  expect(await run(layer, fakeMap(), state([sheet('same', 0, 0), sheet('same', 0, 0)]))).toEqual({
    loaded: 1,
    failed: 0,
  });
  expect(layer.calls).toEqual([ann('same')]);
});

test('failed fetches and parse failures retry after a cooldown on a later call', async () => {
  const originalNow = Date.now;
  let now = originalNow();
  Date.now = () => now;
  try {
    const layer = fakeLayer([new Error('404'), [new Error('parse')], ['a'], ['b']]);
    const st = state([sheet('a', 0, 0), sheet('b', 0, 0)]);
    expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 0, failed: 2 });
    expect(st.loaded.size).toBe(0);
    expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 0, failed: 0 });
    now += 30_001;
    expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 2, failed: 0 });
    expect(layer.calls).toHaveLength(4);
  } finally {
    Date.now = originalNow;
  }
});

test('clearing or destroying a layer discards queued work and removes late results', async () => {
  for (const invalidate of [clearOverlay, destroyWarpedLayer]) {
    const layer = heldLayer();
    const map = fakeMap();
    const st = state(manySheets(20));
    const result = run(layer, map, st);
    invalidate(layer as never);
    layer.releases.splice(0).forEach((release) => release());
    expect(await result).toEqual({ loaded: 0, failed: 0 });
    expect(layer.calls).toHaveLength(SERIES_REQUEST_LIMIT);
    expect(layer.removed).toHaveLength(SERIES_REQUEST_LIMIT);
    expect(st.loaded.size).toBe(0);
    expect(map.renders).toBe(0);
  }
});

/** Resources model the installed Allmaps removal contract: map destruction frees GL state. */
function resourceLayer() {
  const resources = new Set<string>();
  const removed: string[] = [];
  const calls: string[] = [];
  return {
    resources,
    removed,
    calls,
    clear() {},
    getMapIds() {
      return [...resources];
    },
    setOpacity() {},
    async addGeoreferenceAnnotationByUrl(url: string) {
      calls.push(url);
      resources.add(url);
      return [url];
    },
    removeGeoreferencedMapById(id: string) {
      if (!resources.delete(id)) throw new Error(`Already removed ${id}`);
      removed.push(id);
      return id;
    },
  };
}

test('hundreds of distant pans keep parsed maps and renderer resources stable, then reload evicted sheets', async () => {
  const layer = resourceLayer();
  const st = state(Array.from({ length: 250 }, (_, i) => sheet(`pan-${i}`, i * 3, 0)));
  for (let i = 0; i < st.sheets.length; i++) {
    await run(layer, fakeMap(), st, [i * 3 + 0.2, 0.2, i * 3 + 0.4, 0.4]);
    expect(st.loaded.size).toBeLessThanOrEqual(SERIES_CACHE_LIMIT);
    expect(layer.resources.size).toBe(st.loaded.size);
    expect(st.loaded.has(`pan-${i}`)).toBe(true);
  }
  expect(layer.removed.length).toBe(250 - SERIES_CACHE_LIMIT);
  expect(st.loaded.has('pan-0')).toBe(false);
  await run(layer, fakeMap(), st, [0.2, 0.2, 0.4, 0.4]);
  expect(layer.calls.filter((url) => url === ann('pan-0'))).toHaveLength(2);
  expect(layer.resources.size).toBe(SERIES_CACHE_LIMIT);
});

test('overview keeps every visible sheet and trims the excess when zooming back in', async () => {
  const layer = resourceLayer();
  const st = state(Array.from({ length: 100 }, (_, i) => sheet(`overview-${i}`, i * 3, 0)));
  await run(layer, fakeMap(), st, [0, 0, 300, 1]);
  expect(st.loaded.size).toBe(100);
  expect(layer.resources.size).toBe(100);
  await run(layer, fakeMap(), st, [0.2, 0.2, 0.4, 0.4]);
  expect(st.loaded.size).toBe(SERIES_CACHE_LIMIT);
  expect(layer.resources.size).toBe(SERIES_CACHE_LIMIT);
  expect(st.loaded.has('overview-0')).toBe(true);
});

test('destroy disposes resources exactly once after pending annotation cleanup finishes', async () => {
  const layer = {
    ...heldLayer(),
    disposals: 0,
    dispose() {
      this.disposals++;
    },
  };
  const pending = run(layer, fakeMap(), state(manySheets(10)));
  destroyWarpedLayer(layer as never);
  destroyWarpedLayer(layer as never);
  expect(layer.disposals).toBe(0);
  layer.releases.splice(0).forEach((release) => release());
  await pending;
  expect(layer.removed).toHaveLength(SERIES_REQUEST_LIMIT);
  expect(layer.disposals).toBe(1);
});

test('clearing a loaded layer releases map resources and resets its series cache on reuse', async () => {
  const layer = resourceLayer();
  const st = state([sheet('reusable', 0, 0)]);
  await run(layer, fakeMap(), st);
  clearOverlay(layer as never);
  expect(layer.resources.size).toBe(0);
  expect(layer.removed).toEqual([ann('reusable')]);
  await run(layer, fakeMap(), st);
  expect(layer.calls).toHaveLength(2);
  expect(layer.resources.size).toBe(1);
});

test('destroy aborts tile and sprite caches before pending annotations settle', async () => {
  const events: string[] = [];
  const layer = {
    ...heldLayer(),
    renderer: {
      tileCache: { clear: () => events.push('tiles') },
      spritesTileCache: { clear: () => events.push('sprites') },
    },
    dispose: () => events.push('dispose'),
  };
  const pending = run(layer, fakeMap(), state(manySheets(10)));
  destroyWarpedLayer(layer as never);
  expect(events).toEqual(['tiles', 'sprites']);
  layer.releases.splice(0).forEach((release) => release());
  await pending;
  expect(events).toEqual(['tiles', 'sprites', 'dispose']);
});

test('a smaller admission allocation immediately releases loaded maps including visible ones', async () => {
  const layer = resourceLayer();
  const sheets = manySheets(12);
  const st = state(sheets);
  await run(layer, fakeMap(), st);
  retainSeriesSources(layer as never, st, sheets.slice(0, 2));
  expect(st.sheets).toHaveLength(2);
  expect(st.loaded.size).toBe(2);
  expect(layer.resources.size).toBe(2);
  expect(layer.removed).toHaveLength(10);
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 0, failed: 0 });
  retainSeriesSources(layer as never, st, sheets.slice(0, 3));
  expect(await run(layer, fakeMap(), st)).toEqual({ loaded: 1, failed: 0 });
  expect(layer.resources.size).toBe(3);
});

test('admission changes cancel queued sheets and discard already fetching unselected sources', async () => {
  const layer = heldLayer();
  const sheets = manySheets(20);
  const st = state(sheets);
  const pending = run(layer, fakeMap(), st);
  retainSeriesSources(layer as never, st, sheets.slice(0, 1));
  layer.releases.splice(0).forEach((release) => release());
  expect(await pending).toEqual({ loaded: 1, failed: 0 });
  expect(layer.calls).toHaveLength(SERIES_REQUEST_LIMIT);
  expect(layer.removed).toHaveLength(SERIES_REQUEST_LIMIT - 1);
  expect([...st.loaded]).toEqual([sheets[0].source]);
});

test('destroy releases loaded GPU maps immediately while an annotation is still fetching', async () => {
  const layer = {
    ...resourceLayer(),
    disposals: 0,
    dispose() {
      this.disposals++;
    },
  };
  const first = sheet('already-loaded', 0, 0);
  const second = sheet('still-fetching', 0, 0);
  const st = state([first]);
  await run(layer, fakeMap(), st);
  let release!: () => void;
  const add = layer.addGeoreferenceAnnotationByUrl.bind(layer);
  layer.addGeoreferenceAnnotationByUrl = async (url: string) => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    return add(url);
  };
  st.sheets = [first, second];
  const pending = run(layer, fakeMap(), st);
  destroyWarpedLayer(layer as never);
  expect(layer.removed).toEqual([ann(first.source)]);
  expect(layer.resources.size).toBe(0);
  expect(layer.disposals).toBe(0);
  release();
  expect(await pending).toEqual({ loaded: 0, failed: 0 });
  expect(layer.removed).toEqual([ann(first.source), ann(second.source)]);
  expect(layer.resources.size).toBe(0);
  expect(layer.disposals).toBe(1);
  destroyWarpedLayer(layer as never);
  expect(layer.disposals).toBe(1);
});
