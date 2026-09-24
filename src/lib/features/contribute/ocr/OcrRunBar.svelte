<!--
  OcrRunBar.svelte — the batch verdict buttons for the OCR review table.
  Nothing that only *filters* belongs here: the run picker sat among these
  buttons until Sept 2026, which is how "All runs" plus "Validate shown" came
  to mean accepting two passes at once, one of them misregistered.

  Save and Reload used to live in this same strip, behind a `showSaveReload`
  flag, but they are a per-row-edit action pair, not a run-scoped verdict —
  they moved into `OcrSidebar`'s own toolbar, next to the search field and the
  status filter, and this component shrank to what it was actually for.

  Bulk actions are deliberately scoped to one OCR run, so an "All runs" review
  view cannot turn into an accidental multi-pass verdict. Validate and Reject
  are a pair over one selection — the filters above decide which rows, these
  two decide the verdict. Rejecting in bulk is what the printed-index reads
  need and what previously took a script; giving it the same selection as
  Validate is what makes it safe to reach for.

  The parent retains the exact ids from the last batch and offers its own
  operation-level undo in the result notice.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import '$styles/components/shapes-table.css';

  /** Pending rows the current filters show — what the two verdict buttons take. */
  export let pendingShown = 0;
  /** A batch verdict must name exactly one pass. Empty means "All runs". */
  export let batchRunId = '';
  export let loading = false;

  const dispatch = createEventDispatcher<{
    validateShown: void;
    rejectShown: void;
  }>();
</script>

<div class="run-filter-bar">
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
</style>
