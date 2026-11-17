<script lang="ts">
  /**
   * WorkAreasLayer — outlines a sheet's work areas (workAreas.ts) on the
   * ImageShell canvas: squares to trace, and areas to leave alone. Draws
   * nothing for a sheet with no areas. `focus` (an area id, from `?area=`)
   * zooms to that square.
   */
  import { onDestroy } from 'svelte';
  import VectorLayer from 'ol/layer/Vector';
  import TileLayer from 'ol/layer/Tile';
  import type { CollectionEvent } from 'ol/Collection';
  import type BaseLayer from 'ol/layer/Base';
  import VectorSource from 'ol/source/Vector';
  import Feature from 'ol/Feature';
  import Polygon from 'ol/geom/Polygon';
  import Style from 'ol/style/Style';
  import Stroke from 'ol/style/Stroke';
  import Fill from 'ol/style/Fill';
  import Text from 'ol/style/Text';
  import { INK, inkAlpha } from '$lib/core/ink';
  import { toOlRing } from '$lib/core/geo/rectUtils';
  import { getImageShellStore } from '$lib/map/shell/imageContext';
  import type { ImageShellContext } from '$lib/map/shell/imageContext';
  import { WORK_AREAS } from './workAreas';
  import type { WorkArea, WorkAreaRole } from './workAreas';

  export let mapId: string;
  export let focus: string | null = null;

  const shellStore = getImageShellStore();
  const source = new VectorSource();
  const ROLE_INK: Record<WorkAreaRole, string> = {
    train: INK.plum,
    check: INK.green,
    'keep-out': INK.ink,
  };
  const ROLE_LABEL: Record<WorkAreaRole, string> = {
    train: 'train',
    check: 'check',
    'keep-out': 'no draw',
  };

  function areaStyle(feature: any): Style {
    const area = feature.get('area') as WorkArea;
    const ink = ROLE_INK[area.role];
    const keepOut = area.role === 'keep-out';
    return new Style({
      stroke: new Stroke({ color: ink, width: 3, lineDash: keepOut ? [10, 6] : undefined }),
      fill: new Fill({ color: inkAlpha(ink, keepOut ? 0.28 : 0) }),
      text: new Text({
        text: `${area.id} ${ROLE_LABEL[area.role]}`,
        font: '600 13px system-ui, sans-serif',
        fill: new Fill({ color: INK.paper }),
        backgroundFill: new Fill({ color: ink }),
        padding: [2, 4, 2, 4],
        overflow: true,
      }),
    });
  }

  const layer = new VectorLayer({ source, style: areaStyle, zIndex: 5 });
  let attachedTo: ImageShellContext | null = null;

  function attach(ctx: ImageShellContext | null) {
    if (!ctx || attachedTo === ctx) return;
    attachedTo = ctx;
    ctx.map.addLayer(layer);
  }

  function load(id: string) {
    source.clear();
    source.addFeatures(
      (WORK_AREAS[id] ?? []).map((area) => {
        const f = new Feature(new Polygon([toOlRing(...area.box)]));
        f.set('area', area);
        return f;
      })
    );
  }

  let zoomed: string | null = null;

  /**
   * Zoom to `?area=` once. ImageShell fits the whole sheet after its IIIF info
   * loads, which would undo an earlier fit, so wait for that first move to end.
   */
  function zoomTo(ctx: ImageShellContext | null, id: string | null) {
    if (!ctx || !id || zoomed === id) return;
    const area = (WORK_AREAS[mapId] ?? []).find((a) => a.id === id);
    if (!area) return;
    zoomed = id;
    const fit = () =>
      ctx.map.getView().fit(new Polygon([toOlRing(...area.box)]).getExtent(), {
        padding: [40, 40, 40, 40],
        duration: 350,
      });
    const layers = ctx.map.getLayers();
    if (layers.getArray().some((l) => l instanceof TileLayer)) return fit();
    const onAdd = (e: CollectionEvent<BaseLayer>) => {
      if (!(e.element instanceof TileLayer)) return;
      layers.un('add', onAdd);
      ctx.map.once('moveend', fit);
    };
    layers.on('add', onAdd);
  }

  $: attach($shellStore);
  $: load(mapId);
  $: zoomTo($shellStore, focus);

  onDestroy(() => {
    attachedTo?.map.removeLayer(layer);
  });
</script>
