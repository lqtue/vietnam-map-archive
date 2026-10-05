<!--
  OcrSidebar.svelte — the OCR review table.

  Rows come from `ocrApi`; each is editable inline. An edit or a verdict is a
  draft — marked on the row, counted on Save — and one Save writes them all, as
  the legend tool does with its staged entries. Moving or resizing a box on the
  canvas still writes at once (`ocrReviewController`).
  Search, status, category, confidence, run and group-by are one
  `FacetFilters` (the same bar /catalog wears, described by `core/utils/facets`)
  and the batch verdict buttons are OcrRunBar — this file declares the facets,
  owns the data and the filter/sort/group pipeline, the table itself, and the
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
  import {
    fetchExtractions,
    batchSetStatus,
    withEditState,
    isRowDirty,
    saveDrafts,
    promoteSaved,
    reviewedCategory,
    type OcrStatus,
  } from '../shared/ocrApi';
  import { toggleSort as nextSort, applySort } from '$lib/core/utils/tableSort';
  import { filterRows, groupRows, type Facet, type Selection } from '$lib/core/utils/facets';
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

  const STATUSES: OcrStatus[] = ['pending', 'validated', 'rejected'];
  const titled = (v: string) => v.charAt(0).toUpperCase() + v.slice(1);

  /**
   * A reviewer arrives at undecided work, in the job's own categories; history
   * and the other categories are one chip away. Pending *and* validated together
   * is the point of the status chips: what has been done is what you check
   * against, so the same label is not read twice.
   */
  const freshSelection = (): Selection => ({
    status: ['pending'],
    category: [...(JOBS.find((j) => j.key === job)?.cats ?? [])],
  });
  let selected: Selection = freshSelection();
  /** The settled search box. */
  let query = '';
  let groupBy = '';

  $: filterRunId = selected.run?.[0] ?? '';
  $: floorPct = Math.round(Number(selected.conf?.[0] ?? 0) * 100);
  /** What the chips go back to on reset — the open job's categories. */
  $: defaults = { status: ['pending'], category: JOBS.find((j) => j.key === job)?.cats ?? [] };

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
      label: 'Category',
      kind: 'many',
      color: (v) => CAT_COLORS[v],
      value: reviewedCategory,
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
    { key: 'category', label: 'Category', of: reviewedCategory },
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

  /** The server answers for status and run (it caps a page at 2000 rows); the rest is here. */
  let loadedKey = '';
  const fetchKey = () => `${selected.status?.join()}|${selected.run?.join()}`;
  function onFacetChange(e: CustomEvent<{ key: string }>) {
    if (e.detail.key === 'status' || e.detail.key === 'run') load();
  }
  function onReset() {
    if (fetchKey() !== loadedKey) load();
  }
  /** The totals the server holds for the whole sheet — the loaded rows are only what is chosen. */
  $: totals = { status: statusCounts };

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

  /**
   * Changing job reframes the canvas on the part of the sheet the job reads,
   * starts the table in that job's own order, and puts the category chips back
   * to the job's own set — they are a refinement inside a job, not the axis.
   * Status, run and the confidence floor are the reviewer's, and stay.
   *
   * `openedJob` rather than a plain `$:` on `job`: the reviewer is free to sort
   * and to uncheck a chip afterwards, and a reactive block that re-ran on any
   * dependency would undo their choice under them.
   *
   * Keep this above `jobRows` and `sorted`. `applyJob` assigns `selected` and
   * `sort` from inside a function, which `$:` ordering cannot see, so a
   * statement placed after them runs them on the previous job's categories and
   * nothing runs them again.
   */
  let openedJob: JobKey | '' = '';
  $: if (job !== openedJob && extractions.length) applyJob();

  function applyJob() {
    openedJob = job;
    const def = JOBS.find((j) => j.key === job);
    if (!def) return;
    sort = { ...def.sort };
    selected = { ...selected, category: [...def.cats], suspect: [] };
    dispatch('regionFocus', { bbox: jobBox(job, regions), printed: isPrintedJob(job) });
  }

  const searchText = (e: EditableOcrExtraction) => `${e._editText} ${e._editCategory}`;

  /** The open job's rows: the partition comes first, and the facets count inside it. */
  $: jobRows = extractions.filter((e) => jobOf(e, regions) === job);
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

  $: jobHint = JOBS.find((j) => j.key === job)?.hint ?? '';
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
    if (!filterRunId) return;
    const ids = visible.filter((e) => e.status === 'pending').map((e) => e.id);
    if (!ids.length) return;
    const verb = status === 'validated' ? 'Validate' : 'Reject';
    if (
      !confirm(
        `${verb} ${ids.length} label${ids.length === 1 ? '' : 's'} from ${filterRunId} (confidence ≥ ${floorPct}%)?`
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

  export async function load() {
    if (!mapId) return;
    loading = true;
    error = '';
    try {
      // Pending is the default review queue. A reviewer can open history, or
      // several statuses at once, or a single run, from the filters above.
      loadedKey = fetchKey();
      const page = await fetchExtractions(mapId, {
        limit: 2000,
        status: selected.status,
        // `selected`, not `filterRunId`: that one is derived and has not caught up
        // when a facet's change event calls this in the same tick.
        runId: selected.run?.[0] ?? '',
      });
      statusCounts = page.statusCounts;
      // eslint-disable-next-line svelte/infinite-reactive-loop
      if (page.runIds.length) availableRuns = page.runIds;
      // Drafts outlive a reload: a facet that re-queries must not eat unsaved
      // work. A draft row the new page did not return stays, hidden by the same
      // facets that hid it, and still counts toward Save.
      const drafts = new Map(extractions.filter(isRowDirty).map((r) => [r.id, r]));
      const fresh = withEditState(page.extractions).map((r) => drafts.get(r.id) ?? r);
      // eslint-disable-next-line svelte/infinite-reactive-loop
      extractions = [...fresh, ...[...drafts.values()].filter((r) => !fresh.includes(r))];
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
    selected = freshSelection();
    availableRuns = [];
    extractions = [];
    // eslint-disable-next-line svelte/infinite-reactive-loop
    load();
  }

  /**
   * A verdict is a draft, like a text edit: it changes what the row shows and
   * waits for Save. The row keeps its place in the list — `status` is still what
   * the server holds, and the status facet reads that — so a pending row marked
   * validated stays where it was, in green, instead of vanishing under the
   * reviewer mid-pass.
   */
  function stage(id: string, status: OcrStatus) {
    extractions = extractions.map((r) => (r.id === id ? { ...r, _editStatus: status } : r));
  }

  $: dirtyCount = extractions.filter(isRowDirty).length;

  let saving = false;
  /** Every draft, in one go. A failure leaves the unsaved rows as drafts to try again. */
  async function saveAll() {
    if (saving || !dirtyCount) return;
    saving = true;
    error = '';
    notice = '';
    const { saved, error: failed } = await saveDrafts(mapId, extractions);
    ({ rows: extractions, statusCounts } = promoteSaved(
      { rows: extractions, statusCounts },
      saved
    ));
    if (failed) error = `${saved.size ? `Saved ${saved.size}, then: ` : ''}${failed}`;
    else notice = `Saved ${saved.size} change${saved.size === 1 ? '' : 's'}.`;
    saving = false;
  }

  /** Throw the drafts away and read the rows as the server has them. */
  function discard() {
    if (!confirm(`Discard ${dirtyCount} unsaved change${dirtyCount === 1 ? '' : 's'}?`)) return;
    extractions = [];
    return load();
  }

  let inputEls: Record<string, HTMLInputElement> = {};
  let rowEls: Record<string, HTMLTableRowElement> = {};

  /** The full shortcut list is read once and then known — fold it away by default. */
  let hintExpanded = false;

  /** Open one OCR pass — what "load run" on the Run step asks for. */
  export function showRun(runId: string) {
    selected = { ...selected, run: [runId] };
    return load();
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

<!-- A reload or a close would otherwise take the drafts with it. -->
<svelte:window
  on:beforeunload={(e) => {
    if (dirtyCount > 0) e.preventDefault();
  }}
/>

<div class="sidebar-content">
  <div class="ocr-filters">
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
      on:change={onFacetChange}
      on:reset={onReset}
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
          title="Save every drafted edit and verdict at once"
        >
          {saving ? 'Saving…' : `Save${dirtyCount > 0 ? ` (${dirtyCount})` : ''}`}
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
          disabled={loading}
          title="Reload"
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
        {#if jobHint}<p class="job-hint">{jobHint}</p>{/if}
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
            selected={ext.id === selectedId}
            bind:rowEl={rowEls[ext.id]}
            bind:inputEl={inputEls[ext.id]}
            on:select
            on:zoomToExtraction
            on:edit={() => (extractions = extractions)}
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
  /* The bar's own plate. `FacetFilters` brings the search, the chips and the
     disclosure; this is only the panel it sits in. */
  .ocr-filters {
    padding: 0.6rem 0.75rem;
    background: var(--color-white);
    border-bottom: var(--border-thin);
    flex-shrink: 0;
  }
  .job-hint {
    margin: 0 0 0.4rem;
    font-size: 0.7rem;
    line-height: 1.35;
    color: var(--sb-text-meta);
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
