<!--
  ReviewTool.svelte — SAM2 footprint polygons on the IIIF canvas.
  Must be a child of <ImageShell>; the OL map, view and tile layer come from
  getImageShellStore() (see TraceTool for the same arrangement).

  Orange = needs review · yellow = selected (and zoomed to) · green vertices =
  the Modify handles, which are only attached to the selected polygon.

  Dispatches:
    select { id }
    edit   { id, pixelPolygon }   — after a vertex drag, in IIIF pixel space
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
  import Circle from 'ol/style/Circle';
  import Modify from 'ol/interaction/Modify';
  import Collection from 'ol/Collection';
  import { unByKey } from 'ol/Observable';
  import type { EventsKey } from 'ol/events';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import type { SamFootprint } from '$lib/data/supabase/footprints';
  import { toOlCoords, olCoordsToImage } from '$lib/core/geo/rectUtils';

  export let footprints: SamFootprint[] = [];
  export let selectedId: string | null = null;

  const dispatch = createEventDispatcher<{
    select: { id: string };
    edit: { id: string; pixelPolygon: [number, number][] };
  }>();

  const shellStore = getImageShellStore();

  let source: VectorSource | null = null;
  let layer: VectorLayer | null = null;
  let modify: Modify | null = null;
  let clickKey: EventsKey | null = null;
  const modifyTargets = new Collection<Feature>();
  let initialized = false;

  // Canvas colours, matching the legend below.
  const styleDefault = new Style({
    // Literal: OpenLayers styles cannot read a CSS custom property.
    stroke: new Stroke({ color: '#f97316', width: 1.5 }),
    fill: new Fill({ color: 'rgba(249,115,22,0.12)' }),
  });
  const styleSelected = new Style({
    stroke: new Stroke({ color: '#eab308', width: 2.5 }),
    fill: new Fill({ color: 'rgba(234,179,8,0.22)' }),
  });

  function getStyle(feature: any): Style {
    return feature.getId() === selectedId ? styleSelected : styleDefault;
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
      const feature = new Feature({ geometry: new Polygon([toOlCoords(fp.pixelPolygon)]) });
      feature.setId(fp.id);
      source.addFeature(feature);
    }
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

    modify = new Modify({
      features: modifyTargets,
      style: new Style({
        image: new Circle({
          radius: 5,
          fill: new Fill({ color: '#22c55e' }),
          stroke: new Stroke({ color: '#fff', width: 1.5 }),
        }),
      }),
    });
    modify.on('modifyend', (event) => {
      event.features.forEach((f: Feature) => {
        const geom = f.getGeometry() as Polygon;
        if (!geom) return;
        // OL coords are y-flipped; hand the caller IIIF pixel space back.
        dispatch('edit', {
          id: String(f.getId()),
          pixelPolygon: olCoordsToImage(geom.getCoordinates()[0]),
        });
      });
    });
    ctx.map.addInteraction(modify);

    clickKey = ctx.map.on('click', (e) => {
      const hit = ctx.map.forEachFeatureAtPixel(e.pixel, (f, l) => (l === layer ? f : undefined));
      if (hit) dispatch('select', { id: String(hit.getId()) });
    }) as EventsKey;

    render(footprints, selectedId);
  }

  $: setup($shellStore);
  $: render(footprints, selectedId);
  $: focusSelected(selectedId);

  onDestroy(() => {
    const ctx = get(shellStore);
    if (clickKey) unByKey(clickKey);
    if (ctx && modify) ctx.map.removeInteraction(modify);
    if (ctx && layer) ctx.map.removeLayer(layer);
    source = null;
    layer = null;
    modify = null;
  });
</script>

<div class="legend">
  <span class="legend-dot orange"></span> Needs review
  <span class="legend-dot yellow" style="margin-left:0.75rem"></span> Selected
  <span class="legend-dot green" style="margin-left:0.75rem"></span> Drag to edit
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
    background: color-mix(in srgb, var(--ink) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--ground-raised) 18%, transparent);
    border-radius: 6px;
    padding: 0.3rem 0.75rem;
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--ink-soft);
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

  /* Literal, because these mirror the OpenLayers styles above exactly. */
  .legend-dot.orange {
    background: #f97316; /* token-exempt: legend swatch, mirrors the OL canvas style above */
  }
  .legend-dot.yellow {
    background: #eab308; /* token-exempt: legend swatch, mirrors the OL canvas style above */
  }
  .legend-dot.green {
    background: #22c55e; /* token-exempt: legend swatch, mirrors the OL canvas style above */
  }
</style>
