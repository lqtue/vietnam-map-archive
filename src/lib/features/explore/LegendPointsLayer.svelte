<!--
  LegendPointsLayer.svelte — plots a georeferenced map's numbered-legend
  references on the ground. Headless: mounts an OL point layer on the shell map.

  Fetches /api/maps/[id]/legend-points (body numerals already warped to lng/lat
  and joined to legend names), renders numbered markers, and shows the name in a
  hover popup. Gated by the caller to the active overlay map.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
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

  // Literal hex on purpose: OpenLayers style objects are canvas fills, not CSS —
  // they cannot read a custom property.
  const markerStyle = (n: number) =>
    new Style({
      image: new CircleStyle({
        radius: 9,
        fill: new Fill({ color: '#eab308' }),
        stroke: new Stroke({ color: '#111', width: 1.5 }),
      }),
      text: new Text({
        text: String(n),
        font: "700 10px 'Space Grotesk', sans-serif",
        fill: new Fill({ color: '#111' }),
      }),
      zIndex: 5,
    });

  function render() {
    if (!source) return;
    source.clear();
    if (!enabled) return;
    for (const p of points) {
      const f = new Feature({ geometry: new Point(fromLonLat([p.lng, p.lat])) });
      f.setStyle(markerStyle(p.n));
      f.set('legend', p);
      source.addFeature(f);
    }
  }

  async function load(id: string) {
    try {
      const res = await fetch(`/api/maps/${id}/legend-points`);
      if (!res.ok) {
        points = [];
        return;
      }
      const data = await res.json();
      points = (data.points ?? []) as LegendPoint[];
    } catch {
      points = [];
    }
    loadedFor = id;
    render();
  }

  // Fetch on (map, enabled) change; re-render whenever enabled or points change
  // (referencing both so Svelte tracks them as dependencies).
  $: if (enabled && mapId && mapId !== loadedFor) load(mapId);
  $: {
    enabled;
    points;
    if (source) render();
    if (!enabled && overlay) overlay.setPosition(undefined);
  }

  function onMove(e: any) {
    if (!olMap || !overlay || !enabled) return;
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
    background: var(--ground-raised);
    color: var(--ink);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 4px;
    padding: 3px 7px;
    font:
      600 12px 'Space Grotesk',
      sans-serif;
    white-space: nowrap;
    pointer-events: none;
    box-shadow: 2px 2px 0 rgba(0, 0, 0, 0.15);
  }
  .legend-popup:empty {
    display: none;
  }
</style>
