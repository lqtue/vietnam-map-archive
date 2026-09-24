<!--
  OcrSidebar.svelte — the OCR review table.

  Rows come from `ocrApi`; each is editable inline and auto-saves on blur.
  The confidence/category filters live in OcrFilterBar and the batch verdict
  buttons in OcrRunBar — this file owns the data, the filter/sort pipeline,
  the table itself, and the toolbar's own Save/reload pair.
-->
<script lang="ts">
  import { OCR_CATEGORIES } from '../shared/constants';
  import { createEventDispatcher, onDestroy, tick } from 'svelte';
  import '$styles/layouts/tool-page.css';
  import '$styles/components/shapes-table.css';
  import OcrFilterBar from './OcrFilterBar.svelte';
  import OcrRow from './OcrRow.svelte';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import OcrRunBar from './OcrRunBar.svelte';
  import type { EditableOcrExtraction } from '../shared/types';
  import {
    fetchExtractions,
    batchSetStatus,
    withEditState,
    markRowSaving,
    saveRowStatus,
    saveRowText,
    isRowDirty,
    reviewedCategory,
    type OcrStatus,
  } from '../shared/ocrApi';
  import { toggleSort as nextSort, applySort } from '$lib/core/utils/tableSort';
  import { legendEntries, suspectRefs, entryForRow, indexGaps, printedLine } from './legendIndex';
  import { JOBS, jobOf, jobCounts, jobBox, isPrintedJob, type JobKey } from './jobs';
  import type { LayoutRegion } from '$lib/data/maps/triageTypes';

  const dispatch = createEventDispatcher<{
    zoomToExtraction: { globalX: number; globalY: number; globalW: number; globalH: number };
    loaded: { extractions: EditableOcrExtraction[] };
    filter: { extractions: EditableOcrExtraction[] };
    select: { id: string };
    /** A job was chosen — fit the canvas to the part of the sheet it reads. */
    regionFocus: { bbox: [number, number, number, number] | null; printed: boolean };
    /** Rows per job, so the tabs can carry counts the panel already knows. */
    counts: Record<JobKey, number>;
  }>();

  export let mapId: string;
  export let selectedId: string | null = null;
  /** The sheet's layout, so rows can be reviewed one job at a time. */
  export let regions: LayoutRegion[] = [];
  /** Which of the four jobs is open. Owned by the panel that draws the tabs. */
  export let job: JobKey = 'names';

  let extractions: EditableOcrExtraction[] = [];
  let loading = false;
  let error = '';
  let notice = '';
  let statusCounts: Record<string, number> = {};
  let availableRuns: string[] = [];

  /** A reviewer arrives at undecided work; history is an explicit choice. */
  let filterStatus: '' | 'pending' | 'validated' | 'rejected' = 'pending';
  let filterSearch = '';
  /** What the box holds right now; `filterSearch` is what the table answers to. */
  let searchInput = '';
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  /**
   * One keystroke re-filters and re-sorts every loaded row, hands the result to
   * the canvas, and walks 2000 OL features. Typing a street name is a dozen of
   * those. 150 ms is below the pause between keystrokes and above the cost of
   * the work, so it runs once per word rather than once per letter.
   */
  function onSearchInput() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => (filterSearch = searchInput), 150);
  }
  export let filterRunId = '';
  let filterMinConf = 0;
  let filterCategories = new Set<string>(OCR_CATEGORIES);
  let filterSuspectOnly = false;

  /**
   * The sheet's own printed legend, used twice: to name the numeral in a row
   * (a bare `37` is unreviewable — 37 and 87 look identical in the table), and
   * to flag the numerals that contradict the index. Both derive from the rows
   * already loaded, so neither costs a request.
   */
  $: legendMap = legendEntries(extractions);
  $: suspects = suspectRefs(extractions);

  type SortKey = 'text' | 'category' | 'confidence' | 'cell' | 'n';
  let sort: { key: SortKey; asc: boolean } = { key: 'confidence', asc: false };

  const onSort = (e: CustomEvent<{ key: string }>) => toggleSort(e.detail.key);

  function toggleSort(key: string) {
    sort = nextSort(sort, key as SortKey, (k) => k !== 'confidence');
  }

  function sortValue(e: EditableOcrExtraction, key: SortKey): string | number | null {
    // Ordered the way the paper orders them: the legend prints by number, so a
    // string sort would put 100 between 10 and 11. A line with no number is
    // blank, not `MAX_SAFE_INTEGER` — `applySort` keeps blanks last in both
    // directions, which the sentinel only managed in one.
    if (key === 'n') return printedLine(e)?.n ?? null;
    if (key === 'cell') return printedLine(e)?.grid ?? null;
    if (key === 'text') return e._editText;
    if (key === 'category') return e._editCategory;
    return e.confidence;
  }

  $: visible = (() => {
    const list = extractions.filter((e) => {
      if (filterStatus && e.status !== filterStatus) return false;
      if (filterRunId && e.run_id !== filterRunId) return false;
      if (e.confidence < filterMinConf) return false;
      if (!filterCategories.has(reviewedCategory(e))) return false;
      if (filterSuspectOnly && !suspects.has(e.id)) return false;
      if (jobOf(e, regions) !== job) return false;
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
   * Rows are rendered up to a cap, not all at once. Each one emits ~29 DOM
   * nodes, so 2000 of them is ~58,000 — for a list nobody reads end to end.
   * The filters are the navigation; this is only the tail being cut off it.
   * The cap grows rather than resets, so stepping past it with `j` or clicking
   * a far-down box on the canvas never hits a row that is not there (see
   * `focusRow`).
   */
  const RENDER_STEP = 300;
  let renderCap = RENDER_STEP;
  $: shownRows = visible.slice(0, renderCap);

  // What the loaded rows actually hold, so the chips are the sheet's own
  // vocabulary rather than the whole one. A saved correction is the category
  // a reviewer sees and filters, not the machine's original guess.
  $: categoryCounts = extractions.reduce<Record<string, number>>((acc, e) => {
    const category = reviewedCategory(e);
    return { ...acc, [category]: (acc[category] ?? 0) + 1 };
  }, {});
  $: jobTally = jobCounts(extractions, regions);
  $: dispatch('counts', jobTally);
  /** The job's own row count, before the confidence floor and the chips. */
  $: jobTotal = jobTally[job] ?? 0;

  /**
   * The Index job is a table, so it is shown as one: the category dropdown and
   * the confidence give way to the cell each line names and the number the
   * paper prints beside it. It is also ordered the way it is printed, which is
   * how a reader would find a line in it.
   */
  $: printedView = isPrintedJob(job);
  /* The middle columns are the job's: the Index job reads a printed list, so it
     answers "which cell, which line"; every other job keeps only its category. */
  $: COLUMNS = [
    { key: 'dot', label: '', klass: 'col-dot', srLabel: 'Status', sortable: false },
    { key: 'text', label: 'Text', klass: 'col-text' },
    ...(printedView
      ? [
          { key: 'cell', label: 'Cell', klass: 'col-cat' },
          { key: 'n', label: 'N', klass: 'col-conf num' },
        ]
      : [{ key: 'category', label: 'Cat', klass: 'col-cat' }]),
    { key: 'actions', label: '', klass: 'col-actions', srLabel: 'Verdict', sortable: false },
  ] satisfies TableColumn[];

  /**
   * Changing job reframes the canvas on the part of the sheet the job reads,
   * starts the table in that job's own order, and puts the category chips back
   * to the job's own set — they are a refinement inside a job, not the axis.
   *
   * `openedJob` rather than a plain `$:` on `job`: the reviewer is free to sort
   * and to uncheck a chip afterwards, and a reactive block that re-ran on any
   * dependency would undo their choice under them.
   */
  let openedJob: JobKey | '' = '';
  $: if (job !== openedJob && extractions.length) applyJob();

  function applyJob() {
    openedJob = job;
    const def = JOBS.find((j) => j.key === job);
    if (!def) return;
    sort = { ...def.sort };
    filterCategories = new Set(def.cats);
    filterSuspectOnly = false;
    dispatch('regionFocus', { bbox: jobBox(job, regions), printed: isPrintedJob(job) });
  }

  /** The printed index's own report on itself — see `indexGaps`. */
  $: gaps = indexGaps(extractions);

  /**
   * One verdict over every pending row the filters currently show. The
   * confidence slider and the category chips are the selection; sort by
   * confidence, drag the floor up until the rows look right, then accept or
   * reject the lot. One PUT.
   *
   * Both verdicts remember their ids so the result notice can undo precisely
   * this operation. A reject has no validation stamp, so a broad time-window
   * revert could never have safely recovered it.
   */
  async function batchVerdict(status: 'validated' | 'rejected') {
    // A model pass is the unit that can be trusted or rolled back. Never let
    // the default "All runs" view silently make a batch decision across runs.
    if (!filterRunId) return;
    const ids = visible.filter((e) => e.status === 'pending').map((e) => e.id);
    if (!ids.length) return;
    const verb = status === 'validated' ? 'Validate' : 'Reject';
    const floor = Math.round(filterMinConf * 100);
    if (
      !confirm(
        `${verb} ${ids.length} label${ids.length === 1 ? '' : 's'} from ${filterRunId} (confidence ≥ ${floor}%)?`
      )
    )
      return;
    loading = true;
    error = '';
    try {
      const count = await batchSetStatus(mapId, ids, status);
      lastBatch = { ids, status, count };
      notice = `${status === 'validated' ? 'Validated' : 'Rejected'} ${count} label${count === 1 ? '' : 's'}.`;
      await load();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  /** The last batch verdict is an operation-level undo, never a broad time sweep. */
  let lastBatch: { ids: string[]; status: OcrStatus; count: number } | null = null;

  async function undoBatch() {
    if (!lastBatch) return;
    loading = true;
    error = '';
    try {
      const count = await batchSetStatus(mapId, lastBatch.ids, 'pending');
      lastBatch = null;
      notice = `Put ${count} label${count === 1 ? '' : 's'} back to pending.`;
      setTimeout(() => (notice = ''), 4000);
      await load();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onDestroy(() => {
    if (searchTimer) clearTimeout(searchTimer);
  });

  export async function load() {
    if (!mapId) return;
    loading = true;
    error = '';
    try {
      // Pending is the default review queue. A reviewer can explicitly open
      // history or a single run from the filters above.
      const page = await fetchExtractions(mapId, {
        limit: 2000,
        status: filterStatus,
        runId: filterRunId,
      });
      statusCounts = page.statusCounts;
      // eslint-disable-next-line svelte/infinite-reactive-loop
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

  // Reset run selection and reload when map changes.
  //
  // `load()` assigns `availableRuns`, but this statement only *reads* `mapId`,
  // so `availableRuns` is not one of its dependencies and there is no loop.
  $: if (mapId) {
    filterStatus = 'pending';
    filterRunId = '';
    availableRuns = [];
    // eslint-disable-next-line svelte/infinite-reactive-loop
    load();
  }

  async function save(ext: EditableOcrExtraction, status: OcrStatus) {
    extractions = markRowSaving(extractions, ext.id, true);
    error = '';
    try {
      ({ rows: extractions, statusCounts } = await saveRowStatus(
        mapId,
        { rows: extractions, statusCounts },
        ext.id,
        status,
        filterStatus
      ));
    } catch (e: any) {
      error = e.message;
    } finally {
      extractions = markRowSaving(extractions, ext.id, false);
    }
  }

  $: dirtyCount = extractions.filter(isRowDirty).length;

  async function saveAllEdits() {
    // Snapshot the ids first: each commit reassigns `extractions`.
    for (const id of extractions.filter(isRowDirty).map((e) => e.id)) {
      const row = extractions.find((e) => e.id === id);
      if (row) await commitText(row);
    }
  }

  async function commitText(ext: EditableOcrExtraction) {
    if (!isRowDirty(ext)) return;
    extractions = markRowSaving(extractions, ext.id, true);
    error = '';
    try {
      extractions = await saveRowText(mapId, extractions, ext.id);
    } catch (e: any) {
      error = e.message;
    } finally {
      extractions = markRowSaving(extractions, ext.id, false);
    }
  }

  let inputEls: Record<string, HTMLInputElement> = {};
  let rowEls: Record<string, HTMLTableRowElement> = {};

  /** The full shortcut list is read once and then known — fold it away by default. */
  let hintExpanded = false;

  export function getRunId(): string {
    return filterRunId || availableRuns[availableRuns.length - 1] || 'manual';
  }

  /**
   * Scrolls a row into view. `focusInput` puts the caret in its text field —
   * right after a canvas click, wrong during keyboard navigation, where the
   * keys have to keep reaching the page.
   */
  export function focusRow(id: string, focusInput = true) {
    // Ensure "All" filter so the row is visible
    if (filterStatus && extractions.find((e) => e.id === id)?.status !== filterStatus) {
      filterStatus = '';
    }
    // A row past the render cap has no element to scroll to. Raise the cap to
    // reach it, so `j`/`k` and a canvas click behave the same at row 50 and at
    // row 1500.
    const at = visible.findIndex((e) => e.id === id);
    if (at >= renderCap) renderCap = at + RENDER_STEP;
    tick().then(() => {
      rowEls[id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      if (!focusInput) return;
      inputEls[id]?.focus();
      inputEls[id]?.select();
    });
  }

  /** One row's status, written the same way the row buttons write it. */
  export async function setRowStatus(id: string, status: OcrStatus) {
    const ext = extractions.find((e) => e.id === id);
    if (ext) await save(ext, status);
  }
</script>

<div class="sidebar-content">
  <!-- Toolbar -->
  <div class="shapes-toolbar">
    <div class="sb-search is-compact">
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
        bind:value={searchInput}
        on:input={onSearchInput}
        class="sb-search-input"
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
    <button
      type="button"
      class="sb-btn is-primary is-sm"
      on:click={saveAllEdits}
      disabled={loading || dirtyCount === 0}
      title="Save all pending text/category edits"
    >
      Save{dirtyCount > 0 ? ` (${dirtyCount})` : ''}
    </button>
    <button type="button" class="sb-btn is-icon" on:click={load} disabled={loading} title="Reload">
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
      </svg>
    </button>
  </div>

  <OcrFilterBar
    bind:minConf={filterMinConf}
    bind:categories={filterCategories}
    bind:suspectOnly={filterSuspectOnly}
    suspectCount={suspects.size}
    counts={categoryCounts}
    hint={JOBS.find((j) => j.key === job)?.hint ?? ''}
  >
    <svelte:fragment slot="sweep">
      {#if availableRuns.length > 1}
        <select
          class="filter-type-select run-select"
          bind:value={filterRunId}
          on:change={load}
          aria-label="Filter by run"
        >
          <option value="">All runs</option>
          {#each availableRuns as r (r)}
            <option value={r}>{r}</option>
          {/each}
        </select>
      {/if}
      <OcrRunBar
        {pendingShown}
        {loading}
        batchRunId={filterRunId}
        on:validateShown={() => batchVerdict('validated')}
        on:rejectShown={() => batchVerdict('rejected')}
      />
      {#if !filterRunId && pendingShown > 0}
        <div class="batch-scope">Choose one run above to enable a batch verdict.</div>
      {:else if filterRunId}
        <div class="batch-scope">Batch scope · {filterRunId} · {pendingShown} pending</div>
      {/if}
    </svelte:fragment>
  </OcrFilterBar>

  {#if gaps && (job === 'index' || job === 'numbers')}
    <div class="index-gaps">
      <strong>{gaps.min}–{gaps.max}</strong>
      · {gaps.missing.length} missing{#if gaps.missing.length}
        <span class="gap-list">{gaps.missing.join(', ')}</span>
      {/if}
      · {gaps.repeated.length} repeated{#if gaps.repeated.length}
        <span class="gap-list">{gaps.repeated.join(', ')}</span>
      {/if}
    </div>
  {/if}

  {#if notice}
    <div class="ocr-notice">
      {notice}
      {#if lastBatch}
        <button type="button" class="notice-undo" on:click={undoBatch}>Undo</button>
      {/if}
    </div>
  {/if}

  {#if error}
    <div class="ocr-error">{error}</div>
  {/if}

  <!-- Table -->
  {#if loading}
    <div class="table-wrap custom-scrollbar">
      <p class="empty-state table-empty">Loading…</p>
    </div>
  {:else}
    <DataTable columns={COLUMNS} klass="is-dense" wrapClass="custom-scrollbar" bind:sort>
      {#each shownRows as ext (ext.id)}
        {@const entry = entryForRow(ext, legendMap)}
        {@const reasons = suspects.get(ext.id)}
        {@const line = printedView ? printedLine(ext) : null}
        <OcrRow
          {ext}
          {entry}
          {reasons}
          {line}
          {printedView}
          selected={ext.id === selectedId}
          bind:rowEl={rowEls[ext.id]}
          bind:inputEl={inputEls[ext.id]}
          on:select
          on:zoomToExtraction
          on:commit={() => commitText(ext)}
          on:verdict={(e) => save(ext, e.detail.status)}
        />
      {/each}
      <svelte:fragment slot="after">
        {#if visible.length > shownRows.length}
          <button type="button" class="render-more" on:click={() => (renderCap += RENDER_STEP)}>
            Showing {shownRows.length} of {visible.length} — show {RENDER_STEP} more
          </button>
        {/if}
        {#if !extractions.length}
          <p class="empty-state table-empty">
            No extractions for this map. Push a run to DB first:<br />
            <code>ocr.py batch --map-id … --db</code>
          </p>
        {:else if !visible.length}
          <p class="empty-state table-empty">
            {jobTotal
              ? 'No rows match the filters — try the confidence floor or the categories.'
              : `Nothing on this sheet for ${JOBS.find((j) => j.key === job)?.label ?? job}.`}
          </p>
        {/if}
      </svelte:fragment>
    </DataTable>
  {/if}

  <div class="hint-bar">
    <kbd>j</kbd>/<kbd>k</kbd> next/prev · <kbd>v</kbd> validate · <kbd>x</kbd> reject
    <button
      type="button"
      class="sb-btn is-icon is-ghost hint-toggle"
      on:click={() => (hintExpanded = !hintExpanded)}
      aria-expanded={hintExpanded}
      aria-label={hintExpanded ? 'Hide more shortcuts' : 'Show more shortcuts'}
      title="More shortcuts"
    >
      ?
    </button>
  </div>
  {#if hintExpanded}
    <div class="hint-bar">
      Click row to select · double-click to zoom · <kbd>e</kbd> edit text ·
      <kbd>,</kbd>/<kbd>.</kbd> turn label · <kbd>r</kbd> turn sheet
    </div>
  {/if}
</div>

<style>
  .ocr-error {
    padding: 0.4rem 0.75rem;
    background: var(--tone-red-pale);
    color: var(--tone-red-ink);
    font-size: 0.72rem;
    border-bottom: var(--border-thin);
    flex-shrink: 0;
  }
  .ocr-notice {
    padding: 0.4rem 0.75rem;
    background: var(--tone-amber-pale);
    color: var(--tone-amber-ink);
    font-size: 0.72rem;
    border-bottom: var(--border-thin);
    flex-shrink: 0;
  }
  .batch-scope {
    padding: 0.3rem 0.75rem;
    background: var(--tone-blue-wash);
    border-bottom: var(--border-thin);
    color: var(--color-text);
    font-size: 0.66rem;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  /* A link inside the notice plate, so it inherits the plate's ink instead of
     introducing a second colour to a strip that is already a warning. */
  /* The run picker is a filter, so it sits with the filters. It only appears
     when a sheet has been read more than once — which is when choosing between
     runs is a question at all. */
  .run-select {
    font-family: ui-monospace, monospace;
    font-size: 0.66rem;
    max-width: 11rem;
  }
  /* The printed index numbers itself 1..N with no gaps, so this one line is the
     whole quality report for a block — which reading 235 rows never gives you.
     The numbers wrap rather than scroll: a long list is itself the finding. */
  .index-gaps {
    padding: 0.35rem 0.75rem;
    font-size: 0.68rem;
    color: var(--color-text);
    background: var(--color-bg);
    border-bottom: var(--border-thin);
    flex-shrink: 0;
  }
  .gap-list {
    font-variant-numeric: tabular-nums;
    opacity: 0.65;
  }
  .render-more {
    display: block;
    width: 100%;
    padding: 0.5rem;
    background: none;
    border: 0;
    border-top: var(--border-thin);
    font: inherit;
    font-size: 0.68rem;
    color: var(--color-text);
    opacity: 0.6;
    cursor: pointer;
  }
  .render-more:hover {
    opacity: 1;
  }
  .notice-undo {
    background: none;
    border: 0;
    padding: 0;
    margin-left: 0.4rem;
    font: inherit;
    font-weight: var(--font-bold);
    color: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  /* Sits inline with the compact hint line rather than on its own row. */
  .hint-toggle {
    margin-left: 0.35rem;
    vertical-align: middle;
  }
  .table-empty code {
    display: block;
    margin-top: 0.5rem;
    font-size: 0.72rem;
    color: var(--color-text);
    opacity: 0.6;
  }
</style>
