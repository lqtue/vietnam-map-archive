<!--
  BboxPanel.svelte — the floating editor for the selected OCR bbox.

  Sits above the bottom bar of /scan?mode=triage while a bbox is selected:
  text, category, confidence, validate / reject / deselect. Owns the edit
  buffer; the parent only hears about it on `save`.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { OCR_CATEGORIES, CAT_COLORS } from '../shared/constants';
  import type { OcrExtraction } from '../shared/types';
  import type { OcrStatus } from '../shared/ocrApi';

  export let extraction: OcrExtraction;
  export let saving = false;

  const dispatch = createEventDispatcher<{
    save: { status: OcrStatus; text: string; category: string };
    close: void;
  }>();

  let text = '';
  let category = '';

  // Re-seed whenever the selection (or the row behind it) changes.
  $: if (extraction) {
    text = extraction.text_validated ?? extraction.text;
    category = extraction.category_validated ?? extraction.category;
  }

  function save(status: OcrStatus) {
    dispatch('save', { status, text, category });
  }
</script>

<div class="bbox-panel">
  <div class="bbox-panel-row">
    <span
      class="bbox-panel-cat-dot"
      style="background: {CAT_COLORS[extraction.category] ?? CAT_COLORS.other}"
    ></span>
    <input
      class="bbox-panel-text"
      type="text"
      bind:value={text}
      placeholder="Label text…"
      on:keydown={(e) => {
        if (e.key === 'Enter') save('validated');
      }}
    />
    <select class="bbox-panel-cat" bind:value={category}>
      {#each OCR_CATEGORIES as cat}
        <option value={cat}>{cat}</option>
      {/each}
    </select>
  </div>
  <div class="bbox-panel-actions">
    <span class="bbox-panel-conf">{((extraction.confidence ?? 0) * 100).toFixed(0)}%</span>
    <button
      class="bbox-panel-btn validate"
      class:active={extraction.status === 'validated'}
      disabled={saving}
      on:click={() => save(extraction.status === 'validated' ? 'pending' : 'validated')}
      title={extraction.status === 'validated' ? 'Unvalidate' : 'Validate'}
    >
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
      >
      {extraction.status === 'validated' ? 'Validated' : 'Validate'}
    </button>
    <button
      class="bbox-panel-btn reject"
      class:active={extraction.status === 'rejected'}
      disabled={saving}
      on:click={() => save(extraction.status === 'rejected' ? 'pending' : 'rejected')}
      title={extraction.status === 'rejected' ? 'Unreject' : 'Reject'}
    >
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg
      >
      {extraction.status === 'rejected' ? 'Rejected' : 'Reject'}
    </button>
    <button class="bbox-panel-close" on:click={() => dispatch('close')} title="Deselect">
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg
      >
    </button>
  </div>
</div>

<style>
  .bbox-panel {
    position: absolute;
    /* --bottom-bar-height is set by the page shell; tokens.css has no such token. */
    bottom: calc(var(--bottom-bar-height, 36px) + 8px);
    left: 50%;
    transform: translateX(-50%);
    z-index: 20;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.55rem 0.7rem;
    min-width: 320px;
    max-width: min(560px, calc(100vw - 2rem));
  }
  .bbox-panel-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }
  .bbox-panel-cat-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .bbox-panel-text {
    flex: 1;
    min-width: 0;
    font-family: var(--font-body);
    font-size: 0.82rem;
    border: 1px solid var(--rule);
    border-radius: 3px;
    padding: 0.3rem 0.5rem;
    background: var(--ground);
  }
  .bbox-panel-text:focus {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
    background: var(--ground-raised);
  }
  .bbox-panel-cat {
    font-family: var(--font-body);
    font-size: 0.75rem;
    border: 1px solid var(--rule);
    border-radius: 3px;
    padding: 0.3rem 0.35rem;
    background: var(--ground);
    cursor: pointer;
    flex-shrink: 0;
  }
  .bbox-panel-actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .bbox-panel-conf {
    font-size: 0.68rem;
    font-weight: var(--w-semi);
    font-variant-numeric: tabular-nums;
    opacity: 0.45;
    margin-right: 0.2rem;
  }
  .bbox-panel-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-family: var(--font-body);
    font-size: 0.72rem;
    font-weight: var(--w-semi);
    padding: 0.28rem 0.65rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: 4px;
    background: var(--ground);
    color: var(--ink);
    cursor: pointer;
    transition: all 0.1s;
  }
  .bbox-panel-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .bbox-panel-btn.validate:hover,
  .bbox-panel-btn.validate.active {
    background: var(--tone-green-pale);
    color: var(--tone-green-ink);
    border-color: var(--tone-green-ink);
  }
  .bbox-panel-btn.reject:hover,
  .bbox-panel-btn.reject.active {
    background: var(--tone-red-pale);
    color: var(--tone-red-ink);
    border-color: var(--tone-red-ink);
  }
  .bbox-panel-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    margin-left: auto;
    border: 1px solid var(--rule);
    border-radius: 3px;
    background: transparent;
    cursor: pointer;
    color: var(--ink);
    opacity: 0.4;
  }
  .bbox-panel-close:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
  }
</style>
