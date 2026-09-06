<!--
  TraceSidebar.svelte — Sidebar content for trace/polygon mode.
  Shows a sortable, filterable table of placed footprint shapes.
-->
<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import '$styles/layouts/tool-page.css';
  import '$styles/components/shapes-table.css';
  import {
    toggleSort as nextSort,
    sortIcon as iconFor,
    applySort,
  } from '$lib/features/contribute/shared/tableSort';
  import type { FootprintSubmission, FeatureType } from '$lib/data/maps/footprintTypes';
  import { FEATURE_TYPE_LABELS, FEATURE_TYPE_COLORS } from '$lib/data/maps/footprintTypes';

  const dispatch = createEventDispatcher<{
    removeFootprint: { footprintId: string };
    updateFootprintMeta: {
      footprintId: string;
      name?: string;
      featureType?: FeatureType;
      category?: string | null;
    };
  }>();

  export let traceCategories: string[] = [];
  export let placedFootprints: FootprintSubmission[] = [];
  export let drawMode: 'trace' | 'select' = 'trace';
  export let newFootprintId: string | null = null;

  function featureColor(ft: FeatureType) {
    return FEATURE_TYPE_COLORS[ft] ?? FEATURE_TYPE_COLORS.other;
  }
  const FEATURE_TYPES = Object.keys(FEATURE_TYPE_LABELS) as FeatureType[];

  $: categoryOptions = traceCategories.map((cat) => ({ val: cat, label: cat }));

  type SortKey = 'name' | 'type' | 'category';
  let sort: { key: SortKey; asc: boolean } = { key: 'name', asc: true };
  let filterType: FeatureType | '' = '';
  let filterSearch = '';

  function toggleSort(key: SortKey) {
    sort = nextSort(sort, key);
  }
  function sortIcon(key: SortKey): string {
    return iconFor(sort, key);
  }

  function sortValue(fp: FootprintSubmission, key: SortKey): string {
    if (key === 'name') return fp.name ?? '';
    if (key === 'type') return fp.featureType;
    return fp.category ?? '';
  }

  $: visibleFootprints = (() => {
    let list = [...placedFootprints];
    if (filterType) list = list.filter((fp) => fp.featureType === filterType);
    if (filterSearch.trim()) {
      const q = filterSearch.trim().toLowerCase();
      list = list.filter(
        (fp) =>
          (fp.name ?? '').toLowerCase().includes(q) || (fp.category ?? '').toLowerCase().includes(q)
      );
    }
    return applySort(list, sort, sortValue);
  })();

  let draftLabels: Record<string, string> = {};
  let inputEls: Record<string, HTMLInputElement> = {};

  $: {
    for (const fp of placedFootprints) {
      if (!(fp.id in draftLabels)) draftLabels[fp.id] = fp.name ?? '';
    }
    const ids = new Set(placedFootprints.map((f) => f.id));
    for (const k of Object.keys(draftLabels)) {
      if (!ids.has(k)) delete draftLabels[k];
    }
    draftLabels = draftLabels;
  }

  $: if (newFootprintId) {
    tick().then(() => {
      inputEls[newFootprintId!]?.focus();
      inputEls[newFootprintId!]?.select();
    });
  }

  function commitLabel(fp: FootprintSubmission) {
    const draft = (draftLabels[fp.id] ?? '').trim();
    if (draft && draft !== fp.name) {
      dispatch('updateFootprintMeta', { footprintId: fp.id, name: draft });
    }
  }

  function commitType(fp: FootprintSubmission, ft: FeatureType) {
    if (ft !== fp.featureType)
      dispatch('updateFootprintMeta', { footprintId: fp.id, featureType: ft });
  }

  function commitCategory(fp: FootprintSubmission, cat: string) {
    const val = cat || null;
    if (val !== fp.category) dispatch('updateFootprintMeta', { footprintId: fp.id, category: val });
  }

  let confirmDeleteId: string | null = null;
  function requestDelete(fpId: string) {
    confirmDeleteId = fpId;
  }
  function cancelDelete() {
    confirmDeleteId = null;
  }
  function executeDelete(fpId: string) {
    confirmDeleteId = null;
    dispatch('removeFootprint', { footprintId: fpId });
  }
</script>

