<!--
  HeroRegistration.svelte — the home page's thesis, running live.

  The characteristic act of this archive is REGISTRATION: a surveyed sheet from
  1898 laid onto the city as it stands, and made to line up. So the hero is not
  a picture of that — it is that, warped in the browser from the same IIIF tiles
  and the same Allmaps annotation every other page uses. The sheet breathes
  between nearly-transparent and nearly-opaque, and the modern street grid
  underneath appears and disappears through it.

  It bypasses layersStore on purpose: that store is the visitor's saved layer
  stack, and a hero has no business writing to it. MapShell's own stores are
  per-instance, and the warped layer is attached straight to the OL map.

  Non-interactive by design — the whole field is one link into /explore at the
  sheet it is showing.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type OlMap from 'ol/Map';
  import type { WarpedMapLayer } from '@allmaps/openlayers';

  import MapShell from '$lib/map/shell/MapShell.svelte';
  import { createGeoMapStores } from '$lib/map/shell/geoMapSetup';
  import {
    createWarpedLayer,
    destroyWarpedLayer,
    loadOverlayByUrl,
    setOverlayOpacity,
  } from '$lib/map/shell/warpedOverlay';
  import { resolveBounds } from '$lib/core/geo/mapBounds';
  import type { MapListItem } from '$lib/data/maps/types';

  /** The sheet to register. Must be georeferenced; the caller picks it. */
  export let map: MapListItem | null = null;

  const { mapStore, layerStore } = createGeoMapStores();

  let olMap: OlMap | null = null;
  let warped: WarpedMapLayer | null = null;
  let raf = 0;
  let loadedFor: string | null = null;

  /** Opacity floor and ceiling of the breath, and one full cycle in ms. */
  const LOW = 0.12;
  const HIGH = 0.88;
  const PERIOD = 14000;
  /** What a visitor who has asked for less motion sees instead: both, held. */
  const STILL = 0.6;

  $: source = map?.allmaps_id ?? map?.annotation_url ?? null;
  // Guarded, not a loop: register() sets loadedFor to the source it just took,
  // so the next run of this statement finds them equal and does nothing.
  $: if (olMap && source && source !== loadedFor) register(source);

  async function register(src: string) {
    if (!olMap || !map) return;
    loadedFor = src;

    const bounds = await resolveBounds(map);
    if (bounds && olMap) {
      olMap
        .getView()
        .fit(
          [
            ...([bounds[0], bounds[1]] as [number, number]),
            ...([bounds[2], bounds[3]] as [number, number]),
          ] as [number, number, number, number],
          { padding: [24, 24, 24, 24], duration: 0 }
        );
    }

    if (!warped) warped = createWarpedLayer(olMap, { zIndex: 10, name: 'hero' });
    await loadOverlayByUrl(warped, olMap, src, STILL);
    breathe();
  }

  function breathe() {
    if (!warped || !olMap) return;

    const reduced =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setOverlayOpacity(warped, olMap, STILL);
      return;
    }

    const t0 = performance.now();
    const tick = (t: number) => {
      if (!warped || !olMap) return;
      // Cosine, so it eases at both ends instead of snapping at the turn.
      const phase = (1 - Math.cos((2 * Math.PI * (t - t0)) / PERIOD)) / 2;
      setOverlayOpacity(warped, olMap, LOW + (HIGH - LOW) * phase);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
  }

  onMount(() => () => cancelAnimationFrame(raf));

  onDestroy(() => {
    cancelAnimationFrame(raf);
    if (warped) destroyWarpedLayer(warped);
    warped = null;
  });
</script>

<div class="hero">
  <MapShell {mapStore} {layerStore} disableUrlSync bind:map={olMap} />

  {#if map}
    <a class="hero__seal" href="/explore?map={map.id}">
      <span class="hero__year">{map.year ?? '—'}</span>
      <span class="hero__name">{map.name}</span>
      <span class="hero__go">Open in Explore →</span>
    </a>
  {/if}
</div>

<style>
  .hero {
    position: relative;
    height: clamp(320px, 58vh, 620px);
    overflow: hidden;
    background: var(--ground);
  }

  /* The map is the picture, not the control. Every gesture belongs to the page
     until the visitor follows the link. */
  .hero :global(.ol-viewport) {
    pointer-events: none;
  }

  .hero :global(.ol-control) {
    display: none;
  }

  /* Sits where a title cartouche sits on a real sheet: inside the neatline,
     bottom left, ruled off from the map. */
  .hero__seal {
    position: absolute;
    left: 0;
    bottom: 0;
    z-index: 2;

    display: grid;
    gap: 2px;
    padding: var(--s-3) var(--s-4);
    max-width: min(90%, 34ch);

    background: var(--ground);
    border-top: var(--rule-hair) solid var(--rule);
    border-right: var(--rule-hair) solid var(--rule);
    text-decoration: none;
  }

  .hero__year {
    font-family: var(--font-mono);
    font-size: var(--t-2xs);
    letter-spacing: 0.08em;
    color: var(--ink-soft);
  }

  .hero__name {
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-weight: var(--w-light);
    line-height: var(--leading-tight);
    color: var(--ink);
  }

  .hero__go {
    font-family: var(--font-mono);
    font-size: var(--t-2xs);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .hero__seal:hover .hero__go {
    text-decoration: underline;
  }
</style>
