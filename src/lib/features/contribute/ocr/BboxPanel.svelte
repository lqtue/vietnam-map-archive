<!--
  BboxPanel.svelte — the floating editor for the selected OCR bbox.

  Sits above the bottom bar of /scan?mode=text while a bbox is selected:
  text, category, confidence, validate / reject / deselect. Owns the edit
  buffer; the parent only hears about it on `save`.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { OCR_CATEGORIES, CAT_COLORS } from '../shared/constants';
  import { reviewedCategory } from '../shared/ocrApi';
  import type { OcrExtraction } from '../shared/types';
  import type { OcrStatus } from '../shared/ocrApi';

  export let extraction: OcrExtraction;
  export let saving = false;

  const dispatch = createEventDispatcher<{
    save: { status: OcrStatus; text: string; category: string };
    rotate: { deg: number };
    close: void;
  }>();

  $: angle = Math.round(extraction.rotation_deg ?? 0);

  let text = '';
  let category = '';
  let textEl: HTMLInputElement | undefined;

  /** Called by the page when the operator presses `e`. */
  export function focusText() {
    textEl?.focus();
    textEl?.select();
  }

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
      style="background: {CAT_COLORS[reviewedCategory(extraction)] ?? CAT_COLORS.other}"
    ></span>
    <input
      class="bbox-panel-text"
      type="text"
      bind:value={text}
      bind:this={textEl}
      placeholder="Label text…"
      on:keydown={(e) => {
        if (e.key === 'Enter') save('validated');
      }}
    />
    <select class="bbox-panel-cat" bind:value={category}>
      {#each OCR_CATEGORIES as cat (cat)}
        <option value={cat}>{cat}</option>
      {/each}
    </select>
  </div>
  <div class="bbox-panel-actions">
    <span class="bbox-panel-conf">{((extraction.confidence ?? 0) * 100).toFixed(0)}%</span>
    <button
      class="sb-btn is-sm"
      on:click={() => dispatch('rotate', { deg: 0 })}
      disabled={angle === 0}
      title="Drag the round handle to turn the label · , and . nudge 1° · click to reset"
    >
      {angle}°
    </button>
    <button
      class="sb-btn is-sm validate"
      class:is-on={extraction.status === 'validated'}
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
      class="sb-btn is-sm reject"
      class:is-on={extraction.status === 'rejected'}
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
    background: var(--color-white);
    border: var(--border-thick);
    border-radius: var(--sb-radius);
    box-shadow: var(--shadow-solid-sm);
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
    font-family: var(--font-family-base);
    font-size: 0.82rem;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    padding: 0.3rem 0.5rem;
    background: var(--color-bg);
  }
  .bbox-panel-text:focus {
    outline: 2px solid var(--color-blue);
    outline-offset: -1px;
    background: var(--color-white);
  }
  .bbox-panel-cat {
    font-family: var(--font-family-base);
    font-size: 0.75rem;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    padding: 0.3rem 0.35rem;
    background: var(--color-bg);
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
    font-weight: var(--font-bold);
    font-variant-numeric: tabular-nums;
    opacity: 0.45;
    margin-right: 0.2rem;
  }
  /* The buttons are `.sb-btn.is-sm` (sidebar.css). Only the two tones are
     local: validate and reject answer in green and red rather than the shared
     yellow hover and `.is-on`, and the two-class selectors outrank both. The
     disabled face is the shared one. */
  .sb-btn.validate:hover,
  .sb-btn.validate.is-on {
    background: var(--tone-green-pale);
    color: var(--tone-green-ink);
    border-color: var(--tone-green-ink);
  }
  .sb-btn.reject:hover,
  .sb-btn.reject.is-on {
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
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    background: transparent;
    cursor: pointer;
    color: var(--color-text);
    opacity: 0.4;
  }
  .bbox-panel-close:hover {
    opacity: 1;
    background: var(--color-gray-100);
  }
</style>
