<!--
  ShapeTool.svelte — the one canvas tool for /scan?mode=shapes.
  Must be a child of <ImageShell>; draws on its footprintLayer rather than a
  layer of its own, so a sheet's shapes are drawn once.

  It replaced two tools (TraceTool for drawing, ReviewTool for checking) that
  did select-and-drag twice, each missing what the other had: checking could not
  add a missing shape, drawing could not see the machine's.

  Tools:
    polygon / line — Draw, staged on drawSource. Emits `draw` when finished.
    edit           — click a shape to select it; drag the selected one's corners.

  Every shape on the sheet is drawn, coloured by state (waiting orange, approved
  green, draft grey; selected yellow). Only those in `activeIds` — the list the
  sidebar shows — can be selected or edited; the rest are faint context.
  Selection is the parent's (`selectedId`); this reports clicks and zooms to it.

  Keys: Enter finishes a shape, Ctrl/Cmd+Z drops its last point, Esc cancels it,
  Delete removes the selected shape if it is yours.

  Dispatches:
    draw   { pixelPolygon, geometry }
    select { id }
    modify { id, pixelPolygon }   — after a corner drag, in IIIF pixel space
    remove { id }
-->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { get } from 'svelte/store';
  import { INK, inkAlpha } from '$lib/core/ink';
  import Draw from 'ol/interaction/Draw';
  import Modify from 'ol/interaction/Modify';
  import Snap from 'ol/interaction/Snap';
  import Collection from 'ol/Collection';
  import Feature from 'ol/Feature';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import CircleStyle from 'ol/style/Circle';
  import Polygon from 'ol/geom/Polygon';
  import LineString from 'ol/geom/LineString';
  import { unByKey } from 'ol/Observable';
  import type { EventsKey } from 'ol/events';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import type { FootprintSubmission, PixelCoord } from '$lib/data/maps/footprintTypes';
  import { olCoordsToImage } from '$lib/core/geo/rectUtils';

  export let footprints: FootprintSubmission[] = [];
  /** The rows the sidebar lists: the only ones a click can select. */
  export let activeIds: Set<string> = new Set();
  export let selectedId: string | null = null;
  export let tool: 'polygon' | 'line' | 'edit' = 'edit';
  export let myUserId: string | null = null;

  const dispatch = createEventDispatcher<{
    draw: { pixelPolygon: PixelCoord[]; geometry: 'Polygon' | 'LineString' };
    select: { id: string | null };
    modify: { id: string; pixelPolygon: PixelCoord[] };
    remove: { id: string };
  }>();

  const shellStore = getImageShellStore();

  let draw: Draw | null = null;
  let snap: Snap | null = null;
  let modify: Modify | null = null;
  const modifyTargets = new Collection<Feature>();
  let keys: EventsKey[] = [];
  let previousStyle: ReturnType<ImageShellContext['footprintLayer']['getStyle']> | undefined;
  let initialized = false;
  let isDrawing = false;
  let pointCount = 0;
  /** A selection made before its feature was on the canvas; fitted when it lands. */
  let pendingFocus: string | null = null;

  $: byId = new Map(footprints.map((f) => [f.id, f]));
  $: geometry = (tool === 'line' ? 'LineString' : 'Polygon') as 'Polygon' | 'LineString';

  // ── Styles ─────────────────────────────────────────────────────────────────
  function stateInk(status: string): string {
    if (status === 'approved') return INK.green;
    if (status === 'draft') return INK.grey;
    return INK.orange; // submitted, needs_review: waiting on a person
  }

  const DRAW_STYLE = new Style({
    stroke: new Stroke({ color: INK.yellow, width: 2, lineDash: [6, 4] }),
    fill: new Fill({ color: inkAlpha(INK.yellow, 0.15) }),
    image: new CircleStyle({ radius: 5, fill: new Fill({ color: INK.yellow }) }),
  });

  const VERTEX_STYLE = new Style({
    image: new CircleStyle({
      radius: 5,
      fill: new Fill({ color: INK.green }),
      stroke: new Stroke({ color: INK.paper, width: 1.5 }),
    }),
  });

  function shapeStyle(feature: any): Style {
    const id = String(feature.getId());
    const isLine = feature.getGeometry()?.getType() === 'LineString';
    if (id === selectedId) {
      return new Style({
        stroke: new Stroke({ color: INK.yellow, width: isLine ? 3.5 : 2.5 }),
        fill: isLine ? undefined : new Fill({ color: inkAlpha(INK.yellow, 0.22) }),
      });
    }
    const ink = stateInk(byId.get(id)?.status ?? '');
    if (!activeIds.has(id)) {
      return new Style({ stroke: new Stroke({ color: inkAlpha(ink, 0.45), width: 1 }) });
    }
    return new Style({
      stroke: new Stroke({ color: ink, width: isLine ? 3 : 1.5 }),
      fill: isLine ? undefined : new Fill({ color: inkAlpha(ink, 0.12) }),
    });
  }

  // ── Selection ──────────────────────────────────────────────────────────────
  function syncModifyTarget(ctx: ImageShellContext | null, id: string | null) {
    modifyTargets.clear();
    if (!ctx || !id || !activeIds.has(id)) return;
    const feature = ctx.footprintSource.getFeatureById(id);
    if (feature) modifyTargets.push(feature as Feature);
  }

  function focus(ctx: ImageShellContext | null, id: string | null) {
    if (!ctx || !id) return;
    const geom = ctx.footprintSource.getFeatureById(id)?.getGeometry();
    if (!geom) {
      pendingFocus = id;
      return;
    }
    pendingFocus = null;
    // Cap the zoom by resolution, not zoom level. ImageShell's view keeps the default
    // web-map zoom ladder, where zoom 6 is ~2,446 units per screen pixel; in image
    // pixels that shrank a whole sheet to a few pixels, so every row "flew to nothing".
    // 0.5 = at most two screen pixels per source pixel.
    ctx.map
      .getView()
      .fit(geom.getExtent(), { padding: [80, 80, 80, 80], duration: 350, minResolution: 0.5 });
  }

  // ── Drawing ────────────────────────────────────────────────────────────────
  function clearDraw(ctx: ImageShellContext) {
    if (draw) ctx.map.removeInteraction(draw);
    if (snap) ctx.map.removeInteraction(snap);
    draw = null;
    snap = null;
    isDrawing = false;
    pointCount = 0;
  }

  function setupDraw(ctx: ImageShellContext | null, t: typeof tool, g: typeof geometry) {
    if (!ctx) return;
    clearDraw(ctx);
    if (modify) modify.setActive(t === 'edit');
    if (t === 'edit') return;

    draw = new Draw({ source: ctx.drawSource, type: g, style: DRAW_STYLE });
    draw.on('drawstart', (evt: any) => {
      isDrawing = true;
      pointCount = 0;
      evt.feature.getGeometry().on('change', (geomEvt: any) => {
        const shape = geomEvt.target;
        if (shape instanceof Polygon) {
          pointCount = Math.max(0, shape.getCoordinates()[0].length - 1);
        } else if (shape instanceof LineString) {
          pointCount = shape.getCoordinates().length;
        }
      });
    });
    draw.on('drawabort', () => {
      isDrawing = false;
      pointCount = 0;
      ctx.drawSource.clear();
    });
    draw.on('drawend', (evt: any) => {
      isDrawing = false;
      pointCount = 0;
      const shape = evt.feature.getGeometry();
      let pixelPolygon: PixelCoord[];
      if (shape instanceof Polygon) {
        pixelPolygon = olCoordsToImage(shape.getCoordinates()[0]);
        pixelPolygon.pop(); // OL closes the ring; the table stores it open
      } else if (shape instanceof LineString) {
        pixelPolygon = olCoordsToImage(shape.getCoordinates());
      } else {
        return;
      }
      // Clear after OL has finished adding the sketch to the source.
      setTimeout(() => ctx.drawSource.clear(), 0);
      dispatch('draw', { pixelPolygon, geometry: g });
    });
    ctx.map.addInteraction(draw);
    // Snap to the corners already on the sheet, so a block drawn beside its
    // neighbours shares their edge instead of leaving a sliver. Added after
    // Draw, as OL requires.
    snap = new Snap({ source: ctx.footprintSource });
    ctx.map.addInteraction(snap);
  }

  // ── Setup ──────────────────────────────────────────────────────────────────
  function setup(ctx: ImageShellContext | null) {
    if (!ctx || initialized) return;
    initialized = true;

    previousStyle = ctx.footprintLayer.getStyle();
    ctx.footprintLayer.setStyle(shapeStyle);

    modify = new Modify({ features: modifyTargets, style: VERTEX_STYLE });
    modify.on('modifyend', (event) => {
      event.features.forEach((f) => {
        const shape = f.getGeometry();
        let pixelPolygon: PixelCoord[];
        if (shape instanceof Polygon) {
          pixelPolygon = olCoordsToImage(shape.getCoordinates()[0]);
          pixelPolygon.pop();
        } else if (shape instanceof LineString) {
          pixelPolygon = olCoordsToImage(shape.getCoordinates());
        } else {
          return;
        }
        dispatch('modify', { id: String(f.getId()), pixelPolygon });
      });
    });
    ctx.map.addInteraction(modify);

    keys = [
      ctx.map.on('click', (e) => {
        if (tool !== 'edit') return;
        const hit = ctx.map.forEachFeatureAtPixel(
          e.pixel,
          (f) => (activeIds.has(String(f.getId())) ? f : undefined),
          { layerFilter: (l) => l === ctx.footprintLayer }
        );
        if (hit) dispatch('select', { id: String(hit.getId()) });
      }) as EventsKey,
      // ImageShell rebuilds every feature when the list changes, so the selected
      // one is a new object: point Modify at it, and fit a selection that was
      // waiting for its feature to arrive.
      ctx.footprintSource.on('addfeature', (e) => {
        const id = e.feature ? String(e.feature.getId()) : '';
        if (id !== selectedId) return;
        syncModifyTarget(ctx, id);
        if (pendingFocus === id) focus(ctx, id);
      }),
    ];

    setupDraw(ctx, tool, geometry);
  }

  $: setup($shellStore);
  $: setupDraw($shellStore, tool, geometry);
  $: syncModifyTarget($shellStore, activeIds.has(selectedId ?? '') ? selectedId : null);
  $: focus($shellStore, selectedId);
  /** Repaint when what the style reads changes; the features themselves are ImageShell's. */
  function repaint(ctx: ImageShellContext | null, ..._styleInputs: unknown[]) {
    ctx?.footprintLayer.changed();
  }
  $: repaint($shellStore, selectedId, activeIds, byId);

  onMount(() => {
    const onKeydown = (evt: KeyboardEvent) => {
      // A Vietnamese (or any IME) keyboard sends Enter to confirm a syllable;
      // that keypress belongs to the input method, not to the drawing.
      if (evt.isComposing) return;
      const target = evt.target as HTMLElement | null;
      if (
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.isContentEditable
      )
        return;

      if ((evt.ctrlKey || evt.metaKey) && evt.key === 'z') {
        if (draw && isDrawing) {
          evt.preventDefault();
          draw.removeLastPoint();
        }
        return;
      }
      if (evt.key === 'Enter') {
        if (draw && isDrawing && pointCount >= 2) {
          evt.preventDefault();
          draw.finishDrawing();
        }
        return;
      }
      if (evt.key === 'Escape') {
        if (draw && isDrawing) draw.abortDrawing();
        return;
      }
      if ((evt.key === 'Delete' || evt.key === 'Backspace') && tool === 'edit' && selectedId) {
        const row = byId.get(selectedId);
        if (row && myUserId && row.userId === myUserId) {
          evt.preventDefault();
          dispatch('remove', { id: row.id });
        }
      }
    };
    window.addEventListener('keydown', onKeydown);
    return () => window.removeEventListener('keydown', onKeydown);
  });

  onDestroy(() => {
    const ctx = get(shellStore);
    keys.forEach((k) => unByKey(k));
    if (!ctx) return;
    clearDraw(ctx);
    if (modify) ctx.map.removeInteraction(modify);
    if (previousStyle !== undefined) ctx.footprintLayer.setStyle(previousStyle);
  });
