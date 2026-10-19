/**
 * Shared WarpedMapLayer lifecycle utilities.
 *
 * Extracted from StudioMap + TripTracker so every mode
 * (shell, annotate, trip, lab) uses the same proven code.
 */

import type { WarpedMapLayer } from '@allmaps/openlayers';
import { annotationUrlForSource } from '$lib/core/iiif/annotationUrl';
import type Map from 'ol/Map';

// Unmanaged Allmaps layers do not appear in map.getLayers(). Keep their loaded
// source identities so layer actions can trace the same transformed edge they draw.
const layersByMap = new WeakMap<Map, Set<WarpedMapLayer>>();
const ownerByLayer = new WeakMap<WarpedMapLayer, Map>();
const idsBySource = new WeakMap<WarpedMapLayer, globalThis.Map<string, string[]>>();

export function loadedSheetEdges(map: Map, source: string): number[][][] {
  const rings: number[][][] = [];
  for (const layer of layersByMap.get(map) ?? []) {
    for (const id of idsBySource.get(layer)?.get(source) ?? []) {
      const ring = layer.getWarpedMap(id)?.geoMask;
      if (ring?.length) rings.push(ring.map((point) => [...point]));
    }
  }
  return rings;
}

// ── Create / destroy ─────────────────────────────────────────────

/**
 * Creates a WarpedMapLayer with the required OL polyfills
 * and attaches it to the map via setMap().
 *
 * The import is dynamic, and that is the only reason this is async.
 * @allmaps/openlayers pulls @allmaps/render, /transform and proj4 behind it —
 * about 180 kB gzipped, which is more than OpenLayers itself — and this is the
 * single runtime import of it in the whole app (everything else takes the type
 * only). Statically imported, every visitor to /explore paid for it before the
 * basemap drew, whether or not they ever put a historical sheet on the map.
 * Now it arrives with the first sheet.
 */
type ImageInfoLoader = { loadMissingImagesInViewport(): Promise<void>[] };

/**
 * Installed Allmaps WebGL2Renderer.render discards this method's promises.
 * Observe those exact requests so map eviction's expected AbortError is handled;
 * return the original promises so callers that await them retain failure semantics.
 */
export function observeImageInfoLoads(
  renderer: ImageInfoLoader,
  report: (error: unknown) => void = (error) =>
    console.error('[Allmaps] Image information failed:', error)
): void {
  const load = renderer.loadMissingImagesInViewport.bind(renderer);
  renderer.loadMissingImagesInViewport = () => {
    const requests = load();
    for (const request of requests) {
      void request.catch((error: unknown) => {
        if (error && typeof error === 'object' && 'name' in error && error.name === 'AbortError')
          return;
        report(error);
      });
    }
    return requests;
  };
}

export async function createWarpedLayer(
  map: Map,
  opts: { zIndex?: number; name?: string } = {}
): Promise<WarpedMapLayer> {
  const { WarpedMapLayer } = await import('@allmaps/openlayers');
  const layer = new WarpedMapLayer();
  // Upstream marks this method protected, but its WebGL renderer drops the
  // promises it creates. Keep the version-specific compatibility shim here.
  observeImageInfoLoads(layer.renderer as unknown as ImageInfoLoader);
  layer.setZIndex(opts.zIndex ?? 10);
  layer.setProperties({ name: opts.name ?? 'allmaps-overlay' });

  // Polyfills required by some OL versions
  const compat = layer as unknown as {
    getDeclutter?: () => boolean;
    renderDeferred?: (...args: unknown[]) => boolean;
  };
  if (!compat.getDeclutter) compat.getDeclutter = () => false;
  if (!compat.renderDeferred) compat.renderDeferred = () => false;

  // Must use setMap(), not the layers array
  const cast = layer as unknown as { setMap?: (m: unknown) => void };
  cast.setMap?.(map as unknown);

  clearBeforeEachFrame(layer);

  const layers = layersByMap.get(map) ?? new Set<WarpedMapLayer>();
  layers.add(layer);
  layersByMap.set(map, layers);
  ownerByLayer.set(layer, map);
  idsBySource.set(layer, new globalThis.Map());

  return layer;
}

