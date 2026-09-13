<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { stepDown } from '$lib/core/iiif/thumbUrl';
  import type { MapListItem } from '$lib/data/maps/types';
  export let map: MapListItem;
  /** Full href for the card link. Caller builds it (home page adds &city=, catalog doesn't).
   *  Null makes the card a `<button>` that dispatches `open` instead — /catalog's
   *  grid opens the same detail drawer its table rows do, and a draft has no
   *  public page to link to. */
  export let href: string | null = null;
  /** Preloaded thumbnail URL; undefined shows the placeholder pattern. */
  export let thumbnail: string | undefined = undefined;
  /** Whether the heart button appears at all (only when a session exists). */
  export let showFavorite: boolean = false;
  /** Filled vs. empty heart state. */
  export let isFavorited: boolean = false;
  /** Show the collection/source badge (catalog uses it; home page omits it). */
  export let showSourceBadge: boolean = false;
  const dispatch = createEventDispatcher<{ toggleFavorite: string; open: MapListItem }>();

  /** The `thumbnail` prop is a width the caller asked for, and a width is not
   *  guaranteed to exist: the R2 worker renders nothing, so a sheet mirrored
   *  without that derivative and without a `sources/` proxy entry 404s it
   *  forever. 62 Indochine sheets are in exactly that state — only the `w,h`
   *  form vips wrote is stored, which is what `map.thumbnail` holds. Hiding the
   *  image outright made 56 published sheets invisible in /catalog's grid while
   *  the same rows drew fine in list view, which has always used `stepDown`. */
  let failedSrc: string | null = null;
  $: showPlaceholder = !thumbnail || failedSrc === thumbnail;

  function handleImageError(e: Event) {
    const img = e.currentTarget as HTMLImageElement;
    if (map.thumbnail && img.src !== map.thumbnail) {
      stepDown(e, map.thumbnail);
      return;
    }
    failedSrc = thumbnail ?? null;
  }

  function shortCollection(c: string | undefined): string {
    if (!c) return '';
    if (c.includes('BnF')) return 'BnF';
    if (c.includes('HumaZur')) return 'HumaZur';
    if (c.includes('UT Austin')) return 'UT Austin';
    if (c.includes('Internet Archive')) return 'IA';
    if (c.includes('Library of Congress')) return 'LOC';
    if (c.includes('MSU Vietnam')) return 'MSU';
    if (c === 'Wikimedia Commons') return 'Wikimedia';
    if (c.includes('Geographicus')) return 'Geographicus';
    if (c.includes('Virtual Saigon')) return 'Virtual Saigon';
    return c.split(',')[0].trim();
  }
</script>

<div class="map-card-wrapper">
  <!-- One card, two elements: a link where there is somewhere to go, a button
       where the click is an action on this page. Neither is the other wearing
       the wrong role. -->
  <svelte:element
    this={href ? 'a' : 'button'}
    href={href || undefined}
    type={href ? undefined : 'button'}
    role={href ? undefined : 'button'}
    class="map-card"
    on:click={() => !href && dispatch('open', map)}
  >
    <div class="map-thumbnail">
      {#if showPlaceholder}
        <div class="placeholder-pattern"></div>
      {:else}
        <img src={thumbnail} alt={map.name} loading="lazy" on:error={handleImageError} />
      {/if}
      <div class="map-badges">
        {#if map.year}
          <span class="badge-chip is-sm chip-green">{map.year}</span>
        {/if}
        {#if showSourceBadge && map.collection}
          <span class="badge-chip is-sm chip-orange">{shortCollection(map.collection)}</span>
        {/if}
      </div>
    </div>
    <div class="map-info">
      <h3 class="map-name">{map.name}</h3>
      {#if map.location}
        <span class="map-city">{map.location}</span>
      {/if}
    </div>
  </svelte:element>

  {#if showFavorite}
    <button
      class="btn is-icon fav-btn"
      on:click|stopPropagation={() => dispatch('toggleFavorite', map.id)}
      aria-label={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
    >
      <span class="notranslate">{isFavorited ? '❤️' : '🤍'}</span>
    </button>
  {/if}
</div>

<style>
  .map-card-wrapper {
    position: relative;
  }

  .map-card {
    display: flex;
    width: 100%;
    padding: 0;
    font: inherit;
    text-align: left;
    cursor: pointer;
    flex-direction: column;
    background: var(--color-white);
    border: var(--border-thick);
    border-radius: var(--radius-md);
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    box-shadow: var(--shadow-solid-sm);
    transition:
      transform 0.2s,
      box-shadow 0.2s;
    height: 100%;
  }

  .map-card:hover {
    transform: translate(-4px, -4px) rotate(-1deg);
    box-shadow: var(--shadow-solid-hover);
  }

  .map-card-wrapper:nth-child(even) .map-card:hover {
    transform: translate(-4px, -4px) rotate(1.5deg);
  }

  .map-thumbnail {
    position: relative;
    aspect-ratio: 4 / 3;
    background: var(--color-bg);
    border-bottom: var(--border-thick);
    overflow: hidden;
  }

  .map-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .placeholder-pattern {
    width: 100%;
    height: 100%;
    background-image: repeating-linear-gradient(
      45deg,
      var(--color-yellow) 0,
      var(--color-yellow) 10px,
      var(--color-white) 10px,
      var(--color-white) 20px
    );
  }

  .map-badges {
    position: absolute;
    bottom: 0.75rem;
    left: 0.75rem;
    display: flex;
    gap: 0.5rem;
  }

  .map-info {
    padding: 1.25rem;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
  }

  .map-name {
    font-family: var(--font-family-base);
    font-size: 1.125rem;
    font-weight: 800;
    margin: 0 0 0.5rem 0;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .map-city {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--color-gray-500);
    margin-top: auto;
  }

  /* Placement and size only — the round face, border and hover are `.btn.is-icon`.
     It hangs off the card's corner and is 44px, not the 48px map control. */
  .fav-btn {
    position: absolute;
    top: -10px;
    right: -10px;
    width: 44px;
    height: 44px;
    font-size: 1.5rem;
    z-index: 2;
  }
</style>
