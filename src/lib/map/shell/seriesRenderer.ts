import Feature from 'ol/Feature';
import MultiPolygon from 'ol/geom/MultiPolygon';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Style from 'ol/style/Style';
import Stroke from 'ol/style/Stroke';
import Fill from 'ol/style/Fill';
import type OlMap from 'ol/Map';
import { getRenderPixel } from 'ol/render';
import { unByKey } from 'ol/Observable';
import type { WarpedMapLayer } from '@allmaps/openlayers';
import { INK, inkAlpha } from '$lib/core/ink';
import { looksValidBbox, type Bbox } from '$lib/core/geo/mapBounds';
import { chooseSeriesRendering } from './seriesRenderPolicy';
import {
  createWarpedLayer,
  destroyWarpedLayer,
  loadSeriesInView,
  retainSeriesSources,
  applyClipMask,
  type SeriesLoad,
  type SeriesSheetSource,
  type ViewModeClip,
} from './warpedOverlay';

export interface SeriesRenderSettings {
  view: Bbox | null;
  allocation: number;
  visible: boolean;
  opacity: number;
  zIndex: number;
  clip: ViewModeClip;
  lensRadius: number;
}
export interface SeriesRenderStatus {
  mode: 'overview' | 'detail' | 'hidden';
  visibleCount: number;
}

/** Overview owns only vector bounds; a live renderer exists only for an admitted detail page. */
export function createSeriesRenderer(
  map: OlMap,
  sheets: SeriesSheetSource[],
  options: { name: string; bounds?: Bbox; onStatus: (status: SeriesRenderStatus) => void }
) {
  const source = new VectorSource<Feature<MultiPolygon>>();
  const overview = new VectorLayer({
    source,
    style: new Style({
      stroke: new Stroke({ color: inkAlpha(INK.blue, 0.8), width: 1 }),
      fill: new Fill({ color: inkAlpha(INK.blue, 0.08) }),
    }),
    properties: { seriesOverview: true },
  });
  // Managed layers let OL release the canvas when this overview is removed.
  map.addLayer(overview);
  overview.setVisible(false);
  let state: SeriesLoad = { sheets: [], loaded: new Set() };
  let layer: WarpedMapLayer | null = null;
  let creating: Promise<void> | null = null;
  let generation = 0;
  let destroyed = false;
  let settings: SeriesRenderSettings | null = null;
  let choice: ReturnType<typeof chooseSeriesRendering> | null = null;
  let mode: SeriesRenderStatus['mode'] = 'hidden';
  let geometryReady = false;
  let reported = '';
  let clippedContext: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null = null;
  const clipEvents = [
    overview.on('prerender', (event) => {
      const context = event.context;
      const size = map.getSize();
      if (settings?.clip !== 'spy' || !context || !('save' in context) || !size) return;
      const center = getRenderPixel(event, [size[0] / 2, size[1] / 2]);
      const edge = getRenderPixel(event, [size[0] / 2 + settings.lensRadius, size[1] / 2]);
      context.save();
      context.beginPath();
      context.arc(
        center[0],
        center[1],
        Math.hypot(edge[0] - center[0], edge[1] - center[1]),
        0,
        Math.PI * 2
      );
      context.clip();
      clippedContext = context;
    }),
    overview.on('postrender', () => {
      clippedContext?.restore();
      clippedContext = null;
    }),
  ];

  function report(nextMode: SeriesRenderStatus['mode'], visibleCount: number) {
    mode = nextMode;
    const key = `${nextMode}:${visibleCount}`;
    if (key === reported) return;
    reported = key;
    options.onStatus({ mode: nextMode, visibleCount });
  }

  function releaseWarped() {
    generation++;
    if (layer) destroyWarpedLayer(layer);
    layer = null;
    state = { sheets: [], loaded: new Set() };
  }

  function showOverview() {
    if (!geometryReady) {
      const bounds = sheets.flatMap((sheet) => (looksValidBbox(sheet.bbox) ? [sheet.bbox] : []));
      if (!bounds.length && looksValidBbox(options.bounds)) bounds.push(options.bounds);
      const polygons = bounds.map(([w, s, e, n]) => [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ]);
      if (polygons.length) {
        const geometry = new MultiPolygon(polygons).transform(
          'EPSG:4326',
          map.getView().getProjection()
        );
        source.addFeature(new Feature(geometry));
      }
      geometryReady = true;
    }
    overview.setVisible(true);
  }

  function loadDetail() {
    if (!layer || !settings || !choice || choice.mode !== 'detail') return;
    const current = layer;
    current.setZIndex(settings.zIndex);
    applyClipMask(current, map, settings.clip, settings.lensRadius);
    retainSeriesSources(current, state, choice.sources);
    // Do not block layer removal, opacity changes or a zoom-out on network requests.
    void loadSeriesInView(current, map, state, settings.view, settings.opacity).catch((error) => {
      if (!destroyed && current === layer) console.warn('[series] Detail load failed', error);
    });
  }

  function ensureWarped() {
    if (creating || layer || destroyed || mode !== 'detail' || !choice?.sources.length) return;
    const token = generation;
    creating = (async () => {
      const next = await createWarpedLayer(map, {
        zIndex: settings!.zIndex,
        name: options.name,
      });
      if (destroyed || token !== generation || mode !== 'detail') {
        destroyWarpedLayer(next);
        return;
      }
      layer = next;
      loadDetail();
    })()
      .catch((error) => {
        if (!destroyed) console.warn('[series] Could not create detail renderer', error);
      })
      .finally(() => {
        creating = null;
        // A rapid out/in can invalidate a pending dynamic import; only its current view may resume.
        if (!destroyed && token !== generation) ensureWarped();
      });
  }

  return {
    intersectsView(view: Bbox | null) {
      return (
        !view ||
        sheets.some(
          (sheet) =>
            !looksValidBbox(sheet.bbox) ||
            (sheet.bbox[0] <= view[2] &&
              sheet.bbox[2] >= view[0] &&
              sheet.bbox[1] <= view[3] &&
              sheet.bbox[3] >= view[1])
        )
      );
    },
    update(next: SeriesRenderSettings) {
      if (destroyed) return;
      const clipChanged = settings?.clip !== next.clip || settings?.lensRadius !== next.lensRadius;
      settings = next;
      if (clipChanged) overview.changed();
      overview.setOpacity(next.opacity);
      overview.setZIndex(next.zIndex);
      if (!next.visible) {
        if (mode !== 'hidden') releaseWarped();
        overview.setVisible(false);
        source.clear();
        geometryReady = false;
        report('hidden', 0);
        return;
      }
      choice = chooseSeriesRendering(
        sheets,
        next.view,
        next.allocation,
        mode === 'overview' ? 'overview' : undefined
      );
      if (choice.mode === 'overview') {
        if (mode !== 'overview') releaseWarped();
        showOverview();
        report('overview', choice.visibleCount);
      } else {
        overview.setVisible(false);
        if (geometryReady) {
          source.clear();
          geometryReady = false;
        }
        report('detail', choice.visibleCount);
        if (!choice.sources.length) {
          releaseWarped();
          return;
        }
        if (layer) loadDetail();
        else ensureWarped();
      }
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      releaseWarped();
      map.removeLayer(overview);
      unByKey(clipEvents);
      source.clear();
      overview.dispose();
    },
  };
}

export type SeriesRenderer = ReturnType<typeof createSeriesRenderer>;
