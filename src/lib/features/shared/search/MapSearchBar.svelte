<!--
  MapSearchBar.svelte — Reusable search trigger bar + SearchPanel wrapper.
  Positions both relative to a toolbar element (width-matching via ResizeObserver).
  Used in ViewMode, CreateMode, AnnotateMode, Studio.
-->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import SearchPanel from './SearchPanel.svelte';
  import type { MapListItem } from '$lib/data/maps/types';

  const dispatch = createEventDispatcher<{
    navigate: { result: import('$lib/map/types').SearchResult };
    selectMap: { map: MapListItem };
    addAsPoint: { result: import('$lib/map/types').SearchResult };
  }>();

  export let maps: MapListItem[] = [];
  export let selectedMapId: string | null = null;
  /** The toolbar element to match width against */
  export let toolbarEl: HTMLElement | null = null;
  /** When true, show 'Add as point' on location results */
  export let showAddAsPoint = false;
  /** When true, hide the Location tab — maps only */
  export let mapsOnly = false;
  /** When false, hide the layer-stack compare button (no geo map to stack onto). */
  export let showCompare = true;

  let searchOpen = false;
  let toolbarWidth = 0;
  let toolbarRo: ResizeObserver | null = null;

  $: if (toolbarEl && toolbarRo) {
    // Re-observe if element changes
    toolbarRo.disconnect();
    toolbarRo.observe(toolbarEl);
    toolbarWidth = toolbarEl.offsetWidth;
  }

  onMount(() => {
    toolbarRo = new ResizeObserver(() => {
      if (toolbarEl) toolbarWidth = toolbarEl.offsetWidth;
    });
    if (toolbarEl) toolbarRo.observe(toolbarEl);
  });

  onDestroy(() => {
    toolbarRo?.disconnect();
  });
</script>

<!-- Search Trigger Bar -->
<div
  class="top-search-bar"
  class:hidden={searchOpen}
  style:width={toolbarWidth ? `${toolbarWidth}px` : undefined}
>
  <button type="button" class="search-trigger" on:click={() => (searchOpen = true)}>
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
    <span class="search-trigger-text"
      >{mapsOnly ? 'Search maps…' : 'Search maps, places, coordinates...'}</span
    >
  </button>
</div>

<!-- Search Panel Anchor (positions SearchPanel to top center) -->
<div class="search-anchor" style:--toolbar-width={toolbarWidth ? `${toolbarWidth}px` : '320px'}>
  <SearchPanel
    open={searchOpen}
    {maps}
    {selectedMapId}
    {showAddAsPoint}
    {mapsOnly}
    {showCompare}
    on:close={() => (searchOpen = false)}
    on:navigate={(e) => {
      dispatch('navigate', e.detail);
    }}
    on:selectMap={(e) => {
      dispatch('selectMap', e.detail);
      searchOpen = false;
    }}
    on:addAsPoint={(e) => {
      dispatch('addAsPoint', e.detail);
    }}
  />
</div>

<style>
  /* ---------- Top Search Bar ---------- */
  .top-search-bar {
    position: absolute;
    top: 1rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 50;
    pointer-events: auto;
  }

  .top-search-bar.hidden {
    display: none;
  }

  .search-trigger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    width: 100%;
    min-width: 320px;
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius-pill);
    background: var(--ground-raised);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.1s;
  }

  .search-trigger:hover {
    background: var(--accent);
    transform: translate(-2px, -2px);
    box-shadow: var(--shadow-overlay);
  }

  .search-trigger:active {
    transform: translate(0, 0);
    box-shadow: 0 0 0 var(--rule);
  }

  .search-trigger svg {
    flex-shrink: 0;
    color: var(--ink);
  }

  .search-trigger-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
    flex: 1;
    opacity: 0.7;
  }

  /* ---------- Search Anchor ---------- */
  .search-anchor {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 100;
    pointer-events: none;
  }

  .search-anchor :global(.search-backdrop) {
    pointer-events: auto;
  }

  .search-anchor :global(.search-panel) {
    top: 1rem;
    left: 50%;
    right: auto;
    transform: translateX(-50%);
    pointer-events: auto;
    width: var(--toolbar-width);
    min-width: 320px;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius);
  }
</style>
