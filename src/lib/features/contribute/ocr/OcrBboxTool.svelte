<!--
  OcrBboxTool.svelte — Renders OCR extraction bboxes on the IIIF canvas.
  Must be a child of <ImageShell>. Accesses the OL map via getImageShellStore().

  Coordinate system:
    global_x/y/w/h are SOURCE IMAGE PIXEL COORDINATES (same space as OL canvas).
    OL uses y-flipped convention: ol_y = -image_y.

  Interactions:
    click        → select bbox, dispatch 'select'
    drag body    → Translate (move whole bbox), dispatch 'move' on end
    drag corner  → Translate on dedicated handle Point features, dispatch 'move' on end

  Corner handles appear only for the selected bbox (4 squares, one per corner).
  This replaces the old OL Modify + getModifiedRect() approach.
-->
<script lang="ts">
  import { CAT_COLORS } from '../shared/constants';
  import { onDestroy, createEventDispatcher } from 'svelte';
  import { get } from 'svelte/store';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Feature from 'ol/Feature';
  import Polygon from 'ol/geom/Polygon';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import TextStyle from 'ol/style/Text';
  import RegularShape from 'ol/style/RegularShape';
  import Select from 'ol/interaction/Select';
  import Translate from 'ol/interaction/Translate';
  import Draw, { createBox } from 'ol/interaction/Draw';
  import { click } from 'ol/events/condition';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { OcrExtraction } from '../shared/types';
  import { toOlRing, fromOlExtent, type Rect } from '$lib/core/geo/rectUtils';
  import { createRectEditor, type RectEditor } from '../shared/bboxHandles';

  export let extractions: OcrExtraction[] = [];
  export let selectedId: string | null = null;
  export let filteredIds = new Set<string>();
  export let isolationMode = false;
  export let drawMode = false;

  const dispatch = createEventDispatcher<{
    select: { id: string };
    move: { id: string; global_x: number; global_y: number; global_w: number; global_h: number };
    draw: { global_x: number; global_y: number; global_w: number; global_h: number };
  }>();

  const STATUS_DASH: Record<string, number[]> = {
    pending: [5, 4],
    validated: [],
    rejected: [2, 2],
  };

  const shellStore = getImageShellStore();
  let bboxSource: VectorSource | null = null;
  let bboxLayer: VectorLayer | null = null;
  let rectEditor: RectEditor | null = null;
  let selectInteraction: Select | null = null;
  let bodyTranslate: Translate | null = null;
  let drawInteraction: Draw | null = null;
  let activeId: string | null = null;
  let initialized = false;

  // ── Styling ──────────────────────────────────────────────────────────────

  function handleStyleFn(feat: Feature): Style {
    const bboxId = feat.get('bboxId') as string;
    const ext = extractions.find((e) => e.id === bboxId);
    const color = CAT_COLORS[ext?.category ?? ''] ?? '#9ca3af';
    return new Style({
      image: new RegularShape({
        points: 4,
        radius: 6,
        angle: Math.PI / 4,
        // Literal: OpenLayers styles cannot read a CSS custom property.
        fill: new Fill({ color: '#fff' }),
        stroke: new Stroke({ color, width: 2 }),
      }),
    });
  }

  function makeStyle(ext: OcrExtraction, selected = false): Style | any[] {
    const isFiltered = filteredIds.size === 0 || filteredIds.has(ext.id);
    const hasSelection = !!selectedId;

    let opacity = selected ? 1 : 0.45;
    if (!isFiltered) {
      opacity = 0;
    } else if (hasSelection && !selected) {
      opacity = isolationMode ? 0 : 0.25;
    }

    if (opacity === 0) return [];

    const color = CAT_COLORS[ext.category] ?? '#9ca3af';
    const dash = STATUS_DASH[ext.status] ?? [];
    const label = ext.text_validated ?? ext.text;

    return new Style({
      stroke: new Stroke({
        color: color + (opacity < 1 ? '66' : ''),
        width: selected ? 3 : 1.5,
        lineDash: dash,
      }),
      fill: new Fill({ color: color + (selected ? '44' : opacity < 0.5 ? '08' : '18') }),
      text:
        opacity > 0.5
          ? new TextStyle({
              text: label.length > 28 ? label.slice(0, 28) + '…' : label,
              font: '10px "Be Vietnam Pro", sans-serif',
              fill: new Fill({ color: '#fff' }),
              stroke: new Stroke({ color: '#2b2520', width: 2.5 }),
              overflow: true,
            })
          : undefined,
    });
  }

  // ── Sync extractions → OL features ───────────────────────────────────────
  function syncFeatures() {
    if (!bboxSource) return;
    const seenIds = new Set<string>();

    for (const ext of extractions) {
      if (!(ext.global_w > 0) || !(ext.global_h > 0)) continue;
      seenIds.add(ext.id);

      if (ext.id === activeId) {
        const feat = bboxSource.getFeatureById(ext.id);
        if (feat) {
          feat.set('extraction', ext);
          feat.setStyle(makeStyle(ext, ext.id === selectedId));
        }
        continue;
      }

      const ring = toOlRing(ext.global_x, ext.global_y, ext.global_w, ext.global_h);
      let feat = bboxSource.getFeatureById(ext.id);

      if (!feat) {
        feat = new Feature({ geometry: new Polygon([ring]) });
        feat.setId(ext.id);
        feat.set('extractionId', ext.id);
        bboxSource.addFeature(feat);
      } else {
        (feat.getGeometry() as Polygon).setCoordinates([ring]);
      }

      feat.set('extraction', ext);
      feat.setStyle(makeStyle(ext, ext.id === selectedId));
    }

    for (const feat of bboxSource.getFeatures()) {
      const id = feat.get('extractionId') as string;
      if (!seenIds.has(id)) bboxSource.removeFeature(feat);
    }
  }

  // ── Sync corner handles for the selected extraction ───────────────────────
  function rectOf(id: string): Rect | null {
    const ext = extractions.find((e) => e.id === id);
    if (!ext || !(ext.global_w > 0)) return null;
    return { x: ext.global_x, y: ext.global_y, w: ext.global_w, h: ext.global_h };
  }

  function syncHandles() {
    if (!rectEditor) return;
    rectEditor.show(selectedId, selectedId ? rectOf(selectedId) : null);
  }

  $: {
    extractions;
    selectedId;
    filteredIds;
    isolationMode;
    bboxSource && syncFeatures();
  }
  $: {
    selectedId;
    extractions;
    rectEditor && syncHandles();
  }

  // Toggle draw mode: disable select/translate, enable Draw interaction
  $: if (initialized) toggleDrawMode(drawMode);

  function toggleDrawMode(active: boolean) {
    if (!selectInteraction || !bodyTranslate || !rectEditor) return;
    selectInteraction.setActive(!active);
    bodyTranslate.setActive(!active);
    rectEditor.setActive(!active);
    if (drawInteraction) drawInteraction.setActive(active);
  }

  /** Snaps the bbox polygon + its cached extraction to a resized rect. */
  function snapBboxToRect(bboxId: string, rect: Rect) {
    const ext = extractions.find((e) => e.id === bboxId);
    const bboxFeat = bboxSource?.getFeatureById(bboxId);
    if (!ext || !bboxFeat) return;
    (bboxFeat.getGeometry() as Polygon).setCoordinates([toOlRing(rect.x, rect.y, rect.w, rect.h)]);
    const updatedExt = {
      ...ext,
      global_x: rect.x,
      global_y: rect.y,
      global_w: rect.w,
      global_h: rect.h,
    };
    bboxFeat.set('extraction', updatedExt);
    bboxFeat.setStyle(makeStyle(updatedExt, true));
  }

  // ── Tool setup ────────────────────────────────────────────────────────────
  $: setupTool($shellStore);

  function setupTool(ctx: typeof $shellStore) {
    if (!ctx || initialized) return;
    initialized = true;
    const olMap = ctx.map;

    // Bbox layer (z8)
    bboxSource = new VectorSource();
    bboxLayer = new VectorLayer({ source: bboxSource, zIndex: 8 });
    olMap.addLayer(bboxLayer);

    // Click to select bbox
    selectInteraction = new Select({
      condition: click,
      layers: (l: any) => l === bboxLayer,
      style: (feat: any) => makeStyle(feat.get('extraction'), true),
    });
    selectInteraction.on('select', (e: any) => {
      const feat = e.selected[0];
      if (feat) dispatch('select', { id: feat.get('extractionId') as string });
    });
    olMap.addInteraction(selectInteraction);

    // Body translate — move entire selected bbox
    bodyTranslate = new Translate({ features: selectInteraction.getFeatures() });
    bodyTranslate.on('translatestart', (e: any) => {
      const feat = e.features.getArray()[0];
      if (feat) activeId = feat.get('extractionId');
    });
    bodyTranslate.on('translateend', (e: any) => {
      activeId = null;
      for (const feat of e.features.getArray()) {
        const id = feat.get('extractionId') as string;
        const extent = (feat.getGeometry() as Polygon).getExtent();
        const rect = fromOlExtent(extent);
        dispatch('move', {
          id,
          global_x: rect.x,
          global_y: rect.y,
          global_w: rect.w,
          global_h: rect.h,
        });
        // Refresh handle positions to match new body position
        if (rectEditor && id === selectedId) rectEditor.move(rect);
      }
    });
    olMap.addInteraction(bodyTranslate);

    // Corner-handle resize (z9) — added after bodyTranslate so a corner drag
    // wins over a body drag (OL dispatches interactions last-added-first).
    rectEditor = createRectEditor(olMap, {
      zIndex: 9,
      style: (f: any) => handleStyleFn(f as Feature),
      getRect: rectOf,
      onDragStart: (bboxId) => (activeId = bboxId),
      onChange: (bboxId, rect) => {
        activeId = null;
        snapBboxToRect(bboxId, rect);
        dispatch('move', {
          id: bboxId,
          global_x: rect.x,
          global_y: rect.y,
          global_w: rect.w,
          global_h: rect.h,
        });
      },
    });

    // Draw interaction for adding new bboxes (inactive until drawMode=true)
    const drawSource = new VectorSource();
    drawInteraction = new Draw({
      source: drawSource,
      type: 'Circle',
      geometryFunction: createBox(),
    });
    drawInteraction.setActive(false);
    drawInteraction.on('drawend', (e: any) => {
      const extent = e.feature.getGeometry().getExtent();
      const rect = fromOlExtent(extent);
      drawSource.clear();
      dispatch('draw', { global_x: rect.x, global_y: rect.y, global_w: rect.w, global_h: rect.h });
    });
    olMap.addInteraction(drawInteraction);

    syncFeatures();
    syncHandles();
  }

  onDestroy(() => {
    const ctx = get(shellStore);
    rectEditor?.destroy();
    if (ctx) {
      if (drawInteraction) ctx.map.removeInteraction(drawInteraction);
      if (bodyTranslate) ctx.map.removeInteraction(bodyTranslate);
      if (selectInteraction) ctx.map.removeInteraction(selectInteraction);
      if (bboxLayer) ctx.map.removeLayer(bboxLayer);
    }
  });
</script>
