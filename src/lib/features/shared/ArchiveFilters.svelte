<!--
  ArchiveFilters.svelte — the search box, the facet dropdowns and the
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
  import Tabs from '$lib/ui/Tabs.svelte';
  import type { CatalogSearchController } from '$lib/features/shared/catalogSearch';

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

  /** Staff get the Type select; for a reader it is one value in 96% of rows, so it filters nothing. */
  export let staff = false;

  const { query, areaChoices, typeChoices, institutionChoices, yearBins, selected } = search;

  /** The caller that offers surveys also offers the Surveys / Plans switch — same reason. */
  $: hasKinds = seriesChoices.length > 0;
  $: kind = $selected.kind?.[0] ?? '';
  $: KINDS = [
    { key: '', label: $t('All maps') },
    { key: 'surveys', label: $t('Surveys') },
    { key: 'plans', label: $t('Plans & other') },
  ];
  /** Area is filled on the one-off plans and empty on survey sheets, so it belongs to that view. */
  $: showArea = $areaChoices.length > 0 && (!hasKinds || kind === 'plans');
  function setKind(k: string) {
    search.setSingle('kind', k);
    if (k !== 'plans') search.clearGroup('area');
  }

  $: [yFrom, yTo] = [$selected.year?.[0] ?? '', $selected.year?.[1] ?? ''];
  $: maxBin = Math.max(1, ...$yearBins.map((b) => b.count));
  function setYears(from: string, to: string) {
    selected.update((s) => ({ ...s, year: from || to ? [from, to] : [] }));
  }
  const inRange = (decade: number) =>
    (!yFrom || decade + 9 >= Number(yFrom)) && (!yTo || decade <= Number(yTo));

  /** How many facets are set — the number on the summary. */
  $: activeFacets =
    ($selected.area?.length ? 1 : 0) +
    ($selected.type?.length ? 1 : 0) +
    ($selected.series_key?.length ? 1 : 0) +
    ($selected.institution?.length ? 1 : 0) +
    ($selected.year?.length ? 1 : 0);

  $: hasFilters = !!$query.trim() || activeFacets > 0 || !!kind;

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
  {#if hasKinds}
    <div class="kinds">
      <Tabs
        tabs={KINDS}
        active={kind}
        label={$t('Kind of map')}
        on:change={(e) => setKind(e.detail.key)}
      />
    </div>
  {/if}
  <details class="sb-more">
    <summary
      >Filters{#if activeFacets}
        · {activeFacets}{/if}</summary
    >
    <div class="dropdowns">
      {#if showArea}
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
      {#if staff && $typeChoices.length}
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
      {#if $institutionChoices.length > 1}
        <select
          value={$selected.institution?.[0] ?? ''}
          on:change={(e) =>
            search.setSingle('institution', (e.currentTarget as HTMLSelectElement).value)}
          aria-label="Filter by institution"
        >
          <option value="">{$t('All institutions')}</option>
          {#each $institutionChoices as i (i)}
            <option value={i}>{i}</option>
          {/each}
        </select>
      {/if}
    </div>
    {#if $yearBins.length}
      <!-- A decade bar is a shortcut for the two boxes under it: click one for that decade, or
           type any span. The bars are counted against every other filter, so they say what is
           left, and drawn on a square-root scale — ~1,000 sheets are from the 1960s and a handful
           before, so a straight scale left every other decade a hairline. -->
      <div class="years">
        <div class="bars" role="group" aria-label={$t('Maps per decade')}>
          {#each $yearBins as b (b.decade)}
            <button
              type="button"
              class="bar"
              class:is-on={inRange(b.decade)}
              style="height: {b.count ? Math.max(8, Math.sqrt(b.count / maxBin) * 100) : 2}%"
              title="{b.decade}s · {b.count}"
              aria-label="{b.decade}s, {b.count}"
              on:click={() => setYears(String(b.decade), String(b.decade + 9))}
            ></button>
          {/each}
        </div>
        <div class="span">
          <label
            >{$t('From')}
            <input
              type="number"
              inputmode="numeric"
              placeholder={String($yearBins[0].decade)}
              value={yFrom}
              on:change={(e) => setYears(e.currentTarget.value, yTo)}
            /></label
          >
          <label
            >{$t('To')}
            <input
              type="number"
              inputmode="numeric"
              placeholder={String($yearBins[$yearBins.length - 1].decade + 9)}
              value={yTo}
              on:change={(e) => setYears(yFrom, e.currentTarget.value)}
            /></label
          >
        </div>
      </div>
    {/if}
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

  .kinds {
    padding-top: 0.2rem;
  }
  .years {
    padding-top: 0.5rem;
  }
  .bars {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 2.2rem;
  }
  .bar {
    flex: 1 1 0;
    min-width: 3px;
    padding: 0;
    border: none;
    background: color-mix(in srgb, var(--color-text) 22%, transparent);
    cursor: pointer;
  }
  .bar.is-on {
    background: var(--sb-accent);
  }
  .span {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.3rem;
    font-size: 0.78rem;
  }
  .span label {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
  .span input {
    width: 4.5rem;
    padding: 0.25rem 0.35rem;
    font: inherit;
    background: var(--sb-card-bg);
    border: var(--border-thin);
    border-radius: var(--sb-radius-sm);
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
