<!--
  ArchiveMapRows.svelte — the archive list, everywhere it is not the full
  /catalog page: both /explore browse modes (GPS coverage and the full archive
  browser), the /scan left rail, and /catalog's own compact sidebar.

  It is **the catalog table with its columns reduced** — the same `DataTable`,
  the same header, the same row rules, dropping the columns a 380px rail
  cannot carry (Area, Series, Institution, Status, Type) and making the
  thumbnail the pick control. The sheet number and the survey ride in a line
  under the title: the picture of the sheet *is* the button that puts it on the map. Until Sept 2026 it was a hand-built `<ul>`
  of bordered buttons, and `CatalogTableCompact` was a *second* hand-built
  `<ul>` beside it: same data, same sidebar job, and no two details alike —
  year 1rem extrabold against 0.82rem bold, title semibold-muted against
  regular-ink, the pick control a 32px circle against a `.btn.is-xs`.

  Two row actions, because the two callers mean different things by a tap:

    toggle  (default)  the row is a layer — tapping adds the sheet to the map,
                       tapping an "on" row removes it. /explore and /scan.
    open               the row is a record — tapping opens it, and the layer
                       toggle is the separate button in the pick column.

  `activeIds` switches `toggle` from the /explore layer stack to a caller's own
  selection, which makes it a radio: a /scan tool has one open sheet, so
  tapping it again is a no-op rather than a remove nothing can undo.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { layersStore, toggleOverlayFor } from '$lib/map/stores/layersStore';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import { atWidth, stepDown } from '$lib/core/iiif/thumbUrl';
  import { applySort, type SortState } from '$lib/core/utils/tableSort';
  import { sheetLabel } from '$lib/features/shared/catalogFilters';

  export let rows: any[] = [];
  /** Ids to draw as "on". Null (the default) means the /explore layer stack,
   *  and restores tap-again-to-remove. */
  export let activeIds: string[] | null = null;
  /** id → short text drawn where the type chip goes. The catalog rows carry no
   *  pass progress, so /scan supplies "OCR'd" / "12 pending" from its own list. */
  export let badges: Record<string, string> = {};
  /** Draw the map_type chip when a row has no badge. Off by default: for a reader it is one value
   *  in 96% of rows. /scan keeps it off too — that column is "have I done this sheet yet?", and a
   *  type chip on the rows with no pass yet reads as a status the sheet does not have. */
  export let showTypes = false;
  /** What a tap on the row body means — see the header. */
  export let rowAction: 'toggle' | 'open' = 'toggle';
  /** `open` mode only: the row drawn as the current one. */
  export let activeId: string | null = null;
  /** `open` mode only: draw the overlay toggle. Off where there is no map to
   *  add a sheet to — /catalog's own sidebar on a page without one. */
  export let showLayerActions = true;

  const dispatch = createEventDispatcher<{
    pick: { map: any };
    remove: { mapId: string };
    open: any;
  }>();

  $: stackedIds = new Set(activeIds ?? $layersStore.overlays.map((o) => o.ref.mapId));

  // Year first, which is how the archive is read. The header is the catalog's,
  // so the reader can re-order a long list without leaving the rail.
  let sort: SortState<string> = { key: 'year', asc: true };
  $: sorted = applySort(rows, sort, (m: any, key) =>
    key === 'year' ? (m.year ?? null) : key === 'type' ? (m.map_type ?? null) : (m.name ?? null)
  );

  /** The line under a title: the sheet number (23 names repeat) and the survey it belongs to. */
  const subOf = (m: any) =>
    [sheetLabel(m), m.series_key ? m.collection : ''].filter(Boolean).join(' · ');

  $: hasLast = showTypes || Object.keys(badges).length > 0;
  $: columns = [
    { key: 'pick', label: '', klass: 'col-pick', srLabel: 'Sheet', sortable: false },
    { key: 'year', label: 'Year', klass: 'col-year num' },
    { key: 'name', label: 'Title', klass: 'col-name' },
    ...(hasLast ? [{ key: 'type', label: showTypes ? 'Type' : '', klass: 'col-type' }] : []),
  ] satisfies TableColumn[];

  function onRowClick(map: any) {
    if (rowAction === 'open') return dispatch('open', map);
    if (activeIds) {
      if (!stackedIds.has(map.id)) dispatch('pick', { map });
      return;
    }
    if (stackedIds.has(map.id)) dispatch('remove', { mapId: map.id });
    else dispatch('pick', { map });
  }
</script>