<div class="sidebar-content">
  <div class="shapes-toolbar">
    <div class="shapes-search">
      <svg
        width="13"
        height="13"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="7" cy="7" r="5" /><path d="M15 15l-3.5-3.5" />
      </svg>
      <input
        type="text"
        placeholder="Filter by name…"
        bind:value={filterSearch}
        class="shapes-search-input"
      />
    </div>
    <select class="filter-type-select" bind:value={filterType} aria-label="Filter by type">
      <option value="">All types</option>
      {#each FEATURE_TYPES as ft}
        <option value={ft}>{FEATURE_TYPE_LABELS[ft]}</option>
      {/each}
    </select>
    <span class="shapes-count"
      >{visibleFootprints.length}{visibleFootprints.length !== placedFootprints.length
        ? ` / ${placedFootprints.length}`
        : ''}</span
    >
  </div>

  <div class="table-wrap custom-scrollbar">
    <table class="data-table is-dense">
      <thead>
        <tr>
          <th class="col-dot"></th>
          <th class="col-name sortable" on:click={() => toggleSort('name')}
            >Name{sortIcon('name')}</th
          >
          <th class="col-type sortable" on:click={() => toggleSort('type')}
            >Type{sortIcon('type')}</th
          >
          <th class="col-cat sortable" on:click={() => toggleSort('category')}
            >Category{sortIcon('category')}</th
          >
          <th class="col-actions"></th>
        </tr>
      </thead>
      <tbody>
        {#each visibleFootprints as fp (fp.id)}
          <tr class="shape-tr">
            <td class="col-dot"
              ><span class="dot" style="background:{featureColor(fp.featureType)}"></span></td
            >
            <td class="col-name">
              <input
                class="cell-input"
                type="text"
                bind:value={draftLabels[fp.id]}
                bind:this={inputEls[fp.id]}
                placeholder="Name…"
                on:blur={() => commitLabel(fp)}
                on:keydown={(e) => {
                  if (e.key === 'Enter') {
                    commitLabel(fp);
                    e.currentTarget.blur();
                  }
                }}
                aria-label="Shape name"
              />
            </td>
            <td class="col-type">
              <div class="dropdown-wrap">
                <select
                  class="cell-select"
                  value={fp.featureType}
                  on:change={(e) => commitType(fp, e.currentTarget.value as FeatureType)}
                  aria-label="Feature type"
                >
                  <option value="other" disabled={fp.featureType !== 'other'}>— Type —</option>
                  {#each FEATURE_TYPES as ft}
                    {#if ft !== 'other'}
                      <option value={ft}>{FEATURE_TYPE_LABELS[ft]}</option>
                    {/if}
                  {/each}
                  <option value="other">Other</option>
                </select>
                <svg
                  class="dropdown-chevron"
                  width="10"
                  height="10"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"><polyline points="4 6 8 10 12 6" /></svg
                >
              </div>
            </td>
            <td class="col-cat">
              <div class="dropdown-wrap">
                <select
                  class="cell-select"
                  value={fp.category ?? ''}
                  on:change={(e) => commitCategory(fp, e.currentTarget.value)}
                  aria-label="Category"
                >
                  <option value="">— Category —</option>
                  {#each categoryOptions as opt}
                    <option value={opt.val}>{opt.label}</option>
                  {/each}
                </select>
                <svg
                  class="dropdown-chevron"
                  width="10"
                  height="10"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"><polyline points="4 6 8 10 12 6" /></svg
                >
              </div>
            </td>
            <td class="col-actions">
              {#if confirmDeleteId === fp.id}
                <button
                  type="button"
                  class="row-action confirm-yes"
                  on:click={() => executeDelete(fp.id)}
                  title="Confirm delete"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"
                    stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
                  >
                </button>
                <button
                  type="button"
                  class="row-action confirm-no"
                  on:click={cancelDelete}
                  title="Cancel"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg
                  >
                </button>
              {:else}
                <button
                  type="button"
                  class="row-action delete-action"
                  on:click={() => requestDelete(fp.id)}
                  aria-label="Remove shape"
                  title="Delete"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    ><polyline points="3 6 5 6 21 6" /><path
                      d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
                    /></svg
                  >
                </button>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if !placedFootprints.length}
      <p class="empty-state table-empty">
        {drawMode === 'trace' ? 'Draw a shape on the map to start.' : 'No shapes yet.'}
      </p>
    {:else if !visibleFootprints.length}
      <p class="empty-state table-empty">No shapes match the current filter.</p>
    {/if}
  </div>

  <div class="hint-bar">
    {#if drawMode === 'trace'}
      <kbd>Enter</kbd> or double-click to finish · <kbd>Ctrl+Z</kbd> undo · <kbd>Esc</kbd> cancel
    {:else}
      Click shape to select · drag vertices to edit · <kbd>Delete</kbd> to remove
    {/if}
  </div>
</div>

<style>
  /* Table chrome lives in $styles/components/shapes-table.css — only the
     column widths and delete-confirm colours are trace-specific. */
  .col-name {
    min-width: 70px;
  }
  .col-type {
    min-width: 75px;
  }
  .col-cat {
    min-width: 80px;
  }
  .col-actions {
    width: 52px;
    text-align: right;
    white-space: nowrap;
    padding-right: 0.5rem;
  }
  .delete-action:hover {
    color: var(--tone-red-ink);
    background: var(--tone-red-pale);
  }
  .confirm-yes {
    opacity: 0.8;
    color: var(--tone-red-ink);
    background: var(--tone-red-pale);
  }
  .confirm-yes:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--status-bad) 28%, var(--ground-raised));
    color: color-mix(in srgb, var(--status-bad) 70%, var(--ink));
  }
  .confirm-no {
    opacity: 0.6;
  }
  .confirm-no:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
  }
</style>
