<!--
  HeroMap.svelte — the "how this works" demo: one georeferenced sheet laying
  itself over the city that replaced it, then the work done on top of it, one
  claim at a time.

  Everything here already existed for /explore. What is new is the sequencing
  and one rule: this uses its **own** map and layer stores, never the persisted
  globals, so a visit to the home page cannot rearrange the reader's /explore
  layer stack.

  It is **not** the front page's header any more. The header is two stills —
  `hero-now.webp` and `hero-1882.webp`, photographed out of this section by
  `scripts/gen-hero-still.mjs` and cross-faded by a slider, though they predate
  the refit below and hold the sheet closer than this does —
  and this plays further down, mounted by `HeroDemo.svelte` only once the
  reader scrolls it into view, so OpenLayers, ol-pmtiles, Allmaps and ~390 kB
  of basemap are never fetched by a visitor who does not reach it.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import type OlMap from 'ol/Map';
  import { transformExtent } from 'ol/proj';
  import { PUBLIC_SUPABASE_URL } from '$env/static/public';
  import { fade, fly } from 'svelte/transition';
  import MapShell from '$lib/map/shell/MapShell.svelte';
  import { setVisibleBasemap } from '$lib/map/shell/basemapLayers';
  import { createMapStore } from '$lib/map/stores/mapStore';
  import { createLayerStore } from '$lib/map/stores/layerStore';
  import FootprintsLayer from '$lib/features/shared/FootprintsLayer.svelte';
  import HeroSequence from '$lib/features/explore/HeroSequence.svelte';
  import {
    HERO_FOOTPRINTS,
    HERO_FOOTPRINT_COUNT,
    HERO_LABEL_COUNT,
  } from '$lib/features/explore/heroFabric';

  /** `maps.id` of the sheet to play. */
  export let mapId: string;
  /**
   * The mirrored annotation for `mapId`, not allmaps.org's copy: theirs still
   * points at archive.org, which 500s on the large tiles the warp asks for.
   * Derived rather than passed, so changing which sheet the hero plays is one
   * uuid on the home page.
   */
  $: source = `${PUBLIC_SUPABASE_URL}/storage/v1/object/public/annotations/${mapId}.json`;
  /**
   * What to frame: the sheet's own `maps.bbox` and the angle to hold it at.
   *
   * It was a pinned camera — a centre and a zoom on the Charner canal — which
   * meant the demo opened on a detail and the reader never saw what a sheet
   * is. The whole sheet, with a margin around it, is the subject; the frame
   * follows from the stage's size rather than from a zoom number that is only
   * right at one window width.
   *
   * `rotation` is still by hand: it lays the portrait sheet's long axis across
   * a landscape frame, and no bbox implies it.
   */
  export let view: { bbox: [number, number, number, number]; rotation: number };
  /**
   * Whether the four beats may start. The map mounts, fetches its tiles and
   * parses the annotation without waiting for this — that work is worth doing
   * before the reader arrives. The sequence is not: played off screen it is a
   * demonstration nobody sees, and what the reader scrolls into is the frame
   * the demonstration was supposed to arrive at. `HeroDemo` turns it on when
   * the stage is actually in the viewport.
   */
  export let play = true;

  /**
   * One line per beat, shown alone. They are claims about the archive, so the
   * two that quote numbers take them from the frozen fabric itself — they used
   * to be typed by hand, one regeneration away from lying.
   */
  export let captions: string[] = [
    'Hồ Chí Minh City, today',
    'Saigon, 1882 — laid over the ground it drew',
    `${HERO_FOOTPRINT_COUNT} plots and waterways, traced by hand`,
    `${HERO_LABEL_COUNT} names, read off the sheet and placed`,
  ];

  /** Longest the slider will ever wait, however the sequence goes. */
  const FAILSAFE_MS = 12000;

  let live = false;
  let stage = -1;
  /*
   * There was an `immediate` flag here, fed by `vma-hero-played-v1` in
   * sessionStorage, that composed the final frame at once on a revisit within
   * the same tab. Both are gone as of Sept 2026: the four beats are the
   * argument the front page is making, and a reader coming back to it — or
   * anyone reloading to look at the thing — was handed the conclusion with the
   * reasoning cut out. The sequence plays on every visit.
   *
   * `prefers-reduced-motion` still composes the frame at once. That check
   * lives in `HeroSequence`, which owns it, and is not this.
   */

  /**
   * Null until the reader moves the slider — see HeroSequence.overlayOpacity.
   * Bound by `HeroDemo`, which owns the slider.
   */
  export let overlayOpacity: number | null = null;
  /** True once the sequence has had its say, so the slider can appear. */
  export let settled = false;
  $: settled = stage >= captions.length;

  /** The one place `stage` moves. */
  function setStage(index: number) {
    // eslint-disable-next-line svelte/infinite-reactive-loop
    stage = index;
  }
  $: caption = stage >= 0 && stage < captions.length ? captions[stage] : null;

  /**
   * How much air to leave around the sheet, as a share of its own size on each
   * side — a share rather than a pixel inset, so it holds at every stage size,
   * and enough to read as a margin rather than a crop. `view.bbox` is already
   * the whole scan, so the paper's own blank edge is doing some of the work.
   */
  const FIT_PAD = 0.06;

  const mapStore = createMapStore({
    // A first guess only — `fitSheet` replaces it as soon as the map exists.
    // The stage is under the still image until then, so nobody sees it.
    lng: (view.bbox[0] + view.bbox[2]) / 2,
    lat: (view.bbox[1] + view.bbox[3]) / 2,
    // OL keeps basemap labels upright regardless of this, so the modern city
    // stays readable at any angle.
    rotation: view.rotation,
    zoom: 14,
  });
  /**
   * Satellite, not the vector streets. The streets style is deliberately quiet
   * — at this zoom it draws roads, water and nothing else — so the "today"
   * end of the fade was a pale diagram next to a hand-coloured survey, and the
   * comparison the whole hero exists to make had one side missing. Imagery is
   * the photograph the sheet is being checked against.
   *
   * `HeroMap` mounts no `LayerRenderer` (that one is driven by the persisted
   * `layersStore`, which a decorative map must not touch), and the layers come
   * out of `createBasemapLayers` with their construction-time visibility — so
   * the choice has to be applied to the map by hand, once it exists.
   */
  const BASEMAP = 'g-satellite';
  const layerStore = createLayerStore({ basemap: BASEMAP });

  let olMap: OlMap | null = null;
  $: if (olMap) setVisibleBasemap(olMap, BASEMAP);
  $: if (olMap) fitSheet(olMap);

  /**
   * True once OpenLayers has drawn a complete frame — every tile in view
   * fetched and painted, not merely "the map exists".
   *
   * `HeroDemo` retires its poster on this. The poster is a **close-up**, kept
   * deliberately for the header (see `HERO_1882` on the home page), while this
   * section was refitted to frame the whole sheet. So while it is up the reader
   * is looking at the same survey at roughly twice the size, behind a live map
   * that has not covered it yet — satellite in the patches whose tiles have
   * landed, enlarged 1882 sheet everywhere else. It used to stay there for good,
   * because nothing ever took it down.
   *
   * `rendercomplete` rather than a timer: it is the moment the map genuinely has
   * something to show, so a slow connection keeps its poster exactly as long as
   * it needs it. If it never fires — no WebGL, tiles refused, a metered reader
   * whose map was never fetched — the poster stays, which is the right answer
   * to all three.
   */
  export let painted = false;
  // Not a loop, on the same reasoning as the failsafe below: the block's only
  // dependencies are `olMap` and `watchingPaint`, and setting the latter closes
  // it. `once` unregisters itself, so a re-render cannot double-fire.
  let watchingPaint = false;
  $: if (olMap && !watchingPaint) {
    watchingPaint = true;
    olMap.once('rendercomplete', () => (painted = true));
  }

  /**
   * The whole sheet, with a margin, at the stage's own aspect ratio. `fit`
   * works in the view's rotated frame, so holding the sheet at an angle costs
   * nothing here.
   *
   * ponytail: fitted once, when the map appears. Not on resize — a refit would
   * also undo a reader who has panned or ⌘-zoomed, and the frame only has to
   * be right for the beats. Re-fit on `change:size` the day the stage becomes
   * resizable.
   */
  function fitSheet(m: OlMap) {
    const size = m.getSize();
    if (!size) return;
    const [minX, minY, maxX, maxY] = transformExtent(
      view.bbox,
      'EPSG:4326',
      m.getView().getProjection()
    );
    const padX = (maxX - minX) * FIT_PAD;
    const padY = (maxY - minY) * FIT_PAD;
    m.getView().fit([minX - padX, minY - padY, maxX + padX, maxY + padY], { duration: 0 });
  }

  onMount(() => {
    // Let the section paint before pulling in OpenLayers. `requestIdleCallback`
    // is Safari 18+, hence the timeout fallback.
    const idle =
      window.requestIdleCallback?.(() => (live = true), { timeout: 1200 }) ??
      window.setTimeout(() => (live = true), 400);

    return () => {
      if (window.cancelIdleCallback && typeof idle === 'number') window.cancelIdleCallback(idle);
      clearTimeout(idle as number);
    };
  });

  /**
   * The slider must arrive even when the sequence never does: an annotation
   * that 404s, WebGL refused, a tab woken from the back-forward cache.
   *
   * Armed on `play`, not on mount. On mount it fired 12 s after the page
   * loaded whether or not anyone had reached the section — which marked the
   * hero `settled` before anyone had scrolled to the section, so a reader who
   * left the front page open and then came down to it got the composed frame
   * and never saw the sequence at all.
   */
  let failsafe = 0;
  // Not a loop: the block's only dependencies are `play` and `failsafe`, and
  // setting `failsafe` is what closes it. The timer moves `stage`, which this
  // does not read.
  $: if (play && !failsafe) {
    failsafe = window.setTimeout(() => {
      // eslint-disable-next-line svelte/infinite-reactive-loop
      if (stage < captions.length) setStage(captions.length);
    }, FAILSAFE_MS);
  }
  onDestroy(() => clearTimeout(failsafe));
