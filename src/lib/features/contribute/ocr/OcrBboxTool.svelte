<!--
  OcrBboxTool.svelte — the OCR labels on the IIIF canvas, as editable objects.

  Must be a child of <ImageShell>; the OL map comes from getImageShellStore().

  Each label is one rotated rectangle — an `Obb` (`$lib/core/geo/rectUtils`):
  centre, length along the text, thickness across it, and the angle. That
  rectangle is what gets drawn, hit-tested and edited; there is no axis-aligned
  outer box on screen any more. `global_*` is the box *around* it and is
  recomputed on every write (`obbToRow`), which is why turning a label no longer
  resizes it and why 45 degrees is no longer a blind spot.

  Coordinates are image pixels, y-down; OL is y-up (ol_y = -image_y) and every
  flip goes through rectUtils.

  Interactions, on the selected label only:
    click       → select
    drag body   → move the centre
    drag corner → resize along the label's own axes, opposite corner anchored
    drag knob   → turn about the centre
  Each dispatches `edit` with the columns to write; the parent owns the PATCH.
-->
<script lang="ts">
  import { CAT_COLORS } from '../shared/constants';
  import { reviewedCategory } from '../shared/ocrApi';
  import { INK } from '$lib/core/ink';
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
  import CircleStyle from 'ol/style/Circle';
  import Select from 'ol/interaction/Select';
  import Translate from 'ol/interaction/Translate';
  import Draw, { createBox } from 'ol/interaction/Draw';
  import { click } from 'ol/events/condition';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { OcrExtraction } from '../shared/types';
  import {
    fromOlExtent,
    obbFromRow,
    obbRing,
    obbToRow,
    ringCentre,
    rotationFromPointer,
    rotationHandlePoint,
    type Obb,
    type ObbRow,
  } from '$lib/core/geo/rectUtils';
  import {
    createObbEditor,
    createRotateHandle,
    type ObbEditor,
    type RotateHandle,
  } from '../shared/bboxHandles';

  export let extractions: OcrExtraction[] = [];
  export let selectedId: string | null = null;
  export let filteredIds = new Set<string>();
  export let isolationMode = false;
  export let drawMode = false;
  /** Layer visibility, owned by the left rail. Hidden boxes are also
   *  uninteractive: a Select over an invisible layer selects nothing a person
   *  can see. */
  export let visible = true;

  const dispatch = createEventDispatcher<{
    select: { id: string };
    edit: { id: string } & Required<ObbRow>;
    draw: Required<ObbRow>;
  }>();

  const STATUS_DASH: Record<string, number[]> = {
    pending: [5, 4],
    validated: [],
    rejected: [2, 2],
  };

  const shellStore = getImageShellStore();
  let labelSource: VectorSource | null = null;
  let labelLayer: VectorLayer | null = null;
  let obbEditor: ObbEditor | null = null;
  let rotateHandle: RotateHandle | null = null;
  /** The edit in flight, so the canvas can show it before the write lands. */
  let preview: { id: string; obb: Obb } | null = null;
  let selectInteraction: Select | null = null;
  let bodyTranslate: Translate | null = null;
  let drawInteraction: Draw | null = null;
  let initialized = false;

  // ── The label rectangle ───────────────────────────────────────────────────
  function rowOf(id: string): OcrExtraction | undefined {
    return extractions.find((e) => e.id === id);
  }

  /** As stored — the anchor a drag is resolved against, so never the preview. */
  function storedObb(id: string): Obb | null {
    const ext = rowOf(id);
    return ext && ext.global_w > 0 && ext.global_h > 0 ? obbFromRow(ext) : null;
  }

  /** What to draw: the live edit if there is one, else the row. */
  function obbOf(ext: OcrExtraction): Obb {
    return preview?.id === ext.id ? preview.obb : obbFromRow(ext);
  }

  // ── Styling ───────────────────────────────────────────────────────────────
  function cornerStyleFn(feat: Feature): Style {
    const ext = rowOf(feat.get('bboxId') as string);
    const color = CAT_COLORS[ext ? reviewedCategory(ext) : ''] ?? INK.grey;
    return new Style({
      image: new RegularShape({
        points: 4,
        radius: 6,
        angle: Math.PI / 4,
        fill: new Fill({ color: INK.paper }),
        stroke: new Stroke({ color, width: 2 }),
      }),
    });
  }

  function rotateStyleFn(feat: Feature): Style {
    const ext = rowOf(feat.get('bboxId') as string);
    const color = CAT_COLORS[ext ? reviewedCategory(ext) : ''] ?? INK.grey;
    return new Style({
      image: new CircleStyle({
        radius: 6,
        fill: new Fill({ color: INK.paper }),
        stroke: new Stroke({ color, width: 2 }),
      }),
    });
  }

  function makeStyle(ext: OcrExtraction, selected = false): Style | Style[] {
    const isFiltered = filteredIds.size === 0 || filteredIds.has(ext.id);
    const hasSelection = !!selectedId;

    let opacity = selected ? 1 : 0.45;
    if (!isFiltered) {
      opacity = 0;
    } else if (hasSelection && !selected) {
      opacity = isolationMode ? 0 : 0.25;
    }
    if (opacity === 0) return [];

    const color = CAT_COLORS[reviewedCategory(ext)] ?? INK.grey;
    const label = ext.text_validated ?? ext.text;

    return new Style({
      stroke: new Stroke({
        color: color + (opacity < 1 ? '66' : ''),
        width: selected ? 3 : 1.5,
        lineDash: STATUS_DASH[ext.status] ?? [],
      }),
      fill: new Fill({ color: color + (selected ? '44' : opacity < 0.5 ? '08' : '18') }),
      text:
        opacity > 0.5
          ? new TextStyle({
              text: label.length > 28 ? label.slice(0, 28) + '…' : label,
              font: '10px "Be Vietnam Pro", sans-serif',
              fill: new Fill({ color: INK.paper }),
              stroke: new Stroke({ color: INK.ink, width: 2.5 }),
              overflow: true,
              // OL rotation is clockwise; the stored angle reads counter-clockwise.
              // Rotating with the view keeps the caption on the lettering when the
              // whole sheet is turned.
              rotation: (-obbOf(ext).deg * Math.PI) / 180,
              rotateWithView: true,
            })
          : undefined,
    });
  }

  /**
   * Everything `makeStyle` reads. Typing one character in the review filter
   * moves `filteredIds`, which used to rebuild a Style, a Stroke, two Fills and
   * a Text for all 2000 features and repaint the lot — per keystroke. Almost
   * none of them actually change, so each feature remembers what it was drawn
   * with and only the ones whose answer moved are restyled.
   */
  function styleKey(ext: OcrExtraction, selected: boolean): string {
    const shown = filteredIds.size === 0 || filteredIds.has(ext.id);
    return [
      ext.category_validated ?? ext.category,
      ext.status,
      ext.text_validated ?? ext.text,
      obbOf(ext).deg,
      selected ? 1 : 0,
      shown ? 1 : 0,
      selectedId ? 1 : 0,
      isolationMode ? 1 : 0,
    ].join('|');
  }

  // ── Sync rows → OL features ───────────────────────────────────────────────
  //
  // Every write here — `setStyle`, `set`, `setCoordinates` — fires a change on
  // the feature, then on the source, then a repaint. The loop used to do all
  // three for all 2000 features on every run, and it runs on every keystroke in
  // the review filter (which moves `filteredIds`). So each write is now guarded
  // by whether its input actually moved: the rows are immutable, so identity is
  // the test for the data, and `styleKey` for the drawing.
  const styleKeys = new Map<string, string>();

  function syncFeatures() {
    if (!labelSource) return;
    const seen = new Set<string>();

    for (const ext of extractions) {
      if (!(ext.global_w > 0) || !(ext.global_h > 0)) continue;
      seen.add(ext.id);
      let feat = labelSource.getFeatureById(ext.id);
      if (!feat) {
        feat = new Feature({ geometry: new Polygon([obbRing(obbOf(ext))]) });
        feat.setId(ext.id);
        feat.set('extractionId', ext.id);
        feat.set('extraction', ext);
        labelSource.addFeature(feat);
      } else if (feat.get('extraction') !== ext) {
        (feat.getGeometry() as Polygon).setCoordinates([obbRing(obbOf(ext))]);
        feat.set('extraction', ext);
      }
      const selected = ext.id === selectedId;
      const key = styleKey(ext, selected);
      if (styleKeys.get(ext.id) !== key) {
        styleKeys.set(ext.id, key);
        feat.setStyle(makeStyle(ext, selected));
      }
    }

    for (const feat of labelSource.getFeatures()) {
      const id = feat.get('extractionId') as string;
      if (seen.has(id)) continue;
      labelSource.removeFeature(feat);
      styleKeys.delete(id);
    }
  }

  function syncHandles() {
    // Not mid-drag: repositioning the handle under the pointer fights the drag.
    if (preview) return;
    const obb = selectedId ? storedObb(selectedId) : null;
    obbEditor?.show(selectedId, obb);
    rotateHandle?.show(obb ? selectedId : null, obb ? rotationHandlePoint(obb) : null);
  }

  $: {
    void extractions;
    void selectedId;
    void filteredIds;
    void isolationMode;
    if (labelSource) syncFeatures();
  }
  $: {
    void selectedId;
    void extractions;
    if (obbEditor) syncHandles();
  }

  // Toggle draw mode: disable select/translate, enable Draw interaction
  $: labelLayer?.setVisible(visible);
  // Re-run the interaction split whenever either input moves: `visible` and
  // `drawMode` both decide the same four interactions, so one owner settles it.
  $: if (initialized) {
    void visible;
    toggleDrawMode(drawMode);
  }

  function toggleDrawMode(active: boolean) {
    if (!selectInteraction || !bodyTranslate || !obbEditor) return;
    const editable = !active && visible;
    selectInteraction.setActive(editable);
    bodyTranslate.setActive(editable);
    obbEditor.setActive(editable);
    rotateHandle?.setActive(editable);
    if (drawInteraction) drawInteraction.setActive(active && visible);
  }

  /**
   * Draw one label at the rectangle an edit is heading for. Both the feature
   * style and its `extraction` property are written, because a selected feature
   * is drawn twice — once by its layer and once by Select's overlay, which
   * styles from that property.
   */
  function showPreview(id: string, obb: Obb) {
    preview = { id, obb };
    const ext = rowOf(id);
    const feat = labelSource?.getFeatureById(id);
    if (!ext || !feat) return;
    (feat.getGeometry() as Polygon).setCoordinates([obbRing(obb)]);
    feat.set('extraction', ext);
    feat.setStyle(makeStyle(ext, true));
  }

  /** Hand the finished rectangle to the parent: itself plus the box around it. */
  function commit(id: string, obb: Obb) {
    preview = null;
    dispatch('edit', { id, ...obbToRow(obb) });
  }

  // ── Tool setup ────────────────────────────────────────────────────────────
  $: setupTool($shellStore);

  function setupTool(ctx: typeof $shellStore) {
    if (!ctx || initialized) return;
    initialized = true;
    const olMap = ctx.map;

    labelSource = new VectorSource();
    labelLayer = new VectorLayer({ source: labelSource, zIndex: 8 });
    olMap.addLayer(labelLayer);

    selectInteraction = new Select({
      condition: click,
      // A legend label can be 8 px tall at full zoom-out; an exact hit test
      // makes it unclickable.
      hitTolerance: 6,
      layers: (l: any) => l === labelLayer,
      style: (feat: any) => makeStyle(feat.get('extraction'), true),
    });
    selectInteraction.on('select', (e: any) => {
      const feat = e.selected[0];
      if (feat) dispatch('select', { id: feat.get('extractionId') as string });
    });
    olMap.addInteraction(selectInteraction);

    // Body drag — move the centre. OL drags the polygon itself, so the centre
    // is read back off the moved ring and the handles are carried along.
    bodyTranslate = new Translate({
      features: selectInteraction.getFeatures(),
      hitTolerance: 6,
    });
    const movedObb = (feat: Feature): { id: string; obb: Obb } | null => {
      const id = feat.get('extractionId') as string;
      const stored = storedObb(id);
      if (!stored) return null;
      const ring = (feat.getGeometry() as Polygon).getCoordinates()[0];
      const [cx, cy] = ringCentre(ring);
      return { id, obb: { ...stored, cx, cy } };
    };
    bodyTranslate.on('translating', (e: any) => {
      const feat = e.features.getArray()[0];
      const next = feat && movedObb(feat);
      if (!next) return;
      preview = next;
      obbEditor?.move(next.obb);
      rotateHandle?.show(next.id, rotationHandlePoint(next.obb));
    });
    bodyTranslate.on('translateend', (e: any) => {
      for (const feat of e.features.getArray()) {
        const next = movedObb(feat);
        if (next) commit(next.id, next.obb);
      }
    });
    olMap.addInteraction(bodyTranslate);

    // Corner resize (z9) — added after the body drag so a corner wins next to
    // it (OL dispatches interactions last-added-first).
    obbEditor = createObbEditor(olMap, {
      zIndex: 9,
      style: (f: any) => cornerStyleFn(f as Feature),
      getObb: storedObb,
      onDrag: (id, obb) => {
        showPreview(id, obb);
        rotateHandle?.show(id, rotationHandlePoint(obb));
      },
      onChange: commit,
    });

    // Turn handle (z10) — added last, so it wins wherever it overlaps a corner.
    rotateHandle = createRotateHandle(olMap, {
      zIndex: 10,
      style: (f: any) => rotateStyleFn(f as Feature),
      onDrag: (id, olPoint) => {
        const stored = storedObb(id);
        if (!stored) return;
        // Nothing but the angle changes — the label keeps the size it has.
        showPreview(id, { ...stored, deg: rotationFromPointer(stored.cx, stored.cy, olPoint) });
        obbEditor?.move(preview!.obb);
      },
      onChange: (id, olPoint) => {
        const stored = storedObb(id);
        preview = null;
        if (!stored) return;
        commit(id, { ...stored, deg: rotationFromPointer(stored.cx, stored.cy, olPoint) });
      },
    });

    // Draw interaction for adding new labels (inactive until drawMode=true).
    // A drawn box is upright, so it starts as its own rectangle at 0 degrees.
    const drawSource = new VectorSource();
    drawInteraction = new Draw({
      source: drawSource,
      type: 'Circle',
      geometryFunction: createBox(),
    });
    drawInteraction.setActive(false);
    drawInteraction.on('drawend', (e: any) => {
      const rect = fromOlExtent(e.feature.getGeometry().getExtent());
      drawSource.clear();
      dispatch(
        'draw',
        obbToRow({
          cx: rect.x + rect.w / 2,
          cy: rect.y + rect.h / 2,
          w: rect.w,
          h: rect.h,
          deg: 0,
        })
      );
    });
    olMap.addInteraction(drawInteraction);

    syncFeatures();
    syncHandles();
    // Same reason the two lines above are here: the `$: if (initialized)` block
    // that owns the interaction split has already run by the time a *remount*
    // reaches this function, so the four interactions would keep the defaults
    // they were constructed with — a live Draw tool on a panel that is not in
    // draw mode.
    toggleDrawMode(drawMode);
  }

  onDestroy(() => {
    const ctx = get(shellStore);
    obbEditor?.destroy();
    rotateHandle?.destroy();
    if (ctx) {
      if (drawInteraction) ctx.map.removeInteraction(drawInteraction);
      if (bodyTranslate) ctx.map.removeInteraction(bodyTranslate);
      if (selectInteraction) ctx.map.removeInteraction(selectInteraction);
      if (labelLayer) ctx.map.removeLayer(labelLayer);
    }
  });
</script>
