<!--
  LayerRenderer.svelte — single component that owns all map-layer rendering.
  Subscribes to layersStore and maintains:
    - The basemap (modern TileLayer) OR a historical base (WarpedMapLayer at z=5)
    - One OL layer per overlay PART (z = 10 + 2i, opacity from layer, visibility
      toggle). A catalogued sheet is one part; a series row is up to two — a
      pre-tiled raster archive and the sheets warped live above it — which is
      why each row owns two z-slots rather than one.

  Replaces HistoricalOverlay + HistoricalBaseLayer + manual StackedOverlay loops.

  Display-mode behaviour (clip mask for Lens / Side, basemap hiding) is handled here
  reading from layerStore.viewMode.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import type { WarpedMapLayer } from '@allmaps/openlayers';
  import type OlMap from 'ol/Map';
  import { transformExtent } from 'ol/proj';
  import type { Unsubscriber } from 'svelte/store';

  import { getShellContext } from './context';
  import { setVisibleBasemap } from './basemapLayers';
  import {
    createWarpedLayer,
    destroyWarpedLayer,
    loadOverlayByUrl,
    loadSeriesInView,
    clearOverlay,
    setOverlayOpacity,
    applyClipMask,
    type SeriesLoad,
  } from './warpedOverlay';
  import { layersStore, type OverlayLayer, type LayerRef } from '$lib/map/stores/layersStore';
  import { buildRasterOverlayLayer } from '$lib/map/basemapStyle';
  import { fetchSeriesSheets } from '$lib/data/maps/service';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import type TileLayer from 'ol/layer/Tile';

  const { map: mapWritable, layerStore } = getShellContext();
  // Set by the root layout, so it is there for every MapShell in the app. A
  // series row is the only thing here that needs the database at all.
  const { supabase } = getSupabaseContext();

  let olMap: OlMap | null = null;
  let initialized = false;
  let unsubs: Unsubscriber[] = [];

  // Base historical layer (only when base.kind === 'historical')
  let baseWarped: WarpedMapLayer | null = null;
  let baseLoadedId: string | null = null;

  // Overlay layers keyed by layer.id. `series` is set only for a `sheets` ref:
  // it is the sheet list plus the sources already in the layer, so a pan can
  // top the layer up with what has newly come into view.
  const overlayInstances = new Map<
    string,
    { layer: WarpedMapLayer; loadedAllmapsId: string | null; series?: SeriesLoad }
  >();

  // The raster part of a series row (a pre-warped tile archive), keyed by
  // layer.id. Ordinary OL tile layers, so they are kept apart from the Allmaps
  // ones — nothing about loading, clipping or teardown is shared. One row can
  // have an entry in both maps: that is a survey held both ways.
  const rasterInstances = new Map<string, TileLayer>();

  function dropRaster(id: string) {
    const layer = rasterInstances.get(id);
    if (layer && olMap) olMap.removeLayer(layer);
    rasterInstances.delete(id);
  }

  function hideAllBasemaps(map: OlMap) {
    map.getLayers().forEach((layer) => {
      const props = layer.getProperties() as { base?: boolean };
      if (props?.base) (layer as any).setVisible(false);
    });
  }

  /** The current view as `[minLon, minLat, maxLon, maxLat]`, or null before first render. */
  function lonLatViewport(): [number, number, number, number] | null {
    if (!olMap) return null;
    const size = olMap.getSize();
    if (!size || !size[0] || !size[1]) return null;
    const extent = olMap.getView().calculateExtent(size);
    return transformExtent(extent, 'EPSG:3857', 'EPSG:4326') as [number, number, number, number];
  }

  /**
   * Run one sync at a time, and coalesce everything that arrives while it runs.
   *
   * Both subscriptions below fire synchronously on subscribe, so two passes
   * started in the same tick and both ran to the `await createWarpedLayer`
   * inside — which is a dynamic import of 151 kB and therefore a very long
   * window. Neither saw the other's instance in `overlayInstances`, so both
   * created one, and the loser stayed attached to the OL map drawing forever.
   * Measured on the 56-sheet Indochine series restored from localStorage:
   * every annotation fetched **four** times, 276 requests and 712 kB where 56
   * and 180 kB were wanted, plus three orphaned WebGL layers.
   *
   * Only the newest state is worth applying, so `pending` is overwritten rather
   * than queued: a slider dragged through twenty values runs the first pass and
   * then one more with the value it ended on.
   */
  let syncing = false;
  let pending: { base: LayerRef; overlays: OverlayLayer[] } | null = null;

  async function queueSync(base: LayerRef, overlays: OverlayLayer[]) {
    pending = { base, overlays };
    if (syncing) return;
    syncing = true;
    try {
      while (pending) {
        const next = pending;
        pending = null;
        await syncBase(next.base);
        await syncOverlays(next.overlays);
      }
    } finally {
      syncing = false;
    }
  }

  // ── Base sync ────────────────────────────────────────────────────
  async function syncBase(ref: LayerRef) {
    if (!olMap) return;
    if (ref.kind === 'basemap') {
      setVisibleBasemap(olMap, ref.key); // 'none' / unknown key → all hidden
      if (baseWarped) {
        destroyWarpedLayer(baseWarped);
        baseWarped = null;
        baseLoadedId = null;
      }
      return;
    }
    // Historical base: hide modern basemaps, ensure WarpedMapLayer exists, load if changed
    hideAllBasemaps(olMap);
    if (!baseWarped) {
      baseWarped = await createWarpedLayer(olMap, { zIndex: 5, name: 'allmaps-base' });
    }
    if (!olMap) return; // torn down inside the dynamic import
    if (ref.allmapsId !== baseLoadedId) {
      baseLoadedId = ref.allmapsId;
      try {
        await loadOverlayByUrl(baseWarped, olMap, ref.allmapsId, 1.0);
      } catch (err) {
        console.warn('[LayerRenderer] base load failed', ref, err);
      }
    }
  }

  // ── Overlays sync ────────────────────────────────────────────────
  async function syncOverlays(overlays: OverlayLayer[]) {
    if (!olMap) return;
    const ls = get(layerStore);
    const sideBySide = ls.viewMode === 'dual';
    // Top of stack = first item → highest z. base sits at z=0 or 5; overlays start at z=10.
    const existingIds = new Set(overlayInstances.keys());
    const wantedIds = new Set(overlays.map((o) => o.id));

    // Remove dropped overlays
    for (const id of existingIds) {
      if (!wantedIds.has(id)) {
        const inst = overlayInstances.get(id);
        if (inst) destroyWarpedLayer(inst.layer);
        overlayInstances.delete(id);
      }
    }
    for (const id of [...rasterInstances.keys()]) {
      if (!wantedIds.has(id)) dropRaster(id);
    }

    // Create or update
    const N = overlays.length;
    for (let i = 0; i < N; i++) {
      const o = overlays[i];
      // Two z-slots per row: a series row draws its raster archive at `z` and
      // its warped sheets at `z + 1`, because the sheets are the sharper survey
      // of the ground the archive is missing and belong above its pixels.
      const z = 10 + 2 * (N - 1 - i); // topmost (i=0) → highest z
      // Side-by-side: the left pane shows ONLY the topmost overlay; the right
      // pane (DualMapPane) handles the second overlay independently.
      const visible = o.visible && !(sideBySide && i > 0);
      const parts = o.ref.kind === 'series' ? o.ref.parts : [];

      const archive = parts.find((p) => p.kind === 'raster');
      if (archive) {
        let raster = rasterInstances.get(o.id);
        if (!raster) {
          raster = buildRasterOverlayLayer(archive.key);
          rasterInstances.set(o.id, raster);
          olMap.addLayer(raster);
        }
        raster.setZIndex(z);
        raster.setOpacity(o.opacity);
        raster.setVisible(visible);
      } else if (rasterInstances.has(o.id)) {
        dropRaster(o.id);
      }

      // Everything below is the Allmaps half: one WarpedMapLayer holding either
      // a single sheet's annotation or a whole series' worth.
      const sheets = parts.find((p) => p.kind === 'sheets');
      if (o.ref.kind === 'series' && !sheets) {
        const stale = overlayInstances.get(o.id);
        if (stale) {
          destroyWarpedLayer(stale.layer);
          overlayInstances.delete(o.id);
        }
        continue;
      }

      let inst = overlayInstances.get(o.id);
      if (!inst) {
        const layer = await createWarpedLayer(olMap, {
          zIndex: z + 1,
          name: `allmaps-overlay-${o.id}`,
        });
        inst = { layer, loadedAllmapsId: null };
        overlayInstances.set(o.id, inst);
      } else {
        try {
          (inst.layer as any).setZIndex(z + 1);
        } catch {}
      }

      // A series and a single sheet are the same layer with a different number
      // of annotations in it. `loadedAllmapsId` is the sentinel for "what is in
      // this layer already" either way — the collection name stands in for it,
      // so a series reloads only when the row itself changes.
      const wanted = sheets
        ? `sheets:${sheets.collection}`
        : o.ref.kind === 'historical'
          ? o.ref.allmapsId
          : '';

      if (inst.loadedAllmapsId !== wanted) {
        inst.loadedAllmapsId = wanted;
        try {
          if (sheets) {
            const found = await fetchSeriesSheets(supabase, sheets.collection);
            if (!found.length) {
              // Every sheet in the series is a draft this reader may not read,
              // or the collection name has drifted. Either way an empty layer
              // explains nothing, so say it once.
              console.warn('[LayerRenderer] series resolved to no sheets', sheets.collection);
            }
            // The loader is purely additive, so whatever the previous series
            // left in this layer has to come out by hand.
            clearOverlay(inst.layer);
            inst.series = { sheets: found, loaded: new Set<string>() };
            const { failed } = await loadSeriesInView(
              inst.layer,
              olMap,
              inst.series,
              lonLatViewport(),
              o.opacity
            );
            if (failed)
              console.warn(
                `[LayerRenderer] series ${sheets.collection}: ${failed} sheet(s) failed to load`
              );
          } else {
            await loadOverlayByUrl(inst.layer, olMap, wanted, o.opacity);
          }
        } catch (err) {
          console.warn('[LayerRenderer] overlay load failed', o, err);
        }
      } else {
        setOverlayOpacity(inst.layer, olMap, o.opacity);
      }

      const canvas = inst.layer.canvas;
      if (canvas) canvas.style.display = visible ? '' : 'none';
    }
  }

  // ── Clip mask (Lens / Side-by-side) ──────────────────────────────
  function refreshClips() {
    if (!olMap) return;
    const ls = get(layerStore);
    if (baseWarped) applyClipMask(baseWarped, olMap, ls.viewMode, ls.lensRadius);
    for (const { layer } of overlayInstances.values()) {
      applyClipMask(layer, olMap, ls.viewMode, ls.lensRadius);
    }
  }

  /**
   * Fetch the annotations of any series sheet that has just come into view.
   *
   * A series layer starts holding only the sheets the reader could see when it
   * was added; this is how the rest arrive. Additive by construction — a sheet
   * already in the layer is never asked for twice — so this is safe to fire on
   * every `moveend`, and it does nothing at all once the reader has visited the
   * whole extent of the survey.
   */
  function topUpSeries() {
    if (!olMap) return;
    const view = lonLatViewport();
    const overlays = get(layersStore).overlays;
    for (const o of overlays) {
      const inst = overlayInstances.get(o.id);
      if (!inst?.series || !o.visible) continue;
      loadSeriesInView(inst.layer, olMap, inst.series, view, o.opacity).catch((err) =>
        console.warn('[LayerRenderer] series top-up failed', err)
      );
    }
  }

  // ── Lifecycle ────────────────────────────────────────────────────
  onMount(() => {
    unsubs.push(
      mapWritable.subscribe(($map) => {
        if (!$map || initialized) return;
        initialized = true;
        olMap = $map;

        unsubs.push(
          layersStore.subscribe(($l) => {
            queueSync($l.base, $l.overlays);
          })
        );

        unsubs.push(
          layerStore.subscribe(() => {
            refreshClips();
            // viewMode changes (e.g. entering/leaving side-by-side) affect overlay visibility.
            const $l = get(layersStore);
            queueSync($l.base, $l.overlays);
          })
        );

        $map.on('moveend', refreshClips);
        $map.on('moveend', topUpSeries);
        $map.on('change:size', refreshClips);
      })
    );
  });

  onDestroy(() => {
    unsubs.forEach((u) => u());
    unsubs = [];
    if (baseWarped) {
      destroyWarpedLayer(baseWarped);
      baseWarped = null;
    }
    for (const inst of overlayInstances.values()) destroyWarpedLayer(inst.layer);
    overlayInstances.clear();
    for (const id of [...rasterInstances.keys()]) dropRaster(id);
  });
</script>