/**
 * Wipe the WebGL canvas before every frame the layer draws.
 *
 * @allmaps/render's WebGL2Renderer.render() does not clear: the only
 * gl.clear(COLOR_BUFFER_BIT) it owns sits in clear(), a teardown path that also
 * empties the tile cache. Per frame it relies on the implicit clear a browser
 * performs when it composites a canvas whose context was created with
 * preserveDrawingBuffer false (WarpedMapLayer.ts does not pass the flag, so it
 * is false). When the compositor coalesces or skips that step — its choice, not
 * ours, which is why this reproduces on one profile and not another on the same
 * GPU — the previous frames survive and each new one draws over them. Panning
 * ghosts along the drag; zooming leaves a scaled fan of copies.
 *
 * #renderInternal redraws every map in the viewport each frame, so an explicit
 * clear first can never leave a gap. Where the browser was already clearing,
 * this is a no-op.
 *
 * ponytail: monkey-patch over a fork. It is six lines against an upstream beta
 * that may well fix this; drop it when @allmaps/render clears for itself.
 */
function clearBeforeEachFrame(layer: WarpedMapLayer): void {
  const host = layer as unknown as {
    render: (frameState: unknown) => unknown;
    renderer?: { gl?: WebGL2RenderingContext };
  };
  const inner = host.render.bind(layer);
  host.render = (frameState: unknown) => {
    const gl = host.renderer?.gl;
    if (gl) {
      gl.clearColor(0, 0, 0, 0); // transparent, so the basemap still shows through
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    }
    return inner(frameState);
  };
}

/**
 * Detaches a WarpedMapLayer from the map.
 */
export function destroyWarpedLayer(layer: WarpedMapLayer): void {
  if (destroyedLayers.has(layer)) return;
  destroyedLayers.add(layer);
  invalidateSeriesLoads(layer);
  const owner = ownerByLayer.get(layer);
  if (owner) layersByMap.get(owner)?.delete(layer);
  ownerByLayer.delete(layer);
  // Free every already-parsed map's GL textures/VAOs now. Annotation fetches
  // cannot be aborted, so only their minimal parser/context survives until idle.
  const ids = new Set([
    ...(layer.getMapIds?.() ?? []),
    ...[...(idsBySource.get(layer)?.values() ?? [])].flat(),
  ]);
  const cast = layer as unknown as { setMap?: (m: unknown) => void };
  cast.setMap?.(null);
  for (const id of ids) layer.removeGeoreferencedMapById(id);
  idsBySource.delete(layer);
  // Abort image fetches immediately while non-abortable annotation requests
  // finish. The installed renderer destroy path omits its sprite tile cache.
  layer.renderer?.tileCache?.clear();
  layer.renderer?.spritesTileCache?.clear();
  disposeIfIdle(layer);
}

// ── Load overlay ─────────────────────────────────────────────────

/**
 * Loads an overlay into a WarpedMapLayer using `addGeoreferenceAnnotationByUrl`.
 *
 * Same approach as TripTracker. The WarpedMapLayer handles fetching + parsing.
 * Calls `map.render()` after load to force a repaint (critical).
 */
export async function loadOverlayByUrl(
  layer: WarpedMapLayer,
  map: Map,
  source: string,
  opacity = 0.8
): Promise<void> {
  // Clear any previous overlay
  invalidateSeriesLoads(layer);
  clearLayerMaps(layer);
  idsBySource.get(layer)?.clear();

  const generation = layerGeneration.get(layer) ?? 0;
  startLayerRequest(layer);
  try {
    const added = await layer.addGeoreferenceAnnotationByUrl(annotationUrlForSource(source));
    const ids = added.filter((id): id is string => typeof id === 'string');
    if (destroyedLayers.has(layer) || (layerGeneration.get(layer) ?? 0) !== generation) {
      const retained = new Set([...(idsBySource.get(layer)?.values() ?? [])].flat());
      for (const id of ids) if (!retained.has(id)) layer.removeGeoreferencedMapById(id);
      return;
    }
    idsBySource.get(layer)?.set(source, ids);
    layer.setOpacity(opacity);
    map.render();
  } finally {
    finishLayerRequest(layer);
  }
}

/**
 * One sheet of a series: its annotation source and where on the ground it is.
 *
 * Named `…Source` because `data/maps/seriesSheets.ts` already exports a
 * `SeriesSheet`, and that one is a row of the `series_sheets` table — the
 * survey's own denominator, what it contains whether or not the archive holds
 * it. This is the other end: a sheet the archive *has*, reduced to the two
 * things drawing it needs. (The two files also each had a `fetchSeriesSheets`,
 * against different tables with different signatures; the index reader is
 * `fetchSeriesSheetIndex` now, and this one kept the name. Nothing imported
 * both, but the trap is worth a sentence even after the collision is gone —
 * read the import line before assuming which side of the survey you have.)
 *
 * The bbox is what makes a 627-sheet survey affordable. A `WarpedMapLayer` only
 * ever *draws* the maps in the viewport — `loadMissingImagesInViewport` is the
 * renderer's own rule — but it cannot know a sheet exists, let alone where, until
 * its annotation has been fetched and parsed. So handing it the whole series
 * up front paid 56 round trips to learn that four of them were on screen.
 * `maps.bbox` already says where each sheet is, in the row the picker read, so
 * the same question is answered for nothing before any of it is fetched.
 */
