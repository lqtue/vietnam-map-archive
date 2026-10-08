<!--
  LegendTable.svelte — a sheet's numbered legend as the app's one table.

  Both legend lists draw this: the /explore right rail (SheetLegendPanel) and
  the staff tool (/scan?mode=legend). They were two hand-built `<ul>`s beside
  the map list's `DataTable`, which is why the two rails looked unrelated; this
  is `ArchiveMapRows`' table with the legend's columns — № · Name · Grid, and a
  State column where the caller has one.

  It sorts itself (`applySort`, so numbers are numeric and blanks sit last in
  either direction); the caller filters and searches. A row is a pointer
  convenience on the `<tr>` plus a real `<button>` in the Name cell for the
  keyboard. Per-row extras (an editor) arrive through the `extra` slot and sit
  under the name, inside the same cell, so a row with nothing extra is one row.
-->
<script context="module" lang="ts">
  export type LegendTableRow = {
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    /** Drives the State column; ignored when `showState` is false. */
    placed?: boolean;
    /** Not placed, but a detected numeral could be taken for it. */
    suggested?: boolean;
    /** An unsaved draft: the State column says so ahead of placed/unplaced. */
    draft?: boolean;
    /** Appended to the state: `*` for an unsaved edit. */
    mark?: string;
  };
</script>

<script lang="ts" generics="Row extends LegendTableRow">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import { applySort, type SortState } from '$lib/core/utils/tableSort';

  export let rows: Row[] = [];
  export let selectedN: number | null = null;
  export let showState = false;
  /** Rows that do nothing when tapped (no point to fly to) are drawn inert. */
  export let actionable: (row: Row) => boolean = () => true;
  export let rowTitle: (row: Row) => string | undefined = () => undefined;
  export let empty = '';
  export let sort: SortState<string> = { key: 'n', asc: true };

  const dispatch = createEventDispatcher<{ select: { n: number } }>();

  $: columns = [
    { key: 'n', label: '№', klass: 'col-n num' },
    { key: 'name', label: $t('Name'), klass: 'col-name' },
    { key: 'grid', label: $t('Grid'), klass: 'col-grid' },
    ...(showState ? [{ key: 'placed', label: '', klass: 'col-state', srLabel: $t('State') }] : []),
  ] satisfies TableColumn[];

  $: sorted = applySort(rows, sort, (row, key) =>
    key === 'n'
      ? row.n
      : key === 'name'
        ? row.name
        : key === 'grid'
          ? row.grid
          : (row.draft ? 2 : 0) + (row.placed ? 1 : 0)
  );
</script>

<div class="lgt">
  <DataTable {columns} klass="is-dense" bind:sort>
    {#each sorted as row (row.n)}
      {@const live = actionable(row)}
      <tr
        class:is-active={selectedN === row.n}
        class:is-inert={!live}
        title={rowTitle(row)}
        on:click={() => live && dispatch('select', { n: row.n })}
      >
        <td class="col-n num">{row.n}</td>
        <td class="col-name">
          {#if live}
            <button
              type="button"
              class="pick"
              aria-pressed={selectedN === row.n}
              on:click|stopPropagation={() => dispatch('select', { n: row.n })}
              >{row.name ?? '—'}{#if row.vn}<em> · {row.vn}</em>{/if}</button
            >
          {:else}
            {row.name ?? '—'}{#if row.vn}<em> · {row.vn}</em>{/if}
          {/if}
          {#if $$slots.extra}
            <!-- Taps in here are the editor's, not the row's. -->
            <div class="extra" role="presentation" on:click|stopPropagation>
              <slot name="extra" {row} />
            </div>
          {/if}
        </td>
        <td class="col-grid">{row.grid ?? ''}</td>
        {#if showState}
          <td class="col-state">
            {#if row.draft}<span class="badge-chip is-sm chip-blue">{$t('draft')}</span>{/if}
            {#if row.placed}<span class="badge-chip is-sm chip-green">{$t('placed')}</span
              >{:else if row.suggested}<span class="badge-chip is-sm chip-yellow"
                >{$t('suggested')}</span
              >{:else}<span class="muted">{$t('unplaced')}</span>{/if}{row.mark ?? ''}
          </td>
        {/if}
      </tr>
    {/each}
    <svelte:fragment slot="after">
      {#if !rows.length && empty}<p class="table-empty">{empty}</p>{/if}
    </svelte:fragment>
  </DataTable>
</div>

<style>
  /* `:global` because these widths have to reach the `<th>`s, which are
     DataTable's; `.lgt` keeps them inside this list. */
  .lgt :global(.col-n) {
    width: 1%;
    white-space: nowrap;
  }
  .lgt :global(.col-grid),
  .lgt :global(.col-state) {
    width: 1%;
    white-space: nowrap;
  }
  .lgt :global(.col-state) {
    text-align: right;
  }

  tr {
    cursor: pointer;
  }
  tr.is-inert {
    cursor: default;
  }
  /* Same yellow as the map's pulse ring, so the row and the spot read as one. */
  tr.is-active td {
    background: var(--sb-accent-yellow);
  }
  .extra {
    cursor: default;
  }

  .col-n {
    font-weight: var(--font-bold);
    color: var(--sb-accent);
  }
  .col-grid,
  .muted {
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
  em {
    font-style: normal;
    color: var(--sb-text-meta);
  }
  /* The keyboard's way in: looks like the cell's own text. */
  .pick {
    display: block;
    width: 100%;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: inherit;
  }
  .pick:focus-visible {
    outline: 2px solid var(--color-blue);
    outline-offset: 1px;
  }
</style>
