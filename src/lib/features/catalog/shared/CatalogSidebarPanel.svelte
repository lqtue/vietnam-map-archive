<!--
  CatalogSidebarPanel — single-search browse panel.
  One input drives both the catalog filter (by map title) and an inline
  "Places" suggestion list (Nominatim) above the table.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import CatalogUnifiedSearch from '../CatalogUnifiedSearch.svelte';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';

  export let role: 'user' | 'mod' | 'admin' = 'user';
  /** Show place-name suggestions (Nominatim). Disable on /scan. */
  export let showLocation: boolean = true;
  /** Highlight this row in the table. */
  export let activeId: string | null = null;
  /** Hide image-only entries. */
  export let requireGeoref: boolean = false;
  /** Show layer-action toggles (B / +) on each row. */
  export let showLayerActions: boolean = false;

  const dispatch = createEventDispatcher<{
    pick: any;
    pickLocation: {
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
    };
  }>();
  let searchQuery = '';
</script>

<div class="csp">
  <div class="csp-sticky">
    <label class="mo-search">
      <svg
        class="mo-search-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        class="mo-search-input"
        type="text"
        placeholder="Search maps…"
        bind:value={searchQuery}
      />
      {#if searchQuery}
        <button
          type="button"
          class="mo-search-clear"
          on:click={() => (searchQuery = '')}
          aria-label="Clear">×</button
        >
      {/if}
    </label>
  </div>

  {#if showLocation}
    <LocationSearch
      query={searchQuery}
      on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
    />
  {/if}

  <CatalogUnifiedSearch
    bind:searchQuery
    {role}
    {activeId}
    {requireGeoref}
    {showLayerActions}
    pickMode={true}
    compact={true}
    on:pick={(e) => dispatch('pick', e.detail)}
  />
</div>

<style>
  .csp {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.5rem 0.6rem 0.6rem;
  }
  .csp-sticky {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.2rem 0 0.4rem;
    background: var(--ground-raised);
  }
</style>
