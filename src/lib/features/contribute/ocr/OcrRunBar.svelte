<!--
  OcrRunBar.svelte — the write actions for the OCR review table. Nothing that
  only *filters* belongs here: the run picker sat among these buttons until
  Sept 2026, which is how "All runs" plus "Validate shown" came to mean
  accepting two passes at once, one of them misregistered.

  Save flushes the pending inline text/category edits; ↻ reloads. Bulk actions
  are deliberately scoped to one OCR run, so an "All runs" review view cannot
  turn into an accidental multi-pass verdict.

  Validate and Reject are a pair over one selection — the filters above decide
  which rows, these two decide the verdict. Rejecting in bulk is what the
  printed-index reads need and what previously took a script; giving it the
  same selection as Validate is what makes it safe to reach for.

  The parent retains the exact ids from the last batch and offers its own
  operation-level undo in the result notice.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import '$styles/components/shapes-table.css';

  export let dirtyCount = 0;
  /** Pending rows the current filters show — what the two verdict buttons take. */
  export let pendingShown = 0;
  /** A batch verdict must name exactly one pass. Empty means "All runs". */
  export let batchRunId = '';
  export let loading = false;

  const dispatch = createEventDispatcher<{
    save: void;
    validateShown: void;
    rejectShown: void;
    reload: void;
  }>();
</script>

<div class="run-filter-bar">
  <button
    class="sb-btn is-primary is-sm"
    on:click={() => dispatch('save')}
    disabled={loading || dirtyCount === 0}
    title="Save all pending text/category edits"
  >
    Save{dirtyCount > 0 ? ` (${dirtyCount})` : ''}
  </button>
  <button
    class="sb-btn is-success is-sm"
    on:click={() => dispatch('validateShown')}
    disabled={loading || pendingShown === 0 || !batchRunId}
    title={batchRunId
      ? `Validate pending rows from ${batchRunId} that the filters currently show.`
      : 'Choose one OCR run before validating a batch.'}
  >
    Validate shown{pendingShown > 0 ? ` (${pendingShown})` : ''}
  </button>
  <button
    class="sb-btn is-danger is-sm"
    on:click={() => dispatch('rejectShown')}
    disabled={loading || pendingShown === 0 || !batchRunId}
    title={batchRunId
      ? `Reject pending rows from ${batchRunId} that the filters currently show.`
      : 'Choose one OCR run before rejecting a batch.'}
  >
    Reject shown{pendingShown > 0 ? ` (${pendingShown})` : ''}
  </button>
  <div class="run-bar-spacer"></div>
  <button
    class="sb-btn is-icon"
    on:click={() => dispatch('reload')}
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
</div>

<style>
  .run-filter-bar {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.75rem;
    border-bottom: var(--border-thin);
    background: var(--color-bg);
    flex-shrink: 0;
  }
  .run-bar-spacer {
    flex: 1;
  }
</style>
