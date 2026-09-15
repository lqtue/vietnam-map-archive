<!--
  HeroDemo.svelte — the "how this works" section on the front page.

  The animated hero used to *be* the header, which meant every visitor paid for
  OpenLayers, ol-pmtiles, Allmaps and ~390 kB of basemap to look at scenery.
  The header is now the still frame; this section is where the map actually
  plays, and it costs nothing until the reader scrolls it into view.

  What plays by default is a **clip**, not the map. The section's claim is a
  sheet arriving over the city, and a reader who never got OpenLayers — metered,
  WebGL refused, gone before ~600 kB of map arrived — used to see one frozen
  frame of the end state and none of the movement. `scripts/gen-hero-video.mjs`
  records the real section, so the clip is the same four beats: 699 kB at
  1200px, 298 kB at 800px, against ~179 kB of JavaScript plus ~390 kB of basemap
  before OL draws a tile. Cheaper than what it stands in for, and it moves.

  The live map is the **upgrade**, behind a button, because the clip cannot do
  the two things the copy promises — the Today/1882 slider and ⌘-scroll zoom.
  Ask for it and the section is exactly what it was before.

  Four gates, cheapest first:
    1. the poster is the section's own content — it renders with the page,
       and it is frame 0 of the clip, so the two cannot disagree,
    2. `prefers-reduced-motion` or `isMeteredConnection()` stops at the poster,
    3. otherwise an IntersectionObserver fetches the clip 400px early,
    4. the live map is fetched only when the reader asks for it.

  **Loading early and playing early are not the same thing**, and they used to
  share one trigger. The bytes are worth fetching before the reader arrives —
  that is the whole point of the 400px of lead. The beats are not: on a laptop
  the stage was still below the fold while the sequence played to nobody, and
  the reader scrolled down into a composed frame having missed the sheet coming
  over the city, which is the one thing the section exists to show. So there are
  two observers: one with the lead, for loading, and one at the real viewport
  edge, for playing. The clip is held at frame 0 until the second one fires, for
  the same reason.
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
  /**
   * The clip, wide cut and phone cut, and the poster it opens on. All four come
   * out of `scripts/gen-hero-video.mjs` in one pass, so the poster is literally
   * the clip's first frame — which is what keeps the still and the moving
   * picture on the same camera. The header's own stills are a pinned close-up
   * kept on purpose and are deliberately not reused here.
   */
  export let video: string;
  export let videoSmall: string;
  export let poster: string;
  export let posterSrcset: string | undefined = undefined;

  let HeroMap: typeof import('$lib/features/explore/HeroMap.svelte').default | null = null;
  let stage: HTMLElement;
  let clip: HTMLVideoElement | undefined;

  /**
   * True once the stage is genuinely on screen. The clip is fetched and the map
   * warms its tiles before this; only the beats wait for it.
   */
  let playing = false;

  /**
   * True once the live map has drawn a complete frame. Until then the poster is
   * the only thing in the stage; after it, the poster is a second copy of the
   * same survey sitting behind a live one, so it goes. Same job as `rolling`
   * below, for the other of the two things that can fill the stage.
   */
  let painted = false;
  /** True once the clip has actually put a frame up. */
  let rolling = false;
  /** The chosen cut, once the section is near enough to be worth fetching. */
  let clipSrc = '';
  /** True once the reader has asked for the map the clip stands in for. */
  let wantsMap = false;
  /** The sheet's opacity once the reader takes the slider; null until then. */
  let overlayOpacity: number | null = null;
  /** True once the sequence has had its say. The slider waits for it. */
  let settled = false;

  /**
   * Start the clip once there is both a clip and a reason to.
   *
   * The two observers can fire in the same tick — a section already near the
   * fold on load intersects both — and then `playing` is set before Svelte has
   * rendered the `<video>` that `bind:this` fills, so calling `play()` from
   * inside the observer reached `undefined` and the poster sat there over a
   * loaded, paused clip. Here both are known.
   *
   * Muted, `playsinline`, and only after the reader has scrolled to it, so no
   * autoplay policy has anything to object to. A refusal is not worth
   * surfacing: the poster is already the composed frame.
   */
  $: if (playing && clip && !rolling) clip.play().catch(() => {});

  /** The live map, fetched only on the reader's say-so. */
  function openMap() {
    wantsMap = true;
    import('$lib/features/explore/HeroMap.svelte').then((m) => (HeroMap = m.default));
  }

  onMount(() => {
    // Both are reasons to stop at the poster: one is the reader's stated
    // preference, the other their data plan. Neither wants 300-700 kB of
    // scenery, and the poster is the composed frame either way.
    const still =
      isMeteredConnection() || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (still) return;

    // `<video>` has no `srcset`, so the cut is chosen here. The breakpoint is
    // the stage's own: below it the wide cut is pixels the screen cannot draw.
    const load = () => {
      clipSrc = window.innerWidth <= 800 ? videoSmall : video;
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
    <!-- Frame 0 of the clip, so the wait and the thing waited for are the same
         picture. It comes down once either the clip or the map has put a frame
         up; it used to stay for good, and since it was then the header's
         close-up while this section frames the whole sheet, that left an
         enlarged 1882 sheet behind a live map, showing through every patch
         whose basemap tile had not landed. -->
    {#if !rolling && !painted}
      <img
        class="hero-demo-still"
        src={poster}
        srcset={posterSrcset}
        sizes="100vw"
        alt={$t(
          'The 1882 cadastral survey of Saigon laid over the modern city around the Charner canal'
        )}
        width="1200"
        height="675"
        loading="lazy"
        decoding="async"
        out:fade={{ duration: 300 }}
      />
    {/if}

    <!-- Decorative: the captions burnt into it are the same four claims the
         paragraph above makes, so a screen reader that skips this has lost
         nothing. No `controls` — there is nothing to scrub, and the one real
         control is the button below, which fetches the map. -->
    {#if clipSrc && !wantsMap}
      <video
        class="hero-demo-clip"
        bind:this={clip}
        src={clipSrc}
        muted
        playsinline
        preload="auto"
        aria-hidden="true"
        on:playing={() => (rolling = true)}
      ></video>
    {/if}

    {#if wantsMap}
      <svelte:component
        this={HeroMap}
        {mapId}
        {view}
        play={playing}
        bind:overlayOpacity
        bind:settled
        bind:painted
      />
    {/if}

    <div class="hero-controls">
      {#if wantsMap && settled}
        <label class="hero-fade" transition:fade={{ duration: 400 }}>
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
      {:else if !wantsMap}
        <!-- The clip's whole cost is that it cannot be touched. This is where
             the reader buys that back, and it is the only thing on the page
             that fetches OpenLayers. -->
        <button class="btn" on:click={openMap}>{$t('Try it yourself')}</button>
      {/if}
    </div>
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

  /* The clip sits in the same box as the poster it opens on, so the handover
     is a cross-fade in place rather than a jump. `cover` on both, because the
     stage turns 3/4 on a phone while the recording stays 16:9. */
  .hero-demo-still,
  .hero-demo-clip {
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
    /* Empty between the clip ending and the reader asking for the map, and an
       empty flex column still takes its gap. */
    pointer-events: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    max-width: calc(100% - 2rem);
  }

  .hero-controls > * {
    pointer-events: auto;
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
