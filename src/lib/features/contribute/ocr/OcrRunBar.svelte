<!--
  OcrRunBar.svelte — run picker + write actions for the OCR review table.

  Save flushes the pending inline text/category edits; the ⟲ button is the
  two-step "that batch was a mistake" escape hatch (the parent arms it and
  renders the confirmation notice); ↻ reloads.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import '$styles/components/shapes-table.css';

  export let runs: string[] = [];
  /** Two-way: '' means every run. */
  export let runId = '';
  export let dirtyCount = 0;
  /** Pending rows the current filters show — what "Validate shown" would accept. */
  export let pendingShown = 0;
  export let loading = false;
  /** True while the revert button is waiting for its confirming second click. */
  export let revertArmed = false;

  const dispatch = createEventDispatcher<{
    change: void;
    save: void;
    validateShown: void;
    revert: void;
    reload: void;
  }>();
</script>

<div class="run-filter-bar">
  {#if runs.length > 0}
    <div class="dropdown-wrap run-select-wrap">
      <select
        class="cell-select run-select"
        bind:value={runId}
        on:change={() => dispatch('change')}
        aria-label="Select run"
      >
        <option value="">All runs</option>
        {#each runs as r}
          <option value={r}>{r}</option>
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
  {:else}
    <span class="run-placeholder">No runs</span>
  {/if}
  <button
    class="save-btn"
    on:click={() => dispatch('save')}
    disabled={loading || dirtyCount === 0}
    title="Save all pending text/category edits"
  >
    Save{dirtyCount > 0 ? ` (${dirtyCount})` : ''}
  </button>
  <button
    class="save-btn validate-btn"
    on:click={() => dispatch('validateShown')}
    disabled={loading || pendingShown === 0}
    title="Validate every pending row the filters currently show. Undo with ⟲ within 15 minutes."
  >
    Validate shown{pendingShown > 0 ? ` (${pendingShown})` : ''}
  </button>
  <div class="run-bar-spacer"></div>
  <button
    class="icon-btn text-danger"
    class:armed={revertArmed}
    on:click={() => dispatch('revert')}
    title={revertArmed
      ? 'Click again to revert everything validated in the last 15 min'
      : 'Accidental batch? Revert everything from last 15 mins'}
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
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
    </svg>
  </button>
  <button class="icon-btn" on:click={() => dispatch('reload')} disabled={loading} title="Reload">
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
    border-bottom: var(--rule-hair) solid var(--rule);
    background: var(--ground);
    flex-shrink: 0;
  }
  .run-select-wrap {
    flex: 1;
    min-width: 0;
  }
  .run-select {
    width: 100%;
    font-family: ui-monospace, monospace;
    font-size: 0.68rem;
  }
  .run-placeholder {
    font-size: 0.7rem;
    opacity: 0.4;
    flex: 1;
  }
  .run-bar-spacer {
    flex: 1;
  }
  .save-btn {
    font-family: var(--font-body);
    font-size: 0.7rem;
    font-weight: var(--w-semi);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.28rem 0.55rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: 4px;
    background: var(--accent);
    color: var(--ink);
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
    transition: all 0.1s;
  }
  .validate-btn {
    background: var(--status-ok);
    color: var(--ground-raised);
  }
  .save-btn:hover:not(:disabled) {
    transform: translate(-1px, -1px);
    box-shadow: 3px 3px 0 var(--rule);
  }
  .save-btn:active:not(:disabled) {
    transform: none;
    box-shadow: none;
  }
  .save-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    filter: grayscale(1);
    box-shadow: none;
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    cursor: pointer;
    flex-shrink: 0;
    color: var(--ink);
  }
  .icon-btn:hover {
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
  }
  .icon-btn.armed {
    background: var(--tone-red-pale);
    border-color: var(--tone-red-ink);
    color: var(--tone-red-ink);
  }
  .text-danger {
    color: var(--status-bad);
  }
</style>
