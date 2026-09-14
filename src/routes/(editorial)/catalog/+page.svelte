<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import PageHero from '$lib/ui/PageHero.svelte';
  import CatalogUnifiedSearch from '$lib/features/catalog/CatalogUnifiedSearch.svelte';
  import MapEditModal from '$lib/features/admin/MapEditModal.svelte';
  import SeriesList from '$lib/features/catalog/SeriesList.svelte';
  import SeriesDetailDrawer from '$lib/features/catalog/SeriesDetailDrawer.svelte';
  import { fetchMapRow } from '$lib/data/maps/service';
  import type { MapRow } from '$lib/data/admin/adminApi';
  import type { SeriesIndexEntry } from '$lib/data/maps/seriesIndex';
  import type { PageData } from './$types';
  import '$styles/layouts/catalog.css';

  export let data: PageData;

  $: heroTitle = splitHighlight($t('The **Archive.**'));

  /* The surveys, server-loaded. Two things read them, and they are not the
     same thing: the band below is a way *out* of this page, into the coverage
     pages that list every sheet a survey contains including the ones we do not
     hold; the filter narrows the sheets *on* this page to one survey. A reader
     who wants "what is missing from L7014" needs the first and would never
     find it from the second. */
  $: series = data.series;
  // The filter matches `maps.collection`; the label is what the reader reads.
  $: seriesChoices = series.map((s) => ({ value: s.collection, label: s.name }));

  /** True until the reader narrows the list — see `CatalogUnifiedSearch`. */
  let atRest = true;

  /* The open survey, or null. A row is still a link to the coverage page —
     the drawer is what an unmodified click gets, the same bargain a map row
     strikes with its own drawer. */
  let openedSeries: SeriesIndexEntry | null = null;
  function filterToSeries(s: SeriesIndexEntry) {
    openedSeries = null;
    searchRef?.filterSeries(s.collection);
  }

  const { supabase, session } = getSupabaseContext();

  let role: 'user' | 'mod' | 'admin' = 'user';
  let searchQuery: string = '';

  // Admin edit. The drawer item is the search-result shape (subset of columns);
  // load the full row first so saving can't clobber fields it didn't carry.
  let searchRef: CatalogUnifiedSearch;
  let editingMap: MapRow | null = null;
  let editError = '';
  async function openEditor(item: { id: string }) {
    editError = '';
    const row = await fetchMapRow(supabase, item.id);
    if (!row) {
      editError = 'Could not load this map for editing.';
      return;
    }
    editingMap = row as MapRow;
  }
  function afterEdit() {
    editingMap = null;
    searchRef?.refresh();
  }

  const CONTRIBUTE_EMAIL = 'vietnammaproject@gmail.com';
  const contributeHref = `mailto:${CONTRIBUTE_EMAIL}?subject=${encodeURIComponent('VMA — map submission')}&body=${encodeURIComponent("Hi VMA,\n\nI'd like to submit a map to the archive.\n\n• Title:\n• Year / period:\n• Location (city / region):\n• Source (URL, institution, or attachment):\n• Anything else we should know:\n\nThanks!")}`;

  onMount(async () => {
    role = (await fetchUserRole(supabase, session?.user?.id)) ?? 'user';
  });
</script>

<svelte:head>
  <title>Catalog — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Every historical map in the archive — georeferenced, searchable, and linked back to the library or collection that holds the scan."
  />
</svelte:head>

<div class="page catalog-page">
  <PageHero
    eyebrow="Collection"
    sub="Every historical map in the archive — georeferenced, searchable, and linked back to the library or collection that holds the scan."
  >
    <svelte:fragment slot="title"
      >{heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}</svelte:fragment
    >
    <div slot="actions">
      <a class="btn is-lg is-primary" href={contributeHref}>{$t('Submit a map')}</a>
    </div>
  </PageHero>

  <main class="content">
    <label class="sb-search is-page">
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        class="sb-search-input"
        type="search"
        placeholder={$t('Search by title, creator, year, or description…')}
        bind:value={searchQuery}
      />
      {#if searchQuery}
        <button
          type="button"
          class="sb-search-clear"
          on:click={() => (searchQuery = '')}
          aria-label={$t('Clear')}>×</button
        >
      {/if}
    </label>

    <!-- Above the results, and only at rest. A survey is a coarser thing than a
         sheet and belongs in front of the list rather than inside it; but once
         a reader has typed or filtered, it is three cards between them and
         what they asked for. -->
    {#if atRest && series.length}
      <section class="series-band" aria-labelledby="series-band-title">
        <div class="band-head">
          <h2 id="series-band-title">{$t('Browse by series')}</h2>
          <a class="band-all" href="/catalog/series">{$t('All series')} →</a>
        </div>
        <p class="band-lead">
          {$t(
            'A survey is one map printed as many sheets. Each page lists every sheet the survey contains, held or not.'
          )}
        </p>
        <SeriesList {series} dense drawer on:open={(e) => (openedSeries = e.detail)} />
      </section>
    {/if}

    <CatalogUnifiedSearch
      bind:this={searchRef}
      bind:searchQuery
      bind:atRest
      {seriesChoices}
      {role}
      on:edit={(e) => openEditor(e.detail)}
    />
    <SeriesDetailDrawer
      series={openedSeries}
      on:close={() => (openedSeries = null)}
      on:filter={(e) => filterToSeries(e.detail)}
    />

    {#if editError}<div class="edit-error" role="alert">{editError}</div>{/if}
    {#if editingMap}
      <MapEditModal
        map={editingMap}
        on:saved={afterEdit}
        on:deleted={afterEdit}
        on:close={() => (editingMap = null)}
      />
    {/if}
  </main>
</div>

<style>
  /* The search field itself is `.sb-search.is-page` (components/sidebar.css) —
     the same bar both /explore rails wear, one size up. It was 40 lines of a
     fourth design here. */
  .content {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.25rem;
    max-width: 1400px;
    margin: 0 auto;
  }

  /* No card around it: the rows are cards already, and a card of cards is the
     nesting `.section-card` exists to stop. The rule under it is what separates
     the band from the search results, at the width the page already uses. */
  .series-band {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-bottom: 1rem;
    border-bottom: var(--border-thin);
  }
  .band-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .band-head h2 {
    margin: 0;
    font-family: var(--font-family-display);
    font-weight: var(--font-extrabold);
    font-size: 1.1rem;
  }
  .band-all {
    font-size: 0.82rem;
    font-weight: var(--font-bold);
    color: var(--sb-accent);
    text-decoration: underline;
    white-space: nowrap;
  }
  .band-lead {
    margin: 0;
    font-size: 0.85rem;
    color: var(--color-gray-500);
    max-width: 52ch;
  }
</style>
