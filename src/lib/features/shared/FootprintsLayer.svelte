<!--
  FootprintsLayer.svelte — the reviewed vector fabric of one or more maps,
  drawn on the ground over the modern basemap.

  Headless. Fetches `/api/export/footprints?map_id=<csv>` — approved polygons
  only, already warped server-side — and renders them coloured by feature type.
  Turning it on for two sheets from different decades is the point: the
  difference between them *is* the urban change.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import GeoJSON from 'ol/format/GeoJSON';
  import VectorSource from 'ol/source/Vector';
  import VectorLayer from 'ol/layer/Vector';
  import Style from 'ol/style/Style';
  import Fill from 'ol/style/Fill';
  import Stroke from 'ol/style/Stroke';
  import type { FeatureLike } from 'ol/Feature';
  import type Map from 'ol/Map';

  import { getShellContext } from '$lib/map/shell/context';
  import { featureTypeFill } from '$lib/data/maps/footprintTypes';

  /** Map ids whose fabric should be drawn. Empty means the layer sits idle. */
  export let mapIds: string[] = [];

  /**
   * Which review status to draw. `approved` is the only thing a reader should
   * be shown as finished work, so it stays the default; the home page passes
   * `submitted` deliberately and says so in its caption.
   */
  export let status: 'approved' | 'submitted' = 'approved';

  /**
   * A ready-made FeatureCollection to draw instead of asking the API. The home
   * page hero passes its one sheet's fabric from `heroFabric.ts`, which is the
   * same rows frozen at build time: it plays on every visit and the polygons
   * only move when somebody reviews one.
   */
  export let featureCollection: { features?: unknown[] } | null = null;

  const { map: mapWritable } = getShellContext();

  let olMap: Map | null = null;
  let source: VectorSource | null = null;
  let layer: VectorLayer<VectorSource> | null = null;
  let loadedKey = '';
  let loading = false;

  const styleFor = (f: FeatureLike) => {
    const type = String(f.get('feature_type') ?? 'other');
    return new Style({
      fill: new Fill({ color: featureTypeFill(type) }),
      stroke: new Stroke({ color: 'rgba(17, 17, 17, 0.55)', width: 1 }),
    });
  };

  onMount(() => {
    const unsub = mapWritable.subscribe((m) => {
      if (!m || olMap) return;
      olMap = m;
      source = new VectorSource();
      layer = new VectorLayer({ source, style: styleFor, zIndex: 55 });
      m.addLayer(layer);
      void load();
    });
    return unsub;
  });

  onDestroy(() => {
    if (olMap && layer) olMap.removeLayer(layer);
  });

  /**
   * ponytail: one request per set of ids, re-fetched whenever the set changes,
   * with no per-map cache. A sheet's fabric is a few hundred polygons and the
   * response is edge-cacheable; add a cache only if switching sheets feels slow.
   */
  async function load() {
    if (!source) return;
    const key = [...mapIds].sort().join(',');
    if (`${key}|${status}` === loadedKey) return;
    loadedKey = `${key}|${status}`;
    source.clear();
    if (!key) return;

    loading = true;
    try {
      // The frozen collection was filtered when it was generated, so it comes
      // through as it is; only a fetched one still needs the pass below.
      const fc = featureCollection ?? warpedOnly(await fetchCollection(key));
      if (!fc) return;
      if (loadedKey !== `${key}|${status}`) return; // a newer request won
      source.addFeatures(new GeoJSON().readFeatures(fc, { featureProjection: 'EPSG:3857' }));
    } catch {
      /* offline or a 500: an empty fabric is the honest result */
    } finally {
      loading = false;
    }
  }

  async function fetchCollection(key: string) {
    const res = await fetch(
      `/api/export/footprints?map_id=${encodeURIComponent(key)}&status=${status}`
    );
    return res.ok ? await res.json() : null;
  }

  /**
   * Rows that could not be warped carry pixel coordinates, not degrees; drawing
   * them would scatter garbage across the Gulf of Guinea.
   */
  function warpedOnly(fc: { features?: unknown[] } | null) {
    if (!fc) return null;
    return {
      ...fc,
      features: (fc.features ?? []).filter(
        (f) => (f as { properties?: { geo_converted?: boolean } }).properties?.geo_converted
      ),
    };
  }

  $: if (source && (mapIds || status)) void load();
</script>
