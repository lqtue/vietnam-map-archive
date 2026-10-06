<!--
  OcrSidebar.svelte — the OCR review table.

  Rows come from `ocrApi`; each is editable inline. An edit or a verdict is a
  draft — marked on the row, counted on Save — and one Save writes them all, as
  the legend tool does with its staged entries. The controller owns the shared
  working copy: geometry, new boxes and groups are cached drafts too.
  Search, status, category, confidence, run and group-by are one
  `FacetFilters` (the same bar /catalog wears, described by `core/utils/facets`)
  and the batch verdict buttons are OcrRunBar — this file declares the facets,
  loads the data and owns the filter/sort/group pipeline, the table itself, and the
  Save/reload pair on the filter bar's own line.
-->
<script lang="ts">
  import { CAT_COLORS } from '../shared/constants';
  import { createEventDispatcher, tick } from 'svelte';
  import '$styles/layouts/tool-page.css';
  import '$styles/components/shapes-table.css';
  import FacetFilters from '$lib/features/shared/FacetFilters.svelte';
  import GroupRow from '$lib/ui/GroupRow.svelte';
  import OcrRow from './OcrRow.svelte';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import OcrRunBar from './OcrRunBar.svelte';
  import type { EditableOcrExtraction } from '../shared/types';
  import { fetchExtractions, type OcrStatus } from '../shared/ocrApi';
  import { applySort } from '$lib/core/utils/tableSort';
  import { filterRows, groupRows, type Facet, type Selection } from '$lib/core/utils/facets';
  import { legendEntries, suspectRefs, entryForRow, indexGaps, printedLine } from './legendIndex';
  import { JOBS, jobBox, isPrintedJob, type JobKey } from './jobs';
  import { regionOf, REGION_LABELS } from './regionFilter';
  import type { OcrReviewController } from './ocrReviewController';
  import type { LayoutRegion } from '$lib/data/maps/triageTypes';

  const dispatch = createEventDispatcher<{
    zoomToExtraction: { globalX: number; globalY: number; globalW: number; globalH: number };
    loaded: { extractions: EditableOcrExtraction[]; groupingAvailable?: boolean };
    filter: { extractions: EditableOcrExtraction[] };
    select: { id: string };
    /** A job was chosen — fit the canvas to the part of the sheet it reads. */
    regionFocus: { bbox: [number, number, number, number] | null; printed: boolean };
    /** Rows per job, so the tabs can carry counts the panel already knows. */
    counts: Record<JobKey, number>;
  }>();

  export let mapId: string;
  export let review: OcrReviewController;
  export let selectedId: string | null = null;
  /** The sheet's layout, so rows can be reviewed one job at a time. */
  export let regions: LayoutRegion[] = [];
  /** Which of the four jobs is open. Owned by the panel that draws the tabs. */
  let job: JobKey | 'all' | 'custom' = 'all';

  $: extractions = $review.extractions.filter((r) => !r.text_group_id) as EditableOcrExtraction[];
  let loading = false;
  let error = '';
  let notice = '';

  const STATUSES: OcrStatus[] = ['pending', 'validated', 'rejected'];
  const titled = (v: string) => v.charAt(0).toUpperCase() + v.slice(1);

  /**
   * A reviewer arrives at undecided work, in the job's own categories; history
   * and the other categories are one chip away. Pending *and* validated together
   * is the point of the status chips: what has been done is what you check
   * against, so the same label is not read twice.
   */
  const freshSelection = (): Selection => ({
    status: ['pending', 'validated'],
  });
  let selected: Selection = freshSelection();
  /** The settled search box. */
  let query = '';
  let groupBy = '';

  $: filterRunId = selected.run?.[0] ?? '';
  /** What the chips go back to on reset — the open job's categories. */
  const defaults = { status: ['pending', 'validated'] };

  $: facets = [
    {
      key: 'status',
      label: 'Status',
      kind: 'many',
      primary: true,
      values: STATUSES,
      valueLabel: titled,
      value: (e) => e.status,
    },
    {
      // Offers one chip, and only when the index contradicts something.
      key: 'suspect',
      label: 'Check',
      kind: 'many',
      primary: true,
      valueLabel: () => 'Suspect',
      value: (e) => (suspects.has(e.id) ? 'suspect' : ''),
    },
    {
      key: 'category',
      label: 'Type',
      kind: 'many',
      color: (v) => CAT_COLORS[v],
      value: (r) => r._editCategory,
    },
    {
      key: 'region',
      label: 'Region',
      kind: 'many',
      value: (e) => regionOf(e, regions),
      valueLabel: (v) => REGION_LABELS[v as keyof typeof REGION_LABELS] ?? v,
    },
    { key: 'run', label: 'Run', kind: 'one', values: availableRuns, value: (e) => e.run_id ?? '' },
    {
      key: 'conf',
      label: 'Confidence',
      kind: 'min',
      min: 0,
      max: 1,
      step: 0.05,
      format: (n) => `${Math.round(n * 100)}%`,
      value: (e) => String(e.confidence),
    },
  ] satisfies Facet<EditableOcrExtraction>[];

  $: GROUPS = [
    { key: 'category', label: 'Type', of: (r: EditableOcrExtraction) => r._editCategory },
    // One status is one group; offer the grouping only when it can say something.
    ...((selected.status?.length ?? 0) === 1
      ? []
      : [
          {
            key: 'status',
            label: 'Status',
            of: (e: EditableOcrExtraction) => titled(e.status),
            order: STATUSES.map(titled),
          },
        ]),
    ...(availableRuns.length > 1 && !filterRunId
      ? [{ key: 'run', label: 'Run', of: (e: EditableOcrExtraction) => e.run_id ?? '' }]
      : []),
  ];
  $: grouper = GROUPS.find((g) => g.key === groupBy);

  // All status/run filtering is local after one paged load of the sheet.
  $: totals = { status: statusCounts };
  $: statusCounts = extractions.reduce<Record<string, number>>((counts, r) => {
    counts[r.status] = (counts[r.status] ?? 0) + 1;
    return counts;
  }, {});
  $: availableRuns = [...new Set(extractions.map((r) => r.run_id ?? '').filter(Boolean))].sort();
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

  function choosePreset() {
    if (job === 'custom') return;
    query = '';
    groupBy = '';
    const recipes: Record<JobKey | 'all', { category: string[]; region: string[] }> = {
      all: { category: [], region: [] },
      names: {
        category: ['street', 'place', 'hydrology', 'institution', 'building'],
        region: ['map', 'off'],
      },
      index: { category: [], region: ['legend', 'names'] },
      numbers: { category: ['legend_ref'], region: ['map', 'off'] },
      other: { category: ['title', 'legend', 'legend_entry', 'other'], region: [] },
    };
    selected = { ...selected, ...recipes[job], suspect: [] };
    sort =
      job === 'all' ? { key: 'text', asc: true } : { ...JOBS.find((j) => j.key === job)!.sort };
    dispatch('regionFocus', {
      bbox: job === 'all' || job === 'names' ? null : jobBox(job, regions),
      printed: job !== 'all' && isPrintedJob(job),
    });
  }
  const searchText = (e: EditableOcrExtraction) => `${e._editText} ${e._editCategory}`;

  /** The open job's rows: the partition comes first, and the facets count inside it. */
  $: jobRows = extractions;
  $: sorted = applySort(
    filterRows(jobRows, facets, selected, { query, text: searchText }),
    sort,
    sortValue
  );
  /**
   * Grouped, `visible` is the groups end to end, so the canvas and `j`/`k` walk
   * the rows in the order the table draws them — one list, read by everything.
   */
  $: groupsOfRows = grouper ? groupRows(sorted, grouper.of, grouper.order) : null;
  $: visible = groupsOfRows ? groupsOfRows.flatMap((g) => g.rows) : sorted;

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
  /** What is drawn, grouped. A group's count is its full size, not the rows under the cap. */
  $: drawn = groupsOfRows
    ? groupRows(shownRows, grouper!.of, grouper!.order).map((g) => ({
        ...g,
        count: groupsOfRows!.find((f) => f.key === g.key)?.rows.length ?? g.rows.length,
      }))
    : [{ key: '', rows: shownRows, count: visible.length }];

  $: jobTotal = extractions.length;

  /**
   * The Index job is a table, so it is shown as one: the category dropdown and
   * the confidence give way to the cell each line names and the number the
   * paper prints beside it. It is also ordered the way it is printed, which is
   * how a reader would find a line in it.
   */
  $: printedView = job === 'index';
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
      : [{ key: 'category', label: 'Type', klass: 'col-cat' }]),
    { key: 'actions', label: '', klass: 'col-actions', srLabel: 'Verdict', sortable: false },
  ] satisfies TableColumn[];

  /** The printed index's own report on itself — see `indexGaps`. */
  $: gaps = indexGaps(extractions);

  /**
   * One verdict over every pending row the filters currently show. The
   * confidence slider and the facets are the selection; sort by
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
    if (!filterRunId || saving) return;
    const ids = visible.filter((e) => e._editStatus === 'pending').map((e) => e.id);
    if (!ids.length) return;
    for (const id of ids) stage(id, status);
    lastBatch = { ids, status, count: ids.length };
    notice = `Drafted ${ids.length} verdicts.`;
  }
  let lastBatch: { ids: string[]; status: OcrStatus; count: number } | null = null;
  function undoBatch() {
    if (!lastBatch) return;
    for (const id of lastBatch.ids) stage(id, 'pending');
    lastBatch = null;
  }

  let loadGeneration = 0;
  export async function load() {
    if (!mapId || $review.saving) return;
    const requestedMap = mapId;
    const generation = ++loadGeneration;
    loading = true;
    error = '';
    try {
      const page = await fetchExtractions(requestedMap, { all: true });
      if (generation !== loadGeneration || mapId !== requestedMap) return;
      inputEls = {};
      rowEls = {};
      review.loaded(
        new CustomEvent('loaded', {
          detail: {
            extractions: [...page.extractions, ...(page.parts ?? [])],
            groupingAvailable: page.groupingAvailable,
          },
        })
      );
    } catch (e: any) {
      if (generation === loadGeneration) error = e.message;
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }
  $: if (mapId) {
    selected = freshSelection();
    job = 'all';
    lastBatch = null;
    load();
  }
  function stage(id: string, status: OcrStatus) {
    review.stage(id, { _editStatus: status });
  }
  $: dirtyCount = $review.dirtyCount;
  $: saving = $review.saving;
  function saveAll() {
    notice = '';
    lastBatch = null;
    return review.saveAll();
  }
  function discard() {
    if (confirm(`Discard ${dirtyCount} unsaved changes?`)) review.discard();
  }

  let inputEls: Record<string, HTMLInputElement> = {};
  let rowEls: Record<string, HTMLTableRowElement> = {};

  /** The full shortcut list is read once and then known — fold it away by default. */

  /** Open one OCR pass — what "load run" on the Run step asks for. */
  export function showRun(runId: string) {
    selected = { ...selected, run: [runId] };
  }

  export function getRunId(): string {
    return filterRunId || availableRuns[availableRuns.length - 1] || 'manual';
  }

  /**
   * Scrolls a row into view. `focusInput` puts the caret in its text field —
   * right after a canvas click, wrong during keyboard navigation, where the
   * keys have to keep reaching the page.
   */
  export function focusRow(id: string, focusInput = true) {
    // A box clicked on the canvas must have a row: choose its status if it is not.
    const status = extractions.find((e) => e.id === id)?.status;
    if (status && selected.status?.length && !selected.status.includes(status)) {
      selected = { ...selected, status: [...selected.status, status] };
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
  export function setRowStatus(id: string, status: OcrStatus) {
    const ext = extractions.find((e) => e.id === id);
    if (ext) stage(id, status);
  }
</script>

<div class="sidebar-content">
  <div class="ocr-filters">
    <select
      class="text-preset"
      aria-label="Text task preset"
      bind:value={job}
      on:change={choosePreset}
    >
      <option value="all">All text</option>
      {#if job === 'custom'}<option value="custom">Custom filters</option>{/if}
      <option value="names">Map labels</option>
      <option value="index">Printed lists</option>
      <option value="numbers">Numbers</option>
      <option value="other">Sheet notes</option>
    </select>
    <FacetFilters
      {facets}
      rows={jobRows}
      bind:selected
      {defaults}
      bind:query
      text={searchText}
      placeholder="Search text…"
      groups={GROUPS}
      bind:groupBy
      {totals}
      on:change={(e) => {
        if (e.detail.key === 'category' || e.detail.key === 'region') job = 'custom';
      }}
      on:reset={() => (job = 'all')}
    >
      <svelte:fragment slot="primary">
        <span class="shapes-count"
          >{visible.length}{visible.length !== jobRows.length ? `/${jobRows.length}` : ''}</span
        >
        <button
          type="button"
          class="sb-btn is-primary is-sm"
          on:click={saveAll}
          disabled={loading || saving || dirtyCount === 0}
          title="Save all locally cached text, verdict, box and group drafts to the database"
        >
          {saving ? 'Saving…' : `Save drafts${dirtyCount > 0 ? ` (${dirtyCount})` : ''}`}
        </button>
        {#if dirtyCount > 0}
          <button type="button" class="sb-btn is-ghost is-sm" on:click={discard} disabled={saving}>
            Discard
          </button>
        {/if}
        <button
          type="button"
          class="sb-btn is-icon"
          on:click={load}
          disabled={loading || saving}
          title="Reload saved labels; keep local drafts"
        >
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
      </svelte:fragment>
      <svelte:fragment slot="more">
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
    </FacetFilters>
  </div>

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

  {#if $review.notice || notice}
    <div class="ocr-notice">
      {$review.notice || notice}
      {#if lastBatch}
        <button type="button" class="notice-undo" on:click={undoBatch}>Undo</button>
      {/if}
    </div>
  {/if}

  {#if error || $review.error}
    <div class="ocr-error">{error || $review.error}</div>
  {/if}

  <!-- Table -->
  {#if loading}
    <div class="table-wrap custom-scrollbar">
      <p class="empty-state table-empty">Loading…</p>
    </div>
  {:else}
    <DataTable columns={COLUMNS} klass="is-dense" wrapClass="custom-scrollbar" bind:sort>
      {#each drawn as g (g.key)}
        {#if g.key}<GroupRow label={g.key} count={g.count} span={COLUMNS.length} />{/if}
        {#each g.rows as ext (ext.id)}
          {@const entry = entryForRow(ext, legendMap)}
          {@const reasons = suspects.get(ext.id)}
          {@const line = printedView ? printedLine(ext) : null}
          <OcrRow
            {ext}
            {entry}
            {reasons}
            {line}
            {printedView}
            {saving}
            selected={ext.id === selectedId}
            bind:rowEl={rowEls[ext.id]}
            bind:inputEl={inputEls[ext.id]}
            on:select
            on:zoomToExtraction
            on:edit={() =>
              review.stage(ext.id, { _editText: ext._editText, _editCategory: ext._editCategory })}
            on:verdict={(e) => stage(ext.id, e.detail.status)}
          />
        {/each}
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
              ? 'No rows match the filters — try another status, the categories or the confidence floor.'
              : `Nothing on this sheet for ${JOBS.find((j) => j.key === job)?.label ?? job}.`}
          </p>
        {/if}
      </svelte:fragment>
    </DataTable>
  {/if}

  <details class="text-help">
    <summary>Keyboard &amp; selection</summary>
    <div class="hint-bar">
      Click to select · Shift-click to group · j/k next/previous · e edit · v validate · x reject ·
      ,/. turn box · r turn sheet. All edits are drafts until Save.
    </div>
  </details>
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
  /* The bar's own plate. `FacetFilters` brings the search, the chips and the
     disclosure; this is only the panel it sits in. */
  .ocr-filters {
    padding: 0.6rem 0.75rem;
    background: var(--color-white);
    border-bottom: var(--border-thin);
    flex-shrink: 0;
  }
  .text-preset {
    width: 100%;
    font: inherit;
    font-size: 0.75rem;
    padding: 0.35rem;
    margin-bottom: 0.5rem;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    background: var(--color-bg);
    color: var(--color-text);
  }
  .text-help {
    font-size: 0.7rem;
    padding: 0.45rem 0.75rem;
    color: var(--sb-text-meta);
  }
  .text-help summary {
    cursor: pointer;
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
  .table-empty code {
    display: block;
    margin-top: 0.5rem;
    font-size: 0.72rem;
    color: var(--color-text);
    opacity: 0.6;
  }
</style>
