<!--
  LegendSidebar.svelte — the legend list for /scan?mode=legend: number, name,
  grid, placed or not; the selected row opens its three text fields.

  Dispatches:
    select { id }                         (the same row again puts it out)
    edit   { id, field, value }           field is 'name' | 'vn' | 'grid'
    reset  { id }                         drop the position
    save
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';
  import LegendTable from '$lib/features/shared/LegendTable.svelte';
  import FilterBar from '$lib/features/shared/FilterBar.svelte';
  import { filterRows, type LegendRow, type RowFilter } from './legendStage';

  export let rows: LegendRow[] = [];
  export let selectedId: string | null = null;
  export let filter: RowFilter = 'all';
  export let query = '';
  /** Entry numbers with a detected numeral to take, and how many of those agree with their index cell. */
  export let suggested: Set<number> = new Set();
  export let matching = 0;
  /** "Add another point" is armed. */
  export let addingMore = false;
  export let staged: Set<string> = new Set();
  export let failures: Record<string, string> = {};
  export let saving = false;
  export let message = '';

  const dispatch = createEventDispatcher<{
    select: { id: string };
    edit: { id: string; field: 'name' | 'vn' | 'grid'; value: string };
    reset: { id: string };
    accept: { id: string };
    acceptMatching: void;
    addMore: void;
    removeMore: { id: string; index: number };
    save: void;
  }>();

  $: shown = filterRows(rows, { filter, query, staged, suggested, keepId: selectedId }).map(
    (row) => ({
      ...row,
      placed: row.x != null,
      suggested: suggested.has(row.n),
      mark: (row.more.length ? ` +${row.more.length}` : '') + (staged.has(row.id) ? ' *' : ''),
    })
  );
  $: selected = rows.find((r) => r.id === selectedId) ?? null;
  $: placedCount = rows.filter((r) => r.x != null).length;

  function field(id: string, name: 'name' | 'vn' | 'grid', e: Event) {
    dispatch('edit', { id, field: name, value: (e.currentTarget as HTMLInputElement).value });
  }
</script>

<div class="lg">
  <p class="lg-count">
    {$t('{N} of {M} placed', { N: placedCount, M: rows.length })}
  </p>
  <FilterBar
    bind:query
    placeholder={$t('Search number, name or grid')}
    searchLabel={$t('Search the legend')}
    active={filter === 'all' ? 0 : 1}
    resettable={!!query.trim() || filter !== 'all'}
    on:reset={() => {
      query = '';
      filter = 'all';
    }}
  >
    <select bind:value={filter} aria-label={$t('Show')}>
      <option value="all">{$t('All')}</option>
      <option value="unplaced">{$t('Unplaced')}</option>
      <option value="suggested">{$t('Suggested')}</option>
      <option value="placed">{$t('Placed')}</option>
      <option value="edited">{$t('Edited, unsaved')}</option>
    </select>
  </FilterBar>
  {#if matching}
    <button type="button" class="sb-btn is-sm is-block" on:click={() => dispatch('acceptMatching')}
      >{$t('Accept {N} matching numerals', { N: matching })}</button
    >
  {/if}
  <button
    type="button"
    class="sb-btn is-sm is-block"
    disabled={saving || !staged.size}
    on:click={() => dispatch('save')}
  >
    {saving ? $t('Saving…') : $t('Save {N}', { N: staged.size })}
  </button>
  {#if message}<p class="lg-msg" role="status">{message}</p>{/if}

  <LegendTable
    rows={shown}
    selectedN={selected?.n ?? null}
    showState
    empty={$t('No entries match.')}
    on:select={(e) => {
      const row = rows.find((r) => r.n === e.detail.n);
      if (row) dispatch('select', { id: row.id });
    }}
  >
    <svelte:fragment slot="extra" let:row>
      {#if failures[row.id]}<p class="lg-msg" role="alert">{failures[row.id]}</p>{/if}
      {#if row.id === selectedId}
        <div class="lg-edit">
          <label
            >{$t('Name')}
            <input value={row.name} maxlength="1000" on:change={(e) => field(row.id, 'name', e)} />
          </label>
          <label
            >{$t('Vietnamese name')}
            <input
              value={row.vn ?? ''}
              maxlength="1000"
              on:change={(e) => field(row.id, 'vn', e)}
            />
          </label>
          <label
            >{$t('Grid reference')}
            <input
              value={row.grid ?? ''}
              maxlength="1000"
              on:change={(e) => field(row.id, 'grid', e)}
            />
          </label>
          {#if row.suggested}
            <button
              type="button"
              class="sb-btn is-sm is-primary"
              on:click={() => dispatch('accept', { id: row.id })}
              >{$t('Accept detected numeral')}</button
            >
          {/if}
          {#each row.more as point, index (index)}
            <p class="lg-more">
              {$t('Point {N}', { N: index + 2 })} · {point[0]}, {point[1]}
              <button
                type="button"
                class="sb-btn is-sm"
                on:click={() => dispatch('removeMore', { id: row.id, index })}
                >{$t('Remove')}</button
              >
            </p>
          {/each}
          <button
            type="button"
            class="sb-btn is-sm"
            class:is-on={addingMore}
            disabled={row.x == null}
            title={$t('Or hold Shift and click the scan')}
            on:click={() => dispatch('addMore')}
            >{addingMore ? $t('Click the scan…') : $t('Add another point')}</button
          >
          <button
            type="button"
            class="sb-btn is-sm"
            disabled={row.x == null}
            on:click={() => dispatch('reset', { id: row.id })}>{$t('Remove point')}</button
          >
        </div>
      {/if}
    </svelte:fragment>
  </LegendTable>
  <p class="lg-keys">
    {$t(
      'N next unplaced · Enter accept numeral · Esc cancel · Delete removes · drag a pin to move it · Shift+click adds a point'
    )}
  </p>
</div>

<style>
  .lg {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.5rem;
    overflow-y: auto;
    min-height: 0;
  }
  .lg-count,
  .lg-keys,
  .lg-msg {
    margin: 0;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-edit {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    padding: 0.4rem 0.2rem;
  }
  .lg-edit label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.72rem;
  }
  .lg-more {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
    margin: 0;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-edit input {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }
</style>
