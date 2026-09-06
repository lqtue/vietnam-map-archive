<!--
  CatalogUnifiedSearch.svelte — the catalog page / sidebar view over the shared
  search engine (`$lib/features/shared/catalogSearch`). The engine owns the /api/search
  fetch, caching, facet tallying, and filtering; this component only renders.

  Inputs:
    searchQuery   — bind from parent's search box
    role          — 'user' | 'mod' | 'admin' (controls scout toggle visibility)
-->
<script lang="ts">
  import FacetRail from '$lib/ui/FacetRail.svelte';
  import CatalogTable from '$lib/features/catalog/CatalogTable.svelte';
  import CatalogDetailDrawer from '$lib/features/catalog/CatalogDetailDrawer.svelte';
  import LabelHits from '$lib/features/shared/LabelHits.svelte';
  import { createEventDispatcher, onMount } from 'svelte';
  import { createCatalogSearch } from '$lib/features/shared/catalogSearch';

  export let searchQuery: string = '';
  export let role: 'user' | 'mod' | 'admin' = 'user';
  /** When true, row clicks dispatch `pick` instead of opening the detail drawer. */
  export let pickMode: boolean = false;
  /** Compact layout: facet rail collapses to a chip strip, table loses extra cols. Suitable for narrow sidebars. */
  export let compact: boolean = false;
  /** Highlight this row as the currently-active map. */
  export let activeId: string | null = null;
  /** Restrict results to maps with georeferencing (excludes image-only entries). */
  export let requireGeoref: boolean = false;
  /** Show "+ overlay" and "B base" toggles on each row (only enabled in /view sidebar). */
  export let showLayerActions: boolean = false;

  const dispatch = createEventDispatcher<{ pick: any; edit: any }>();

  const search = createCatalogSearch({ requireGeoref });
  const {
    query,
    loading,
    periods,
    results,
    facets,
    total,
    areaChoices,
    typeChoices,
    includeScout,
    labels,
  } = search;

  // Mirror the parent's search box into the engine's query store.
  $: query.set(searchQuery);

  // Facet selection lives locally (FacetRail two-way binds it; the compact
  // selects mutate it); we push it into the engine which owns the filtering.
  let selected: Record<string, string[]> = {};
  $: search.selected.set(selected);

  onMount(() => search.start());

  let openedItem: any | null = null;

  // ── Admin edit: the page owns MapEditModal (catalog UI must not import admin) ──
  /** Re-run the current query (call after an admin edit lands). */
  export function refresh() {
    openedItem = null;
    search.refresh();
  }

  function handleRowFacet(e: CustomEvent<{ group: string; value: string }>) {
    const { group, value } = e.detail;
    // Only the area chip is a filter. Other clicks (year, type, etc.) are no-ops.
    if (group !== 'area') return;
    const cur = new Set(selected.area ?? []);
    if (cur.has(value)) cur.delete(value);
    else cur.add(value);
    selected = { ...selected, area: Array.from(cur) };
  }

  $: activeAreas = selected.area ?? [];
  // Type selections live under the `type` key — the same key the engine's
  // filter and the FacetRail use. (The compact <select> below previously wrote
  // `map_type`, which the filter never read, so it silently did nothing.)
  $: activeTypes = selected.type ?? [];
</script>