export type SeriesSheetSource = {
  id: string;
  source: string;
  bbox?: [number, number, number, number];
};

/** Incremental loader state for one series layer. */
export type SeriesLoad = {
  sheets: SeriesSheetSource[];
  loaded: Set<string>;
  /** When supplied by the overview/detail manager, this is a hard admission budget. */
  admitted?: Set<string>;
};

// Shared across series and overlapping moveend calls, so adding another layer
// cannot multiply the browser's annotation request budget.
export const SERIES_REQUEST_LIMIT = 6;
/** Soft source budget: every visible sheet is protected, even in a wide overview. */
export const SERIES_CACHE_LIMIT = 64;
const SERIES_RETRY_DELAY_MS = 30_000;
type SeriesRuntime = {
  pending: Set<string>;
  retryAfter: globalThis.Map<string, number>;
  box: [number, number, number, number] | null;
  view: [number, number, number, number] | null;
  recent: globalThis.Map<string, number>;
  visible: Set<string>;
  offscreen: Set<string>;
  clock: number;
  generation: number;
};
const seriesRuntime = new WeakMap<SeriesLoad, SeriesRuntime>();
const layerGeneration = new WeakMap<WarpedMapLayer, number>();
const destroyedLayers = new WeakSet<WarpedMapLayer>();
const disposedLayers = new WeakSet<WarpedMapLayer>();
const requestsByLayer = new WeakMap<WarpedMapLayer, number>();

/** Replace a series admission set and immediately release no-longer-selected maps. */
export function retainSeriesSources(
  layer: WarpedMapLayer,
  state: SeriesLoad,
  sheets: SeriesSheetSource[]
): void {
  state.sheets = [...sheets];
  state.admitted = new Set(sheets.map((sheet) => sheet.source));
  const runtime = seriesRuntime.get(state);
  const sources = idsBySource.get(layer);
  const evictedIds = new Set<string>();
  for (const source of state.loaded) {
    if (state.admitted.has(source)) continue;
    for (const id of sources?.get(source) ?? []) evictedIds.add(id);
    sources?.delete(source);
    state.loaded.delete(source);
    runtime?.recent.delete(source);
    runtime?.retryAfter.delete(source);
    runtime?.visible.delete(source);
    runtime?.offscreen.delete(source);
  }
  const retainedIds = new Set([...(sources?.values() ?? [])].flat());
  for (const id of evictedIds) if (!retainedIds.has(id)) layer.removeGeoreferencedMapById(id);
  // Pending work checks admission before it starts and after a fetch settles.
  // Do not clear pending: re-admitting a source must share its existing request.
}

function disposeIfIdle(layer: WarpedMapLayer): void {
  if (!destroyedLayers.has(layer) || disposedLayers.has(layer) || requestsByLayer.get(layer))
    return;
  disposedLayers.add(layer);
  // Allmaps dispose destroys GPU resources, tile caches, its worker and ResizeObserver.
  // Wait for non-abortable annotation fetches to settle before destroying their renderer.
  layer.dispose?.();
}

function startLayerRequest(layer: WarpedMapLayer): void {
  requestsByLayer.set(layer, (requestsByLayer.get(layer) ?? 0) + 1);
}

function finishLayerRequest(layer: WarpedMapLayer): void {
  requestsByLayer.set(layer, (requestsByLayer.get(layer) ?? 1) - 1);
  disposeIfIdle(layer);
}

/** Evict oldest offscreen sources; nearby padded sheets are refreshed on each pan. */
function trimSeriesCache(
  layer: WarpedMapLayer,
  state: SeriesLoad,
  runtime: SeriesRuntime
): boolean {
  if (state.loaded.size <= SERIES_CACHE_LIMIT) return false;
  if (!runtime.offscreen.size) return false;
  const sources = idsBySource.get(layer);
  const candidates = [...runtime.offscreen].sort(
    (a, b) => (runtime.recent.get(a) ?? 0) - (runtime.recent.get(b) ?? 0)
  );
  let removed = false;
  for (const source of candidates) {
    if (state.loaded.size <= SERIES_CACHE_LIMIT) break;
    const ids = sources?.get(source) ?? [];
    sources?.delete(source);
    const retained = new Set([...(sources?.values() ?? [])].flat());
    // The public removal path destroys the map's GL textures/VAOs and aborts image
    // loads. Renderer viewport pruning separately bounds CPU tiles (100 delayed).
    for (const id of ids) if (!retained.has(id)) layer.removeGeoreferencedMapById(id);
    state.loaded.delete(source);
    runtime.recent.delete(source);
    runtime.offscreen.delete(source);
    removed = true;
  }
  return removed;
}
let activeSeriesRequests = 0;
const seriesQueue: (() => Promise<void>)[] = [];

