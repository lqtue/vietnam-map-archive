<!--
  CatalogTable — sortable, groupable table for the unified catalog.
  Click a column header to sort (toggle direction). The Group by choice
  comes from the filter group above (CatalogUnifiedSearch).

  `compact` delegates to `ArchiveMapRows` — this same table with four columns
  dropped, which is what a 380px rail can carry. It was `CatalogTableCompact`,
  a hand-built `<ul>`, until Sept 2026.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import { layersStore, toggleOverlayFor } from '$lib/map/stores/layersStore';
  import ArchiveMapRows from '$lib/features/shared/ArchiveMapRows.svelte';
  import { atWidth, stepDown } from '$lib/core/iiif/thumbUrl';
  import { sortRows, groupRows, type SortKey, type GroupKey } from './catalogTableModel';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import SheetWork from './SheetWork.svelte';
  import { fetchSheetWork } from '$lib/data/admin/sheetWork';
  import type { WorkFactsById } from '$lib/core/sheetWork';

  export let items: MapListItem[] = [];
  export let compact: boolean = false;
  export let activeId: string | null = null;
  /** Show the "+ overlay" toggle (only on the /explore sidebar). */
  export let showLayerActions: boolean = false;
  /** Admin/mod: the Status cell also shows what has run on the sheet and where to open it. */
  export let staff: boolean = false;

  const dispatch = createEventDispatcher();

  $: overlayMapIds = new Set($layersStore.overlays.map((o) => o.ref.mapId));

  let sort = { key: 'year' as SortKey, asc: true };
  /** Chosen in the catalog's filter group, not here. */
  export let groupBy: GroupKey = 'none';

  const COLUMNS: TableColumn[] = [
    { key: 'thumb', label: '', klass: 'thumb-col', srLabel: 'Thumbnail', sortable: false },
    { key: 'name', label: 'Title' },
    { key: 'year', label: 'Year', klass: 'num' },
    { key: 'location', label: 'Area' },
    { key: 'map_type', label: 'Type' },
    { key: 'collection', label: 'Collection' },
    { key: 'status', label: 'Status', klass: 'status-col' },
  ];

  // One read for the whole table, once a reader is known to be staff.
  let work: WorkFactsById = {};
  let workLoaded = false;
  async function loadWork() {
    workLoaded = true;
    work = (await fetchSheetWork()) ?? {};
  }
  $: if (staff && !compact && !workLoaded) void loadWork();

  // Staff: Status and the work tracks read the loaded work state.
  $: ctx = staff && !compact ? work : null;
  $: sorted = sortRows(items, sort, ctx);
  $: groups = groupRows(sorted, groupBy, ctx);

  let collapsed = new Set<string>();
  function toggleGroup(label: string | null) {
    if (label == null) return;
    if (collapsed.has(label)) collapsed.delete(label);
    else collapsed.add(label);
    collapsed = new Set(collapsed);
  }

  function openItem(item: MapListItem) {
    dispatch('open', item);
  }
  function chip(group: string, value: string | null | undefined) {
    if (!value) return;
    dispatch('facet', { group, value: String(value) });
  }
</script>