<div class="v2-layout" class:compact>
  {#if !compact}
    <FacetRail facets={$facets} periods={$periods} bind:selected showScoutFacets={$includeScout} />
  {/if}
  <div class="v2-results">
    {#if compact && ($areaChoices.length > 0 || $typeChoices.length > 0)}
      <div class="v2-selects">
        {#if $areaChoices.length > 0}
          <label class="v2-select">
            <span class="v2-select-label">Show maps of</span>
            <select
              value={activeAreas[0] ?? ''}
              on:change={(e) => {
                const v = (e.currentTarget as HTMLSelectElement).value;
                selected = { ...selected, area: v ? [v] : [] };
              }}
            >
              <option value="">All areas</option>
              {#each $areaChoices as a}
                <option value={a}>{a}</option>
              {/each}
            </select>
          </label>
        {/if}
        {#if $typeChoices.length > 0}
          <label class="v2-select">
            <span class="v2-select-label">Type</span>
            <select
              value={activeTypes[0] ?? ''}
              on:change={(e) => {
                const v = (e.currentTarget as HTMLSelectElement).value;
                selected = { ...selected, type: v ? [v] : [] };
              }}
            >
              <option value="">All types</option>
              {#each $typeChoices as t}
                <option value={t}>{t}</option>
              {/each}
            </select>
          </label>
        {/if}
      </div>
    {/if}
    {#if !compact}
      <div class="v2-toolbar">
        <span class="v2-count">
          <strong>{$total.maps}</strong> in archive
          {#if $includeScout}· <strong>{$total.scout}</strong> in scout queue{/if}
          {#if $loading}<span class="v2-loading">…</span>{/if}
        </span>
        {#if role === 'admin' || role === 'mod'}
          <label class="v2-scout-toggle">
            <input type="checkbox" bind:checked={$includeScout} />
            Include scout queue
          </label>
        {/if}
      </div>
    {/if}
    <LabelHits hits={$labels} />
    {#if $results.length === 0 && $labels.length === 0 && !$loading}
      <div class="state-panel">
        <div class="empty-emoji">🏜️</div>
        <h2 class="state-title">Nothing matches.</h2>
        <p class="state-desc">Try another keyword, or clear a filter and start over.</p>
      </div>
    {:else if $results.length}
      <CatalogTable
        items={$results as any}
        {compact}
        {activeId}
        {showLayerActions}
        on:open={(e) => (pickMode ? dispatch('pick', e.detail) : (openedItem = e.detail))}
        on:facet={handleRowFacet}
      />
    {/if}
  </div>
</div>

{#if !pickMode}
  <CatalogDetailDrawer
    item={openedItem}
    {role}
    on:close={() => (openedItem = null)}
    on:edit={(e) => dispatch('edit', e.detail)}
  />
{/if}

<style>
  .v2-layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 1.25rem;
    align-items: start;
  }
  .v2-layout.compact {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  .v2-layout.compact .v2-toolbar {
    font-size: 0.78rem;
    padding: 0.35rem 0.55rem;
  }
  .v2-results {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .v2-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--ground-raised);
    border: 1.5px solid var(--rule);
    border-radius: var(--sb-radius-sm);
    font-family: var(--font-body);
    font-size: 0.85rem;
  }
  .v2-count strong {
    font-weight: var(--w-semi);
  }
  .v2-loading {
    margin-left: 0.4rem;
    opacity: 0.6;
  }
  .v2-scout-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-weight: var(--w-semi);
    cursor: pointer;
  }
  .v2-selects {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-family: var(--font-body);
  }
  .v2-select {
    flex: 1 1 140px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .v2-select-label {
    font-family: var(--font-display);
    font-size: 0.62rem;
    font-weight: var(--w-semi);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--sb-text-meta);
  }
  .v2-select select {
    width: 100%;
    min-height: 38px;
    padding: 0.35rem 0.55rem;
    background: var(--ground-raised);
    border: 1.5px solid var(--rule);
    border-radius: var(--sb-radius-sm);
    font: inherit;
    font-family: var(--font-body);
    font-size: 0.85rem;
    font-weight: var(--w-semi);
    color: var(--ink);
    cursor: pointer;
  }

  .state-panel {
    text-align: center;
    padding: 3rem 1rem;
  }
  .empty-emoji {
    font-size: 3rem;
  }
  .state-title {
    font-family: var(--font-display);
    font-weight: var(--w-semi);
    margin: 0.5rem 0;
  }
  .state-desc {
    color: var(--sb-text-meta);
  }
  @media (max-width: 900px) {
    .v2-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