function invalidateSeriesLoads(layer: WarpedMapLayer): void {
  layerGeneration.set(layer, (layerGeneration.get(layer) ?? 0) + 1);
}

function drainSeriesQueue(): void {
  while (activeSeriesRequests < SERIES_REQUEST_LIMIT && seriesQueue.length) {
    const job = seriesQueue.shift()!;
    activeSeriesRequests += 1;
    void job().finally(() => {
      activeSeriesRequests -= 1;
      drainSeriesQueue();
    });
  }
}

function scheduleSeriesRequest<T>(work: () => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    seriesQueue.push(async () => {
      try {
        resolve(await work());
      } catch (error) {
        reject(error);
      }
    });
    drainSeriesQueue();
  });
}

function intersects(
  a: [number, number, number, number],
  b: [number, number, number, number]
): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

/** Grow an extent by `ratio` about its own centre, so a short pan draws no blank. */
function pad(e: [number, number, number, number], ratio: number): [number, number, number, number] {
  const dx = ((e[2] - e[0]) * (ratio - 1)) / 2;
  const dy = ((e[3] - e[1]) * (ratio - 1)) / 2;
  return [e[0] - dx, e[1] - dy, e[2] + dx, e[3] + dy];
}

/** How much ground beyond the viewport counts as "about to be looked at". */
const SERIES_VIEWPORT_PAD = 1.5;

/**
 * Loads the sheets of a series that the reader can currently see, into one layer.
 *
 * A `WarpedMapLayer` is a *set* of georeferenced maps, not one of them —
 * `addGeoreferenceAnnotationByUrl` is additive — so a whole series costs one OL
 * layer, one z-index and one opacity rather than 56 of each. That is the whole
 * reason a live-warped series is affordable at all; the alternative is the
 * pre-tiled mosaic L7014 needs, which is 4 GB and a pipeline.
 *
 * Successful sources and pending requests are tracked separately. A later pan
 * retries failed sources after a cooldown, without a timer retrying indefinitely.
 * Queued work checks the latest viewport before starting; requests already sent
 * cannot be aborted by Allmaps. A missing bbox still loads unconditionally.
 * Retain at most 64 sources after long pans, except currently visible sheets:
 * overview rendering stays complete and may exceed this soft budget. Padded
 * neighbors are favored over older offscreen sheets. Evicted sources can reload.
 *
 * Counts include Error entries returned by Allmaps as well as rejected fetches.
 * Partially parsed annotations retain their valid maps and are not re-added.
 */
