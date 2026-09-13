/**
 * Shared WarpedMapLayer lifecycle utilities.
 *
 * Extracted from StudioMap + TripTracker so every mode
 * (shell, annotate, trip, lab) uses the same proven code.
 */

import type { WarpedMapLayer } from '@allmaps/openlayers';
import { annotationUrlForSource } from '$lib/core/iiif/annotationUrl';
import type Map from 'ol/Map';

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
export async function createWarpedLayer(
  map: Map,
  opts: { zIndex?: number; name?: string } = {}
): Promise<WarpedMapLayer> {
  const { WarpedMapLayer } = await import('@allmaps/openlayers');
  const layer = new WarpedMapLayer();
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
  const cast = layer as unknown as { setMap?: (m: unknown) => void };
  cast.setMap?.(null);
}

// ── Load overlay ─────────────────────────────────────────────────

// Re-exported from its new home in $lib/core/iiif so existing importers keep working.
export { annotationUrlForSource } from '$lib/core/iiif/annotationUrl';

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
  layer.clear();

  const url = annotationUrlForSource(source);
  await layer.addGeoreferenceAnnotationByUrl(url);

  // Apply opacity directly on the layer (same as TripTracker)
  (layer as any).setOpacity(opacity);

  // Force repaint — without this the tiles won't appear
  map.render();
}

/**
 * One sheet of a series: its annotation source and where on the ground it is.
 *
 * Named `…Source` because `data/maps/seriesSheets.ts` already exports a
 * `SeriesSheet`, and that one is a row of the `series_sheets` table — the
 * survey's own denominator, what it contains whether or not the archive holds
 * it. This is the other end: a sheet the archive *has*, reduced to the two
 * things drawing it needs. (The same two files also each export a
 * `fetchSeriesSheets`, against different tables with different signatures.
 * Nothing imports both, but read the import line before assuming which.)
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
export type SeriesLoad = { sheets: SeriesSheetSource[]; loaded: Set<string> };

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
 * Additive is also what makes this callable again on every `moveend`: `loaded`
 * is the set of sources already in the layer, so panning fetches only what has
 * newly come into view and nothing is ever fetched twice. Sheets are never
 * removed — an annotation already parsed costs nothing to keep, and the
 * renderer draws only what is on screen regardless.
 *
 * A sheet with no bbox is loaded unconditionally: not knowing where something is
 * is not a reason to hide it, and it is the one case where the old behaviour was
 * the right one.
 *
 * Annotations are fetched together and failures counted rather than thrown: one
 * sheet whose annotation 404s should cost the reader that sheet, not the
 * series. The count comes back so the caller can say so.
 *
 * Counting them is less obvious than it looks. `addGeoreferenceAnnotationByUrl`
 * resolves with `(string | Error)[]` — one entry per georeferenced map in the
 * annotation — so a sheet that fails to parse comes back *inside* a fulfilled
 * promise rather than as a rejection. Only a fetch that throws rejects. Both
 * have to be counted, or a half-empty series reports itself complete.
 */
export async function loadSeriesInView(
  layer: WarpedMapLayer,
  map: Map,
  state: SeriesLoad,
  view: [number, number, number, number] | null,
  opacity = 0.8
): Promise<{ loaded: number; failed: number }> {
  const box = view ? pad(view, SERIES_VIEWPORT_PAD) : null;
  const wanted = state.sheets.filter(
    (s) => !state.loaded.has(s.source) && (!box || !s.bbox || intersects(s.bbox, box))
  );

  (layer as any).setOpacity(opacity);
  if (!wanted.length) return { loaded: 0, failed: 0 };

  // Claimed before the await, so a second moveend inside the round trip does
  // not ask for the same sheets again.
  for (const s of wanted) state.loaded.add(s.source);

  const results = await Promise.allSettled(
    wanted.map((s) => layer.addGeoreferenceAnnotationByUrl(annotationUrlForSource(s.source)))
  );

  let loaded = 0;
  let failed = 0;
  for (const r of results) {
    if (r.status === 'rejected') failed += 1;
    else
      for (const entry of r.value) {
        if (entry instanceof Error) failed += 1;
        else loaded += 1;
      }
  }

  map.render();
  return { loaded, failed };
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

export function clearOverlay(layer: WarpedMapLayer, map?: Map): void {
  layer.clear();
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