<div class="amr">
  <DataTable {columns} klass="is-dense" bind:sort>
    {#each sorted as m (m.id)}
      {@const on = stackedIds.has(m.id)}
      {@const scout = m._table === 'scout'}
      <tr
        class:is-on={on}
        class:is-active={rowAction === 'open' && m.id === activeId}
        class:is-scout={scout}
        on:click={() => onRowClick(m)}
      >
        <td class="col-pick">
          {#if rowAction === 'toggle' || (showLayerActions && !scout && m.georef_done)}
            <!-- The real control: the `<tr>` click is a pointer convenience, so
                 the keyboard and a screen reader get this instead. The picture
                 of the sheet *is* the button — a plus sign says a row can be
                 added, the scan says which sheet is being added. -->
            <button
              type="button"
              class="pick"
              class:on
              on:click|stopPropagation={() =>
                rowAction === 'toggle' ? onRowClick(m) : toggleOverlayFor(m)}
              aria-pressed={on}
              aria-label={on ? `Remove ${m.name}` : `Add ${m.name} to the map`}
            >
              {#if m.thumbnail}
                <img
                  src={atWidth(m.thumbnail, 200)}
                  alt=""
                  loading="lazy"
                  on:error={(e) => stepDown(e, m.thumbnail)}
                />
              {:else}
                <span class="no-thumb" aria-hidden="true">+</span>
              {/if}
              <!-- Over the sheet rather than beside it: the tint alone reads as
                   a hover on a list you are dragging a finger down. -->
              {#if on}<span class="on-mark" aria-hidden="true">✓</span>{/if}
            </button>
          {/if}
        </td>
        <td class="col-year num">{m.year ?? '—'}</td>
        <td class="col-name">
          <span class="title">{m.name || '—'}</span>
          <!-- The creator line is the catalog sidebar's: a rail beside a map
               wants as many sheets on screen as will fit. -->
          {#if rowAction === 'open' && m.creator && !subOf(m)}<span class="sub">{m.creator}</span
            >{/if}
          {#if subOf(m)}<span class="sub">{subOf(m)}</span>{/if}
        </td>
        {#if hasLast}
          <td class="col-type">
            {#if badges[m.id]}
              <span class="badge-chip is-sm chip-green">{badges[m.id]}</span>
            {:else if showTypes && m.map_type}
              <span class="type-chip">{m.map_type}</span>
            {/if}
          </td>
        {/if}
      </tr>
    {/each}
  </DataTable>
</div>

<style>
  /* `:global` because the cells' geometry has to reach the `<th>`s, which are
     `SortHeader`'s and `DataTable`'s. `.amr` keeps it inside this list. */
  .amr :global(.col-pick) {
    width: 1%;
    padding-left: 0.35rem;
    padding-right: 0;
  }
  .amr :global(.col-year) {
    width: 1%;
    white-space: nowrap;
  }
  /* `width: 1%` + `nowrap` is shrink-to-fit in a table: the three narrow
     columns take what they need and the title keeps the rest, which in a 300px
     rail is the difference between two words and a readable line. */
  .amr :global(.col-type) {
    width: 1%;
    white-space: nowrap;
    text-align: right;
  }

  tr {
    cursor: pointer;
  }
  .is-on td {
    background: var(--sb-success-bg);
  }
  .is-scout td {
    background: var(--sb-scout-bg);
  }
  .is-active td {
    background: var(--sb-accent-yellow);
  }

  /* The scan itself, at the size the /catalog table draws it. 4:3 because a
     sheet is landscape more often than not and a ragged column of heights is
     harder to scan than a cropped one. */
  .pick {
    position: relative;
    display: block;
    width: 48px;
    height: 36px;
    padding: 0;
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
    background: var(--sb-thumb-bg);
    cursor: pointer;
    overflow: hidden;
  }
  .pick img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .no-thumb {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: var(--sb-text-meta);
    font-size: 0.95rem;
    line-height: 1;
  }
  .pick.on {
    border-color: var(--sb-success-dark);
  }
  .on-mark {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--sb-success) 72%, transparent);
    color: var(--color-white);
    font-size: 0.95rem;
    font-weight: var(--font-bold);
    line-height: 1;
  }

  .col-year {
    font-weight: var(--font-bold);
    color: var(--sb-accent);
  }
  .col-name {
    min-width: 0;
  }
  .title {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.3;
  }
  .sub {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.68rem;
    color: var(--sb-text-muted);
  }
  /* The catalog's Type cell, minus the click: there it adds a facet, and a rail
     has its own facet row above the list. */
  .type-chip {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border: 1.5px solid var(--color-border);
    border-radius: var(--radius-pill);
    font-size: 0.68rem;
    text-transform: capitalize;
    white-space: nowrap;
    color: var(--sb-text-meta);
  }
</style>
