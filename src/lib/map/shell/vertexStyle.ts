import Style from 'ol/style/Style';
import Fill from 'ol/style/Fill';
import Stroke from 'ol/style/Stroke';
import CircleStyle from 'ol/style/Circle';
import MultiPoint from 'ol/geom/MultiPoint';
import Polygon from 'ol/geom/Polygon';
import LineString from 'ol/geom/LineString';
import type { FeatureLike } from 'ol/Feature';
import { INK } from '$lib/core/ink';

/** A dot on every vertex of a polygon's outer ring or a line — so a shape's point count is visible. */
export function vertexStyle(color: string): Style {
  return new Style({
    image: new CircleStyle({
      radius: 3.5,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: INK.paper, width: 1 }),
    }),
    geometry: (feature: FeatureLike) => {
      const g = feature.getGeometry();
      if (g instanceof Polygon) return new MultiPoint(g.getCoordinates()[0].slice(0, -1));
      if (g instanceof LineString) return new MultiPoint(g.getCoordinates());
      return undefined;
    },
  });
}
