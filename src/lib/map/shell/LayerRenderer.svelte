<!--
  LayerRenderer.svelte — single component that owns all map-layer rendering.
  Subscribes to layersStore and maintains:
    - The basemap (modern TileLayer) OR a historical base (WarpedMapLayer at z=5)
    - One warped layer per overlay row (z = 10 + 2i, opacity from layer, visibility
      toggle). A catalogued sheet holds one annotation; a series row holds every
      sheet of its collection in the same layer.

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
  import { unByKey } from 'ol/Observable';
  import type { EventsKey } from 'ol/events';
  import type { Unsubscriber } from 'svelte/store';

  import { getShellContext } from './context';
  import { setVisibleBasemap } from './basemapLayers';
  import {
    createWarpedLayer,
    destroyWarpedLayer,
    loadOverlayByUrl,
    setOverlayOpacity,
    applyClipMask,
  } from './warpedOverlay';
  import {
    createSeriesRenderer,
    type SeriesRenderer,
    type SeriesRenderStatus,
  } from './seriesRenderer';
  import { allocateSeriesBudgets } from './seriesRenderPolicy';
  import { t } from '$lib/core/i18n';
  import { layersStore, type OverlayLayer, type LayerRef } from '$lib/map/stores/layersStore';
  import { fetchSeriesSheets } from '$lib/data/maps/service';
  import { getSupabaseContext } from '$lib/data/supabase/context';

  const { map: mapWritable, layerStore } = getShellContext();
  // Set by the root layout, so it is there for every MapShell in the app. A
  // series row is the only thing here that needs the database at all.
  const { supabase } = getSupabaseContext();

  let olMap: OlMap | null = null;
  let initialized = false;
  let destroyed = false;
  let unsubs: Unsubscriber[] = [];
  let mapEvents: EventsKey[] = [];
  let overviewNotices: { id: string; name: string }[] = [];
  const seriesStatus = new Map<string, SeriesRenderStatus>();

  // Base historical layer (only when base.kind === 'historical')
  let baseWarped: WarpedMapLayer | null = null;
  let baseLoadedId: string | null = null;

  // Overlay layers keyed by layer.id. `series` is set only for a `sheets` ref:
  // it is the sheet list plus the sources already in the layer, so a pan can
  // top the layer up with what has newly come into view.
  const overlayInstances = new Map<
    string,
    { layer: WarpedMapLayer | null; loadedAllmapsId: string | null; series?: SeriesRenderer }
  >();

  function updateNotices() {
    overviewNotices = get(layersStore).overlays.flatMap((overlay) =>
      seriesStatus.get(overlay.id)?.mode === 'overview'
        ? [{ id: overlay.id, name: overlay.ref.name ?? '' }]
        : []
    );
  }

  function removeInstance(id: string) {
    const inst = overlayInstances.get(id);
    if (inst?.layer) destroyWarpedLayer(inst.layer);
    inst?.series?.destroy();
    overlayInstances.delete(id);
    seriesStatus.delete(id);
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
    if (destroyed) return;
    pending = { base, overlays };
    // Release removed/hidden series immediately, even during another layer's dynamic import.
    const wanted = new Set(overlays.map((overlay) => overlay.id));
    for (const id of overlayInstances.keys()) if (!wanted.has(id)) removeInstance(id);
    topUpSeries();
    updateNotices();
    if (syncing) return;
    syncing = true;
    try {
      while (pending && !destroyed) {
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
    if (!olMap || destroyed) {
      if (baseWarped) destroyWarpedLayer(baseWarped);
      baseWarped = null;
      return;
    }
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
        removeInstance(id);
      }
    }

    // Create or update
    const N = overlays.length;
    for (let i = 0; i < N; i++) {
      const o = overlays[i];
      // Two z-slots per row, the warped layer at `z + 1`; the spacing is what the rest of the stack
      // (basemap at 5, annotations above) is laid out against.
      const z = 10 + 2 * (N - 1 - i); // topmost (i=0) → highest z
      // Side-by-side: the left pane shows ONLY the topmost overlay; the right
      // pane (DualMapPane) handles the second overlay independently.
      const visible = o.visible && !(sideBySide && i > 0);
      let inst = overlayInstances.get(o.id);
      if (!inst) {
        inst = { layer: null, loadedAllmapsId: null };
        overlayInstances.set(o.id, inst);
      }
      if (o.ref.kind === 'series') {
        const ref = o.ref;
        const wanted = `sheets:${JSON.stringify(ref.parts)}`;
        if (inst.loadedAllmapsId !== wanted) {
          inst.series?.destroy();
          if (inst.layer) destroyWarpedLayer(inst.layer);
          inst.layer = null;
          inst.series = undefined;
          inst.loadedAllmapsId = wanted;
          const instance = inst;
          // Metadata is small; scans and the WebGL renderer stay absent in overview.
          // Do not hold the synchronization queue while a remote index is read.
          void Promise.all(
            ref.parts.map((part) =>
              fetchSeriesSheets(
                supabase,
                part.seriesKey ?? ref.key,
                part.seriesKey ? undefined : part.collection
              )
            )
          )
            .then((parts) => {
              if (
                destroyed ||
                !olMap ||
                overlayInstances.get(o.id) !== instance ||
                instance.loadedAllmapsId !== wanted
              )
                return;
              const found = [
                ...new Map(parts.flat().map((sheet) => [sheet.source, sheet])).values(),
              ];
              if (!found.length) return;
              instance.series = createSeriesRenderer(olMap, found, {
                name: ref.name,
                bounds: ref.bounds,
                onStatus: (status) => {
                  seriesStatus.set(o.id, status);
                  updateNotices();
                },
              });
              topUpSeries();
            })
            .catch((error) => {
              if (!destroyed && overlayInstances.get(o.id) === instance) {
                instance.loadedAllmapsId = null;
                console.warn('[LayerRenderer] Series index failed', error);
              }
            });
        }
        continue;
      }
      if (inst.series) {
        inst.series.destroy();
        inst.series = undefined;
        seriesStatus.delete(o.id);
      }
      if (!visible) {
        if (inst.layer) destroyWarpedLayer(inst.layer);
        inst.layer = null;
        inst.loadedAllmapsId = null;
        continue;
      }
      if (!inst.layer) {
        const layer = await createWarpedLayer(olMap, {
          zIndex: z + 1,
          name: `allmaps-overlay-${o.id}`,
        });
        if (
          destroyed ||
          !olMap ||
          !get(layersStore).overlays.some((row) => row.id === o.id && row.visible)
        ) {
          destroyWarpedLayer(layer);
          continue;
        }
        inst.layer = layer;
      }
      inst.layer.setZIndex(z + 1);
      if (inst.loadedAllmapsId !== o.ref.allmapsId) {
        inst.loadedAllmapsId = o.ref.allmapsId;
        void loadOverlayByUrl(inst.layer, olMap, o.ref.allmapsId, o.opacity).catch((error) =>
          console.warn('[LayerRenderer] Overlay load failed', error)
        );
      } else setOverlayOpacity(inst.layer, olMap, o.opacity);
    }
    topUpSeries();
    updateNotices();
  }

  // ── Clip mask (Lens / Side-by-side) ──────────────────────────────
  function refreshClips() {
    if (!olMap) return;
    const ls = get(layerStore);
    if (baseWarped) applyClipMask(baseWarped, olMap, ls.viewMode, ls.lensRadius);
    for (const { layer } of overlayInstances.values()) {
      if (layer) applyClipMask(layer, olMap, ls.viewMode, ls.lensRadius);
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
    const ls = get(layerStore);
    const overlays = get(layersStore).overlays;
    const active = overlays.filter(
      (o, i) =>
        o.ref.kind === 'series' &&
        o.visible &&
        !(ls.viewMode === 'dual' && i > 0) &&
        overlayInstances.get(o.id)?.series?.intersectsView(view)
    );
    const allocations = allocateSeriesBudgets(active.length, (olMap.getSize()?.[0] ?? 0) < 900);
    const budgetById = new Map(active.map((o, i) => [o.id, allocations[i]]));
    for (let i = 0; i < overlays.length; i++) {
      const o = overlays[i];
      const inst = overlayInstances.get(o.id);
      inst?.series?.update({
        view,
        allocation: budgetById.get(o.id) ?? 0,
        visible: budgetById.has(o.id),
        opacity: o.opacity,
        zIndex: 11 + 2 * (overlays.length - 1 - i),
        clip: ls.viewMode,
        lensRadius: ls.lensRadius,
      });
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

        mapEvents = [
          $map.on('moveend', refreshClips),
          $map.on('moveend', topUpSeries),
          $map.on('change:size', () => {
            refreshClips();
            topUpSeries();
          }),
        ];
      })
    );
  });

  onDestroy(() => {
    destroyed = true;
    pending = null;
    unByKey(mapEvents);
    mapEvents = [];
    unsubs.forEach((u) => u());
    unsubs = [];
    if (baseWarped) {
      destroyWarpedLayer(baseWarped);
      baseWarped = null;
    }
    for (const id of overlayInstances.keys()) removeInstance(id);
    olMap = null;
  });
</script>

{#if overviewNotices.length}
  <div class="series-overview-notice" data-series-overview-notice role="status">
    <strong>{$t('Zoom in to view series scans')}</strong>
    {#each overviewNotices as notice (notice.id)}<span>{notice.name}</span>{/each}
  </div>
{/if}

<style>
  .series-overview-notice {
    position: absolute;
    top: var(--space-3);
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    padding: var(--space-2) var(--space-3);
    max-width: 80%;
    background: var(--sb-card-bg);
    color: var(--sb-text);
    border: var(--border-thin);
    border-radius: var(--sb-radius);
    font-size: 0.75rem;
    pointer-events: none;
    text-align: center;
  }
  .series-overview-notice span {
    display: block;
    color: var(--sb-text-muted);
  }
</style>
