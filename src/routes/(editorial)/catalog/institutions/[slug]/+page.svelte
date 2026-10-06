<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import DataTable from '$lib/ui/DataTable.svelte';
  import { t } from '$lib/core/i18n';
  import type { PageData } from './$types';

  export let data: PageData;
  let query = '';

  $: ({ institution, maps, series, cartomundi, outside } = data);
  $: search = query.trim().toLocaleLowerCase();
  $: shownSeries = series.map((s) => ({
    ...s,
    shown: s.items.filter((i) => matches(search, [i.sheet, i.title, i.year, i.edition])),
    withMap: s.items.filter((i) => i.maps.length).length,
    served: s.items.filter((i) => i.served).length,
  }));
  $: shownOutside = outside.filter((o) => matches(search, [o.series, o.title, o.scale, o.date]));

  function matches(search: string, text: (string | number | null)[]) {
    return !search || text.join(' ').toLocaleLowerCase().includes(search);
  }
  $: outsideSeries = [...new Set(shownOutside.map((o) => o.series))];
  $: itemCount = series.reduce((n, s) => n + s.items.length, 0);

  const itemColumns = [
    { key: 'sheet', label: 'Sheet' },
    { key: 'title', label: 'Title' },
    { key: 'year', label: 'Year', klass: 'num' },
    { key: 'edition', label: 'Edition' },
    { key: 'source', label: 'Source' },
    { key: 'archive', label: 'In the archive' },
  ];
  const outsideColumns = [
    { key: 'title', label: 'Title' },
    { key: 'scale', label: 'Scale' },
    { key: 'date', label: 'Date', klass: 'num' },
    { key: 'source', label: 'Source' },
  ];
</script>

<svelte:head>
  <title>{institution.name} — Vietnam Map Archive</title>
  <meta
    name="description"
    content={`Maps and source records from ${institution.name} in Vietnam Map Archive.`}
  />
</svelte:head>

<div class="page">
  <PageHero
    eyebrow={$t('Institution catalog')}
    title={institution.name}
    sub={institution.about ?? undefined}
  />
  <main class="editorial-main">
    <p class="summary">
      {maps.length}
      {$t('published maps')} · {itemCount}
      {$t('external source items')}
      {#if outside.length}· {outside.length} {$t('other holdings')}{/if}
      {#if institution.url}· <a href={institution.url} rel="external">{$t('Website')}</a>{/if}
      · <a href="/catalog/institutions">{$t('All institutions')}</a>
    </p>

    {#if itemCount || outside.length}
      <label for="holding-search">{$t('Filter by sheet, title or year')}</label>
      <input id="holding-search" class="sb-search" type="search" bind:value={query} />
    {/if}

    {#if maps.length}
      <section class="section-card" aria-labelledby="maps-title">
        <h2 id="maps-title" class="section-title-sm">{$t('Published maps')}</h2>
        <ul>
          {#each maps as map (map.id)}<li>
              <a href={`/catalog/${map.slug ?? map.id}`}>{map.name}</a>{#if map.year}
                · {map.year}{/if}
            </li>{/each}
        </ul>
      </section>
    {/if}

    {#if cartomundi.length}
      <section class="section-card" aria-labelledby="cartomundi-title">
        <h2 id="cartomundi-title" class="section-title-sm">{$t('CartoMundi series')}</h2>
        <ul>
          {#each cartomundi as series (series.id)}<li>
              <a href={`/catalog/cartomundi/${series.id}`}>{series.title}</a>
            </li>{/each}
        </ul>
      </section>
    {/if}

    {#each shownSeries as s (s.key)}
      <section class="section-card" aria-labelledby={`series-${s.key}`}>
        <div class="section-card-header">
          <h2 id={`series-${s.key}`} class="section-title-sm">
            <a href={`/catalog/series/${encodeURIComponent(s.key)}`}>{s.name}</a>
          </h2>
          <p>
            {s.items.length}
            {$t('source items')} · {s.withMap}
            {$t('sheets with a map in the archive')} · {s.served}
            {$t('scans served from this source')}
          </p>
        </div>
        <DataTable columns={itemColumns} klass="is-dense">
          {#each s.shown as item (item.id)}
            <tr>
              <td>{item.sheet}</td>
              <td>{item.title ?? ''}</td>
              <td class="num">{item.year ?? ''}</td>
              <td>{item.edition ?? ''}</td>
              <td
                >{#if item.url}<a href={item.url} rel="external">{$t('Open')}</a>{/if}</td
              >
              <td>
                <div class="in-archive">
                  {#each item.maps as map (map.slug)}
                    <a href={`/catalog/${map.slug}`}>{map.name}</a>
                  {/each}
                  {#if item.served}<span class="chip">{$t('served')}</span>{/if}
                </div>
              </td>
            </tr>
          {/each}
          <svelte:fragment slot="after">
            {#if !s.shown.length}<p class="table-empty">{$t('Nothing matches.')}</p>{/if}
          </svelte:fragment>
        </DataTable>
      </section>
    {/each}

    {#if outside.length}
      <section class="section-card" aria-labelledby="outside-title">
        <div class="section-card-header">
          <h2 id="outside-title" class="section-title-sm">{$t('Other holdings')}</h2>
          <p>
            {$t('Sheets in series the archive does not index yet, as the catalogue lists them on')}
            {data.outsideCheckedAt}.
          </p>
        </div>
        {#each outsideSeries as name (name)}
          <h3>{name}</h3>
          <DataTable columns={outsideColumns} klass="is-dense">
            {#each shownOutside.filter((o) => o.series === name) as o (o.productUrl)}
              <tr>
                <td>{o.title}</td>
                <td>{o.scale}</td>
                <td class="num">{o.date}</td>
                <td><a href={o.url} rel="external">{o.georeferenced ? 'GeoPDF' : 'PDF'}</a></td>
              </tr>
            {/each}
          </DataTable>
        {/each}
      </section>
    {/if}
  </main>
</div>

<style>
  main {
    display: grid;
    gap: var(--space-4);
  }
  label {
    font-weight: var(--font-semibold);
  }
  .summary {
    color: var(--color-gray-500);
  }
  ul {
    max-height: 24rem;
    overflow: auto;
  }
  li {
    margin: var(--space-1) 0;
  }
  h3 {
    font-size: 1rem;
    margin: var(--space-3) 0 var(--space-1);
  }
  a {
    color: var(--color-blue);
  }
  .in-archive {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
    align-items: center;
  }
</style>
