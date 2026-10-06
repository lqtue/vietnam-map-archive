<!--
  LegendTool.svelte — draws the legend work over the scan and reports clicks.
  Must be rendered as a child of <ImageShell>; it adds one vector layer to the
  shell's map and takes it away again, it never makes a map of its own.

  Everything is image pixels (OL y is -y). A click on a numeral candidate is
  `candidate`; a click anywhere else is `place`.

  Dispatches:
    place     { x, y, extra }       extra: Shift was held — one more point for the entry
    candidate { labelId, extra }
    pick      { n }                 a placed pin was clicked: select its row
    move      { n, index, x, y }    a pin was dragged; index -1 is the first point, else into `more`
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
  import Translate from 'ol/interaction/Translate';
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
    place: { x: number; y: number; extra: boolean };
    candidate: { labelId: string; extra: boolean };
    pick: { n: number };
    move: { n: number; index: number; x: number; y: number };
  }>();
  const shellStore = getImageShellStore();

  const source = new VectorSource();
  const layer = new VectorLayer({ source, zIndex: 8 });
  let map: OlMap | null = null;
  // Drag a placed pin to move it; candidates and the grid stay put.
  const translate = new Translate({
    layers: [layer],
    filter: (feature) => feature.get('kind') === 'placed',
  });
  translate.on('translateend', (event) => {
    const feature = event.features.item(0);
    const point = feature?.getGeometry() as Point | undefined;
    if (!feature || !point) return;
    const [x, y] = olPointToImage(point.getCoordinates());
    dispatch('move', {
      n: feature.get('n'),
      index: feature.get('index'),
      x: Math.round(x),
      y: Math.round(y),
    });
  });

  const CANDIDATE_INK = { true: INK.green, false: INK.red, null: INK.grey } as const;

  // Allmaps-style pin: a small dot, with the number beside it on a paper halo,
  // so a dense cluster stays readable where a number inside the dot would not.
  function pin(color: string, radius: number, n: number, selected: boolean): Style {
    return new Style({
      image: new CircleStyle({
        radius,
        fill: new Fill({ color }),
        stroke: new Stroke({ color: selected ? INK.yellow : INK.paper, width: selected ? 3 : 2 }),
      }),
      text: new Text({
        text: String(n),
        font: `bold ${selected ? 16 : 13}px sans-serif`,
        offsetX: radius + 4,
        offsetY: -radius - 2,
        textAlign: 'left',
        fill: new Fill({ color: INK.ink }),
        stroke: new Stroke({ color: INK.paper, width: 4 }),
      }),
      zIndex: selected ? 2 : 1,
    });
  }

  layer.setStyle((feature) => {
    const kind = feature.get('kind');
    const selected = feature.get('n') === selectedN;
    if (kind === 'placed') return pin(INK.blue, selected ? 7 : 5, feature.get('n'), selected);
    if (kind === 'candidate')
      return pin(
        CANDIDATE_INK[String(feature.get('inCell')) as 'true' | 'false' | 'null'],
        selected ? 7 : 4,
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
    on: { placed: boolean; candidates: boolean; grid: boolean },
    openN: number | null
  ) {
    const features: Feature[] = [];
    // A placed entry's detected numeral is spent — drawing both shows the number
    // twice — except for the open entry, whose *other* numerals stay clickable:
    // a number printed on a second plot is how it gets its extra point.
    const spent = (c: LegendCandidate) => {
      const row = placedRows.find((r) => r.n === c.n);
      if (!row || row.x == null || row.y == null) return false;
      if (c.n !== openN) return true;
      return [[row.x, row.y] as [number, number], ...row.more].some(
        ([x, y]) => Math.hypot(x - c.x, y - c.y) < 30
      );
    };
    for (const r of legendRects)
      features.push(
        new Feature({ kind: 'legend', geometry: new Polygon([toOlRing(r.x, r.y, r.w, r.h)]) })
      );
    if (on.grid && gridValue)
      features.push(
        new Feature({ kind: 'grid', geometry: new MultiLineString(gridLines(gridValue)) })
      );
    if (on.candidates)
      for (const c of cands.filter((k) => !spent(k)))
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
              index: -1,
              geometry: new Point(toOlPoint([row.x, row.y])),
            })
          );
    if (on.placed)
      for (const row of placedRows)
        if (row.x != null)
          row.more.forEach((p, index) =>
            features.push(
              new Feature({ kind: 'placed', n: row.n, index, geometry: new Point(toOlPoint(p)) })
            )
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
    const extra = (event.originalEvent as MouseEvent).shiftKey;
    if (hit) return dispatch('candidate', { labelId: hit.get('labelId'), extra });
    const pinned = event.map.forEachFeatureAtPixel(
      event.pixel,
      (feature) => (feature.get('kind') === 'placed' ? feature : undefined),
      { layerFilter: (l) => l === layer, hitTolerance: 6 }
    );
    if (pinned) return dispatch('pick', { n: pinned.get('n') });
    const [x, y] = olPointToImage(event.coordinate);
    dispatch('place', { x: Math.round(x), y: Math.round(y), extra });
  }

  const unsubscribe = shellStore.subscribe((ctx) => {
    if (ctx?.map === map) return;
    if (map) {
      map.un('singleclick', click);
      map.removeInteraction(translate);
      map.removeLayer(layer);
    }
    map = ctx?.map ?? null;
    if (map) {
      map.addLayer(layer);
      map.addInteraction(translate);
      map.on('singleclick', click);
    }
  });

  $: sync(
    placed,
    candidates,
    grid,
    rects,
    {
      placed: showPlaced,
      candidates: showCandidates,
      grid: showGrid,
    },
    selectedN
  );
  // Selecting an entry (a card, or its pin) brings its point to the middle,
  // zooming in only if the view is wider than 2 image px per screen px.
  function flyTo(n: number | null) {
    const row = n == null ? null : placed.find((r) => r.n === n);
    const view = map?.getView();
    if (!row || row.x == null || row.y == null || !view) return;
    view.animate({
      center: toOlPoint([row.x, row.y]),
      resolution: Math.min(view.getResolution() ?? 2, 2),
      duration: 300,
    });
  }
  $: flyTo(selectedN);
  // The selected pin is drawn bigger: redraw when the selection moves.
  $: {
    void selectedN;
    layer.changed();
  }

  onDestroy(() => {
    unsubscribe();
    if (map) {
      map.un('singleclick', click);
      map.removeInteraction(translate);
      map.removeLayer(layer);
    }
    source.clear();
  });
</script>
