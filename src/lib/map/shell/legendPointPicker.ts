/** A draft legend marker and one-click placement on the existing shell map. */
import { get } from 'svelte/store';
import { legendPicking, type LegendPickingSession } from '$lib/map/stores/legendPicking';
import { INK } from '$lib/core/ink';
import Feature from 'ol/Feature';
import Point from 'ol/geom/Point';
import VectorSource from 'ol/source/Vector';
import VectorLayer from 'ol/layer/Vector';
import Style from 'ol/style/Style';
import CircleStyle from 'ol/style/Circle';
import Fill from 'ol/style/Fill';
import Stroke from 'ol/style/Stroke';
import { Draw, Modify, Select, Translate, Snap } from 'ol/interaction';
import type Interaction from 'ol/interaction/Interaction';
import { fromLonLat, toLonLat } from 'ol/proj';
import type Map from 'ol/Map';
import type MapBrowserEvent from 'ol/MapBrowserEvent';

export function createLegendPointPicker(
  onPick: (lng: number, lat: number) => void,
  onPicking: (active: boolean) => void
) {
  let map: Map | null = null;
  let picking = false;
  let sticky = false;
  let previousCursor = '';
  let session: LegendPickingSession | null = null;
  let previousPicking: unknown;
  let suspended: { interaction: Interaction; active: boolean }[] = [];
  const source = new VectorSource();
  const marker = new VectorLayer({
    source,
    zIndex: 90,
    style: new Style({
      image: new CircleStyle({
        radius: 8,
        fill: new Fill({ color: INK.blue }),
        stroke: new Stroke({ color: INK.paper, width: 3 }),
      }),
    }),
  });
  function stop() {
    if (map && picking) {
      map.un('singleclick', pick);
      map.set('legendPointPicking', previousPicking);
      map.getTargetElement().style.cursor = previousCursor;
      for (const { interaction, active } of suspended) interaction.setActive(active);
    }
    if (session && get(legendPicking) === session) legendPicking.set(null);
    session = null;
    suspended = [];
    picking = false;
    onPicking(false);
  }
  function pick(event: MapBrowserEvent) {
    const [lng, lat] = toLonLat(event.coordinate);
    onPick(Number(lng.toFixed(7)), Number(lat.toFixed(7)));
    if (!sticky) stop();
    return false;
  }
  return {
    attach(nextMap: Map | null) {
      if (nextMap === map) return;
      stop();
      if (map) map.removeLayer(marker);
      map = nextMap;
      if (map) map.addLayer(marker);
    },
    show(lng: number | undefined, lat: number | undefined) {
      source.clear();
      if (
        lng != null &&
        lat != null &&
        Number.isFinite(lng) &&
        Number.isFinite(lat) &&
        Math.abs(lng) <= 180 &&
        Math.abs(lat) <= 90
      )
        source.addFeature(new Feature(new Point(fromLonLat([lng, lat]))));
    },
    /** `keep`: stay armed after a pick and don't collapse the mobile drawer —
     *  for an editor that is open for as long as clicks should place. */
    start(keep = false) {
      if (!map) return;
      if (picking) {
        stop();
        return;
      }
      get(legendPicking)?.cancel();
      previousCursor = map.getTargetElement().style.cursor;
      previousPicking = map.get('legendPointPicking');
      suspended = map
        .getInteractions()
        .getArray()
        .filter(
          (interaction) =>
            interaction instanceof Draw ||
            interaction instanceof Modify ||
            interaction instanceof Select ||
            interaction instanceof Translate ||
            interaction instanceof Snap
        )
        .map((interaction) => ({ interaction, active: interaction.getActive() }));
      for (const { interaction } of suspended) interaction.setActive(false);
      picking = true;
      sticky = keep;
      if (!keep) {
        session = { active: true, cancel: stop };
        legendPicking.set(session);
      }
      onPicking(true);
      map.set('legendPointPicking', true);
      map.getTargetElement().style.cursor = 'crosshair';
      map.on('singleclick', pick);
    },
    stop,
    destroy() {
      stop();
      if (map) map.removeLayer(marker);
      source.clear();
      map = null;
    },
  };
}
