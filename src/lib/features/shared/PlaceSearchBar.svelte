<!--
  PlaceSearchBar.svelte — the Nominatim place search: the field, its clear
  button, and the results list under it.

  It was inline in LayerControlsPanel until Sept 2026, when /explore's right
  rail wanted it at the top — mirroring the left rail, whose crown is also a
  search bar. The panel still renders one on mobile (`showSearch`), so the
  markup had to have one home rather than two.

  The bar itself is `.sb-search` (`$styles/components/sidebar.css`) — the same
  one `ArchiveFilters` wears on the left rail, so the two crowns match.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';

  type Pick = { lat: number; lng: number; label: string; bbox?: [number, number, number, number] };
  const dispatch = createEventDispatcher<{ pickLocation: Pick }>();

  /** Overrides the default. Blank takes the translated one below. */
  export let placeholder = '';

  // The field takes a typed position as well as a name — decimal, DMS, or the
  // `XS 8965 4123` grid off a US Army sheet. Nobody tries that unless the
  // placeholder says so, which is the whole reason this string changed.
  $: label = placeholder || $t('Search a place or coordinates…');

  let query = '';

  function onPick(e: CustomEvent<Pick>) {
    query = '';
    dispatch('pickLocation', e.detail);
  }
</script>

<div class="psb">
  <label class="sb-search">
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
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
      class="sb-search-input"
      type="search"
      placeholder={label}
      aria-label={label}
      bind:value={query}
    />
    {#if query}
      <button
        type="button"
        class="sb-search-clear"
        on:click={() => (query = '')}
        aria-label={$t('Clear')}>×</button
      >
    {/if}
  </label>
  {#if query}
    <LocationSearch {query} on:pickLocation={onPick} />
  {/if}
</div>

<style>
  .psb {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    min-width: 0;
  }
</style>
