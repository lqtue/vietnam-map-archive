<!--
  DualMapPane.svelte — Secondary OL Map for dual side-by-side view.

  Shares the View from the primary map for automatic pan/zoom/rotation sync.
  Has its own basemap layers and optional WarpedMapLayer overlay.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import OlMap from 'ol/Map';
  import type BaseLayer from 'ol/layer/Base';
  import { defaults as defaultControls } from 'ol/control/defaults';
  import { Attribution, ScaleLine } from 'ol/control';
  import { createBasemapLayers } from './basemapLayers';
  import {
    createWarpedLayer,
    destroyWarpedLayer,
    loadOverlayByUrl,
    setOverlayOpacity,
  } from './warpedOverlay';
  import type { WarpedMapLayer } from '@allmaps/openlayers';

  export let primaryMap: OlMap;
  export let basemap: string = 'g-streets';
  export let showOverlay: boolean = true;
  export let overlayOpacity: number = 0.8;
  /** maps.allmaps_id — the Allmaps service credential needed for tile loading. */
  export let activeAllmapsId: string = '';
  /** Bindable — exposes the created OL Map to the parent */
  export let map: OlMap | null = null;

  let container: HTMLDivElement;
  let secondaryMap: OlMap | null = null;
  let basemapLayers: Map<string, BaseLayer> = new Map();
  let warpedLayer: WarpedMapLayer | null = null;
  let currentOverlayId: string | null = null;

  function applyBasemap(key: string) {
    basemapLayers.forEach((layer, k) => {
      layer.setVisible(k === key);
    });
  }

  // React to basemap prop changes
  $: if (secondaryMap) {
    applyBasemap(basemap);
  }

  // Expose to parent
  $: map = secondaryMap;

  let destroyed = false;
  let generation = 0;
  let creating: Promise<WarpedMapLayer> | null = null;
  const animationFrames = new Set<number>();

  function releaseOverlay() {
    generation++;
    const layer = warpedLayer;
    warpedLayer = null;
    currentOverlayId = null;
    if (layer) destroyWarpedLayer(layer);
  }

  // A hidden/empty secondary pane owns no renderer, workers or WebGL context.
  $: if (secondaryMap) void syncOverlay(activeAllmapsId, showOverlay, overlayOpacity);

  async function syncOverlay(id: string, visible: boolean, opacity: number) {
    const target = secondaryMap;
    if (destroyed || !target) return;
    if (!id || !visible) {
      releaseOverlay();
      return;
    }
    if (!warpedLayer) {
      if (creating) return;
      const ticket = ++generation;
      const pending = createWarpedLayer(target);
      creating = pending;
      try {
        const layer = await pending;
        if (
          destroyed ||
          target !== secondaryMap ||
          ticket !== generation ||
          !activeAllmapsId ||
          !showOverlay
        ) {
          destroyWarpedLayer(layer);
        } else {
          warpedLayer = layer;
        }
      } catch (err) {
        if (!destroyed) console.warn('[DualMapPane] Failed to create overlay:', err);
        return;
      } finally {
        if (creating === pending) creating = null;
      }
      if (!destroyed && secondaryMap && activeAllmapsId && showOverlay)
        void syncOverlay(activeAllmapsId, showOverlay, overlayOpacity);
      return;
    }
    const layer = warpedLayer;
    setOverlayOpacity(layer, target, opacity);
    if (id === currentOverlayId) return;
    currentOverlayId = id;
    const ticket = generation;
    try {
      await loadOverlayByUrl(layer, target, id, opacity);
      if (
        destroyed ||
        ticket !== generation ||
        warpedLayer !== layer ||
        secondaryMap !== target ||
        currentOverlayId !== id
      )
        return;
      setOverlayOpacity(layer, target, overlayOpacity);
    } catch (err) {
      if (!destroyed && ticket === generation && warpedLayer === layer && currentOverlayId === id) {
        currentOverlayId = null;
        console.warn('[DualMapPane] Failed to load overlay:', err);
      }
    }
  }

  function nextFrame(callback: () => void) {
    const id = requestAnimationFrame(() => {
      animationFrames.delete(id);
      if (!destroyed) callback();
    });
    animationFrames.add(id);
  }

  onMount(() => {
    // Create basemap layers
    basemapLayers = createBasemapLayers();

    // Create secondary map sharing the primary's View
    secondaryMap = new OlMap({
      target: container,
      layers: Array.from(basemapLayers.values()),
      view: primaryMap.getView(),
      controls: defaultControls({
        attribution: false,
        rotate: false,
        zoom: false,
      }).extend([
        // Tile attribution + scale live on the secondary pane so they sit in
        // the rightmost (desktop) / bottommost (mobile) corner of the workspace.
        new Attribution({ collapsible: false }),
        new ScaleLine(),
      ]),
    });

    applyBasemap(basemap);

    // OL needs a valid size — force updateSize after layout settles
    // Double-RAF ensures the browser has completed layout
    nextFrame(() => {
      nextFrame(() => {
        secondaryMap?.updateSize();
        secondaryMap?.render();
      });
    });
  });

  onDestroy(() => {
    destroyed = true;
    for (const frame of animationFrames) cancelAnimationFrame(frame);
    animationFrames.clear();
    releaseOverlay();
    const target = secondaryMap;
    secondaryMap = null;
    target?.setTarget(undefined);
    target?.dispose();
    basemapLayers.clear();
  });
</script>

<div class="dual-pane-root">
  <div bind:this={container} class="dual-pane-map"></div>
</div>

<style>
  .dual-pane-root {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .dual-pane-map {
    position: absolute;
    inset: 0;
  }
</style>
