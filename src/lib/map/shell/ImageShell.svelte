<!--
  ImageShell.svelte — Base IIIF image viewer using OpenLayers in pixel coordinates.

  Extracted from LabelCanvas.svelte. Provides:
  - OL Map with IIIF tile source (pixel space, no geographic projection)
  - Two vector layers: footprintLayer (z5), drawLayer (z4)
  - syncFootprints reactive to prop changes
  - loadIIIFImage() called whenever iiifInfoUrl changes
  - Context exposed via setImageShellContext() for child tools

  Tools (TraceTool, bbox tools) are composed as children via slot and access
  map/sources through getImageShellContext().

  Props:
    iiifInfoUrl   — IIIF info.json URL to load (pass null to show empty state)
    footprints    — FootprintSubmission[] rendered on footprintLayer
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import '$styles/layouts/mode-shared.css';
  import OlMap from 'ol/Map';
  import View from 'ol/View';
  import TileLayer from 'ol/layer/Tile';
  import IIIF from 'ol/source/IIIF';
  import IIIFInfo from 'ol/format/IIIFInfo';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Feature from 'ol/Feature';
  import Polygon from 'ol/geom/Polygon';
  import LineString from 'ol/geom/LineString';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import Text from 'ol/style/Text';
  import { Zoom } from 'ol/control';
  import { defaults as defaultControls } from 'ol/control/defaults';
  import { defaults as defaultInteractions } from 'ol/interaction/defaults';
  import 'ol/ol.css';

  import type { FootprintSubmission } from '$lib/data/maps/footprintTypes';
  import { geometryKind } from '$lib/data/maps/footprintTypes';
  import { toOlCoords } from '$lib/core/geo/rectUtils';
  import { createImageShellContext } from './imageContext';

  // Create context store synchronously during init so child tools can subscribe.
  const shellStore = createImageShellContext();

  export let iiifInfoUrl: string | null = null;
  export let footprints: FootprintSubmission[] = [];
  export let imgWidth = 0;
  export let imgHeight = 0;

  let mapContainer: HTMLDivElement;
  export let map: OlMap | null = null;
  let footprintSource: VectorSource | null = null;
  let drawSource: VectorSource | null = null;
  let fpLayer: VectorLayer | null = null;
  let tileLayer: TileLayer | null = null;
  let loadingImage = false;
  let loadError = '';
  let loadSeq = 0;

  // ── Color palette ─────────────────────────────────────────────────────────
  // Categorical, not a role: each entry encodes *which label* a footprint has,
  // so it must stay a fixed literal. It is also handed to OpenLayers, which
  // cannot read a CSS custom property.
  const labelColors: Record<string, string> = {};
  const palette = [
    '#d4af37',
    '#e06c75',
    '#61afef',
    '#98c379',
    '#c678dd',
    '#e5c07b',
    '#56b6c2',
    '#be5046',
    '#d19a66',
    '#abb2bf',
  ];
  let colorIdx = 0;

  function getLabelColor(label: string): string {
    if (!labelColors[label]) {
      labelColors[label] = palette[colorIdx % palette.length];
      colorIdx++;
    }
    return labelColors[label];
  }

  // ── Style functions ────────────────────────────────────────────────────────
  function createFootprintStyle(feature: any): Style {
    const label = feature.get('label') || '';
    const geomType = feature.getGeometry()?.getType();
    const isLine = geomType === 'LineString';
    const color = getLabelColor(label);
    return new Style({
      stroke: new Stroke({ color, width: isLine ? 3 : 2 }),
      fill: isLine ? undefined : new Fill({ color: color + '33' }),
      text: label
        ? new Text({
            text: label,
            font: 'bold 10px "Be Vietnam Pro", sans-serif',
            fill: new Fill({ color: '#2b2520' }),
            stroke: new Stroke({ color: '#fff', width: 3 }),
            overflow: true,
          })
        : undefined,
    });
  }

  // ── Sync props → OL features ──────────────────────────────────────────────
  function syncFootprints() {
    if (!footprintSource) return;
    footprintSource.clear();
    for (const fp of footprints) {
      const coords = toOlCoords(fp.pixelPolygon);
      const geomKind = geometryKind(fp.featureType);
      let feature: Feature;
      if (geomKind === 'LineString') {
        feature = new Feature({
          geometry: new LineString(coords),
          label: fp.name,
          footprintId: fp.id,
          userId: fp.userId,
        });
      } else {
        const ring =
          coords.length > 0 &&
          (coords[0][0] !== coords[coords.length - 1][0] ||
            coords[0][1] !== coords[coords.length - 1][1])
            ? [...coords, coords[0]]
            : coords;
        feature = new Feature({
          geometry: new Polygon([ring]),
          label: fp.name,
          footprintId: fp.id,
          userId: fp.userId,
        });
      }
      feature.setId(fp.id);
      footprintSource.addFeature(feature);
    }
  }

  $: (footprints, footprintSource && syncFootprints());
  $: if (iiifInfoUrl && map) loadIIIFImage(iiifInfoUrl);

  // ── IIIF loading ──────────────────────────────────────────────────────────
  async function loadIIIFImage(infoUrl: string) {
    if (!map) return;
    const seq = ++loadSeq;
    loadingImage = true;
    loadError = '';
    try {
      const response = await fetch(infoUrl);
      if (seq !== loadSeq) return; // superseded by a newer load
      if (!response.ok) throw new Error(`Failed to fetch IIIF info: ${response.status}`);
      const info = await response.json();
      if (seq !== loadSeq) return;
      imgWidth = info.width ?? 0;
      imgHeight = info.height ?? 0;
      const iiifParser = new IIIFInfo(info);
      const options = iiifParser.getTileSourceOptions();
      if (!options) throw new Error('Could not parse IIIF tile source options');
      if (tileLayer) map.removeLayer(tileLayer);
      const iiifSource = new IIIF(options);
      tileLayer = new TileLayer({ source: iiifSource, zIndex: 0 });
      map.getLayers().insertAt(0, tileLayer);
      const tileGrid = iiifSource.getTileGrid();
      if (tileGrid) {
        map.getView().fit(tileGrid.getExtent(), { padding: [40, 40, 40, 40], duration: 300 });
      }
      loadingImage = false;
    } catch (err: any) {
      if (seq !== loadSeq) return; // stale — don't clobber a successful load's state
      console.error('[ImageShell] IIIF load error:', err);
      loadError = err.message || 'Failed to load image';
      loadingImage = false;
    }
  }

  // ── Mount ─────────────────────────────────────────────────────────────────
  onMount(() => {
    footprintSource = new VectorSource();
    fpLayer = new VectorLayer({
      source: footprintSource,
      zIndex: 5,
      style: createFootprintStyle,
    });

    drawSource = new VectorSource();
    const drawLayer = new VectorLayer({
      source: drawSource,
      zIndex: 4,
      style: createFootprintStyle,
    });

    map = new OlMap({
      target: mapContainer,
      layers: [drawLayer, fpLayer],
      view: new View({ center: [0, 0], zoom: 1, showFullExtent: true }),
      interactions: defaultInteractions({ doubleClickZoom: false }),
      controls: defaultControls({ attribution: false, rotate: false, zoom: false }).extend([
        new Zoom(),
      ]),
    });

    shellStore.set({
      map,
      footprintSource,
      drawSource,
      footprintLayer: fpLayer,
    });

    syncFootprints();
    if (iiifInfoUrl) loadIIIFImage(iiifInfoUrl);
  });

  onDestroy(() => {
    shellStore.set(null);
    if (map) {
      map.setTarget(undefined);
      map = null;
    }
  });
</script>

<div class="image-shell">
  <div bind:this={mapContainer} class="image-map"></div>

  {#if loadingImage}
    <div class="shell-overlay">
      <div class="spinner"></div>
      <span>Loading IIIF image…</span>
    </div>
  {/if}

  {#if loadError}
    <div class="shell-overlay error">
      <span>⚠️ {loadError}</span>
    </div>
  {/if}

  {#if !iiifInfoUrl && !loadingImage}
    <div class="shell-overlay">
      <span class="empty-msg">No image selected</span>
    </div>
  {/if}

  <!-- Tool overlays (PinTool, TraceTool, etc.) compose here -->
  <slot />
</div>

<style>
  .image-shell {
    position: absolute;
    inset: 0;
    background: var(--is-canvas-bg);
  }

  .image-map {
    width: 100%;
    height: 100%;
  }

  .shell-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    background: var(--is-canvas-scrim);
    z-index: 20;
    font-family: 'Be Vietnam Pro', sans-serif;
    font-size: 0.875rem;
    color: var(--is-canvas-text);
    pointer-events: none;
  }

  .shell-overlay.error {
    color: var(--is-canvas-error);
  }
  .empty-msg {
    color: var(--is-canvas-text-dim);
  }
</style>
