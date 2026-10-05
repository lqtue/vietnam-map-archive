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
  import { visibleRows, type LegendRow, type RowFilter, type RowSort } from './legendStage';

  export let rows: LegendRow[] = [];
  export let selectedId: string | null = null;
  export let filter: RowFilter = 'all';
  export let sort: RowSort = 'n';
  export let query = '';
  export let staged: Set<string> = new Set();
  export let failures: Record<string, string> = {};
  export let saving = false;
  export let message = '';

  const dispatch = createEventDispatcher<{
    select: { id: string };
    edit: { id: string; field: 'name' | 'vn' | 'grid'; value: string };
    reset: { id: string };
    save: void;
  }>();

  $: shown = visibleRows(rows, { filter, sort, query, staged, keepId: selectedId });
  $: placedCount = rows.filter((r) => r.x != null).length;

  function field(id: string, name: 'name' | 'vn' | 'grid', e: Event) {
    dispatch('edit', { id, field: name, value: (e.currentTarget as HTMLInputElement).value });
  }
</script>

<div class="lg">
  <p class="lg-count">
    {$t('{N} of {M} placed', { N: placedCount, M: rows.length })}
  </p>
  <input
    type="search"
    class="lg-search"
    placeholder={$t('Search number, name or grid')}
    aria-label={$t('Search the legend')}
    bind:value={query}
  />
  <div class="lg-controls">
    <label
      >{$t('Show')}
      <select bind:value={filter}>
        <option value="all">{$t('All')}</option>
        <option value="unplaced">{$t('Unplaced')}</option>
        <option value="placed">{$t('Placed')}</option>
        <option value="edited">{$t('Edited, unsaved')}</option>
      </select>
    </label>
    <label
      >{$t('Sort')}
      <select bind:value={sort}>
        <option value="n">{$t('Number')}</option>
        <option value="name">{$t('Name')}</option>
        <option value="grid">{$t('Grid')}</option>
        <option value="unplaced">{$t('Unplaced first')}</option>
      </select>
    </label>
  </div>
  <button
    type="button"
    class="sb-btn is-sm is-block"
    disabled={saving || !staged.size}
    on:click={() => dispatch('save')}
  >
    {saving ? $t('Saving…') : $t('Save {N}', { N: staged.size })}
  </button>
  {#if message}<p class="lg-msg" role="status">{message}</p>{/if}

  {#if !shown.length}<p class="lg-msg">{$t('No entries match.')}</p>{/if}
  <ul class="lg-list">
    {#each shown as row (row.id)}
      <li>
        <button
          type="button"
          class="lg-row"
          class:is-on={row.id === selectedId}
          aria-current={row.id === selectedId ? 'true' : undefined}
          on:click={() => dispatch('select', { id: row.id })}
        >
          <span class="lg-n">{row.n}</span>
          <span class="lg-name"
            >{row.name}{#if row.vn}<em> · {row.vn}</em>{/if}</span
          >
          {#if row.grid}<span class="lg-grid">{row.grid}</span>{/if}
          <span class="lg-state" class:is-placed={row.x != null}
            >{row.x != null ? $t('placed') : $t('unplaced')}{staged.has(row.id) ? ' *' : ''}</span
          >
        </button>
        {#if failures[row.id]}<p class="lg-msg" role="alert">{failures[row.id]}</p>{/if}
        {#if row.id === selectedId}
          <div class="lg-edit">
            <label
              >{$t('Name')}
              <input
                value={row.name}
                maxlength="1000"
                on:change={(e) => field(row.id, 'name', e)}
              />
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
            <button
              type="button"
              class="sb-btn is-sm"
              disabled={row.x == null}
              on:click={() => dispatch('reset', { id: row.id })}>{$t('Remove point')}</button
            >
          </div>
        {/if}
      </li>
    {/each}
  </ul>
  <p class="lg-keys">
    {$t(
      'N next unplaced · Enter accept numeral · Esc cancel · Delete removes · drag a pin to move it'
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
  .lg-search {
    width: 100%;
    box-sizing: border-box;
  }
  .lg-controls {
    display: flex;
    gap: 0.5rem;
  }
  .lg-controls label {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .lg-row {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    width: 100%;
    padding: 0.25rem 0.2rem;
    background: none;
    border: 0;
    border-top: var(--sb-border);
    text-align: left;
    font-size: 0.78rem;
    color: var(--sb-text);
    cursor: pointer;
  }
  .lg-row:hover {
    background: var(--sb-row-hover);
  }
  .lg-row.is-on {
    background: var(--sb-accent-yellow);
  }
  .lg-n {
    flex: 0 0 1.4rem;
    font-weight: 800;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-name {
    flex: 1;
    min-width: 0;
  }
  .lg-name em {
    font-style: normal;
    color: var(--sb-text-meta);
  }
  .lg-grid,
  .lg-state {
    flex: 0 0 auto;
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
  .lg-state.is-placed {
    color: var(--color-text);
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
  .lg-edit input {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }
</style>
