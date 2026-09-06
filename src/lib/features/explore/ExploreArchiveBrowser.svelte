<!--
  ExploreArchiveBrowser.svelte — the "Browse the full archive" branch of
  ExploreBrowsePanel.

  Driven by the shared catalog engine (`$lib/features/shared/catalogSearch`) — the same
  full-text search + facet logic that powers /archive — restricted to
  georeferenced maps since only those can overlay. Draft visibility is enforced
  server-side by role, so this doesn't need its own status filter.
-->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { createCatalogSearch, type LabelHit } from '$lib/features/shared/catalogSearch';
  import LabelHits from '$lib/features/shared/LabelHits.svelte';
  import ExploreMapRows from './ExploreMapRows.svelte';

  const dispatch = createEventDispatcher<{ pickLabel: LabelHit }>();

  /** Oldest → newest comparator, supplied by the parent so both modes sort alike. */
  export let sortRows: (a: any, b: any) => number;

  const search = createCatalogSearch({ requireGeoref: true });
  const { query, results, loading, areaChoices, typeChoices, periodChoices, selected, labels } =
    search;
  onMount(() => search.start());

  $: shownRows = [...$results].sort(sortRows);

  $: hasFilters =
    !!$query.trim() ||
    ($selected.area?.length ?? 0) > 0 ||
    ($selected.type?.length ?? 0) > 0 ||
    ($selected.period?.length ?? 0) > 0;

  function resetFilters() {
    query.set('');
    selected.set({});
  }
</script>

<div class="filters">
  <label class="search">
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      stroke-width="2.5"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
    <input type="text" placeholder="Search maps…" bind:value={$query} />
    {#if $query}
      <button type="button" class="clear" on:click={() => query.set('')} aria-label="Clear"
        >×</button
      >
    {/if}
  </label>
  <div class="dropdowns">
    {#if $areaChoices.length}
      <select
        value={$selected.area?.[0] ?? ''}
        on:change={(e) => search.setSingle('area', (e.currentTarget as HTMLSelectElement).value)}
        aria-label="Filter by area"
      >
        <option value="">All areas</option>
        {#each $areaChoices as a}
          <option value={a}>{a}</option>
        {/each}
      </select>
    {/if}
    {#if $typeChoices.length}
      <select
        value={$selected.type?.[0] ?? ''}
        on:change={(e) => search.setSingle('type', (e.currentTarget as HTMLSelectElement).value)}
        aria-label="Filter by map type"
      >
        <option value="">All types</option>
        {#each $typeChoices as t}
          <option value={t}>{t}</option>
        {/each}
      </select>
    {/if}
    {#if $periodChoices.length}
      <select
        value={$selected.period?.[0] ?? ''}
        on:change={(e) => search.setSingle('period', (e.currentTarget as HTMLSelectElement).value)}
        aria-label="Filter by period"
      >
        <option value="">All periods</option>
        {#each $periodChoices as p}
          <option value={p.key}>{p.label}</option>
        {/each}
      </select>
    {/if}
  </div>
</div>

<div class="count-row">
  <span class="count">
    {shownRows.length} map{shownRows.length === 1 ? '' : 's'}{#if $loading}<span class="loading">
        …</span
      >{/if}
  </span>
  {#if hasFilters}
    <button type="button" class="reset" on:click={resetFilters}>Reset filters</button>
  {/if}
</div>

<LabelHits hits={$labels} mode="pick" on:pick={(e) => dispatch('pickLabel', e.detail)} />

{#if shownRows.length}
  <ExploreMapRows rows={shownRows} on:pick on:remove />
{:else if !$labels.length}
  <p class="empty">No maps match those filters.</p>
{/if}

<style>
  .filters {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .search {
    flex: 1 1 160px;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.35rem var(--s-2);
    background: var(--sb-card-bg);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--sb-radius-sm);
    box-shadow: 1px 1px 0 var(--rule);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    font-family: inherit;
    font-size: 0.85rem;
  }
  .clear {
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1.05rem;
    color: var(--sb-text-meta);
    padding: 0 0.2rem;
  }
  .filters select {
    padding: 0.35rem 0.45rem;
    font-family: inherit;
    font-size: 0.82rem;
    background: var(--sb-card-bg);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--sb-radius-sm);
    box-shadow: 1px 1px 0 var(--rule);
    cursor: pointer;
  }

  .dropdowns {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .dropdowns select {
    flex: 1 1 110px;
  }

  .count-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-2);
  }
  .count {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--sb-text-meta);
  }
  .reset {
    background: transparent;
    border: none;
    padding: 0;
    font: inherit;
    font-size: 0.76rem;
    font-weight: var(--w-semi);
    color: var(--sb-accent);
    text-decoration: underline;
    cursor: pointer;
  }

  .empty {
    margin: 0.4rem 0;
    color: var(--sb-text-meta);
    font-size: 0.85rem;
    font-style: italic;
  }
</style>
