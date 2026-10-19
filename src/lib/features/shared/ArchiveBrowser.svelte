<!--
  ArchiveBrowser.svelte — search box, three facet dropdowns, count and rows.

  Driven by the shared catalog engine (`$lib/features/shared/catalogSearch`) —
  the same full-text search + facet logic that powers /catalog. Draft visibility
  is enforced server-side by role, so this doesn't need its own status filter.

  It is the "Browse the full archive" branch of ExploreBrowsePanel and, since
  Sept 2026, the map picker in the /scan left rail — which is why it moved out
  of `features/explore/`. The /scan rail used to render `SearchMapsTab`, whose
  every rule is scoped under `.search-panel`: outside that container the list
  drew with no borders, no hover and titles at the inherited display size.

  It creates its own engine and renders its own filter bar by default. A caller
  that has to share either — /explore's left rail drives this list and its
  layer stack off one bar — passes `search` and `showFilters={false}`.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { writable } from 'svelte/store';
  import LoadError from '$lib/ui/LoadError.svelte';
  import {
    createCatalogSearch,
    type CatalogSearchController,
    type LabelHit,
  } from '$lib/features/shared/catalogSearch';
  import LabelHits from '$lib/features/shared/LabelHits.svelte';
  import ArchiveFilters from './ArchiveFilters.svelte';
  import ArchiveMapRows from './ArchiveMapRows.svelte';

  const dispatch = createEventDispatcher<{ pickLabel: LabelHit }>();

  /** Oldest → newest comparator, supplied by the parent so both modes sort alike. */
  export let sortRows: (a: any, b: any) => number;
  /** Only maps that can be laid on the world. False for /scan?mode=inspect,
   *  where an ungeoreferenced scan is exactly what is being looked at.
   *  Ignored when `search` is supplied — the engine already carries it. */
  export let requireGeoref = true;
  /** When set, only these ids are offered — the /scan?mode=shapes&tab=validate queue. */
  export let filterIds: string[] | null = null;
  /** Passed through to the rows; see `ArchiveMapRows`. */
  export let activeIds: string[] | null = null;
  export let badges: Record<string, string> = {};
  /** Label hits open /explore at a spot, which a /scan tool cannot do. */
  export let showLabels = true;
  /** An engine created by the caller, so several lists can share one filter
   *  bar. Null (the default) means this component owns its own. */
  export let search: CatalogSearchController | null = null;
  /** Render the filter bar. False for a caller that renders `ArchiveFilters`
   *  itself, above its own tabs. */
  export let showFilters = true;
  /** Filters the caller adds inside the filter disclosure, and how many are set. */
  export let extraActive = 0;
  /** The caller's own list has not arrived yet, so an empty result is not "no match". */
  export let waiting = false;

  const engine = search ?? createCatalogSearch({ requireGeoref });
  const { results, loading, labels, total, mapsError } = engine;
  const page = engine.pagination?.page ?? writable(1);
  const hasNext = engine.pagination?.hasNext ?? writable(false);
  // Idempotent: a shared engine has already been started by its owner.
  onMount(() => engine.start());
  onDestroy(() => {
    if (!search) engine.destroy?.();
  });

  $: allowed = filterIds ? new Set(filterIds) : null;
  $: matchingRows = allowed ? $results.filter((r) => allowed.has(r.id)) : [...$results];
  $: shownRows = engine.pagination ? matchingRows : [...matchingRows].sort(sortRows);
</script>

{#if showFilters}
  <ArchiveFilters search={engine} {extraActive}><slot name="filters" /></ArchiveFilters>
{/if}

<div class="count-row">
  <span class="count">
    {engine.pagination ? $total.maps : shownRows.length} map{(engine.pagination
      ? $total.maps
      : shownRows.length) === 1
      ? ''
      : 's'}{#if $loading}<span class="loading"> …</span>{/if}
  </span>
</div>

{#if showLabels}
  <LabelHits hits={$labels} mode="pick" on:pick={(e) => dispatch('pickLabel', e.detail)} />
{/if}

{#if $mapsError}
  <LoadError message={$t('Could not load maps.')} on:retry={() => engine.refresh()} />
{:else if shownRows.length}
  <ArchiveMapRows
    rows={shownRows}
    serverOrdered={!!engine.pagination}
    {activeIds}
    {badges}
    on:pick
    on:remove
  />
{:else if $loading || waiting}
  <p class="empty-state empty">{$t('Loading maps…')}</p>
{:else if !showLabels || !$labels.length}
  <p class="empty-state empty">{$t('No maps match those filters.')}</p>
{/if}

{#if engine.pagination && ($page > 1 || $hasNext)}
  <nav class="count-row" aria-label="Map result pages">
    <button
      type="button"
      class="btn is-sm"
      disabled={$loading || $page <= 1}
      on:click={() => engine.pagination?.previous()}>{$t('Previous')}</button
    >
    <span class="count" aria-live="polite">{$t('Page')} {$page}</span>
    <button
      type="button"
      class="btn is-sm"
      disabled={$loading || !$hasNext}
      on:click={() => engine.pagination?.next()}>{$t('Next')}</button
    >
  </nav>
{/if}

<style>
  .count-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .count {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--sb-text-meta);
  }

  /* Spacing only — the muted line itself is the shared `.empty-state`. */
  .empty {
    margin: 0.4rem 0;
  }
</style>
