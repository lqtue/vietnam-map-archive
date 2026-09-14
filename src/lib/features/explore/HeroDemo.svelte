<!--
  HeroDemo.svelte — the "how this works" section on the front page.

  The animated hero used to *be* the header, which meant every visitor paid for
  OpenLayers, ol-pmtiles, Allmaps and ~390 kB of basemap to look at scenery.
  The header is now the still frame; this section is where the map actually
  plays, and it costs nothing until the reader scrolls it into view.

  Three gates, cheapest first:
    1. the still image is the section's own content — it renders with the page,
    2. `isMeteredConnection()` means the live map is never fetched at all,
    3. otherwise an IntersectionObserver fetches the chunk 400px early.

  **Loading early and playing early are not the same thing**, and they used to
  share one trigger. The chunk, the basemap tiles and the warped sheet are all
  worth fetching before the reader arrives — that is the whole point of the
  400px of lead. The four beats are not: on a laptop the stage was still below
  the fold while the sequence played to nobody, and the reader scrolled down
  into a composed frame having missed the sheet coming over the city, which is
  the one thing the section exists to show. So there are two observers now: one
  with the lead, for loading, and one at the real viewport edge, for playing.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { isMeteredConnection } from '$lib/core/utils/connection';

  /** `maps.id` of the sheet to play, and the frame it opens on. */
  export let mapId: string;
  /** The sheet's readable address, for the outbound link. Falls back to the uuid. */
  export let slug: string | null = null;
  /** The sheet's bbox and the angle to hold it at — passed straight to `HeroMap`. */
  export let view: { bbox: [number, number, number, number]; rotation: number };
  /** The still frame of the same sheet, used as the header image too. */
  export let still: string;
  /**
   * Its `srcset`. The header offers the same pair, so a phone that has already
   * fetched the 800px cut up there reuses it here — without this the poster
   * asks for the 1600 and the small header image was a saving on paper only.
   */
  export let stillSrcset: string | undefined = undefined;

  let HeroMap: typeof import('$lib/features/explore/HeroMap.svelte').default | null = null;
  let stage: HTMLElement;

  /**
   * True once the stage is genuinely on screen. The map mounts and warms its
   * tiles before this; only the beats wait for it.
   */
  let playing = false;

  /** The sheet's opacity once the reader takes the slider; null until then. */
  let overlayOpacity: number | null = null;
  /** True once the sequence has had its say. The slider waits for it. */
  let settled = false;

  onMount(() => {
    if (isMeteredConnection()) return;

    const load = () => {
      import('$lib/features/explore/HeroMap.svelte').then((m) => (HeroMap = m.default));
    };

    // 400px of lead, a fixed distance rather than a share of the viewport: at
    // `100%` the section already intersected on load on a laptop, which is the
    // whole cost this component exists to avoid.
    const preload = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        preload.disconnect();
        load();
      },
      { rootMargin: '400px 0px' }
    );

    // No lead at all, and a third of the stage rather than a single pixel of
    // it: the beats should start when the reader is looking at the section, not
    // when its top edge has just cleared the fold.
    const onScreen = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        onScreen.disconnect();
        playing = true;
      },
      { threshold: 0.35 }
    );

    preload.observe(stage);
    onScreen.observe(stage);
    return () => {
      preload.disconnect();
      onScreen.disconnect();
    };
  });
</script>

<!-- `home-section` is the page's own rhythm (the hairline above, the column
     gap inside); everything below it here is this section's own. -->