</script>

{#if tool !== 'edit'}
  {#if isDrawing}
    <div class="shape-status drawing">
      <span class="pts-badge">{pointCount} pt{pointCount !== 1 ? 's' : ''}</span>
      <span class="hint">
        Drawing {tool === 'line' ? 'line' : 'polygon'}
        &nbsp;·&nbsp; <kbd>Enter</kbd> or double-click to finish &nbsp;·&nbsp; <kbd>Ctrl+Z</kbd>
        undo &nbsp;·&nbsp; <kbd>Esc</kbd> cancel
      </span>
    </div>
  {:else}
    <div class="shape-status idle">
      Click to start drawing a {tool === 'line' ? 'line' : 'polygon'}
    </div>
  {/if}
{:else}
  <div class="legend">
    <span class="legend-dot orange"></span> Waiting
    <span class="legend-dot green"></span> Approved
    <span class="legend-dot yellow"></span> Selected · drag corners to edit
  </div>
{/if}

<style>
  .shape-status {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.9rem;
    border-radius: var(--sb-radius-sm);
    font-size: 0.75rem;
    font-family: var(--font-family-base);
    z-index: 50;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: var(--shadow-solid-xs);
  }

  .shape-status.drawing {
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    top: auto;
    bottom: 0;
    left: 0;
    right: 0;
    transform: none;
    border-radius: 0;
    padding: 0.45rem 0.9rem;
  }

  .shape-status.idle {
    background: var(--color-white);
    border: 1px solid var(--rule);
    color: var(--color-text);
  }

  .pts-badge {
    font-weight: 800;
    font-size: 0.8rem;
    background: color-mix(in srgb, var(--color-text) 12%, transparent);
    padding: 0.1rem 0.4rem;
    border-radius: var(--sb-radius-sm);
    flex-shrink: 0;
  }

  .hint {
    flex: 1;
    text-align: center;
  }

  kbd {
    font-family: monospace;
    font-size: 0.7rem;
    background: color-mix(in srgb, var(--color-text) 15%, transparent);
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
    border: 1px solid color-mix(in srgb, var(--color-text) 20%, transparent);
  }

  .legend {
    position: absolute;
    bottom: 1rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: color-mix(in srgb, var(--color-text) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-white) 18%, transparent);
    border-radius: var(--sb-radius);
    padding: 0.3rem 0.75rem;
    font-family: var(--font-family-base);
    font-size: 0.75rem;
    color: var(--color-gray-400);
    pointer-events: none;
    z-index: 10;
    white-space: nowrap;
  }

  .legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  /* Gap before every dot but the first; sibling combinators skip the label text. */
  .legend-dot ~ .legend-dot {
    margin-left: 0.75rem;
  }

  .legend-dot.orange {
    background: var(--color-orange);
  }
  .legend-dot.yellow {
    background: var(--color-yellow);
  }
  .legend-dot.green {
    background: var(--color-green);
  }
</style>
