<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import type { PageData } from './$types';

  export let data: PageData;

  let query = '';
  let zone = '';

  $: zones = [...new Set(data.series.map((item) => item.zone).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b)
  );
  $: search = query.trim().toLocaleLowerCase();
  $: visibleSeries = data.series.filter(
    (item) =>
      (!zone || item.zone === zone) &&
      (!search ||
        [item.title, item.zone, item.scope, item.holdingInstitution, item.date]
          .join(' ')
          .toLocaleLowerCase()
          .includes(search))
  );

  const number = new Intl.NumberFormat('en');

  function scaleLabel(scale: number | null): string {
    return scale ? `1:${number.format(scale)}` : 'Scale unrecorded';
  }

  function checkedAtLabel(value: string): string {
    if (!value) return 'Date unrecorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
  }
</script>

<svelte:head>
  <title>CartoMundi index — Vietnam Map Archive</title>
  <meta
    name="description"
    content="CartoMundi map series that may cover Vietnam, with catalogue coverage and item-level license checks."
  />
</svelte:head>

<div class="page cartomundi-page">
  <PageHero
    eyebrow="External catalogue"
    title="CartoMundi index"
    sub="Map series that may cover Vietnam, including broader Indochina surveys."
  />

  <main class="editorial-main">
    <section class="section-card intro" aria-labelledby="index-about">
      <div class="section-card-header">
        <h2 id="index-about" class="section-title-sm">What this index shows</h2>
      </div>
      <p>
        This index includes series named for a Vietnam region and broader Indochina surveys that
        still need sheet-level coverage checks. It lists {number.format(data.summary.sheetRecords)}
        catalogue records across {number.format(data.summary.seriesCount)} series. CartoMundi's declared
        sheet counts and the number of returned records can differ; neither counts scans in Vietnam Map
        Archive.
      </p>
      <p>
        {number.format(data.summary.checkedItems)} linked scan items have an item-level license check,
        last checked {checkedAtLabel(data.summary.checkedAt)}. Their posted license is
        {data.summary.license}. A posted license does not establish that every right in the scan and
        underlying map has been cleared. Series with no checked items have no item-level rights
        result here.
      </p>
    </section>

    <section class="section-card" aria-labelledby="index-series">
      <div class="section-card-header">
        <h2 id="index-series" class="section-title-sm">Series</h2>
        <p>Open a series to inspect its catalogue details and checked scan records.</p>
      </div>

      <div class="controls">
        <div class="field">
          <label for="series-search">Search series</label>
          <input
            id="series-search"
            type="search"
            placeholder="Title, place, date, institution"
            bind:value={query}
          />
        </div>
        <div class="field">
          <label for="zone-filter">Catalogue region</label>
          <select id="zone-filter" bind:value={zone}>
            <option value="">All regions</option>
            {#each zones as option (option)}
              <option value={option}>{option}</option>
            {/each}
          </select>
        </div>
      </div>

      <p class="result-count" aria-live="polite">
        {number.format(visibleSeries.length)} of {number.format(data.series.length)} series
      </p>

      {#if visibleSeries.length}
        <ul class="series-list">
          {#each visibleSeries as item (item.id)}
            <li class="series-row">
              <div class="series-main">
                <h3><a href={`/catalog/cartomundi/${item.id}`}>{item.title}</a></h3>
                <p class="series-meta">
                  {item.zone}{#if item.scope}
                    · {item.scope}{/if} · {scaleLabel(item.scale)}
                  {#if item.date}
                    · {item.date}{/if}
                </p>
                {#if item.holdingInstitution}
                  <p class="institution">{item.holdingInstitution}</p>
                {/if}
                <a class="source-link" href={item.url} target="_blank" rel="noopener noreferrer">
                  CartoMundi source ↗
                </a>
              </div>
              <div class="counts">
                <span><strong>{number.format(item.cataloguedSheets)}</strong> sheets declared</span>
                <span
                  ><strong>{number.format(item.indexedRecords)}</strong> sheet records indexed</span
                >
                <span><strong>{number.format(item.checkedItems)}</strong> checked scan items</span>
              </div>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="empty">No series match this search.</p>
      {/if}
    </section>
  </main>
</div>

<style>
  .intro p {
    max-width: 72ch;
    margin: 0 0 var(--space-3);
  }
  .intro p:last-child {
    margin-bottom: 0;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }
  .field {
    display: grid;
    gap: var(--space-1);
    flex: 1 1 14rem;
  }
  .field:first-child {
    flex-grow: 2;
  }
  label {
    font-family: var(--font-family-display);
    font-weight: var(--font-semibold);
  }
  input,
  select {
    width: 100%;
    min-height: 2.75rem;
    padding: var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    background: var(--color-white);
    color: var(--color-text);
    font: inherit;
  }
  .result-count,
  .series-meta,
  .institution {
    color: var(--color-gray-500);
    font-size: 0.875rem;
  }
  .result-count {
    margin: 0 0 var(--space-2);
  }
  .series-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .series-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-4);
    padding: var(--space-4) 0;
    border-top: var(--border-thin);
  }
  .series-row h3 {
    margin: 0 0 var(--space-1);
    font-family: var(--font-family-display);
    font-size: 1.125rem;
  }
  .series-row a {
    color: var(--color-blue);
  }
  .series-meta,
  .institution {
    margin: 0;
  }
  .source-link {
    display: inline-block;
    margin-top: var(--space-1);
    font-size: 0.875rem;
  }
  .counts {
    display: grid;
    align-content: start;
    gap: var(--space-1);
    min-width: 10rem;
    font-size: 0.875rem;
    white-space: nowrap;
  }
  .counts strong {
    font-family: var(--font-family-display);
  }
  .empty {
    margin: var(--space-4) 0 0;
  }
  @media (max-width: 600px) {
    .series-row {
      grid-template-columns: 1fr;
      gap: var(--space-2);
    }
    .counts {
      min-width: 0;
    }
  }
</style>
