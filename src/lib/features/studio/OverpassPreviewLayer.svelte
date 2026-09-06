<!--
  OverpassPreviewLayer.svelte — renders fetched OSM features on the map as
  a preview before the user commits them to the annotation project. Sits
  inside MapShell and is removed when the preview clears.
-->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import VectorLayer from 'ol/layer/Vector';
  import VectorSource from 'ol/source/Vector';
  import GeoJSON from 'ol/format/GeoJSON';
  import { Style, Fill, Stroke } from 'ol/style';
  import CircleStyle from 'ol/style/Circle';
  import { getShellContext } from '$lib/map/shell/context';
  import type { FeatureCollection } from 'geojson';

  const { map: mapStore } = getShellContext();

  /** When null, the preview is hidden / removed. */
  export let features: FeatureCollection | null = null;

  const fmt = new GeoJSON();
  // Literal colours on purpose: OL builds styles in JS and cannot read a CSS
  // custom property, so the role tokens are unavailable here.
  const style = new Style({
    stroke: new Stroke({ color: '#d97706', width: 2, lineDash: [4, 4] }),
    fill: new Fill({ color: 'rgba(217, 119, 6, 0.12)' }),
    image: new CircleStyle({
      radius: 5,
      fill: new Fill({ color: 'rgba(217, 119, 6, 0.6)' }),
      stroke: new Stroke({ color: '#92400e', width: 1.5 }),
    }),
  });

  let layer: VectorLayer<VectorSource> | null = null;
  let source: VectorSource | null = null;

  function teardown() {
    const map = $mapStore;
    if (layer && map) map.removeLayer(layer);
    layer = null;
    source = null;
  }

  $: {
    const map = $mapStore;
    teardown();
    if (map && features && features.features.length > 0) {
      source = new VectorSource({
        features: fmt.readFeatures(features, {
          dataProjection: 'EPSG:4326',
          featureProjection: map.getView().getProjection(),
        }),
      });
      layer = new VectorLayer({ source, style, zIndex: 850 });
      map.addLayer(layer);
    }
  }

  onDestroy(teardown);
</script>