<section class="home-section hero-demo" id="how-it-works">
  <div class="hero-demo-head">
    <h2 class="feature-title">{$t('How this works')}</h2>
    <p class="feature-description">
      {$t(
        'A scan of an 1882 survey, pinned to real coordinates, laid back over the ground it drew — then the plots traced off it and the names read off it. Drag the slider to move between the two cities.'
      )}
    </p>
  </div>

  <div class="hero-demo-stage" bind:this={stage}>
    <!-- The poster is the header's still: the finished frame, but at the older
         pinned camera, since the header was left alone when the live map was
         refitted to the whole sheet. So the map arriving over it is a cut
         rather than a continuation. It is still what a metered reader keeps,
         and still the right shape. -->
    <img
      class="hero-demo-still"
      src={still}
      srcset={stillSrcset}
      sizes="100vw"
      alt={$t(
        'The 1882 cadastral survey of Saigon laid over the modern city around the Charner canal'
      )}
      width="1600"
      height="900"
      loading="lazy"
      decoding="async"
    />

    <svelte:component
      this={HeroMap}
      {mapId}
      {view}
      play={playing}
      bind:overlayOpacity
      bind:settled
    />

    {#if settled}
      <div class="hero-controls" transition:fade={{ duration: 400 }}>
        <label class="hero-fade">
          <span>{$t('Today')}</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={overlayOpacity ?? 0.88}
            on:input={(e) => (overlayOpacity = Number(e.currentTarget.value))}
            aria-label={$t('How much of the 1882 sheet to show')}
          />
          <span>1882</span>
        </label>
        <!-- Pointer-only: this map takes ⌘/Ctrl-wheel rather than the bare
             wheel, which would otherwise trap the page's scroll — an unusual
             gesture nobody guesses. On touch neither half is true, since
             `.ol-viewport` sets `touch-action: pan-y` so a swipe scrolls the
             page rather than panning the map. -->
        <p class="hero-hint">{$t('⌘ / Ctrl + scroll to zoom · drag to move')}</p>
      </div>
    {/if}
  </div>

  <p>
    <a href="/explore?map={slug ?? mapId}" class="text-link"
      >{$t('Open this sheet in the viewer')}</a
    >
  </p>
</section>

<style>
  .hero-demo-head {
    max-width: 62ch;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  /* 16:9, matching the still, so the section reserves its height before either
     the image or the map arrives — no shift when they do. */
  .hero-demo-stage {
    position: relative;
    aspect-ratio: 16 / 9;
    max-height: 70vh;
    overflow: hidden;
    border: var(--border-thick);
    border-radius: var(--radius-md);
    background: var(--color-bg);
  }

  .hero-demo-still {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  /* Bottom centre, under the sheet rather than over it — the slot the caption
     vacates when the beats end, which is exactly when this appears. It sat
     top-left on its own plate for a while, where it was the first thing over
     the map and the heaviest. The corners stay clear for OL's scale line and
     attribution. */
  .hero-controls {
    position: absolute;
    left: 50%;
    bottom: 1rem;
    transform: translateX(-50%);
    z-index: 4;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    max-width: calc(100% - 2rem);
  }

  .hero-fade {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    background: var(--color-white);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    font-family: var(--font-family-display);
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--color-text);
  }

  /* Its own plate, not a third item inside the pill: the pill is a control and
     this is a caption about one. Hidden where neither gesture exists. */
  .hero-hint {
    margin: 0;
    padding: 0.2rem 0.6rem;
    background: var(--color-white);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    font-size: 0.66rem;
    color: var(--color-gray-500);
    white-space: nowrap;
  }

  @media (hover: none), (pointer: coarse) {
    .hero-hint {
      display: none;
    }
  }

  .hero-fade input {
    width: 9rem;
    /* One line instead of a bespoke thumb: the platform's slider already has
       the keyboard behaviour and the hit target. */
    accent-color: var(--color-primary);
    cursor: pointer;
  }

  @media (max-width: 640px) {
    /* 16:9 on a 390px screen is a 190px band — the caption alone fills it and
       the map is a stripe. Taller than wide instead; the still is `cover`, so
       it crops rather than letterboxes. */
    .hero-demo-stage {
      aspect-ratio: 3 / 4;
    }

    .hero-fade input {
      width: 6rem;
    }
  }
</style>