export async function loadSeriesInView(
  layer: WarpedMapLayer,
  map: Map,
  state: SeriesLoad,
  view: [number, number, number, number] | null,
  opacity = 0.8
): Promise<{ loaded: number; failed: number }> {
  if (destroyedLayers.has(layer)) return { loaded: 0, failed: 0 };
  let runtime = seriesRuntime.get(state);
  if (!runtime) {
    runtime = {
      pending: new Set(),
      retryAfter: new globalThis.Map(),
      box: null,
      view: null,
      recent: new globalThis.Map(),
      visible: new Set(),
      offscreen: new Set(),
      clock: 0,
      generation: layerGeneration.get(layer) ?? 0,
    };
    if (!idsBySource.has(layer)) idsBySource.set(layer, new globalThis.Map());
    seriesRuntime.set(state, runtime);
  }
  const current = runtime;
  current.box = view ? pad(view, SERIES_VIEWPORT_PAD) : null;
  current.view = view;
  const generation = layerGeneration.get(layer) ?? 0;
  if (current.generation !== generation) {
    state.loaded.clear();
    current.recent.clear();
    current.retryAfter.clear();
    current.generation = generation;
  }
  const valid = () =>
    !destroyedLayers.has(layer) && (layerGeneration.get(layer) ?? 0) === generation;
  const admitted = (s: SeriesSheetSource) => !state.admitted || state.admitted.has(s.source);
  const inView = (s: SeriesSheetSource) =>
    !current.box || !s.bbox || intersects(s.bbox, current.box);

  current.visible = new Set();
  for (const sheet of state.sheets) {
    if (!view || !sheet.bbox || intersects(sheet.bbox, view)) current.visible.add(sheet.source);
    if (state.loaded.has(sheet.source) && inView(sheet))
      current.recent.set(sheet.source, ++current.clock);
  }
  current.offscreen = new Set([...state.loaded].filter((source) => !current.visible.has(source)));
  const evicted = trimSeriesCache(layer, state, current);
  layer.setOpacity(opacity);
  const jobs: Promise<{ loaded: number; failed: number }>[] = [];
  for (const s of state.sheets) {
    if (!admitted(s) || state.loaded.has(s.source) || current.pending.has(s.source) || !inView(s))
      continue;
    if ((current.retryAfter.get(s.source) ?? 0) > Date.now()) continue;
    current.pending.add(s.source);
    jobs.push(
      scheduleSeriesRequest(async () => {
        let started = false;
        try {
          if (!valid() || !admitted(s) || !inView(s)) return { loaded: 0, failed: 0 };
          startLayerRequest(layer);
          started = true;
          const added = await layer.addGeoreferenceAnnotationByUrl(
            annotationUrlForSource(s.source)
          );
          const ids = added.filter((id): id is string => typeof id === 'string');
          if (!valid() || !admitted(s)) {
            // The request cannot be aborted, but its late result must not restore
            // a cleared/destroyed overlay. Keep any ID a newer load already owns.
            const retained = new Set([...(idsBySource.get(layer)?.values() ?? [])].flat());
            for (const id of ids) if (!retained.has(id)) layer.removeGeoreferencedMapById(id);
            return { loaded: 0, failed: 0 };
          }
          if (ids.length) {
            idsBySource.get(layer)?.set(s.source, ids);
            state.loaded.add(s.source);
            current.retryAfter.delete(s.source);
            current.recent.set(s.source, ++current.clock);
            if (!current.visible.has(s.source)) current.offscreen.add(s.source);
            trimSeriesCache(layer, state, current);
          } else {
            current.retryAfter.set(s.source, Date.now() + SERIES_RETRY_DELAY_MS);
          }
          return { loaded: ids.length, failed: added.length - ids.length || (ids.length ? 0 : 1) };
        } catch {
          if (!valid() || !admitted(s)) return { loaded: 0, failed: 0 };
          current.retryAfter.set(s.source, Date.now() + SERIES_RETRY_DELAY_MS);
          return { loaded: 0, failed: 1 };
        } finally {
          current.pending.delete(s.source);
          if (started) finishLayerRequest(layer);
        }
      })
    );
  }
  const results = await Promise.all(jobs);
  if ((jobs.length || evicted) && valid()) map.render();
  return results.reduce(
    (total, result) => ({
      loaded: total.loaded + result.loaded,
      failed: total.failed + result.failed,
    }),
    { loaded: 0, failed: 0 }
  );
}

// ── Opacity ──────────────────────────────────────────────────────

/**
 * Sets opacity directly on the WarpedMapLayer.
 * Uses layer.setOpacity() which is the approach that works in TripTracker.
 */
export function setOverlayOpacity(layer: WarpedMapLayer, map: Map, opacity: number): void {
  (layer as any).setOpacity(opacity);
  map.render();
}

/** The installed Allmaps clear drops its list without destroying each map's GL state. */
function clearLayerMaps(layer: WarpedMapLayer): void {
  const ids = layer.getMapIds?.() ?? [...(idsBySource.get(layer)?.values() ?? [])].flat();
  for (const id of new Set(ids)) layer.removeGeoreferencedMapById(id);
  layer.clear();
}

export function clearOverlay(layer: WarpedMapLayer, map?: Map): void {
  invalidateSeriesLoads(layer);
  clearLayerMaps(layer);
  idsBySource.get(layer)?.clear();
  map?.render();
}

// ── View mode clip mask ──────────────────────────────────────────

export type ViewModeClip = 'overlay' | 'spy' | 'dual';

/**
 * Applies a CSS clip-path on the WarpedMapLayer canvas to implement
 * side-by-side and spy-glass comparison modes.
 *
 * This is the exact same logic from StudioMap.updateClipMask().
 */
export function applyClipMask(
  layer: WarpedMapLayer,
  map: Map,
  mode: ViewModeClip,
  lensRadius: number
): void {
  const canvas = layer.canvas;
  if (!canvas) return;

  const size = map.getSize();
  if (!size) return;
  const [w, h] = size;

  switch (mode) {
    case 'spy': {
      canvas.style.clipPath = `circle(${lensRadius}px at ${w / 2}px ${h / 2}px)`;
      break;
    }
    default:
      canvas.style.clipPath = '';
  }
}
