<!--
  TraceTool.svelte — OL polygon/line draw and Select+Modify interactions.
  Must be rendered as a child of <ImageShell>. Accesses the OL map,
  footprintSource, drawSource, and footprintLayer via getImageShellStore().

  Modes:
    'trace'  — Draw interaction (polygon or line) using drawSource as staging area.
               Emits drawPolygon when the shape is complete.
    'select' — Select+Modify on the footprintLayer. Delete key removes selected
               footprints that belong to myUserId. Emits modifyFootprint on drag.

  Dispatches:
    drawPolygon    { pixelPolygon: PixelCoord[] }
    modifyFootprint { footprintId: string; pixelPolygon: PixelCoord[] }
    removeFootprint { footprintId: string }
-->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { get } from 'svelte/store';
  import Draw from 'ol/interaction/Draw';
  import Snap from 'ol/interaction/Snap';
  import Select from 'ol/interaction/Select';
  import Modify from 'ol/interaction/Modify';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import CircleStyle from 'ol/style/Circle';
  import Polygon from 'ol/geom/Polygon';
  import LineString from 'ol/geom/LineString';
  import { click as clickCondition } from 'ol/events/condition';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import type { PixelCoord } from '$lib/data/maps/footprintTypes';
  import { olCoordsToImage } from '$lib/core/geo/rectUtils';

  export let drawMode: 'trace' | 'select' = 'trace';
  export let geometryMode: 'Polygon' | 'LineString' = 'Polygon';
  export let placingEnabled = false;
  export let myUserId: string | null = null;

  const shellStore = getImageShellStore();

  const dispatch = createEventDispatcher<{
    drawPolygon: { pixelPolygon: PixelCoord[] };
    modifyFootprint: { footprintId: string; pixelPolygon: PixelCoord[] };
    removeFootprint: { footprintId: string };
  }>();

  // Internal state tracked per interaction lifecycle
  let drawInteraction: Draw | null = null;
  let snapInteraction: Snap | null = null;
  let selectInteraction: Select | null = null;
  let modifyInteraction: Modify | null = null;
  let isDrawing = false;
  let drawingPointCount = 0;

  function clearInteractions(ctx: ImageShellContext) {
    if (drawInteraction) {
      ctx.map.removeInteraction(drawInteraction);
      drawInteraction = null;
    }
    if (snapInteraction) {
      ctx.map.removeInteraction(snapInteraction);
      snapInteraction = null;
    }
    if (selectInteraction) {
      ctx.map.removeInteraction(selectInteraction);
      selectInteraction = null;
    }
    if (modifyInteraction) {
      ctx.map.removeInteraction(modifyInteraction);
      modifyInteraction = null;
    }
    isDrawing = false;
    drawingPointCount = 0;
  }

  // Style used while drawing (dashed amber preview)
  const DRAW_STYLE = new Style({
    // Literal: OpenLayers styles cannot read a CSS custom property.
    stroke: new Stroke({ color: '#f59e0b', width: 2, lineDash: [6, 4] }),
    fill: new Fill({ color: 'rgba(245, 158, 11, 0.15)' }),
    image: new CircleStyle({ radius: 5, fill: new Fill({ color: '#f59e0b' }) }),
  });

  // Style for selected footprint
  function createSelectedStyle(feature: any): Style {
    const geomType = feature.getGeometry()?.getType();
    const isLine = geomType === 'LineString';
    return new Style({
      stroke: new Stroke({ color: '#ff6b35', width: isLine ? 3 : 2.5 }),
      fill: isLine ? undefined : new Fill({ color: 'rgba(255, 107, 53, 0.2)' }),
      image: new CircleStyle({
        radius: 6,
        fill: new Fill({ color: '#ff6b35' }),
        stroke: new Stroke({ color: '#fff', width: 2 }),
      }),
    });
  }

  function setupInteractions(
    ctx: ImageShellContext | null,
    mode: typeof drawMode,
    enabled: boolean,
    gm: typeof geometryMode
  ) {
    if (!ctx) return;
    clearInteractions(ctx);

    // ── Trace mode: Draw + Snap ────────────────────────────────────────────
    if (mode === 'trace' && enabled && ctx.drawSource) {
      drawInteraction = new Draw({
        source: ctx.drawSource,
        type: gm,
        style: DRAW_STYLE,
      });

      drawInteraction.on('drawstart', (evt: any) => {
        isDrawing = true;
        drawingPointCount = 0;
        evt.feature.getGeometry().on('change', (geomEvt: any) => {
          const g = geomEvt.target;
          if (g instanceof Polygon) {
            drawingPointCount = Math.max(0, g.getCoordinates()[0].length - 1);
          } else if (g instanceof LineString) {
            drawingPointCount = Math.max(0, g.getCoordinates().length);
          }
        });
      });

      drawInteraction.on('drawabort', () => {
        isDrawing = false;
        drawingPointCount = 0;
        ctx.drawSource?.clear();
      });

      drawInteraction.on('drawend', (evt: any) => {
        isDrawing = false;
        drawingPointCount = 0;
        // OL adds the feature to drawSource after drawend fires — clear async
        const src = ctx.drawSource;
        setTimeout(() => src?.clear(), 0);

        const geom = evt.feature.getGeometry();
        let pixelCoords: PixelCoord[];
        if (geom instanceof Polygon) {
          pixelCoords = olCoordsToImage(geom.getCoordinates()[0]);
          pixelCoords.pop(); // remove closing duplicate
        } else {
          // LineString (road, waterway)
          pixelCoords = olCoordsToImage((geom as LineString).getCoordinates());
        }
        dispatch('drawPolygon', { pixelPolygon: pixelCoords });
      });

      // Snap to existing footprint vertices for precision
      snapInteraction = new Snap({ source: ctx.footprintSource ?? undefined });

      ctx.map.addInteraction(drawInteraction);
      ctx.map.addInteraction(snapInteraction);
    }

    // ── Select mode: Select + Modify ────────────────────────────────────────
    if (mode === 'select' && ctx.footprintLayer) {
      const targetLayer = ctx.footprintLayer;

      selectInteraction = new Select({
        condition: clickCondition,
        layers: (layer: any) => layer === targetLayer,
        style: createSelectedStyle,
      });

      modifyInteraction = new Modify({
        features: selectInteraction.getFeatures(),
        style: new Style({
          image: new CircleStyle({
            radius: 7,
            fill: new Fill({ color: '#ff6b35' }),
            stroke: new Stroke({ color: '#fff', width: 2 }),
          }),
        }),
      });

      modifyInteraction.on('modifyend', (evt: any) => {
        evt.features.forEach((feature: any) => {
          const footprintId = feature.get('footprintId');
          const userId = feature.get('userId');
          if (!footprintId) return;
          if (myUserId && userId !== myUserId) return;

          const geom = feature.getGeometry();
          let pixelPolygon: PixelCoord[];
          if (geom instanceof Polygon) {
            pixelPolygon = olCoordsToImage(geom.getCoordinates()[0]);
            pixelPolygon.pop();
          } else if (geom instanceof LineString) {
            pixelPolygon = olCoordsToImage(geom.getCoordinates());
          } else {
            return;
          }
          dispatch('modifyFootprint', { footprintId, pixelPolygon });
        });
      });

      ctx.map.addInteraction(selectInteraction);
      ctx.map.addInteraction(modifyInteraction);
    }
  }

  // Re-setup whenever store or mode props change
  $: setupInteractions($shellStore, drawMode, placingEnabled, geometryMode);

  onMount(() => {
    const handleKeydown = (evt: KeyboardEvent) => {
      const tag = (evt.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      // Ctrl/Cmd+Z: undo last point during active drawing
      if ((evt.ctrlKey || evt.metaKey) && evt.key === 'z') {
        if (drawInteraction && isDrawing) {
          evt.preventDefault();
          drawInteraction.removeLastPoint();
        }
        return;
      }

      // Enter: finish current polygon/line (needs ≥2 points for line, ≥3 for polygon)
      if (evt.key === 'Enter') {
        if (drawInteraction && isDrawing && drawingPointCount >= 2) {
          evt.preventDefault();
          drawInteraction.finishDrawing();
        }
        return;
      }

      // Escape: cancel drawing or deselect
      if (evt.key === 'Escape') {
        if (drawInteraction && isDrawing) {
          drawInteraction.abortDrawing();
          isDrawing = false;
          drawingPointCount = 0;
        }
        selectInteraction?.getFeatures().clear();
        return;
      }

      // Delete/Backspace: remove selected footprints (select mode only)
      if ((evt.key === 'Delete' || evt.key === 'Backspace') && drawMode === 'select') {
        if (!selectInteraction) return;
        const features = selectInteraction.getFeatures().getArray().slice();
        for (const feature of features) {
          const footprintId = feature.get('footprintId');
          const userId = feature.get('userId');
          if (!footprintId) continue;
          if (myUserId && userId !== myUserId) continue;
          dispatch('removeFootprint', { footprintId });
        }
        selectInteraction.getFeatures().clear();
      }
    };

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    const ctx = get(shellStore);
    if (ctx) clearInteractions(ctx);
  });
</script>

<!-- Status indicator overlaid on the image canvas -->
{#if drawMode === 'trace' && placingEnabled}
  {#if isDrawing}
    <div class="trace-status drawing">
      <span class="pts-badge">{drawingPointCount} pt{drawingPointCount !== 1 ? 's' : ''}</span>
      <span class="hint">
        Drawing {geometryMode === 'LineString' ? 'line' : 'polygon'}
        &nbsp;·&nbsp; <kbd>Enter</kbd> or double-click to finish &nbsp;·&nbsp; <kbd>Ctrl+Z</kbd>
        undo &nbsp;·&nbsp; <kbd>Esc</kbd> cancel
      </span>
    </div>
  {:else}
    <div class="trace-status idle">
      Click to start drawing a {geometryMode === 'LineString' ? 'line' : 'polygon'}
    </div>
  {/if}
{:else if drawMode === 'select'}
  <div class="trace-status select-mode">
    Click a shape to select · drag vertices to edit · <kbd>Delete</kbd> to remove
  </div>
{/if}

<style>
  .trace-status {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.9rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-family: 'Be Vietnam Pro', sans-serif;
    z-index: 50;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: var(--shadow-overlay);
  }

  /* Three states, one ramp: accent solid while live, an accent tint while a
     feature is selected, plain raised ground at rest. */
  .trace-status.drawing {
    background: var(--accent);
    color: var(--on-accent);
    top: auto;
    bottom: 0;
    left: 0;
    right: 0;
    transform: none;
    border-radius: 0;
    padding: 0.45rem 0.9rem;
  }

  .trace-status.idle {
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    color: var(--ink);
  }

  .trace-status.select-mode {
    background: color-mix(in srgb, var(--accent) 12%, var(--ground-raised));
    border: var(--rule-hair) solid var(--accent);
    color: var(--ink);
  }

  .pts-badge {
    font-weight: 800;
    font-size: 0.8rem;
    background: color-mix(in srgb, currentColor 12%, transparent);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .hint {
    flex: 1;
    text-align: center;
  }

  kbd {
    font-family: monospace;
    font-size: 0.7rem;
    background: color-mix(in srgb, currentColor 15%, transparent);
    padding: 0.05rem 0.3rem;
    border-radius: 2px;
    border: var(--rule-hair) solid color-mix(in srgb, currentColor 25%, transparent);
  }
</style>
