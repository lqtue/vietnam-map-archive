<!--
  StoryMarkers.svelte — numbered point markers for story playback.

  Headless: creates an OL vector layer of styled point features.
    • `revealUpTo`  — render only the first N points (reveal-as-you-go on /trip);
                      null renders all of them (/explore?mode=story editor + /explore).
    • `showTrail`   — draw a dashed line through the revealed points.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Feature from 'ol/Feature';
  import Point from 'ol/geom/Point';
  import LineString from 'ol/geom/LineString';
  import VectorSource from 'ol/source/Vector';
  import VectorImageLayer from 'ol/layer/VectorImage';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import CircleStyle from 'ol/style/Circle';
  import Text from 'ol/style/Text';
  import { fromLonLat } from 'ol/proj';
  import type Map from 'ol/Map';

  import type { StoryPoint } from '$lib/features/stories/shared/types';
  import { markerPalette } from '$lib/features/stories/shared/markerPalette';
  import { getShellContext } from '$lib/map/shell/context';

  export let points: StoryPoint[] = [];
  export let currentIndex = 0;
  export let completedIds: Set<string> = new Set();
  /** Render only the first N points. null = all. */
  export let revealUpTo: number | null = null;
  export let showTrail = false;

  const { map: mapWritable } = getShellContext();

  let olMap: Map | null = null;
  let source: VectorSource | null = null;
  let layer: VectorImageLayer<VectorSource> | null = null;
  let trailSource: VectorSource | null = null;
  let trailLayer: VectorImageLayer<VectorSource> | null = null;

  function styleFor(index: number): Style {
    const p = markerPalette();
    const isDone = completedIds.has(points[index]?.id ?? '');
    const isCurrent = index === currentIndex && !isDone;
    return new Style({
      image: new CircleStyle({
        radius: isCurrent ? 16 : 12,
        fill: new Fill({ color: isDone ? p.done : isCurrent ? p.current : p.pending }),
        stroke: new Stroke({ color: p.border, width: 2 }),
      }),
      text: new Text({
        text: isDone ? '✓' : String(index + 1),
        font: `800 ${isCurrent ? 13 : 11}px ${p.font}`,
        fill: new Fill({ color: p.label }),
      }),
      zIndex: isCurrent ? 10 : 1,
    });
  }

  function sync() {
    if (!source) return;
    source.clear();
    trailSource?.clear();

    const visible = revealUpTo === null ? points : points.slice(0, Math.max(0, revealUpTo));
    const coords: number[][] = [];

    for (let i = 0; i < visible.length; i++) {
      const pt = visible[i];
      if (!pt.coordinates) continue;
      const c = fromLonLat(pt.coordinates);
      coords.push(c);
      const f = new Feature({ geometry: new Point(c) });
      f.setId(`story-pt-${i}`);
      f.setStyle(styleFor(i));
      source.addFeature(f);
    }

    if (showTrail && trailSource && coords.length >= 2) {
      const line = new Feature({ geometry: new LineString(coords) });
      line.setStyle(
        new Style({
          stroke: new Stroke({
            color: markerPalette().pending,
            width: 3,
            lineDash: [4, 6],
            lineCap: 'round',
          }),
        })
      );
      trailSource.addFeature(line);
    }
  }

  $: deps = [points, currentIndex, completedIds, revealUpTo, showTrail];
  $: if (source && deps) sync();

  onMount(() => {
    const unsub = mapWritable.subscribe(($map) => {
      if (!$map || olMap) return;
      olMap = $map;

      trailSource = new VectorSource();
      trailLayer = new VectorImageLayer({ source: trailSource, zIndex: 28 });
      source = new VectorSource();
      layer = new VectorImageLayer({ source, zIndex: 30 });

      olMap.addLayer(trailLayer);
      olMap.addLayer(layer);
      sync();
    });

    return () => {
      unsub();
    };
  });

  onDestroy(() => {
    if (olMap) {
      if (layer) olMap.removeLayer(layer);
      if (trailLayer) olMap.removeLayer(trailLayer);
    }
  });
</script>
