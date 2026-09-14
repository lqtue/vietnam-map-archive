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

  /** The search engine this bar drives. Created by the caller, because the
   *  point of the component is that several lists can share one. */
  export let search: CatalogSearchController;
  /** Draw the search box. /catalog turns it off: its own field is the page's
   *  `.sb-search.is-page`, at the top of the page above everything. */
  export let showSearch = true;
  /**
   * The surveys offerable as a filter, `{ value: maps.collection, label }`.
   *
   * Passed in rather than derived from the rows, because which collections are
   * surveys is `map_series`' decision and only a server load can ask it — so a
   * caller with no server load (the /explore rail, the /scan picker) passes
   * none and gets no series control, which is right: /explore has a series
   * rail of its own, one that puts the survey on the map.
   */
  export let seriesChoices: { value: string; label: string }[] = [];

  const { query, areaChoices, typeChoices, periodChoices, selected } = search;

  /** How many facets are set — the number on the summary. */
  $: activeFacets =
    ($selected.area?.length ? 1 : 0) +
    ($selected.type?.length ? 1 : 0) +
    ($selected.collection?.length ? 1 : 0) +
    ($selected.period?.length ? 1 : 0);

  $: hasFilters = !!$query.trim() || activeFacets > 0;

  function resetFilters() {
    query.set('');
    selected.set({});
  }
</script>

<div class="filters">
  {#if showSearch}
    <label class="sb-search">
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
      <input
        class="sb-search-input"
        type="search"
        placeholder={$t('Search maps…')}
        bind:value={$query}
      />
      {#if $query}
        <button
          type="button"
          class="sb-search-clear"
          on:click={() => query.set('')}
          aria-label={$t('Clear')}>×</button
        >
      {/if}
    </label>
  {/if}
  <details class="sb-more">
    <summary
      >Filters{#if activeFacets}
        · {activeFacets}{/if}</summary
    >
    <div class="dropdowns">
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
          value={$selected.collection?.[0] ?? ''}
          on:change={(e) =>
            search.setSingle('collection', (e.currentTarget as HTMLSelectElement).value)}
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
          on:change={(e) =>
            search.setSingle('period', (e.currentTarget as HTMLSelectElement).value)}
          aria-label="Filter by period"
        >
          <option value="">{$t('All periods')}</option>
          {#each $periodChoices as p (p.key)}
            <option value={p.key}>{$t(p.label)}</option>
          {/each}
        </select>
      {/if}
    </div>
  </details>
</div>

{#if hasFilters}
  <div class="reset-row">
    <button type="button" class="reset" on:click={resetFilters}>{$t('Reset filters')}</button>
  </div>
{/if}

<style>
  /* No `gap`: `.sb-more` brings its own vertical margin, and doubling the two
     is what separates the search box from the disclosure under it. */
  .filters {
    display: flex;
    flex-direction: column;
  }
  .dropdowns {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    padding-top: 0.3rem;
  }
  /* `max-width` because the same controls sit on a 1280px page as well as in a
     300px rail: without it each one grew to 400px of chrome around two words.
     The 110px basis is still what makes them wrap in the rail — and what lets
     the fourth one (series, /catalog only) wrap rather than squeeze the three
     beside it. */
  .dropdowns select {
    flex: 1 1 110px;
    max-width: 240px;
    padding: 0.35rem 0.45rem;
    font-family: inherit;
    font-size: 0.82rem;
    background: var(--sb-card-bg);
    border: var(--border-thin);
    border-radius: var(--sb-radius-sm);
    box-shadow: 1px 1px 0 var(--shadow-ink);
    cursor: pointer;
  }

  /* Its own row, so the link sits under the bar it resets whether or not the
     list beside it has a count to show. */
  .reset-row {
    display: flex;
    justify-content: flex-end;
  }
  .reset {
    background: transparent;
    border: none;
    padding: 0;
    font: inherit;
    font-size: 0.76rem;
    font-weight: var(--font-bold);
    color: var(--sb-accent);
    text-decoration: underline;
    cursor: pointer;
  }
</style>
