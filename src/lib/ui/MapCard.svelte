<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  export let map: MapListItem;
  /** Full href for the card link. Caller builds it (home page adds &city=, catalog doesn't). */
  export let href: string;
  /** Preloaded thumbnail URL; undefined shows the placeholder pattern. */
  export let thumbnail: string | undefined = undefined;
  /** Whether the heart button appears at all (only when a session exists). */
  export let showFavorite: boolean = false;
  /** Filled vs. empty heart state. */
  export let isFavorited: boolean = false;
  /** Show the collection/source badge (catalog uses it; home page omits it). */
  export let showSourceBadge: boolean = false;
  const dispatch = createEventDispatcher<{ toggleFavorite: string }>();

  function handleImageError(e: Event) {
    (e.target as HTMLImageElement).style.display = 'none';
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
  <a {href} class="map-card">
    <div class="map-thumbnail">
      {#if thumbnail}
        <img src={thumbnail} alt={map.name} loading="lazy" on:error={handleImageError} />
      {:else}
        <div class="placeholder-pattern"></div>
      {/if}
      <div class="map-badges">
        {#if map.year}
          <span class="badge year-badge">{map.year}</span>
        {/if}
        {#if showSourceBadge && map.collection}
          <span class="badge source-badge">{shortCollection(map.collection)}</span>
        {/if}
      </div>
    </div>
    <div class="map-info">
      <h3 class="map-name">{map.name}</h3>
      {#if map.location}
        <span class="map-city">{map.location}</span>
      {/if}
    </div>
  </a>

  {#if showFavorite}
    <button
      class="fav-btn"
      class:faved={isFavorited}
      on:click|stopPropagation={() => dispatch('toggleFavorite', map.id)}
      aria-label={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
    >
      <span class="notranslate" style="display:{isFavorited ? 'block' : 'none'}">❤️</span>
      <span class="notranslate" style="display:{isFavorited ? 'none' : 'block'}">🤍</span>
    </button>
  {/if}
</div>

<style>
  .map-card-wrapper {
    position: relative;
  }

  .map-card {
    display: flex;
    flex-direction: column;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius);
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    transition:
      transform 0.2s,
      box-shadow 0.2s;
    height: 100%;
  }

  .map-card:hover {
    transform: translate(-4px, -4px) rotate(-1deg);
    box-shadow: var(--shadow-overlay);
  }

  .map-card-wrapper:nth-child(even) .map-card:hover {
    transform: translate(-4px, -4px) rotate(1.5deg);
  }

  .map-thumbnail {
    position: relative;
    aspect-ratio: 4 / 3;
    background: var(--ground);
    border-bottom: var(--rule-thick) solid var(--rule);
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
      var(--accent) 0,
      var(--accent) 10px,
      var(--ground-raised) 10px,
      var(--ground-raised) 20px
    );
  }

  .map-badges {
    position: absolute;
    bottom: 0.75rem;
    left: 0.75rem;
    display: flex;
    gap: 0.5rem;
  }

  .badge {
    font-family: var(--font-display);
    font-size: 0.75rem;
    font-weight: 800;
    padding: 0.25rem 0.6rem;
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    box-shadow: 2px 2px 0px var(--rule);
  }

  .year-badge {
    background: var(--status-ok);
    color: var(--ink);
  }
  .source-badge {
    background: var(--status-warn);
    color: var(--ground-raised);
  }

  .map-info {
    padding: 1.25rem;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
  }

  .map-name {
    font-family: var(--font-body);
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
    color: var(--ink-soft);
    margin-top: auto;
  }

  .fav-btn {
    position: absolute;
    top: -10px;
    right: -10px;
    width: 44px;
    height: 44px;
    font-size: 1.5rem;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: 50%;
    cursor: pointer;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.1s;
  }

  .fav-btn:hover {
    transform: scale(1.1) rotate(10deg);
  }
  .fav-btn:active {
    transform: scale(0.95);
  }
</style>
