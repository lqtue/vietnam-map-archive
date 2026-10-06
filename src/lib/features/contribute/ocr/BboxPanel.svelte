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
    draft: { status: OcrStatus; text: string; category: string };
    save: { status: OcrStatus; text: string; category: string };
    rotate: { deg: number };
    close: void;
    ungroup: void;
    duplicate: { text: string; category: string };
  }>();

  $: angle = Math.round(extraction.rotation_deg ?? 0);

  let actionsOpen = false;
  let text = '';
  let category = '';
  let textEl: HTMLTextAreaElement | undefined;

  /** Called by the page when the operator presses `e`. */
  export function focusText() {
    textEl?.focus();
    textEl?.select();
  }

  // Re-seed whenever the selection (or the row behind it) changes.
  $: if (extraction) {
    text = extraction._editText ?? extraction.text_validated ?? extraction.text;
    category = extraction._editCategory ?? extraction.category_validated ?? extraction.category;
  }

  $: status = extraction._editStatus ?? extraction.status;
  function draft() {
    dispatch('draft', { status, text, category });
  }
  function save(status: OcrStatus) {
    dispatch('save', { status, text, category });
  }
</script>

<div class="bbox-panel">
  <div class="bbox-panel-row">
    <span
      class="bbox-panel-cat-dot"
      style="background: {CAT_COLORS[extraction._editCategory ?? reviewedCategory(extraction)] ??
        CAT_COLORS.other}"
    ></span>
    <textarea
      class="bbox-panel-text"
      rows="3"
      bind:value={text}
      bind:this={textEl}
      aria-label="Label text"
      placeholder="Label text…"
      disabled={saving}
      on:input={draft}
      on:keydown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          save('validated');
        }
      }}></textarea>
    <select
      aria-label="Label type"
      class="bbox-panel-cat"
      bind:value={category}
      disabled={saving}
      on:change={draft}
    >
      {#each OCR_CATEGORIES as cat (cat)}
        <option value={cat}>{cat}</option>
      {/each}
    </select>
  </div>
  <div class="bbox-panel-actions">
    <details class="box-actions" bind:open={actionsOpen}>
      <summary class="sb-btn is-sm" aria-label="Box actions" title="Box actions">⋯</summary>
      <div class="box-actions-menu">
        {#if extraction.is_text_group}
          <button
            class="sb-btn is-sm"
            disabled={saving}
            on:click={() => {
              actionsOpen = false;
              dispatch('ungroup');
            }}>Ungroup</button
          >
        {:else}
          <button
            class="sb-btn is-sm"
            disabled={saving}
            on:click={() => {
              actionsOpen = false;
              dispatch('duplicate', { text, category });
            }}>Duplicate box</button
          >
          <button
            class="sb-btn is-sm"
            disabled={saving || angle === 0}
            on:click={() => {
              actionsOpen = false;
              dispatch('rotate', { deg: 0 });
            }}>Reset box angle ({angle}°)</button
          >
        {/if}
      </div>
    </details>
    <button
      class="sb-btn is-sm validate"
      class:is-on={status === 'validated'}
      disabled={saving}
      on:click={() => save(status === 'validated' ? 'pending' : 'validated')}
      title={status === 'validated' ? 'Unvalidate' : 'Validate'}
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
      {status === 'validated' ? 'Validated' : 'Validate'}
    </button>
    <button
      class="sb-btn is-sm reject"
      class:is-on={status === 'rejected'}
      disabled={saving}
      on:click={() => save(status === 'rejected' ? 'pending' : 'rejected')}
      title={status === 'rejected' ? 'Unreject' : 'Reject'}
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
      {status === 'rejected' ? 'Rejected' : 'Reject'}
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
    max-width: min(560px, calc(100vw - 2rem));
    width: min(560px, calc(100% - 2rem));
    min-width: 0;
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
    field-sizing: content;
    max-height: 35vh;
    overflow-y: auto;
    color: var(--color-text);
    resize: vertical;
    overflow-wrap: anywhere;
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
  .box-actions {
    position: relative;
  }
  .box-actions summary {
    list-style: none;
    cursor: pointer;
  }
  .box-actions summary::-webkit-details-marker {
    display: none;
  }
  .box-actions-menu {
    position: absolute;
    bottom: calc(100% + 0.4rem);
    left: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    white-space: nowrap;
    padding: 0.5rem;
    background: var(--color-white);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    box-shadow: var(--shadow-solid-sm);
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
