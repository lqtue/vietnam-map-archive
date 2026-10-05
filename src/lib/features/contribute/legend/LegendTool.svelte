<!--
  LegendTool.svelte — draws the legend work over the scan and reports clicks.
  Must be rendered as a child of <ImageShell>; it adds one vector layer to the
  shell's map and takes it away again, it never makes a map of its own.

  Everything is image pixels (OL y is -y). A click on a numeral candidate is
  `candidate`; a click anywhere else is `place`.

  Dispatches:
    place     { x, y }
    candidate { labelId }
-->
<script lang="ts">
  import { onDestroy, createEventDispatcher } from 'svelte';
  import { INK, inkAlpha } from '$lib/core/ink';
  import Feature from 'ol/Feature';
  import Point from 'ol/geom/Point';
  import Polygon from 'ol/geom/Polygon';
  import MultiLineString from 'ol/geom/MultiLineString';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import CircleStyle from 'ol/style/Circle';
  import Text from 'ol/style/Text';
  import type OlMap from 'ol/Map';
  import type MapBrowserEvent from 'ol/MapBrowserEvent';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import { toOlPoint, toOlRing, olPointToImage } from '$lib/core/geo/rectUtils';
  import type { MapGrid } from '$lib/core/geo/mapGrid';
  import type { LegendCandidate, LegendRow } from './legendStage';

  export let placed: LegendRow[] = [];
  export let candidates: LegendCandidate[] = [];
  export let grid: MapGrid | null = null;
  export let rects: { x: number; y: number; w: number; h: number }[] = [];
  export let selectedN: number | null = null;
  export let showPlaced = true;
  export let showCandidates = true;
  export let showGrid = true;

  const dispatch = createEventDispatcher<{
    place: { x: number; y: number };
    candidate: { labelId: string };
  }>();
  const shellStore = getImageShellStore();

  const source = new VectorSource();
  const layer = new VectorLayer({ source, zIndex: 8 });
  let map: OlMap | null = null;

  const CANDIDATE_INK = { true: INK.green, false: INK.red, null: INK.grey } as const;

  function pin(color: string, radius: number, n: number, selected: boolean): Style {
    return new Style({
      image: new CircleStyle({
        radius,
        fill: new Fill({ color: inkAlpha(color, 0.85) }),
        stroke: new Stroke({ color: selected ? INK.yellow : INK.paper, width: selected ? 3 : 2 }),
      }),
      text: new Text({
        text: String(n),
        font: 'bold 11px sans-serif',
        fill: new Fill({ color: INK.paper }),
      }),
    });
  }

  layer.setStyle((feature) => {
    const kind = feature.get('kind');
    const selected = feature.get('n') === selectedN;
    if (kind === 'placed') return pin(INK.blue, selected ? 13 : 10, feature.get('n'), selected);
    if (kind === 'candidate')
      return pin(
        CANDIDATE_INK[String(feature.get('inCell')) as 'true' | 'false' | 'null'],
        selected ? 11 : 8,
        feature.get('n'),
        selected
      );
    if (kind === 'legend')
      return new Style({
        stroke: new Stroke({ color: INK.orange, width: 2, lineDash: [8, 6] }),
        fill: new Fill({ color: inkAlpha(INK.orange, 0.06) }),
      });
    return new Style({ stroke: new Stroke({ color: inkAlpha(INK.purple, 0.55), width: 1 }) });
  });

  function gridLines(g: MapGrid): number[][][] {
    const [x, y, w, h] = g.bbox;
    const lines: number[][][] = [];
    for (let i = 0; i <= g.columns.length; i++) {
      const gx = x + (w * i) / g.columns.length;
      lines.push([toOlPoint([gx, y]), toOlPoint([gx, y + h])]);
    }
    for (let i = 0; i <= g.rows.length; i++) {
      const gy = y + (h * i) / g.rows.length;
      lines.push([toOlPoint([x, gy]), toOlPoint([x + w, gy])]);
    }
    return lines;
  }

  function sync(
    placedRows: LegendRow[],
    cands: LegendCandidate[],
    gridValue: MapGrid | null,
    legendRects: typeof rects,
    on: { placed: boolean; candidates: boolean; grid: boolean }
  ) {
    const features: Feature[] = [];
    for (const r of legendRects)
      features.push(
        new Feature({ kind: 'legend', geometry: new Polygon([toOlRing(r.x, r.y, r.w, r.h)]) })
      );
    if (on.grid && gridValue)
      features.push(
        new Feature({ kind: 'grid', geometry: new MultiLineString(gridLines(gridValue)) })
      );
    if (on.candidates)
      for (const c of cands)
        features.push(
          new Feature({
            kind: 'candidate',
            n: c.n,
            inCell: c.inCell,
            labelId: c.labelId,
            geometry: new Point(toOlPoint([c.x, c.y])),
          })
        );
    if (on.placed)
      for (const row of placedRows)
        if (row.x != null && row.y != null)
          features.push(
            new Feature({
              kind: 'placed',
              n: row.n,
              geometry: new Point(toOlPoint([row.x, row.y])),
            })
          );
    source.clear();
    source.addFeatures(features);
  }

  function click(event: MapBrowserEvent) {
    const hit = event.map.forEachFeatureAtPixel(
      event.pixel,
      (feature) => (feature.get('kind') === 'candidate' ? feature : undefined),
      { layerFilter: (l) => l === layer, hitTolerance: 4 }
    );
    if (hit) return dispatch('candidate', { labelId: hit.get('labelId') });
    const [x, y] = olPointToImage(event.coordinate);
    dispatch('place', { x: Math.round(x), y: Math.round(y) });
  }

  const unsubscribe = shellStore.subscribe((ctx) => {
    if (ctx?.map === map) return;
    if (map) {
      map.un('singleclick', click);
      map.removeLayer(layer);
    }
    map = ctx?.map ?? null;
    if (map) {
      map.addLayer(layer);
      map.on('singleclick', click);
    }
  });

  $: sync(placed, candidates, grid, rects, {
    placed: showPlaced,
    candidates: showCandidates,
    grid: showGrid,
  });
  // The selected pin is drawn bigger: redraw when the selection moves.
  $: {
    void selectedN;
    layer.changed();
  }

  onDestroy(() => {
    unsubscribe();
    if (map) {
      map.un('singleclick', click);
      map.removeLayer(layer);
    }
    source.clear();
  });
</script>
