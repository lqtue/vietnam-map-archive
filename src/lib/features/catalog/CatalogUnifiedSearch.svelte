<!--
  CatalogUnifiedSearch.svelte — the catalog page / sidebar view over the shared
  search engine (`$lib/features/shared/catalogSearch`). The engine owns the /api/search
  fetch, caching, facet tallying, and filtering; this component only renders.

  Inputs:
    searchQuery   — bind from parent's search box
    role          — 'user' | 'mod' | 'admin' (controls scout toggle visibility)
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import ArchiveFilters from '$lib/features/shared/ArchiveFilters.svelte';
  import CatalogTable from '$lib/features/catalog/CatalogTable.svelte';
  import MapCard from '$lib/ui/MapCard.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import { atWidth } from '$lib/core/iiif/thumbUrl';
  import { readJson, writeJson } from '$lib/core/utils/persistence/storage';
  import CatalogDetailDrawer from '$lib/features/catalog/CatalogDetailDrawer.svelte';
  import LabelHits from '$lib/features/shared/LabelHits.svelte';
  import { createEventDispatcher, onMount } from 'svelte';
  import { createCatalogSearch } from '$lib/features/shared/catalogSearch';

  export let searchQuery: string = '';
  export let role: 'user' | 'mod' | 'admin' = 'user';
  /** When true, row clicks dispatch `pick` instead of opening the detail drawer. */
  export let pickMode: boolean = false;
  /** Compact layout: no toolbar, no view switch, the table loses its extra columns. Suitable for narrow sidebars. */
  export let compact: boolean = false;
  /** Highlight this row as the currently-active map. */
  export let activeId: string | null = null;
  /** Restrict results to maps with georeferencing (excludes image-only entries). */
  export let requireGeoref: boolean = false;
  /** Show "+ overlay" and "B base" toggles on each row (only enabled in /view sidebar). */
  export let showLayerActions: boolean = false;
  /**
   * The surveys offerable as a filter, `{ value: maps.collection, label }`.
   * Only /catalog passes any — it is the only caller with a server load to ask
   * `map_series` which collections are surveys. See `ArchiveFilters`.
   */
  export let seriesChoices: { value: string; label: string }[] = [];
  /**
   * Bound out: true when nothing is narrowing the list — no query, no facet.
   *
   * /catalog reads it to decide whether to draw its series band. The band is a
   * browse surface for a reader who has not asked for anything yet; once they
   * have, it is three cards between them and their results. The page cannot
   * work this out for itself because the facets live in the engine this
   * component owns, and the query is only half the answer.
   */
  export let atRest: boolean = true;

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
    selected,
    toggleFacet,
    setSingle,
  } = search;

  // Mirror the parent's search box into the engine's query store.
  $: query.set(searchQuery);

  $: atRest = !$query.trim() && !Object.values($selected).some((v) => v?.length);

  onMount(() => {
    search.start();
    // ...and back, because the store is no longer a sink: `ArchiveFilters`'
    // Reset clears it, and without this the page's own field would keep showing
    // a query the results had already stopped answering to. The guard is what
    // stops the pair above and below from ringing.
    return query.subscribe((v) => {
      if (v !== searchQuery) searchQuery = v;
    });
  });

  let openedItem: any | null = null;

  /* List or grid. Two words of state, but the reader who wants pictures wants
     them every visit, so it is remembered. */
  const VIEW_KEY = 'vma-catalog-view-v1';
  $: VIEWS = [
    { key: 'list', label: $t('List') },
    { key: 'grid', label: $t('Grid') },
  ];
  let view: string = readJson<string>(VIEW_KEY, 'list');
  $: writeJson(VIEW_KEY, view);

  // ── Admin edit: the page owns MapEditModal (catalog UI must not import admin) ──
  /** Re-run the current query (call after an admin edit lands). */
  export function refresh() {
    openedItem = null;
    search.refresh();
  }

  /**
   * Narrow the list to one survey — what the series drawer's "Filter the
   * catalog" does. A method rather than a two-way binding on `selected`,
   * because the engine's state is this component's and the page should be able
   * to ask for a thing without holding the store that grants it.
   */
  export function filterSeries(collection: string) {
    setSingle('collection', collection);
  }

  function handleRowFacet(e: CustomEvent<{ group: string; value: string }>) {
    const { group, value } = e.detail;
    // Only the area chip is a filter. Other clicks (year, type, etc.) are no-ops.
    if (group !== 'area') return;
    toggleFacet('area', value);
  }

  $: activeAreas = $selected.area ?? [];
  // Type selections live under the `type` key — the same key the engine's
  // filter and the FacetRail use. (The compact <select> below previously wrote
  // `map_type`, which the filter never read, so it silently did nothing.)
  $: activeTypes = $selected.type ?? [];