</script>

<div class="hero-map">
  {#if live}
    <!-- pixelRatio 1: at the screen's own ratio a Retina display asks for about
         four times the tiles, and this map is scenery, not a reading surface. -->
    <MapShell
      {mapStore}
      {layerStore}
      disableUrlSync
      pixelRatio={1}
      wheelZoom={false}
      bind:map={olMap}
    >
      <HeroSequence {source} {overlayOpacity} {play} on:stage={(e) => setStage(e.detail.index)} />
      <FootprintsLayer
        mapIds={stage >= 2 ? [mapId] : []}
        status="submitted"
        featureCollection={HERO_FOOTPRINTS}
      />
    </MapShell>
  {/if}

  <!-- One line at a time, and only a line: it used to be a link to /explore,
       which meant a click anywhere near the middle tore the page down
       mid-sequence. `aria-live` reads each as it lands, so a screen reader
       hears the same four claims a sighted reader watches. -->
  <div class="hero-caption" aria-live="polite">
    {#if caption}
      {#key caption}
        <p in:fly={{ y: 10, duration: 400 }} out:fade={{ duration: 200 }}>
          <span>{caption}</span>
        </p>
      {/key}
    {/if}
  </div>
</div>

<style>
  .hero-map {
    position: absolute;
    inset: 0;
    overflow: hidden;
    /* Deliberately transparent: `HeroDemo` puts the still frame underneath, so
       the section shows the finished picture until OL has tiles to paint. */
  }

  /* Along the bottom, where the fade slider appears once the beats are over —
     the two never coexist (`caption` is null exactly when `settled` is true),
     so they share the spot and neither covers the sheet the section exists to
     show. It was dead centre for a while, which put a pill over the middle of
     the map for four beats. The grid keeps each line in one place while the
     outgoing one fades under the incoming. */
  .hero-caption {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: end center;
    padding-bottom: 1rem;
    z-index: 3;
    pointer-events: none;
  }

  .hero-caption p {
    grid-area: 1 / 1;
    margin: 0;
  }

  .hero-caption span {
    display: inline-block;
    background: var(--color-white);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    padding: 0.4rem 0.9rem;
    font-family: var(--font-family-display);
    font-weight: 700;
    font-size: clamp(0.8rem, 1.3vw, 0.95rem);
    color: var(--color-text);
    text-decoration: none;
    white-space: nowrap;
  }

  /* A one-finger swipe has to scroll the page — without this the map swallows
     it and the reader is stuck in the section with no way past. `pan-y` lets
     the browser claim the gesture on the compositor, before OL sees a pointer
     event at all, which is why it beats rewriting DragPan's condition.

     The cost, measured rather than assumed: Chrome suppresses the pointer
     stream for the whole gesture, so on touch this map no longer pans by drag
     in any direction. That is the right trade for a demo — the reader needs to
     get past it far more than they need to pan it, and /explore is one tap
     away, where panning is the point. Desktop is untouched: mouse drag still
     pans, the wheel still scrolls the page. */
  .hero-map :global(.ol-viewport) {
    touch-action: pan-y;
  }

  @media (max-width: 640px) {
    .hero-caption span {
      font-size: 0.8rem;
      white-space: normal;
      text-align: center;
      max-width: 22ch;
    }
  }
</style>
