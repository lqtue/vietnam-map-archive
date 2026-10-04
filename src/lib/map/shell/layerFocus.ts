import type OlMap from 'ol/Map';
import Feature from 'ol/Feature';
import Polygon, { fromExtent } from 'ol/geom/Polygon';
import VectorSource from 'ol/source/Vector';
import VectorLayer from 'ol/layer/Vector';
import Style from 'ol/style/Style';
import Stroke from 'ol/style/Stroke';
import { transformExtent } from 'ol/proj';
import { createEmpty, extend } from 'ol/extent';
import { unByKey } from 'ol/Observable';
import type { EventsKey } from 'ol/events';
import type { MapListItem } from '$lib/data/maps/types';
import {
  annotationSourceFor,
  looksValidBbox,
  resolveBounds,
  type Bbox,
} from '$lib/core/geo/mapBounds';
import { INK } from '$lib/core/ink';
import { loadedSheetEdges } from './warpedOverlay';

/** Fit the real viewport and briefly mark the selected layer's edge. */
export function createLayerFocus(getMap: () => OlMap | null, getMaps: () => MapListItem[]) {
  let request = 0;
  let outline: VectorLayer<VectorSource> | null = null;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let renderKey: EventsKey | undefined;

  function clear() {
    clearTimeout(timeout);
    if (renderKey) unByKey(renderKey);
    renderKey = undefined;
    outline?.setMap(null);
    outline?.dispose();
    outline = null;
  }

  async function focus(detail: { mapId: string; bounds?: Bbox }) {
    const current = ++request;
    clear();
    const map = getMap();
    if (!map) return;
    const sheet = getMaps().find((item) => item.id === detail.mapId);
    const source = sheet ? annotationSourceFor(sheet) : null;
    const bounds = looksValidBbox(detail.bounds)
      ? detail.bounds
      : sheet
        ? await resolveBounds(sheet)
        : null;
    if (current !== request || !bounds || getMap() !== map) return;
    const projection = map.getView().getProjection();
    const rectangle = fromExtent(transformExtent(bounds, 'EPSG:4326', projection));
    function edges() {
      return (source ? loadedSheetEdges(map!, source) : []).map((ring) => {
        const closed = [...ring, ring[0]];
        return new Polygon([closed]).transform('EPSG:4326', projection);
      });
    }
    const shapes = edges();
    const geometries = shapes.length ? shapes : [rectangle];
    const extent = createEmpty();
    for (const geometry of geometries) extend(extent, geometry.getExtent());
    const vector = new VectorSource({
      features: geometries.map((geometry) => new Feature(geometry)),
    });
    outline = new VectorLayer({
      source: vector,
      // Unmanaged so the outline stays above every overlay, even with a large stack.
      style: [
        new Style({ stroke: new Stroke({ color: INK.paper, width: 7 }) }),
        new Style({ stroke: new Stroke({ color: INK.blue, width: 4 }) }),
      ],
    });
    outline.setMap(map);
    map.getView().cancelAnimations();
    map.getView().fit(extent, {
      size: map.getSize(),
      padding: [20, 20, 20, 20],
      duration: 300,
      maxZoom: 20,
    });
    if (!shapes.length && source) {
      // A series sheet may only start loading after we fly to it.
      renderKey = map.on('postrender', () => {
        const loaded = edges();
        if (!loaded.length || current !== request) return;
        if (renderKey) unByKey(renderKey);
        renderKey = undefined;
        vector.clear();
        vector.addFeatures(loaded.map((geometry) => new Feature(geometry)));
      });
    }
    timeout = setTimeout(() => {
      clear();
    }, 3000);
  }

  return {
    focus,
    destroy() {
      request += 1;
      clear();
    },
  };
}