{#if compact}
  <ArchiveMapRows rows={sorted} rowAction="open" {activeId} showTypes={showLayerActions} on:open />
{:else}
  <!-- The `.ct` wrapper is this component's own element, so its scoped CSS can
       still reach the `<table>`, `<thead>` and `<th>`s that are DataTable's. -->
  <div class="ct" class:is-staff={staff}>
    <DataTable columns={COLUMNS} klass="is-card" bind:sort>
      {#each groups as g (g.label)}
        {#if g.label !== null}
          <tr class="group-row" on:click={() => toggleGroup(g.label)}>
            <td colspan={COLUMNS.length}>
              <span class="caret">{collapsed.has(g.label) ? '▸' : '▾'}</span>
              <strong>{g.label}</strong>
              <span class="group-count">{g.rows.length}</span>
            </td>
          </tr>
        {/if}
        {#if g.label === null || !collapsed.has(g.label)}
          {#each g.rows as item (item.id)}
            {@const isScout = (item as any)._table === 'scout'}
            {@const isOverlay = overlayMapIds.has(item.id)}
            {@const shareHref =
              !isScout && ((item as any).status === 'public' || (item as any).status === 'featured')
                ? `/map/${item.id}`
                : null}
            <tr
              class:scout-row={isScout}
              class:active-row={item.id === activeId}
              on:click={() => openItem(item)}
            >
              <td class="thumb-col">
                {#if item.thumbnail}
                  <!-- The cell is 96px; the stored column is 800. -->
                  <img
                    src={atWidth(item.thumbnail, 200)}
                    alt=""
                    loading="lazy"
                    on:error={(e) => stepDown(e, item.thumbnail)}
                  />
                {:else}
                  <div class="thumb-empty"></div>
                {/if}
              </td>
              <td class="title-col">
                <div class="title-row">
                  {#if shareHref}
                    <!--
                    A real link, not a span: the row's on:click still opens the
                    drawer (a plain click is swallowed here and bubbles), but a
                    crawler, a middle-click and ⌘-click now all reach the share
                    page. /map/<id> and /place/<slug> only linked to each other,
                    so the whole server-rendered half of the site had no entry.
                  -->
                    <a
                      class="title-link"
                      href={shareHref}
                      on:click={(e) => {
                        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                        e.preventDefault();
                      }}>{item.name || '—'}</a
                    >
                  {:else}
                    <span class="title-link">{item.name || '—'}</span>
                  {/if}
                  {#if showLayerActions && !isScout && (item as any).georef_done}
                    <button
                      type="button"
                      class="btn is-icon is-xs"
                      class:is-on={isOverlay}
                      on:click|stopPropagation={() => toggleOverlayFor(item)}
                      title={isOverlay ? 'Remove overlay' : 'Add as overlay'}
                      aria-label={isOverlay ? 'Remove overlay' : 'Add as overlay'}
                      >{isOverlay ? '✓' : '+'}</button
                    >
                  {/if}
                </div>
                {#if (item as any).creator}<div class="sub">{(item as any).creator}</div>{/if}
              </td>
              <td class="num">
                {#if item.year}
                  <button
                    class="tag-chip"
                    on:click|stopPropagation={() => chip('year', String(item.year))}
                    >{item.year}</button
                  >
                {:else}—{/if}
              </td>
              <td>
                {#if item.location}
                  <button
                    class="tag-chip"
                    on:click|stopPropagation={() => chip('area', item.location)}
                    >{item.location}</button
                  >
                {:else}—{/if}
              </td>
              <td>
                {#if item.map_type}
                  <button
                    class="tag-chip"
                    on:click|stopPropagation={() => chip('type', item.map_type)}
                    >{item.map_type}</button
                  >
                {:else}—{/if}
              </td>
              <td title={item.collection || ''} class="collection-col">{item.collection || '—'}</td>
              <td class="status-col">
                {#if isScout}
                  <span class="badge-chip is-sm scout">scout</span>
                {:else if (item as any).georef_done}
                  <span class="badge-chip is-sm status-map" title={$t('Available on map')}
                    >{$t('Map')}</span
                  >
                {:else}
                  <span class="badge-chip is-sm chip-gray" title={$t('Static image only')}
                    >{$t('Image')}</span
                  >
                {/if}
                {#if staff && !isScout}<SheetWork mapId={item.id} state={work[item.id]} />{/if}
              </td>
            </tr>
          {/each}
        {/if}
      {/each}
    </DataTable>
  </div>
{/if}

<style>
  /* Shape, header, row rules and the sort indicator come from
     `.data-table.is-card` in components/table.css. */
  .ct :global(tbody tr) {
    cursor: pointer;
  }
  .ct .title-link {
    font-weight: var(--font-bold);
    color: var(--color-text);
    font-size: 1rem;
    /* An anchor now; keep the row-hover underline as the only one. */
    text-decoration: none;
  }
  .ct :global(tbody tr:hover .title-link) {
    text-decoration: underline;
  }
  /* Not `.chip.ghost`: this is a dense inline affordance inside a table cell,
     and the shared pill's 2.5rem min-height would set the row height. */
  .tag-chip {
    background: transparent;
    border: 1.5px solid transparent;
    padding: 0.15rem var(--space-2);
    border-radius: var(--radius-pill);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    color: var(--color-text);
  }
  .tag-chip:hover {
    background: var(--color-white);
    border-color: var(--color-border);
  }
  .collection-col {
    color: var(--sb-text-meta);
    font-size: 0.85rem;
  }
  .ct :global(.thumb-col) {
    width: 96px;
    padding: var(--space-2) 0.6rem;
  }
  .ct :global(.thumb-col img),
  .ct :global(.thumb-col .thumb-empty) {
    width: 84px;
    height: 64px;
    object-fit: cover;
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
    background: var(--sb-thumb-bg);
    display: block;
  }
  .ct .title-col .sub {
    font-size: 0.8rem;
    color: var(--sb-text-soft);
    margin-top: 0.2rem;
  }
  /* `:global` because the header cell is `SortHeader`'s and the table's own
     elements are `DataTable`'s; a column's geometry has to reach both halves of
     it. The `.ct` wrapper is this component's, so it keeps them from leaking. */
  .ct :global(.status-col) {
    width: 90px;
    text-align: right;
    white-space: nowrap;
  }
  /* Staff: the cell also carries the work chips and the Open-in menu. */
  .ct.is-staff :global(.status-col) {
    width: 14rem;
    text-align: left;
    white-space: normal;
  }
  /* Two tones only: both are tints of a token, and the shared `.chip-green` /
     `.chip-yellow` are a solid fill and a white face — too loud and too blank
     for a badge repeated down every row. */
  .scout {
    background: var(--sb-accent-yellow);
  }
  .status-map {
    background: var(--sb-badge-map);
  }
  .group-row {
    cursor: pointer;
    background: var(--sb-group-bg);
  }
  .group-row td {
    padding: var(--space-2) var(--space-3);
    border-top: 1.5px solid var(--color-border);
    border-bottom: 1.5px solid var(--color-border);
  }
  .group-row:hover {
    background: var(--sb-group-bg-hover);
  }
  .caret {
    display: inline-block;
    width: 1em;
  }
  .group-count {
    margin-left: var(--space-2);
    padding: 0.05rem 0.45rem;
    background: var(--color-text);
    color: var(--color-white);
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: var(--font-extrabold);
  }
  .title-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .scout-row td {
    background: var(--sb-scout-bg);
  }
  .active-row td {
    background: var(--sb-accent-yellow);
    box-shadow: inset 3px 0 0 var(--color-border);
  }
  .active-row:hover td {
    background: var(--sb-accent-yellow-strong);
  }
  .active-row .title-link {
    text-decoration: underline;
  }
  @media (max-width: 800px) {
    .ct :global(th:nth-child(5)),
    .ct td:nth-child(5) {
      display: none;
    }
    .ct :global(th:nth-child(6)),
    .ct td:nth-child(6) {
      display: none;
    }
  }
</style>
