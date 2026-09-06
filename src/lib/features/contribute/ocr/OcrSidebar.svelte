<!--
  OcrSidebar.svelte — the OCR review table.

  Rows come from `ocrApi`; each is editable inline and auto-saves on blur.
  The confidence/category filters live in OcrFilterBar and the run picker plus
  write actions in OcrRunBar — this file owns the data, the filter/sort
  pipeline, and the table itself.
-->
<script lang="ts">
  import { OCR_CATEGORIES, STATUS_COLORS } from '../shared/constants';
  import { createEventDispatcher, tick } from 'svelte';
  import '$styles/layouts/tool-page.css';
  import '$styles/components/shapes-table.css';
  import OcrFilterBar from './OcrFilterBar.svelte';
  import OcrRunBar from './OcrRunBar.svelte';
  import type { EditableOcrExtraction } from '../shared/types';
  import {
    fetchExtractions,
    patchExtraction,
    batchSetStatus,
    revertRecent,
    withEditState,
    type OcrStatus,
  } from '../shared/ocrApi';
  import {
    toggleSort as nextSort,
    sortIcon as iconFor,
    applySort,
  } from '$lib/features/contribute/shared/tableSort';

  const dispatch = createEventDispatcher<{
    zoomToExtraction: { globalX: number; globalY: number; globalW: number; globalH: number };
    loaded: { extractions: EditableOcrExtraction[] };
    filter: { extractions: EditableOcrExtraction[] };
  }>();

  export let mapId: string;
  export let selectedId: string | null = null;

  let extractions: EditableOcrExtraction[] = [];
  let loading = false;
  let error = '';
  let notice = '';
  let statusCounts: Record<string, number> = {};
  let availableRuns: string[] = [];

  let filterStatus: '' | 'pending' | 'validated' | 'rejected' = '';
  let filterSearch = '';
  export let filterRunId = '';
  let filterMinConf = 0;
  let filterCategories = new Set<string>(OCR_CATEGORIES);

  type SortKey = 'text' | 'category' | 'confidence';
  let sort: { key: SortKey; asc: boolean } = { key: 'confidence', asc: false };

  function toggleSort(key: SortKey) {
    sort = nextSort(sort, key, (k) => k !== 'confidence');
  }
  function sortIcon(key: SortKey): string {
    return iconFor(sort, key);
  }

  function sortValue(e: EditableOcrExtraction, key: SortKey): string | number {
    if (key === 'text') return e._editText;
    if (key === 'category') return e._editCategory;
    return e.confidence;
  }

  $: visible = (() => {
    const list = extractions.filter((e) => {
      if (filterStatus && e.status !== filterStatus) return false;
      if (filterRunId && e.run_id !== filterRunId) return false;
      if (e.confidence < filterMinConf) return false;
      if (!filterCategories.has(e.category)) return false;
      if (filterSearch.trim()) {
        const q = filterSearch.trim().toLowerCase();
        if (!e._editText.toLowerCase().includes(q) && !e._editCategory.includes(q)) return false;
      }
      return true;
    });
    return applySort(list, sort, sortValue);
  })();

  $: {
    if (visible) dispatch('filter', { extractions: visible });
  }
  $: pendingShown = visible.filter((e) => e.status === 'pending').length;

  /**
   * Validate every pending row the filters currently show. The confidence
   * slider and category chips are the selection; sort by confidence, drag the
   * floor up until the rows look right, accept the lot. One PUT, one RPC call.
   * The 15-minute ⟲ is the undo, so a confirm() is enough here.
   */
  async function validateShown() {
    const ids = visible.filter((e) => e.status === 'pending').map((e) => e.id);
    if (!ids.length) return;
    const floor = Math.round(filterMinConf * 100);
    if (
      !confirm(
        `Validate ${ids.length} shown label${ids.length === 1 ? '' : 's'} (confidence ≥ ${floor}%)? Undo with ⟲ within 15 minutes.`
      )
    )
      return;
    loading = true;
    error = '';
    try {
      const count = await batchSetStatus(mapId, ids, 'validated');
      notice = `Validated ${count} label${count === 1 ? '' : 's'}.`;
      setTimeout(() => (notice = ''), 4000);
      await load();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  export async function load() {
    if (!mapId) return;
    loading = true;
    error = '';
    try {
      // Default to All runs (filterRunId '') so every category shows at once;
      // the run dropdown still lets you narrow to one. 2000 covers big legends.
      const page = await fetchExtractions(mapId, {
        limit: 2000,
        status: filterStatus,
        runId: filterRunId,
      });
      statusCounts = page.statusCounts;
      if (page.runIds.length) availableRuns = page.runIds;
      extractions = withEditState(page.extractions);
      // Row element maps are keyed by extraction id — drop the stale keys.
      inputEls = {};
      rowEls = {};
      dispatch('loaded', { extractions });
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // Reset run selection and reload when map changes
  $: if (mapId) {
    filterRunId = '';
    availableRuns = [];
    load();
  }

  async function save(ext: EditableOcrExtraction, status: OcrStatus) {
    ext._saving = true;
    extractions = extractions;
    error = '';
    try {
      await patchExtraction(mapId, {
        id: ext.id,
        text: ext._editText,
        category: ext._editCategory,
        status,
      });
      const old = ext.status as string;
      ext.status = status;
      ext.validated_at = status === 'validated' ? new Date().toISOString() : null;
      statusCounts[status] = (statusCounts[status] ?? 0) + 1;
      statusCounts[old] = Math.max(0, (statusCounts[old] ?? 1) - 1);
      if (filterStatus && filterStatus !== status) {
        extractions = extractions.filter((e) => e.id !== ext.id);
      } else {
        extractions = extractions;
      }
    } catch (e: any) {
      error = e.message;
    } finally {
      ext._saving = false;
      extractions = extractions;
    }
  }

  $: dirtyCount = extractions.filter(
    (e) =>
      e._editText !== (e.text_validated ?? e.text) ||
      e._editCategory !== (e.category_validated ?? e.category)
  ).length;

  async function saveAllEdits() {
    const dirty = extractions.filter(
      (e) =>
        e._editText !== (e.text_validated ?? e.text) ||
        e._editCategory !== (e.category_validated ?? e.category)
    );
    for (const ext of dirty) await commitText(ext);
  }

  async function commitText(ext: EditableOcrExtraction) {
    const textChanged = ext._editText !== (ext.text_validated ?? ext.text);
    const catChanged = ext._editCategory !== (ext.category_validated ?? ext.category);
    if (!textChanged && !catChanged) return;
    ext._saving = true;
    extractions = extractions;
    error = '';
    try {
      await patchExtraction(mapId, {
        id: ext.id,
        text: ext._editText,
        category: ext._editCategory,
        status: ext.status,
      });
      ext.text_validated = ext._editText;
      ext.category_validated = ext._editCategory;
    } catch (e: any) {
      error = e.message;
    } finally {
      ext._saving = false;
      extractions = extractions;
    }
  }

  // Two-step inline confirm — no native confirm()/alert() dialogs.
  let revertArmed = false;

  async function emergencyRevert() {
    if (!revertArmed) {
      revertArmed = true;
      setTimeout(() => (revertArmed = false), 4000);
      return;
    }
    revertArmed = false;
    loading = true;
    error = '';
    try {
      const count = await revertRecent(mapId, 15);
      notice = `Reverted ${count} item${count === 1 ? '' : 's'}.`;
      setTimeout(() => (notice = ''), 4000);
      await load();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  let inputEls: Record<string, HTMLInputElement> = {};
  let rowEls: Record<string, HTMLTableRowElement> = {};

  export function getRunId(): string {
    return filterRunId || availableRuns[availableRuns.length - 1] || 'manual';
  }

  export function focusRow(id: string) {
    // Ensure "All" filter so the row is visible
    if (filterStatus && extractions.find((e) => e.id === id)?.status !== filterStatus) {
      filterStatus = '';
    }
    tick().then(() => {
      rowEls[id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      inputEls[id]?.focus();
      inputEls[id]?.select();
    });
  }
</script>

<div class="sidebar-content">
  <!-- Toolbar -->
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
        placeholder="Filter text…"
        bind:value={filterSearch}
        class="shapes-search-input"
      />
    </div>
    <select
      class="filter-type-select"
      bind:value={filterStatus}
      on:change={load}
      aria-label="Filter by status"
    >
      <option value=""
        >All ({(statusCounts['pending'] ?? 0) +
          (statusCounts['validated'] ?? 0) +
          (statusCounts['rejected'] ?? 0)})</option
      >
      <option value="pending">Pending ({statusCounts['pending'] ?? 0})</option>
      <option value="validated">Validated ({statusCounts['validated'] ?? 0})</option>
      <option value="rejected">Rejected ({statusCounts['rejected'] ?? 0})</option>
    </select>
    <span class="shapes-count"
      >{visible.length}{visible.length !== extractions.length ? `/${extractions.length}` : ''}</span
    >
  </div>

  <OcrFilterBar bind:minConf={filterMinConf} bind:categories={filterCategories} />

  <OcrRunBar
    runs={availableRuns}
    bind:runId={filterRunId}
    {dirtyCount}
    {pendingShown}
    {loading}
    {revertArmed}
    on:change={load}
    on:save={saveAllEdits}
    on:validateShown={validateShown}
    on:revert={emergencyRevert}
    on:reload={load}
  />

  {#if revertArmed}
    <div class="ocr-notice">
      Revert the last 15 minutes of validations? Click ⟲ again to confirm.
    </div>
  {:else if notice}
    <div class="ocr-notice">{notice}</div>
  {/if}

  {#if error}
    <div class="ocr-error">{error}</div>
  {/if}

  <!-- Table -->
  <div class="table-wrap custom-scrollbar">
    {#if loading}
      <p class="empty-state table-empty">Loading…</p>
    {:else}
      <table class="data-table is-dense">
        <thead>
          <tr>
            <th class="col-dot"></th>
            <th class="col-text sortable" on:click={() => toggleSort('text')}
              >Text{sortIcon('text')}</th
            >
            <th class="col-cat sortable" on:click={() => toggleSort('category')}
              >Cat{sortIcon('category')}</th
            >
            <th class="col-conf sortable" on:click={() => toggleSort('confidence')}
              >Conf{sortIcon('confidence')}</th
            >
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          {#each visible as ext (ext.id)}
            <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
            <tr
              class="shape-tr status-{ext.status}"
              class:row-selected={ext.id === selectedId}
              bind:this={rowEls[ext.id]}
              on:dblclick={() =>
                dispatch('zoomToExtraction', {
                  globalX: ext.global_x,
                  globalY: ext.global_y,
                  globalW: ext.global_w,
                  globalH: ext.global_h,
                })}
              title="Double-click to zoom"
            >
              <td class="col-dot">
                {#if ext._saving}
                  <span class="dot dot--saving" title="saving…"></span>
                {:else}
                  <span
                    class="dot"
                    class:dot--dirty={ext._editText !== (ext.text_validated ?? ext.text) ||
                      ext._editCategory !== (ext.category_validated ?? ext.category)}
                    style="background:{STATUS_COLORS[ext.status]}"
                    title={ext.status}
                  ></span>
                {/if}
              </td>
              <td class="col-text">
                <input
                  class="cell-input"
                  type="text"
                  bind:value={ext._editText}
                  bind:this={inputEls[ext.id]}
                  placeholder="Text…"
                  on:blur={() => commitText(ext)}
                  on:keydown={(e) => {
                    if (e.key === 'Enter') {
                      commitText(ext);
                      (e.currentTarget as HTMLInputElement).blur();
                    }
                  }}
                  aria-label="Extraction text"
                />
              </td>
              <td class="col-cat">
                <div class="dropdown-wrap">
                  <select
                    class="cell-select"
                    bind:value={ext._editCategory}
                    on:change={() => commitText(ext)}
                    aria-label="Category"
                  >
                    {#each OCR_CATEGORIES as cat}
                      <option value={cat}>{cat}</option>
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
              <td class="col-conf">
                <span class="conf-badge" style="opacity:{0.4 + ext.confidence * 0.6}">
                  {(ext.confidence * 100).toFixed(0)}%
                </span>
              </td>
              <td class="col-actions">
                {#if ext._saving}
                  <span class="saving-dot">…</span>
                {:else}
                  <button
                    type="button"
                    class="row-action validate-action"
                    on:click={() => save(ext, ext.status === 'validated' ? 'pending' : 'validated')}
                    title={ext.status === 'validated' ? 'Unvalidate' : 'Validate (✓)'}
                    class:active-validate={ext.status === 'validated'}
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
                    class="row-action reject-action"
                    on:click={() => save(ext, ext.status === 'rejected' ? 'pending' : 'rejected')}
                    title={ext.status === 'rejected' ? 'Unreject' : 'Reject (✗)'}
                    class:active-reject={ext.status === 'rejected'}
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
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if !extractions.length}
        <p class="empty-state table-empty">
          No extractions for this map. Push a run to DB first:<br />
          <code>ocr.py batch --map-id … --db</code>
        </p>
      {:else if !visible.length}
        <p class="empty-state table-empty">No extractions match the current filter.</p>
      {/if}
    {/if}
  </div>

  <div class="hint-bar">
    Double-click row to zoom · Edit text → auto-saves on blur · <kbd>✓</kbd> validate · <kbd>✗</kbd> reject
  </div>
</div>

<style>
  .ocr-error {
    padding: 0.4rem 0.75rem;
    background: var(--tone-red-pale);
    color: var(--tone-red-ink);
    font-size: 0.72rem;
    border-bottom: var(--rule-hair) solid var(--rule);
    flex-shrink: 0;
  }
  .ocr-notice {
    padding: 0.4rem 0.75rem;
    background: var(--tone-amber-pale);
    color: var(--tone-amber-ink);
    font-size: 0.72rem;
    border-bottom: var(--rule-hair) solid var(--rule);
    flex-shrink: 0;
  }
  .shape-tr.status-validated td {
    background: var(--tone-green-wash);
  }
  .shape-tr.status-rejected td {
    background: var(--tone-red-wash);
    opacity: 0.65;
  }
  .shape-tr.row-selected td {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
    background: var(--tone-blue-wash) !important;
  }
  .dot--dirty {
    background: var(--status-warn) !important;
    border-style: dashed;
    border-color: var(--tone-amber-ink);
  }
  .dot--saving {
    background: transparent !important;
    border: 1.5px dashed var(--ink-soft);
    animation: pulse 0.8s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 0.4;
    }
    50% {
      opacity: 1;
    }
  }
  .col-text {
    min-width: 80px;
  }
  .col-cat {
    min-width: 70px;
  }
  .col-conf {
    width: 38px;
    text-align: right;
  }
  .col-actions {
    width: 48px;
    text-align: right;
    white-space: nowrap;
    padding-right: 0.5rem;
  }
  .conf-badge {
    font-size: 0.68rem;
    font-weight: var(--w-semi);
    font-variant-numeric: tabular-nums;
  }
  .saving-dot {
    font-size: 0.75rem;
    color: var(--ink);
    opacity: 0.4;
    padding-right: 0.4rem;
  }
  .validate-action:hover,
  .validate-action.active-validate {
    color: var(--tone-green-ink);
    background: var(--tone-green-pale);
  }
  .validate-action.active-validate {
    opacity: 1;
  }
  .reject-action:hover,
  .reject-action.active-reject {
    color: var(--tone-red-ink);
    background: var(--tone-red-pale);
  }
  .reject-action.active-reject {
    opacity: 1;
  }
  .table-empty code {
    display: block;
    margin-top: 0.5rem;
    font-size: 0.72rem;
    color: var(--ink);
    opacity: 0.6;
  }
  .empty-state {
    font-size: 0.8rem;
    color: var(--ink);
    opacity: 0.6;
  }
</style>
