<!--
  LegendPointsLayer.svelte — plots a georeferenced map's numbered-legend
  references on the ground. Headless: mounts an OL point layer on the shell map.

  Fetches /api/maps/[id]/legend-points (body numerals already warped to lng/lat
  and joined to legend names), renders numbered markers, and shows the name in a
  hover popup. Gated by the caller to the active overlay map.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { legendRevision } from '$lib/data/maps/legendRevision';
  import { INK } from '$lib/core/ink';
  import Feature from 'ol/Feature';
  import Point from 'ol/geom/Point';
  import VectorSource from 'ol/source/Vector';
  import VectorImageLayer from 'ol/layer/VectorImage';
  import Overlay from 'ol/Overlay';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import CircleStyle from 'ol/style/Circle';
  import Text from 'ol/style/Text';
  import { fromLonLat } from 'ol/proj';
  import type Map from 'ol/Map';

  import { getShellContext } from '$lib/map/shell/context';

  export let mapId: string | null = null;
  export let enabled = false;

  type LegendPoint = {
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number;
    lat: number;
  };

  const { map: mapWritable } = getShellContext();
  let olMap: Map | null = null;
  let source: VectorSource | null = null;
  let layer: VectorImageLayer<VectorSource> | null = null;
  let popupEl: HTMLDivElement;
  let overlay: Overlay | null = null;

  let points: LegendPoint[] = [];
  let loadedFor = '';
  let loadedRevision = -1;
  let loadVersion = 0;
  let destroyed = false;

  const markerStyle = (n: number) =>
    new Style({
      image: new CircleStyle({
        radius: 9,
        fill: new Fill({ color: INK.yellow }),
        stroke: new Stroke({ color: INK.ink, width: 1.5 }),
      }),
      text: new Text({
        text: String(n),
        font: "700 10px 'Be Vietnam Pro', sans-serif",
        fill: new Fill({ color: INK.ink }),
      }),
      zIndex: 5,
    });

  function render() {
    if (!source) return;
    source.clear();
    if (!enabled || mapId !== loadedFor) return;
    for (const p of points) {
      const f = new Feature({ geometry: new Point(fromLonLat([p.lng, p.lat])) });
      f.setStyle(markerStyle(p.n));
      f.set('legend', p);
      source.addFeature(f);
    }
  }

  async function load(id: string, revision: number) {
    const version = ++loadVersion;
    loadedFor = id;
    loadedRevision = revision;
    points = [];
    render();
    try {
      const res = await fetch(`/api/maps/${id}/legend-points`);
      const data = res.ok ? await res.json() : null;
      if (destroyed || version !== loadVersion || mapId !== id) return;
      points = [...(data?.points ?? []), ...(data?.more ?? [])] as LegendPoint[];
    } catch {
      if (destroyed || version !== loadVersion || mapId !== id) return;
      points = [];
    }
    render();
  }

  $: currentRevision = mapId ? ($legendRevision[mapId] ?? 0) : 0;
  $: if (enabled && mapId && (mapId !== loadedFor || currentRevision !== loadedRevision))
    void load(mapId, currentRevision);
  $: {
    void enabled;
    void points;
    void mapId;
    if (source) render();
    if ((!enabled || mapId !== loadedFor) && overlay) overlay.setPosition(undefined);
  }

  function onMove(e: any) {
    if (!olMap || !overlay || !enabled || olMap.get('legendPointPicking')) return;
    const hit = olMap.forEachFeatureAtPixel(
      e.pixel,
      (f) => f.get('legend') as LegendPoint | undefined,
      {
        hitTolerance: 4,
        layerFilter: (l) => l === layer,
      }
    );
    if (hit) {
      const label = hit.name ? `№${hit.n} · ${hit.name}` : `№${hit.n}`;
      // Written straight to the node, not through the template: this runs on
      // every pointermove over the layer, and a reactive round trip per mouse
      // move to change one string is not worth it. Nothing else owns this node.
      // eslint-disable-next-line svelte/no-dom-manipulating
      popupEl.textContent = hit.grid ? `${label}  [${hit.grid}]` : label;
      overlay.setPosition(fromLonLat([hit.lng, hit.lat]));
      olMap.getTargetElement().style.cursor = 'pointer';
    } else {
      overlay.setPosition(undefined);
      olMap.getTargetElement().style.cursor = '';
    }
  }

  onMount(() => {
    const unsub = mapWritable.subscribe(($map) => {
      if (!$map || olMap) return;
      olMap = $map;
      source = new VectorSource();
      layer = new VectorImageLayer({ source, zIndex: 60 });
      olMap.addLayer(layer);
      overlay = new Overlay({
        element: popupEl,
        offset: [0, -16],
        positioning: 'bottom-center',
        stopEvent: false,
      });
      olMap.addOverlay(overlay);
      olMap.on('pointermove', onMove);
      render();
    });
    return () => unsub();
  });

  onDestroy(() => {
    destroyed = true;
    loadVersion += 1;
    if (olMap) {
      olMap.un('pointermove', onMove);
      if (layer) olMap.removeLayer(layer);
      if (overlay) olMap.removeOverlay(overlay);
    }
  });
</script>

<div bind:this={popupEl} class="legend-popup" role="tooltip"></div>

<style>
  .legend-popup {
    background: var(--color-white);
    color: var(--color-text);
    border: 1.5px solid var(--color-border);
    border-radius: 4px;
    padding: 3px 7px;
    font:
      600 12px 'Be Vietnam Pro',
      sans-serif;
    white-space: nowrap;
    pointer-events: none;
    box-shadow: var(--shadow-solid-xs);
  }
  .legend-popup:empty {
    display: none;
  }
</style>
