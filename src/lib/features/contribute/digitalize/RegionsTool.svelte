<!--
  RegionsTool.svelte — the layout regions on the ImageShell canvas.

  One labelled rectangle per region the layout pass returned: main map, title
  block, legend, name list, inset, and the furniture worth skipping. Click one
  to select it; the selected region gets corner handles and can be dragged, so
  a person corrects the model rather than redrawing from nothing.

  Kept out of TriageTool because the two answer different questions. The
  neatline and tile grid decide how the body is cut up; these decide what the
  parts of the sheet ARE. They share a canvas and nothing else.

  Coordinate convention: props/events are IMAGE-SPACE (y-down, [x,y,w,h]);
  OL is y-flipped (ol_y = -image_y).

  Must be a child of <ImageShell>.
-->
<script lang="ts">
  import { onDestroy, createEventDispatcher } from 'svelte';
  import { get } from 'svelte/store';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Feature from 'ol/Feature';
  import Polygon from 'ol/geom/Polygon';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import Text from 'ol/style/Text';
  import RegularShape from 'ol/style/RegularShape';
  import Translate from 'ol/interaction/Translate';
  import { unByKey } from 'ol/Observable';
  import type { EventsKey } from 'ol/events';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import { toOlRing, fromOlExtent, type Rect } from '$lib/core/geo/rectUtils';
  import { createRectEditor, type RectEditor } from '../shared/bboxHandles';
  import { LAYOUT_COLORS, LAYOUT_LABELS, type LayoutRegion } from '$lib/data/maps/triageTypes';

  export let imgWidth: number = 0;
  export let imgHeight: number = 0;
  export let regions: LayoutRegion[] = [];
  /** Index into `regions`, or null. Bound by the sidebar so both stay in step. */
  export let selected: number | null = null;
  export let visible: boolean = true;

  const dispatch = createEventDispatcher<{
    regionsChange: LayoutRegion[];
    select: number | null;
  }>();

  const shellStore = getImageShellStore();

  let source: VectorSource | null = null;
  let layer: VectorLayer | null = null;
  let rectEditor: RectEditor | null = null;
  let bodyTranslate: Translate | null = null;
  let clickKey: EventsKey | null = null;
  let initialized = false;

  const handleStyle = new Style({
    image: new RegularShape({
      points: 4,
      radius: 7,
      angle: Math.PI / 4,
      // Literal: OpenLayers styles cannot read a CSS custom property.
      fill: new Fill({ color: '#ffffff' }),
      stroke: new Stroke({ color: '#111827', width: 1.5 }),
    }),
  });

  /** Hex → rgba, so one palette drives both the stroke and its wash. */
  function wash(hex: string, alpha: number): string {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }

  function styleFor(feat: Feature): Style {
    const region = feat.get('region') as LayoutRegion;
    const isSelected = feat.get('idx') === selected;
    const color = LAYOUT_COLORS[region.category] ?? '#64748b';
    return new Style({
      stroke: new Stroke({
        color,
        width: isSelected ? 3.5 : 2,
        // A dashed edge reads as "proposed"; correcting one makes it solid.
        lineDash: region.source === 'model' ? [10, 5] : undefined,
      }),
      fill: new Fill({ color: wash(color, isSelected ? 0.14 : 0.06) }),
      text: new Text({
        text: LAYOUT_LABELS[region.category] ?? region.category,
        font: `${isSelected ? '600 ' : ''}13px system-ui, sans-serif`,
        fill: new Fill({ color }),
        stroke: new Stroke({ color: 'rgba(255,255,255,0.9)', width: 3 }),
        overflow: true,
        textAlign: 'left',
        textBaseline: 'top',
        offsetX: 6,
        offsetY: 6,
        placement: 'point',
      }),
    });
  }

  function clamp(r: Rect): Rect {
    const w = Math.max(8, Math.min(r.w, imgWidth));
    const h = Math.max(8, Math.min(r.h, imgHeight));
    return {
      x: Math.max(0, Math.min(r.x, imgWidth - w)),
      y: Math.max(0, Math.min(r.y, imgHeight - h)),
      w,
      h,
    };
  }

  function rectOf(r: LayoutRegion): Rect {
    return { x: r.bbox[0], y: r.bbox[1], w: r.bbox[2], h: r.bbox[3] };
  }

  /** A corrected region is a human's, whatever it started as. */
  function commit(idx: number, rect: Rect) {
    const next = regions.map((r, i) =>
      i === idx
        ? {
            ...r,
            bbox: [
              Math.round(rect.x),
              Math.round(rect.y),
              Math.round(rect.w),
              Math.round(rect.h),
            ] as LayoutRegion['bbox'],
            source: 'human' as const,
          }
        : r
    );
    regions = next;
    dispatch('regionsChange', next);
  }

  function rebuild() {
    if (!source) return;
    source.clear();
    // Largest first: a small legend drawn over a big main_map stays clickable,
    // because OL hit-tests the last feature added.
    const order = regions
      .map((r, idx) => ({ r, idx }))
      .sort((a, b) => b.r.bbox[2] * b.r.bbox[3] - a.r.bbox[2] * a.r.bbox[3]);
    for (const { r, idx } of order) {
      const feat = new Feature({ geometry: new Polygon([toOlRing(...r.bbox)]) });
      feat.setId(`region-${idx}`);
      feat.set('idx', idx);
      feat.set('region', r);
      source.addFeature(feat);
    }
  }

  function setup(ctx: ImageShellContext | null) {
    if (!ctx || initialized) return;
    const olMap = ctx.map;
    initialized = true;

    // zIndex 5: over the tile grid (3), under the neatline (6), so the neatline
    // stays draggable while the regions are up.
    source = new VectorSource();
    layer = new VectorLayer({
      source,
      zIndex: 5,
      style: (f: unknown) => styleFor(f as Feature),
    });
    olMap.addLayer(layer);

    bodyTranslate = new Translate({ layers: [layer] });
    bodyTranslate.on('translateend', () => {
      const feats = source!.getFeatures().filter((f) => f.get('idx') === selected);
      const feat = feats[0];
      if (!feat || selected === null) return;
      commit(selected, clamp(fromOlExtent((feat.getGeometry() as Polygon).getExtent())));
    });
    olMap.addInteraction(bodyTranslate);

    rectEditor = createRectEditor(olMap, {
      zIndex: 8,
      style: handleStyle,
      getRect: (id) => {
        const idx = Number(id);
        return regions[idx] ? rectOf(regions[idx]) : null;
      },
      clamp,
      onChange: (id, rect) => commit(Number(id), rect),
    });

    clickKey = olMap.on('singleclick', (event: { pixel: number[] }) => {
      const feat = olMap.forEachFeatureAtPixel(event.pixel, (f: unknown) => f as Feature, {
        layerFilter: (l: unknown) => l === layer,
      });
      const idx = feat ? (feat.get('idx') as number) : null;
      selected = idx;
      dispatch('select', idx);
    });
  }

  // Only the selected region is draggable: without this, brushing a region on
  // the way to a tile moves it.
  $: if (bodyTranslate) bodyTranslate.setActive(visible && selected !== null);
  $: if (layer) layer.setVisible(visible);
  $: if (initialized && source) {
    void regions;
    rebuild();
  }
  $: if (rectEditor) {
    const r = visible && selected !== null ? regions[selected] : null;
    rectEditor.show(r ? String(selected) : null, r ? rectOf(r) : null);
  }
  $: if (source) {
    void selected;
    source.changed();
  }

  $: setup($shellStore);

  onDestroy(() => {
    const ctx = get(shellStore);
    if (clickKey) unByKey(clickKey);
    rectEditor?.destroy();
    if (ctx) {
      if (bodyTranslate) ctx.map.removeInteraction(bodyTranslate);
      if (layer) ctx.map.removeLayer(layer);
    }
  });
</script>
