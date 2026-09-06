<!--
  BboxSelector.svelte — Geo-bbox draw + resize tool.

  Mounts a single rectangle feature inside MapShell when `enabled`, lets the
  user resize it via OL Modify (corner + edge drag), and emits `change` with
  the new [W, S, E, N] bbox on every edit. Pass a starting bbox in or it will
  initialise from the current viewport.
-->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import VectorLayer from 'ol/layer/Vector';
  import VectorSource from 'ol/source/Vector';
  import Feature from 'ol/Feature';
  import Polygon, { fromExtent } from 'ol/geom/Polygon';
  import { Modify, Translate } from 'ol/interaction';
  import { Style, Fill, Stroke } from 'ol/style';
  import CircleStyle from 'ol/style/Circle';
  import { transformExtent } from 'ol/proj';
  import { getShellContext } from '$lib/map/shell/context';
  import type { Bbox4 } from './overpass';

  const dispatch = createEventDispatcher<{ change: { bbox: Bbox4 } }>();
  const shell = getShellContext();

  /** When true, the rectangle is rendered and made editable. */
  export let enabled = false;
  /** Bbox in [W, S, E, N] lon/lat. When null + enabled, picker seeds from viewport. */
  export let bbox: Bbox4 | null = null;

  let layer: VectorLayer<VectorSource> | null = null;
  let source: VectorSource | null = null;
  let feature: Feature<Polygon> | null = null;
  let modify: Modify | null = null;
  let translate: Translate | null = null;

  // Literal colours on purpose: OL builds styles in JS and cannot read a CSS
  // custom property, so the role tokens are unavailable here.
  const style = new Style({
    stroke: new Stroke({ color: '#2563eb', width: 2.5, lineDash: [6, 4] }),
    fill: new Fill({ color: 'rgba(37, 99, 235, 0.08)' }),
    image: new CircleStyle({
      radius: 6,
      fill: new Fill({ color: '#fff' }),
      stroke: new Stroke({ color: '#2563eb', width: 2 }),
    }),
  });

  // The shell exposes `map` as a writable store of OL Map | null.
  const mapStore = shell.map;

  /** Convert a lon/lat bbox to a Polygon in the map projection. */
  function bboxToPolygon(b: Bbox4): Polygon {
    const map = $mapStore;
    if (!map) return fromExtent([0, 0, 0, 0]);
    const proj = map.getView().getProjection();
    const extent = transformExtent([b[0], b[1], b[2], b[3]], 'EPSG:4326', proj);
    return fromExtent(extent);
  }

  function readFeatureBbox(): Bbox4 | null {
    if (!feature) return null;
    const map = $mapStore;
    if (!map) return null;
    const proj = map.getView().getProjection();
    const ext = feature.getGeometry()!.getExtent();
    const lonlat = transformExtent(ext, proj, 'EPSG:4326');
    return [lonlat[0], lonlat[1], lonlat[2], lonlat[3]];
  }

  function viewportBbox(): Bbox4 | null {
    const map = $mapStore;
    if (!map) return null;
    const ext = map.getView().calculateExtent(map.getSize() ?? undefined);
    const proj = map.getView().getProjection();
    const lonlat = transformExtent(ext, proj, 'EPSG:4326');
    // Shrink to ~60% of viewport so handles are visible inside the map view.
    const cx = (lonlat[0] + lonlat[2]) / 2;
    const cy = (lonlat[1] + lonlat[3]) / 2;
    const dx = (lonlat[2] - lonlat[0]) * 0.3;
    const dy = (lonlat[3] - lonlat[1]) * 0.3;
    return [cx - dx, cy - dy, cx + dx, cy + dy];
  }

  function mountInteractions() {
    const map = $mapStore;
    if (!map || layer) return;

    source = new VectorSource();
    layer = new VectorLayer({ source, style, zIndex: 900 });
    map.addLayer(layer);

    const startBbox = bbox ?? viewportBbox();
    if (!startBbox) return;
    feature = new Feature({ geometry: bboxToPolygon(startBbox) });
    source.addFeature(feature);
    // Push initial value out so parent reflects the seeded bbox.
    if (!bbox) {
      bbox = startBbox;
      dispatch('change', { bbox: startBbox });
    }

    // Resize via corner/edge drag.
    modify = new Modify({
      source,
      // Keep the geometry axis-aligned: after every modify, re-fit to extent.
    });
    modify.on('modifyend', () => {
      const f = source!.getFeatures()[0];
      if (!f) return;
      const ext = f.getGeometry()!.getExtent();
      f.setGeometry(fromExtent(ext)); // re-normalize to a clean rect
      const next = readFeatureBbox();
      if (next) {
        bbox = next;
        dispatch('change', { bbox: next });
      }
    });
    map.addInteraction(modify);

    // Translate via click-and-drag inside the rectangle.
    translate = new Translate({ layers: [layer] });
    translate.on('translateend', () => {
      const next = readFeatureBbox();
      if (next) {
        bbox = next;
        dispatch('change', { bbox: next });
      }
    });
    map.addInteraction(translate);
  }

  function unmountInteractions() {
    const map = $mapStore;
    if (modify && map) map.removeInteraction(modify);
    if (translate && map) map.removeInteraction(translate);
    if (layer && map) map.removeLayer(layer);
    modify = null;
    translate = null;
    feature = null;
    source = null;
    layer = null;
  }

  // React to enable/disable + bbox prop changes.
  let lastEnabled = false;
  let lastBboxKey = '';
  $: {
    const key = bbox ? bbox.join(',') : '';
    if (enabled && !lastEnabled) {
      mountInteractions();
    } else if (!enabled && lastEnabled) {
      unmountInteractions();
    } else if (enabled && feature && key !== lastBboxKey && bbox) {
      // External bbox change — re-fit feature geometry.
      feature.setGeometry(bboxToPolygon(bbox));
    }
    lastEnabled = enabled;
    lastBboxKey = key;
  }

  onDestroy(() => {
    unmountInteractions();
  });
</script>
