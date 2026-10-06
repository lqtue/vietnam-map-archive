<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import { t } from '$lib/core/i18n';
  import type { PageData } from './$types';

  export let data: PageData;
  let query = '';
  $: search = query.trim().toLocaleLowerCase();
  $: institutions = data.institutions.filter((item) =>
    [
      item.name,
      ...item.maps.map((map) => map.name),
      ...item.series.map((series) => series.name),
      ...item.cartomundiSeries.map((series) => series.title),
    ]
      .join(' ')
      .toLocaleLowerCase()
      .includes(search)
  );
  $: platforms = data.platforms.filter((item) =>
    [item.name, ...item.maps.map((map) => map.name)].join(' ').toLocaleLowerCase().includes(search)
  );
</script>

<svelte:head>
  <title>Institution catalog — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Holding institutions and source platforms represented in Vietnam Map Archive, with links to maps and external survey records."
  />
</svelte:head>

<div class="page">
  <PageHero
    eyebrow="Sources"
    title={$t('Institution catalog')}
    sub={$t('Libraries, archives and source platforms represented in our records.')}
  />
  <main class="editorial-main">
    <label for="institution-search">{$t('Search institutions and sources')}</label>
    <input id="institution-search" class="sb-search" type="search" bind:value={query} />

    <section class="section-card" aria-labelledby="holding-title">
      <div class="section-card-header">
        <h2 id="holding-title" class="section-title-sm">{$t('Holding institutions')}</h2>
        <p>
          {$t(
            'Published maps and external source records are counted separately. Open an institution to browse its records.'
          )}
        </p>
      </div>
      {#each institutions as institution (institution.name)}
        <details>
          <summary
            ><strong>{institution.name}</strong><span
              >{institution.maps.length}
              {$t('published maps')} · {institution.sourceItems}
              {$t('external source items')} · {institution.cartomundiSeries.length}
              {$t('CartoMundi series')}</span
            ></summary
          >
          {#if institution.maps.length}
            <h3>{$t('Published maps')}</h3>
            <ul>
              {#each institution.maps as map (map.id)}<li>
                  <a href={`/catalog/${map.slug ?? map.id}`}>{map.name}</a>{#if map.year}
                    · {map.year}{/if}
                </li>{/each}
            </ul>
          {/if}
          {#if institution.series.length}
            <h3>{$t('External source records')}</h3>
            <ul>
              {#each institution.series as series (series.key)}<li>
                  <a href={`/catalog/series/${encodeURIComponent(series.key)}`}>{series.name}</a>
                </li>{/each}
            </ul>
          {/if}
          {#if institution.cartomundiSeries.length}
            <h3>{$t('CartoMundi series')}</h3>
            <ul>
              {#each institution.cartomundiSeries as series (series.id)}<li>
                  <a href={`/catalog/cartomundi/${series.id}`}>{series.title}</a>
                </li>{/each}
            </ul>
          {/if}
        </details>
      {:else}
        <p>{$t('No institutions match this search.')}</p>
      {/each}
    </section>

    <section class="section-card" aria-labelledby="platform-title">
      <div class="section-card-header">
        <h2 id="platform-title" class="section-title-sm">{$t('Source platforms')}</h2>
        <p>
          {$t(
            'Platforms provide catalogue access or scans; the holding institution is credited separately.'
          )}
        </p>
      </div>
      {#each platforms as platform (platform.name)}
        <details>
          <summary
            ><strong>{platform.name}</strong><span
              >{platform.maps.length} {$t('published maps')}</span
            ></summary
          >
          {#if platform.name === 'CartoMundi'}
            <p>
              {data.cartomundi.seriesCount}
              {$t('indexed series')} · {data.cartomundi.sheetRecords}
              {$t('sheet records')}
            </p>
            <a href="/catalog/institutions/cartomundi"
              >{$t('Browse the survey index and linked scan evidence.')}</a
            >
          {:else if platform.name === 'Nakala'}
            <p>{data.cartomundi.checkedItems} {$t('checked scan items')}</p>
            <a href="/catalog/institutions/cartomundi">{$t('View item-level rights evidence')}</a>
          {/if}
          <ul>
            {#each platform.maps as map (map.id)}<li>
                <a href={`/catalog/${map.slug ?? map.id}`}>{map.name}</a>
              </li>{/each}
          </ul>
        </details>
      {/each}
    </section>
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
  details {
    border-top: var(--border-thin);
    padding: var(--space-3) 0;
  }
  summary {
    cursor: pointer;
  }
  summary span {
    display: block;
    margin-top: var(--space-1);
    color: var(--color-gray-500);
    font-size: 0.875rem;
  }
  h3 {
    font-size: 1rem;
    margin: var(--space-3) 0 var(--space-1);
  }
  ul {
    max-height: 24rem;
    overflow: auto;
  }
  li {
    margin: var(--space-1) 0;
  }
  p {
    margin: var(--space-1) 0;
  }
  a {
    color: var(--color-blue);
  }
</style>
