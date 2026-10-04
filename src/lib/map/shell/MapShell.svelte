<!--
  MapShell.svelte — The ONE map.

  Responsibilities:
    1. Create and own the single OL Map instance
    2. Mount basemap tile layers (visibility is owned by LayerRenderer via layersStore)
    3. Expose the map + stores via Svelte context
    4. Sync OL View ↔ mapStore (bidirectional)
    5. Start/stop URL hash sync
    6. Render children (LayerRenderer, modes, panels) in a slot on top of the map

  Usage:
    <MapShell {mapStore} {layerStore}>
      <LayerRenderer />
    </MapShell>
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { writable, get } from 'svelte/store';
  import OlMap from 'ol/Map';
  import View from 'ol/View';
  import type BaseLayer from 'ol/layer/Base';
  import TileLayer from 'ol/layer/Tile';
  import XYZ from 'ol/source/XYZ';
  import { Attribution, Rotate, ScaleLine, Zoom } from 'ol/control';
  import { defaults as defaultControls } from 'ol/control/defaults';
  import DragRotate from 'ol/interaction/DragRotate';
  import PinchRotate from 'ol/interaction/PinchRotate';
  import { fromLonLat, toLonLat } from 'ol/proj';
  import 'ol/ol.css';

  import { defaults as defaultInteractions } from 'ol/interaction/defaults';

  import { createBasemapLayers } from './basemapLayers';
  import type { MapStore } from '$lib/map/stores/mapStore';
  import { getOlCenter } from '$lib/map/stores/mapStore';
  import type { LayerStore } from '$lib/map/stores/layerStore';
  import { initUrlSync } from '$lib/map/stores/urlStore';
  import { setShellContext } from './context';

  // ── Props ────────────────────────────────────────────────────────

  export let mapStore: MapStore;
  export let layerStore: LayerStore;

  export let disableUrlSync = false;

  /**
   * OL's device-pixel ratio. Left undefined the map renders at the screen's own
   * ratio, which on a Retina display asks for roughly four times the tiles. A
   * decorative map can pin this to 1 and pay a quarter of the bandwidth; a tool
   * where people read the sheet should not.
   */
  export let pixelRatio: number | undefined = undefined;

  /**
   * Whether the wheel zooms the map. A tool wants that; a map embedded in a
   * scrolling page does not, because the reader's scroll gesture gets eaten and
   * they cannot get past it. Off means the interaction is never constructed —
   * removing it after mount left a window, however short, where the wheel still
   * zoomed.
   */
  export let wheelZoom = true;

  /** Read-only binding to the OL Map instance */
  export let map: OlMap | null = null;

  // ── Internal state ───────────────────────────────────────────────

  let mapContainer: HTMLDivElement;
  let olMap: OlMap | null = null;
  const mapWritable = writable<OlMap | null>(null);

  /** Basemap OL layers keyed by BASEMAP_DEFS key */
  let basemapLayers: Map<string, BaseLayer> = new Map();

  /** Suppress store→OL sync while OL is writing to the store */
  let suppressStoreToOl = false;

  let urlTeardown: (() => void) | null = null;
  let layerUnsub: (() => void) | null = null;
  let mapStoreUnsub: (() => void) | null = null;

  // ── Context ──────────────────────────────────────────────────────

  setShellContext({
    map: mapWritable,
    mapStore,
    layerStore,
  });

  // ── OL View ↔ mapStore sync ──────────────────────────────────────

  function olViewToStore() {
    if (!olMap) return;
    const view = olMap.getView();
    const center = view.getCenter();
    if (!center) return;

    const [lng, lat] = toLonLat(center);
    const zoom = view.getZoom() ?? 14;
    const rotation = view.getRotation();

    suppressStoreToOl = true;
    mapStore.setView({ lng, lat, zoom, rotation });

    // Release suppression after the store subscription has fired
    requestAnimationFrame(() => {
      suppressStoreToOl = false;
    });
  }

  function storeToOlView() {
    if (suppressStoreToOl || !olMap) return;

    const current = get(mapStore);
    const view = olMap.getView();
    const targetCenter = fromLonLat([current.lng, current.lat]);
    view.setCenter(targetCenter);
    view.setZoom(current.zoom);
    view.setRotation(current.rotation);
  }

  // ── Lifecycle ────────────────────────────────────────────────────

  onMount(() => {
    // 1. Create basemap layers
    basemapLayers = createBasemapLayers();

    // 2. Build controls
    const controls = defaultControls({
      attribution: false,
      rotate: false,
      zoom: false,
    }).extend([
      new Attribution({ collapsible: false }),
      new Rotate({ autoHide: false }),
      new Zoom(),
      new ScaleLine(),
    ]);

    // 3. Create the map
    const center = getOlCenter(mapStore);
    const initial = get(mapStore);

    olMap = new OlMap({
      target: mapContainer,
      ...(pixelRatio ? { pixelRatio } : {}),
      layers: Array.from(basemapLayers.values()),
      view: new View({
        center,
        zoom: initial.zoom,
        rotation: initial.rotation,
        enableRotation: true,
      }),
      controls,
      interactions: defaultInteractions({ mouseWheelZoom: wheelZoom }),
    });

    // Sync to prop
    map = olMap;

    // 4. Rotation interactions
    const dragRotate = new DragRotate({
      condition: (event) => event.originalEvent.ctrlKey || event.originalEvent.metaKey,
    });
    olMap.addInteraction(dragRotate);
    olMap.addInteraction(new PinchRotate());

    // 5. Expose via context writable
    mapWritable.set(olMap);

    // 6. OL → store sync on moveend
    olMap.on('moveend', olViewToStore);

    // 7. Store → OL sync on store change
    mapStoreUnsub = mapStore.subscribe(() => storeToOlView());

    // 8. Basemap visibility is now owned by LayerRenderer (driven by layersStore.base).
    //    But the custom-URL basemap needs its XYZ source assigned from layerStore.customBaseUrl.
    const customLayer = basemapLayers.get('g-custom') as TileLayer<XYZ> | undefined;
    let lastCustomUrl: string | null = null;
    layerUnsub = layerStore.subscribe((s) => {
      if (!customLayer) return;
      const url = s.customBaseUrl;
      if (url === lastCustomUrl) return;
      lastCustomUrl = url;
      if (url) {
        customLayer.setSource(
          new XYZ({
            urls: [url],
            crossOrigin: 'anonymous',
            maxZoom: 22,
            attributions: 'Custom tile source',
          })
        );
      } else {
        customLayer.setSource(null as any);
      }
    });

    // 9. URL sync
    if (!disableUrlSync) {
      urlTeardown = initUrlSync({ mapStore, layerStore });
    }
  });

  onDestroy(() => {
    urlTeardown?.();
    layerUnsub?.();
    mapStoreUnsub?.();

    if (olMap) {
      olMap.setTarget(undefined);
      olMap = null;
    }

    mapWritable.set(null);
    basemapLayers.clear();
  });
</script>

<div class="shell">
  <div bind:this={mapContainer} class="shell-map"></div>
  <div class="shell-overlay">
    <slot />
  </div>
</div>

<style>
  .shell {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .shell-map {
    position: absolute;
    inset: 0;
  }

  .shell-overlay {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
  }

  /* Allow interactive children to capture pointer events */
  .shell-overlay :global(*) {
    pointer-events: auto;
  }
</style>
