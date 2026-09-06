<!--
  PhaseTabs.svelte — the Triage / OCR / Segmentation switcher in the
  /scan?mode=triage sidebar footer. The mobile drawer shortens the middle
  label, hence `ocrLabel`.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let phase: 'triage' | 'ocr' | 'segmentation' = 'triage';
  export let ocrLabel = 'OCR Review';

  const dispatch = createEventDispatcher<{ change: { phase: typeof phase } }>();

  function select(next: typeof phase) {
    phase = next;
    dispatch('change', { phase: next });
  }
</script>

<div class="phase-tabs">
  <button class="phase-tab" class:active={phase === 'triage'} on:click={() => select('triage')}>
    Triage
  </button>
  <button class="phase-tab" class:active={phase === 'ocr'} on:click={() => select('ocr')}>
    {ocrLabel}
  </button>
  <button
    class="phase-tab"
    class:active={phase === 'segmentation'}
    on:click={() => select('segmentation')}
  >
    Segmentation
  </button>
</div>

<style>
  .phase-tabs {
    display: flex;
    gap: 2px;
    background: var(--rule);
    border-radius: 6px;
    padding: 2px;
    width: 100%;
  }

  .phase-tab {
    flex: 1;
    padding: 0.35rem 0.6rem;
    font-size: 0.72rem;
    font-weight: var(--w-semi);
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--ground-raised);
    cursor: pointer;
    opacity: 0.5;
    transition: all 0.15s;
    white-space: nowrap;
    text-align: center;
  }

  .phase-tab.active {
    background: var(--ground-raised);
    color: var(--ink);
    opacity: 1;
    box-shadow: 0 1px 2px color-mix(in srgb, var(--rule) 8%, transparent);
  }
</style>
