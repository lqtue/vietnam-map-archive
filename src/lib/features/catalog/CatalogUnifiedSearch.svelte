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
  import { catalogAreaSummary } from '$lib/core/catalogAreas';
  import ArchiveFilters from '$lib/features/shared/ArchiveFilters.svelte';
  import CatalogTable from '$lib/features/catalog/CatalogTable.svelte';
  import { sortRows, groupRows, type GroupKey } from '$lib/features/catalog/catalogTableModel';
  import { sliceGroups } from '$lib/features/catalog/sliceGroups';
  import MapCard from '$lib/ui/MapCard.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import { atWidth } from '$lib/core/iiif/thumbUrl';
  import { readJson, writeJson } from '$lib/core/utils/persistence/storage';
  import CatalogDetailDrawer from '$lib/features/catalog/CatalogDetailDrawer.svelte';
  import LabelHits from '$lib/features/shared/LabelHits.svelte';
  import { createEventDispatcher, onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import {
    favoriteIds,
    loadFavoriteIds,
    toggleFavorite,
  } from '$lib/features/shared/favoritesStore';
  import { get } from 'svelte/store';
  import { trackMeasurement } from '$lib/data/measurement';
  import { createCatalogSearch } from '$lib/features/shared/catalogSearch';
  import { inView } from '$lib/ui/inView';
  import SheetStatus from '$lib/features/catalog/SheetStatus.svelte';
  import { WORK_FILTERS, matchesWork, type WorkFactsById } from '$lib/core/sheetWork';
  import { fetchSheetWork } from '$lib/data/admin/sheetWork';

  export let searchQuery: string = '';
  /** Initial province from a coverage-page link. Other surfaces leave this empty. */
  export let initialArea: string = '';
  export let initialRegion: string = '';
  let groupBy: GroupKey = 'none';
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
   * The surveys offerable as a filter, `{ value: maps.series_key, label }`.
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

  $: staff = role === 'admin' || role === 'mod';

  // Staff: what has been done to each sheet, read once, to show and to filter by.
  let work: WorkFactsById = {};
  let workLoaded = false;
  let workFilter = '';
  async function loadWork() {
    workLoaded = true;
    work = (await fetchSheetWork()) ?? {};
  }
  $: if (staff && !compact && !workLoaded) void loadWork();
  // A scout candidate has no work state, so a work filter leaves it out.
  $: listed = workFilter
    ? $results.filter((r) => (r as any)._table !== 'scout' && matchesWork(workFilter, work[r.id]))
    : $results;

  const dispatch = createEventDispatcher<{ pick: any; edit: any }>();

  const search = createCatalogSearch({ requireGeoref });
  const {
    query,
    loading,
    mapsReady,
    results,
    facets,
    total,
    includeScout,
    labels,
    selected,
    toggleFacet,
    setSingle,
  } = search;

  if (initialArea) setSingle('area', initialArea);
  if (initialRegion) setSingle('region', initialRegion);

  // Mirror the parent's search box into the engine's query store.
  $: query.set(searchQuery);

  let measurementTimer: ReturnType<typeof setTimeout> | null = null;
  let lastMeasuredSearch = '';
  function scheduleSearchMeasurement() {
    if (compact) return;
    if (measurementTimer) clearTimeout(measurementTimer);
    const currentQuery = get(query).trim();
    const currentFilters = get(selected);
    const hasFilters = Object.values(currentFilters).some((value) => value?.length);
    if (!currentQuery && !hasFilters) {
      lastMeasuredSearch = '';
      return;
    }
    measurementTimer = setTimeout(() => {
      const signature = JSON.stringify([currentQuery, currentFilters]);
      const latestSignature = JSON.stringify([get(query).trim(), get(selected)]);
      if (
        signature !== latestSignature ||
        signature === lastMeasuredSearch ||
        get(loading) ||
        !get(mapsReady)
      )
        return;
      lastMeasuredSearch = signature;
      trackMeasurement('search_completed', {
        surface: 'catalog',
        workflow: 'search',
        result_count: get(results).length,
        action: 'complete',
      });
    }, 500);
  }

  $: atRest = !$query.trim() && !Object.values($selected).some((v) => v?.length);

  const { supabase, session } = getSupabaseContext();
  const userId = session?.user?.id;

  onMount(() => {
    if (userId) loadFavoriteIds(supabase, userId);
    search.start();
    const stops = [
      query.subscribe(scheduleSearchMeasurement),
      selected.subscribe(scheduleSearchMeasurement),
      results.subscribe(scheduleSearchMeasurement),
      mapsReady.subscribe((ready) => {
        if (ready) scheduleSearchMeasurement();
      }),
      loading.subscribe((isLoading) => {
        if (!isLoading) scheduleSearchMeasurement();
      }),
    ];
    // ...and back, because the store is no longer a sink: `ArchiveFilters`'
    // Reset clears it, and without this the page's own field would keep showing
    // a query the results had already stopped answering to. The guard is what
    // stops the pair above and below from ringing.
    const stopQueryMirror = query.subscribe((v) => {
      if (v !== searchQuery) searchQuery = v;
    });
    return () => {
      stops.forEach((stop) => stop());
      stopQueryMirror();
      if (measurementTimer) clearTimeout(measurementTimer);
    };
  });

  let openedItem: any | null = null;
  function openResult(item: any) {
    const hasSearch =
      !!get(query).trim() || Object.values(get(selected)).some((value) => value?.length);
    if (!compact && hasSearch) {
      trackMeasurement('search_result_open', {
        surface: 'catalog',
        workflow: 'search',
        result_kind: 'map',
        map_id: item?.id,
        action: 'open',
      });
    }
    if (pickMode) dispatch('pick', item);
    else openedItem = item;
  }

  /* List or grid. Two words of state, but the reader who wants pictures wants
     them every visit, so it is remembered. */
  const VIEW_KEY = 'vma-catalog-view-v1';
  $: VIEWS = [
    { key: 'list', label: $t('List') },
    { key: 'grid', label: $t('Grid') },
  ];
  let view: string = readJson<string>(VIEW_KEY, 'list');
  $: writeJson(VIEW_KEY, view);

  /* The grid draws a slice and the sentinel under it asks for the next, as CatalogTable does. */
  const SLICE = 60;
  let shown = SLICE;
  $: resetSlice($results);
  function resetSlice(_: unknown) {
    shown = SLICE;
  }

  /* The grid groups as the table does: sort by the grouping key so the sections come out in order,
     then slice after grouping so a heading never loses its first cards. */
  $: gridGroups = sliceGroups(
    groupRows(
      groupBy === 'none' ? listed : sortRows(listed as any[], { key: groupBy, asc: true }, null),
      groupBy
    ),
    shown
  );
  let collapsedGroups = new Set<string>();
  function toggleGroup(label: string | null) {
    if (label == null) return;
    if (collapsedGroups.has(label)) collapsedGroups.delete(label);
    else collapsedGroups.add(label);
    collapsedGroups = new Set(collapsedGroups);
  }
  $: shownCount = gridGroups.reduce((n, g) => n + g.rows.length, 0);

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
  export function filterSeries(seriesKey: string) {
    setSingle('series_key', seriesKey);
  }
</script>

<div class="cus" class:compact>
  <!-- The facets are the same disclosure /explore wears: a page with a left
       rail of chips put its filters in a column nobody scrolled back up to,
       and the rail cost the results a third of the page's width. /catalog
       gets a fourth control there, series; nothing else passes choices. -->
  <ArchiveFilters
    {search}
    showSearch={false}
    {seriesChoices}
    {staff}
    extraActive={workFilter ? 1 : 0}
    extraChips={workFilter
      ? [
          {
            label: `${$t('Work')}: ${$t(WORK_FILTERS.find((w) => w.key === workFilter)?.label ?? workFilter)}`,
            clear: () => (workFilter = ''),
          },
        ]
      : []}
  >
    {#if staff && !compact}
      <select bind:value={workFilter} aria-label="Filter by work">
        {#each WORK_FILTERS as w (w.key)}
          <option value={w.key}>{$t(w.label)}</option>
        {/each}
      </select>
    {/if}
  </ArchiveFilters>

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
        <select bind:value={groupBy} aria-label={$t('Group by')}>
          <option value="none">{$t('Group by')}: {$t('None')}</option>
          <option value="year">{$t('Group by')}: {$t('Year')}</option>
          <option value="region">{$t('Group by')}: {$t('Area')}</option>
          <option value="collection">{$t('Group by')}: {$t('Series')}</option>
          <option value="holding_institution">{$t('Group by')}: {$t('Institution')}</option>
        </select>
        <Tabs
          tone="rail"
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
      {#each gridGroups as g (g.label)}
        {#if g.label !== null}
          <button
            type="button"
            class="cus-group"
            aria-expanded={!collapsedGroups.has(g.label)}
            on:click={() => toggleGroup(g.label)}
          >
            <span class="cus-caret">{collapsedGroups.has(g.label) ? '▸' : '▾'}</span>
            <strong>{g.label}</strong>
            <span class="cus-group-n">{g.count}</span>
          </button>
        {/if}
        {#if g.label === null || !collapsedGroups.has(g.label)}
          <div class="cus-grid">
            {#each g.rows as item (item.id)}
              <MapCard
                map={{
                  ...item,
                  location:
                    catalogAreaSummary(item).label === '—'
                      ? undefined
                      : catalogAreaSummary(item).label,
                } as any}
                href={null}
                thumbnail={atWidth(item.thumbnail, 400)}
                showSourceBadge
                showFavorite={!!userId && (item as any)._table !== 'scout'}
                isFavorited={$favoriteIds.has(item.id)}
                on:toggleFavorite={(e) => userId && toggleFavorite(supabase, userId, e.detail)}
                on:open={(e) => openResult(e.detail)}
              >
                <svelte:fragment slot="status">
                  {#if staff}<SheetStatus {item} state={work[item.id]} />{/if}
                </svelte:fragment>
              </MapCard>
            {/each}
          </div>
        {/if}
      {/each}
      {#if shownCount < listed.length}
        <div use:inView={() => (shown += SLICE)}></div>
      {/if}
    {:else}
      <CatalogTable
        items={listed as any}
        {work}
        {compact}
        {activeId}
        {showLayerActions}
        {staff}
        {groupBy}
        on:open={(e) => openResult(e.detail)}
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
    padding: 0.25rem 0;
    font-family: var(--font-family-base);
    font-size: 0.8rem;
    color: var(--sb-text-meta);
  }
  .v2-tools {
    display: flex;
    align-items: center;
    gap: 0.75rem;
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
    cursor: pointer;
  }

  /* `MapCard` carries its own 3px border and 4px drop, so the track is sized
     for the card rather than the card padded to fill a track. */
  .cus-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    margin: 1.25rem 0 0.6rem;
    padding: var(--space-2) var(--space-3);
    font: inherit;
    text-align: left;
    color: inherit;
    cursor: pointer;
    background: var(--sb-group-bg);
    border: none;
    border-top: 1.5px solid var(--color-border);
    border-bottom: 1.5px solid var(--color-border);
  }
  .cus-group:hover {
    background: var(--sb-group-bg-hover);
  }
  .cus-caret {
    display: inline-block;
    width: 1em;
  }
  .cus-group-n {
    padding: 0.05rem 0.45rem;
    background: var(--color-text);
    color: var(--color-white);
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: var(--font-extrabold);
  }
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
