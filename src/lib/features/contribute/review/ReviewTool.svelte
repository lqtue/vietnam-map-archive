<!--
  ReviewTool.svelte — SAM2 footprint polygons on the IIIF canvas.
  Must be a child of <ImageShell>; the OL map, view and tile layer come from
  getImageShellStore() (see TraceTool for the same arrangement).

  Orange = needs review · yellow = selected (and zoomed to) · green vertices =
  the Modify handles, which are only attached to the selected polygon.

  Right-click a vertex of the selected polygon drops that point (an edit);
  right-click any other polygon rejects it.

  Dispatches:
    select { id }
    edit   { id, pixelPolygon }   — after a vertex drag, in IIIF pixel space
    reject { id }                 — right-click on an unselected polygon
-->
<script lang="ts">
  import { onDestroy, createEventDispatcher } from 'svelte';
  import { INK, inkAlpha } from '$lib/core/ink';
  import { get } from 'svelte/store';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Feature from 'ol/Feature';
  import Polygon from 'ol/geom/Polygon';
  import LineString from 'ol/geom/LineString';
  import { geometryKind } from '$lib/data/maps/footprintTypes';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import Circle from 'ol/style/Circle';
  import Modify from 'ol/interaction/Modify';
  import Collection from 'ol/Collection';
  import { unByKey } from 'ol/Observable';
  import type { EventsKey } from 'ol/events';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import { vertexStyle } from '$lib/map/shell/vertexStyle';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import type { SamFootprint } from '$lib/data/supabase/footprints';
  import { toOlCoords, olCoordsToImage } from '$lib/core/geo/rectUtils';

  export let footprints: SamFootprint[] = [];
  export let selectedId: string | null = null;
  export let previewPolygon: [number, number][] | null = null;

  const dispatch = createEventDispatcher<{
    select: { id: string };
    edit: { id: string; pixelPolygon: [number, number][] };
    reject: { id: string };
  }>();

  const shellStore = getImageShellStore();

  let source: VectorSource | null = null;
  let layer: VectorLayer | null = null;
  let modify: Modify | null = null;
  let previewSource: VectorSource | null = null;
  let previewLayer: VectorLayer | null = null;
  let clickKey: EventsKey | null = null;
  let detachContextMenu: (() => void) | null = null;
  const modifyTargets = new Collection<Feature>();
  let initialized = false;

  // Canvas colours, matching the legend below.
  const styleDefault = new Style({
    stroke: new Stroke({ color: INK.orange, width: 1.5 }),
    fill: new Fill({ color: inkAlpha(INK.orange, 0.12) }),
  });
  const styleSelected = new Style({
    stroke: new Stroke({ color: INK.yellow, width: 2.5 }),
    fill: new Fill({ color: inkAlpha(INK.yellow, 0.22) }),
  });

  const styleSelectedVertices = [styleSelected, vertexStyle(INK.yellow)];

  function getStyle(feature: any): Style | Style[] {
    return feature.getId() === selectedId ? styleSelectedVertices : styleDefault;
  }

  /** Rebuilds the vector features, re-points Modify, and repaints the styles. */
  function render(list: SamFootprint[], id: string | null) {
    if (!source) return;
    syncFootprints(list);
    syncModifyTarget(id);
    source.changed();
  }

  function syncFootprints(list: SamFootprint[]) {
    if (!source) return;
    source.clear();
    for (const fp of list) {
      const feature = new Feature({
        geometry:
          geometryKind(fp.featureType, fp.pixelPolygon) === 'LineString'
            ? new LineString(toOlCoords(fp.pixelPolygon))
            : new Polygon([toOlCoords(fp.pixelPolygon)]),
      });
      feature.setId(fp.id);
      source.addFeature(feature);
    }
  }

  function renderPreview(polygon: [number, number][] | null) {
    if (!previewSource) return;
    previewSource.clear();
    if (polygon)
      previewSource.addFeature(new Feature({ geometry: new Polygon([toOlCoords(polygon)]) }));
    modify?.setActive(!polygon);
  }

  function focusSelected(id: string | null) {
    const ctx = get(shellStore);
    if (!ctx || !source || !id) return;
    const geom = source.getFeatureById(id)?.getGeometry();
    if (!geom) return;
    ctx.map
      .getView()
      .fit(geom.getExtent(), { padding: [80, 80, 80, 80], duration: 350, maxZoom: 6 });
  }

  /** Modify only ever targets the selected polygon. */
  function syncModifyTarget(id: string | null) {
    modifyTargets.clear();
    if (!source || !id) return;
    const feature = source.getFeatureById(id);
    if (feature) modifyTargets.push(feature);
  }

  function setup(ctx: ImageShellContext | null) {
    if (!ctx || initialized) return;
    initialized = true;

    source = new VectorSource();
    layer = new VectorLayer({ source, zIndex: 5, style: getStyle });
    ctx.map.addLayer(layer);
    previewSource = new VectorSource();
    previewLayer = new VectorLayer({
      source: previewSource,
      zIndex: 6,
      style: new Style({
        stroke: new Stroke({ color: INK.blue, width: 2.5, lineDash: [7, 5] }),
        fill: new Fill({ color: inkAlpha(INK.blue, 0.06) }),
      }),
    });
    ctx.map.addLayer(previewLayer);

    modify = new Modify({
      features: modifyTargets,
      style: new Style({
        image: new Circle({
          radius: 5,
          fill: new Fill({ color: INK.green }),
          stroke: new Stroke({ color: INK.paper, width: 1.5 }),
        }),
      }),
    });
    modify.on('modifyend', (event) => {
      event.features.forEach((f: Feature) => {
        const geom = f.getGeometry() as Polygon | LineString;
        if (!geom) return;
        // OL coords are y-flipped; hand the caller IIIF pixel space back.
        dispatch('edit', {
          id: String(f.getId()),
          pixelPolygon: olCoordsToImage(
            geom instanceof LineString ? geom.getCoordinates() : geom.getCoordinates()[0]
          ),
        });
      });
    });
    ctx.map.addInteraction(modify);

    clickKey = ctx.map.on('click', (e) => {
      const hit = ctx.map.forEachFeatureAtPixel(e.pixel, (f, l) => (l === layer ? f : undefined));
      if (hit) dispatch('select', { id: String(hit.getId()) });
    }) as EventsKey;

    const onContextMenu = (evt: MouseEvent) => {
      evt.preventDefault();
      if (modifyTargets.getLength() && modify?.removePoint(ctx.map.getEventCoordinate(evt))) return;
      const hit = ctx.map.forEachFeatureAtPixel(ctx.map.getEventPixel(evt), (f, l) =>
        l === layer ? f : undefined
      );
      if (hit && hit.getId() !== selectedId) dispatch('reject', { id: String(hit.getId()) });
    };
    const viewport = ctx.map.getViewport();
    viewport.addEventListener('contextmenu', onContextMenu);
    detachContextMenu = () => viewport.removeEventListener('contextmenu', onContextMenu);

    render(footprints, selectedId);
    renderPreview(previewPolygon);
  }

  $: setup($shellStore);
  $: render(footprints, selectedId);
  $: focusSelected(selectedId);
  $: renderPreview(previewPolygon);

  onDestroy(() => {
    const ctx = get(shellStore);
    if (clickKey) unByKey(clickKey);
    detachContextMenu?.();
    if (ctx && modify) ctx.map.removeInteraction(modify);
    if (ctx && layer) ctx.map.removeLayer(layer);
    if (ctx && previewLayer) ctx.map.removeLayer(previewLayer);
    previewSource = null;
    previewLayer = null;
    source = null;
    layer = null;
    modify = null;
  });
</script>

<div class="legend">
  <span class="legend-dot orange"></span> Needs review
  <span class="legend-dot yellow"></span> Selected
  <span class="legend-dot green"></span> Drag to edit · right-click a vertex to drop it, another shape
  to reject it
</div>

<style>
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
  }

  .legend-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  /* Gap before every dot but the first. Sibling combinators skip the label text
     between them, so this holds however many entries the legend grows to. */
  .legend-dot ~ .legend-dot {
    margin-left: 0.75rem;
  }

  /* The same three inks the OpenLayers styles above use, reached through the
     tokens rather than copied. */
  .legend-dot.orange {
    background: var(--color-orange);
    color: var(--color-on-accent);
  }
  .legend-dot.yellow {
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
  }
  .legend-dot.green {
    background: var(--color-green);
    color: var(--color-on-accent);
  }
</style>
