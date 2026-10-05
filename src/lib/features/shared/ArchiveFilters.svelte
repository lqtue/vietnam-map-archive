<!--
  ArchiveFilters.svelte — the search box, the three facet dropdowns and the
  reset link that steer a catalog list.

  Extracted from `ArchiveBrowser` (Sept 2026) so one bar can steer more than
  one list: /explore's left rail renders it once above its two tabs and hands
  the same controller to the archive browser and to the layer stack. The
  browser still renders it itself by default, so its other callers — the /scan
  map picker among them — are untouched.

  The bar owns no state: everything it reads and writes lives on the
  `CatalogSearchController` the caller passes in.

  The facets sit inside one native `<details class="sb-more">` rather than
  abreast: at a 300px rail's width three selects each got a third of a line and
  read as three abbreviations. They stay separate controls — area AND type AND
  series AND period still combine — the disclosure just folds them out of the
  way, and its summary carries how many are set.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import type { CatalogSearchController } from '$lib/features/shared/catalogSearch';
  import FilterBar from './FilterBar.svelte';

  /** The search engine this bar drives. Created by the caller, because the
   *  point of the component is that several lists can share one. */
  export let search: CatalogSearchController;
  /** Draw the search box. /catalog turns it off: its own field is the page's
   *  `.sb-search.is-page`, at the top of the page above everything. */
  export let showSearch = true;
  /**
   * The surveys offerable as a filter, `{ value: maps.series_key, label }`.
   *
   * Passed in rather than derived from the rows, because which collections are
   * surveys is `map_series`' decision and only a server load can ask it — so a
   * caller with no server load (the /explore rail, the /scan picker) passes
   * none and gets no series control, which is right: /explore has a series
   * rail of its own, one that puts the survey on the map.
   */
  export let seriesChoices: { value: string; label: string }[] = [];

  /** Filters the caller adds inside the same disclosure (slot), counted on its summary. */
  export let extraActive = 0;

  const { query, areaChoices, typeChoices, periodChoices, selected } = search;

  /** How many facets are set — the number on the summary. */
  $: activeFacets =
    ($selected.area?.length ? 1 : 0) +
    ($selected.type?.length ? 1 : 0) +
    ($selected.series_key?.length ? 1 : 0) +
    ($selected.period?.length ? 1 : 0);

  $: hasFilters = !!$query.trim() || activeFacets > 0;

  function resetFilters() {
    query.set('');
    selected.set({});
  }
</script>

<FilterBar
  bind:query={$query}
  placeholder={$t('Search maps…')}
  active={activeFacets + extraActive}
  {showSearch}
  resettable={hasFilters}
  on:reset={resetFilters}
>
  {#if $areaChoices.length}
    <select
      value={$selected.area?.[0] ?? ''}
      on:change={(e) => search.setSingle('area', (e.currentTarget as HTMLSelectElement).value)}
      aria-label="Filter by area"
    >
      <option value="">{$t('All areas')}</option>
      {#each $areaChoices as a (a)}
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
      <option value="">{$t('All types')}</option>
      {#each $typeChoices as t (t)}
        <option value={t}>{t}</option>
      {/each}
    </select>
  {/if}
  {#if seriesChoices.length}
    <select
      value={$selected.series_key?.[0] ?? ''}
      on:change={(e) =>
        search.setSingle('series_key', (e.currentTarget as HTMLSelectElement).value)}
      aria-label="Filter by series"
    >
      <option value="">{$t('All series')}</option>
      {#each seriesChoices as s (s.value)}
        <option value={s.value}>{s.label}</option>
      {/each}
    </select>
  {/if}
  {#if $periodChoices.length}
    <select
      value={$selected.period?.[0] ?? ''}
      on:change={(e) => search.setSingle('period', (e.currentTarget as HTMLSelectElement).value)}
      aria-label="Filter by period"
    >
      <option value="">{$t('All periods')}</option>
      {#each $periodChoices as p (p.key)}
        <option value={p.key}>{$t(p.label)}</option>
      {/each}
    </select>
  {/if}
  <slot />
</FilterBar>