</script>

<div class="cus" class:compact>
  <!-- The facets are the same disclosure /explore wears: a page with a left
       rail of chips put its filters in a column nobody scrolled back up to,
       and the rail cost the results a third of the page's width. /catalog
       gets a fourth control there, series; nothing else passes choices. -->
  <ArchiveFilters {search} showSearch={false} {seriesChoices} />

  {#if !compact}
    <div class="v2-toolbar">
      <span class="v2-count">
        {#if $includeScout}{$t('{N} in archive · {M} in scout queue', {
            N: $total.maps,
            M: $total.scout,
          })}{:else}{$t('{N} in archive', { N: $total.maps })}{/if}
        <!-- Drafts are in that count, because they are in the list under it.
             Saying so is the whole fix: a reader sees no drafts and no suffix,
             staff saw 153 called "in archive" while /about said 103. Gated on
             the number, not the role — the API decides which rows arrive. -->
        {#if $total.drafts}<span class="v2-drafts">{$t('· {N} drafts', { N: $total.drafts })}</span
          >{/if}
        {#if $loading}<span class="v2-loading">…</span>{/if}
      </span>
      <div class="v2-tools">
        {#if role === 'admin' || role === 'mod'}
          <label class="v2-scout-toggle">
            <input type="checkbox" bind:checked={$includeScout} />{$t('Include scout queue')}</label
          >
        {/if}
        <Tabs
          tabs={VIEWS}
          active={view}
          label={$t('Catalog view')}
          on:change={(e) => (view = e.detail.key)}
        />
      </div>
    </div>
  {/if}

  <LabelHits hits={$labels} />
  {#if $results.length === 0 && $labels.length === 0 && !$loading}
    <!-- `state-title`/`state-desc` carry no rule here; they are the hooks
         layouts/catalog.css uses for the two type sizes. The `state-panel`
         card around them is gone — see that file. -->
    <div class="empty-state is-block">
      <h2 class="state-title">{$t('Nothing matches.')}</h2>
      <p class="state-desc">{$t('Try another keyword, or clear a filter and start over.')}</p>
    </div>
  {:else if $results.length}
    {#if view === 'grid' && !compact}
      <!-- A card opens the same drawer a row does, so it carries no `href`:
           the grid is the list in another shape, not a different destination. -->
      <div class="cus-grid">
        {#each $results as item (item.id)}
          <MapCard
            map={item as any}
            href={null}
            thumbnail={atWidth(item.thumbnail, 400)}
            showSourceBadge
            on:open={(e) => (pickMode ? dispatch('pick', e.detail) : (openedItem = e.detail))}
          />
        {/each}
      </div>
    {:else}
      <CatalogTable
        items={$results as any}
        {compact}
        {activeId}
        {showLayerActions}
        on:open={(e) => (pickMode ? dispatch('pick', e.detail) : (openedItem = e.detail))}
        on:facet={handleRowFacet}
      />
    {/if}
  {/if}
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
  /* Top down, one column: filters, then what they filtered. The page was a
     260px facet rail beside the results until Sept 2026 — a column of chips
     that cost the table a third of the page and that nobody scrolled back up
     to touch. The facets are the `.sb-more` disclosure /explore already had. */
  .cus {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .cus.compact {
    gap: 0.5rem;
  }
  .cus.compact .v2-toolbar {
    font-size: 0.78rem;
    padding: 0.35rem 0.55rem;
  }
  .v2-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding: 0.5rem 0.75rem;
    background: var(--color-white);
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
    font-family: var(--font-family-base);
    font-size: 0.85rem;
  }
  .v2-tools {
    display: flex;
    align-items: center;
    gap: 0.9rem;
  }
  .v2-loading {
    margin-left: 0.4rem;
    opacity: 0.6;
  }
  .v2-drafts {
    margin-left: 0.3rem;
    opacity: 0.65;
  }
  .v2-scout-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-weight: var(--font-bold);
    cursor: pointer;
  }

  /* `MapCard` carries its own 3px border and 4px drop, so the track is sized
     for the card rather than the card padded to fill a track. */
  .cus-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1.5rem;
    padding: 0.25rem 0;
  }

  /* The heading keeps its display face; the muted body and the centred block
     come from `.empty-state.is-block`. */
  .state-title {
    font-family: var(--font-family-display);
    font-weight: var(--font-extrabold);
    font-size: 1.1rem;
    color: var(--color-text);
    margin: 0.5rem 0;
  }
</style>
