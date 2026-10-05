<!--
  CatalogTable — sortable, groupable table for the unified catalog.
  Click a column header to sort (toggle direction). The Group by choice (Year / Area /
  Series / Institution) comes from the filter group above, in CatalogUnifiedSearch.

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
  import SheetStatus from './SheetStatus.svelte';
  import OpenInMenu from './OpenInMenu.svelte';
  import type { WorkFactsById } from '$lib/core/sheetWork';
  import { inView } from '$lib/ui/inView';
  import { sliceGroups } from './sliceGroups';
  import { sheetLabel, seriesShort } from '$lib/features/shared/catalogFilters';

  export let items: MapListItem[] = [];
  export let compact: boolean = false;
  export let activeId: string | null = null;
  /** Show the "+ overlay" toggle (only on the /explore sidebar). */
  export let showLayerActions: boolean = false;
  /** Staff also see Type and Status; for a reader Type is one value in 96% of rows and Status is "map". */
  export let staff: boolean = false;
  /** What has been done to each sheet (staff), loaded by the catalog that also filters on it. */
  export let work: WorkFactsById = {};
  /** Chosen in the catalog's filter group, not here. */
  export let groupBy: GroupKey = 'none';

  const dispatch = createEventDispatcher();

  $: overlayMapIds = new Set($layersStore.overlays.map((o) => o.ref.mapId));

  let sort = { key: 'year' as SortKey, asc: true };

  const sheetOf = sheetLabel;

  $: COLUMNS = [
    { key: 'thumb', label: '', klass: 'thumb-col', srLabel: 'Thumbnail', sortable: false },
    { key: 'name', label: 'Title' },
    { key: 'year', label: 'Year', klass: 'num' },
    { key: 'region', label: 'Area' },
    { key: 'collection', label: 'Series' },
    ...(staff
      ? [
          { key: 'map_type', label: 'Type' },
          { key: 'status', label: 'Status', klass: 'status-col' },
          { key: 'open', label: '', srLabel: 'Open in', klass: 'open-col', sortable: false },
        ]
      : []),
  ] satisfies TableColumn[];

  $: ctx = staff && !compact ? work : null;
  $: sorted = sortRows(items, sort, ctx);
  $: groups = groupRows(sorted, groupBy, ctx);

  /* 938 rows is 15,000 DOM nodes and a 1.3 s first render, and nobody has scrolled to most of them.
     Draw a slice; the sentinel under the table asks for the next one. A new result set, sort or
     grouping starts over from the top. */
  const SLICE = 100;
  let shown = SLICE;
  $: resetSlice(groups);
  function resetSlice(_: unknown) {
    shown = SLICE;
  }
  $: drawn = sliceGroups(groups, shown);
  $: total = items.length;

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
</script>

{#if compact}
  <ArchiveMapRows rows={sorted} rowAction="open" {activeId} on:open />
{:else}
  <!-- The `.ct` wrapper is this component's own element, so its scoped CSS can
       still reach the `<table>`, `<thead>` and `<th>`s that are DataTable's. -->
  <div class="ct">
    <DataTable columns={COLUMNS} klass="is-card" bind:sort>
      {#each drawn as g (g.label)}
        {#if g.label !== null}
          <tr class="group-row" on:click={() => toggleGroup(g.label)}>
            <td colspan={COLUMNS.length}>
              <span class="caret">{collapsed.has(g.label) ? '▸' : '▾'}</span>
              <strong>{g.label}</strong>
              <span class="group-count">{g.count}</span>
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
                {#if sheetOf(item) || item.location}
                  <div class="sub">
                    {#if sheetOf(item)}<span class="sheet">{sheetOf(item)}</span>{/if}
                    {item.location ?? ''}
                  </div>
                {/if}
              </td>
              <td class="num">{item.year ?? '—'}</td>
              <td class="area-col">{item.regions?.join(', ') || item.region || '—'}</td>
              <td title={item.collection || ''} class="collection-col">
                {seriesShort(item.collection) || '—'}
              </td>
              {#if staff}
                <td>{item.map_type || '—'}</td>
                <td class="status-col"><SheetStatus item={item as any} state={work[item.id]} /></td>
                <td class="open-col">
                  {#if !isScout}<OpenInMenu mapId={item.id} />{/if}
                </td>
              {/if}
            </tr>
          {/each}
        {/if}
      {/each}
    </DataTable>
    {#if shown < total}
      <div class="ct-more" use:inView={() => (shown += SLICE)}></div>
    {/if}
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
  .area-col {
    white-space: nowrap;
    color: var(--sb-text-meta);
    font-size: 0.85rem;
  }
  .collection-col {
    max-width: 16rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
  .sheet {
    margin-right: 0.35rem;
    padding: 0 0.3rem;
    border: 1px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
    font-size: 0.72rem;
    font-weight: var(--font-bold);
    white-space: nowrap;
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
    width: 9rem;
    white-space: nowrap;
  }
  .ct :global(.open-col) {
    width: 6rem;
    text-align: right;
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
