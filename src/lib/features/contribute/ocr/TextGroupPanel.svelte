<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { OcrExtraction } from '../shared/types';
  import { OCR_CATEGORIES } from '../shared/constants';
  import { reviewedCategory } from '../shared/ocrApi';

  export let extractions: OcrExtraction[] = [];
  export let saving = false;
  export let available = false;
  const dispatch = createEventDispatcher<{
    group: { text: string; category: string };
    close: void;
  }>();
  let text = extractions
    .map((r) => r._editText ?? r.text_validated ?? r.text)
    .join(' ')
    .trim();
  let category = extractions[0]
    ? (extractions[0]._editCategory ?? reviewedCategory(extractions[0]))
    : 'other';
  $: canGroup =
    available &&
    extractions.length > 1 &&
    extractions.every((r) => !r.is_text_group && !r.text_group_id);
  function group() {
    if (canGroup && text.trim() && !saving) dispatch('group', { text: text.trim(), category });
  }
</script>

<form class="text-group-panel" on:submit|preventDefault={group}>
  <span>{extractions.length} boxes · reading order follows your clicks</span>
  <div class="group-fields">
    <textarea
      rows="3"
      aria-label="Combined label text"
      placeholder="Combined label text…"
      bind:value={text}
      disabled={saving}></textarea>
    <select aria-label="Label category" bind:value={category} disabled={saving}>
      {#each OCR_CATEGORIES as cat (cat)}<option value={cat}>{cat}</option>{/each}
    </select>
  </div>
  {#if !available}
    <span>Grouping is not available yet. You can still edit each text box.</span>
  {:else if !canGroup}<span>Ungroup existing labels before making a new group.</span>{/if}
  <div class="group-actions">
    <button type="submit" class="sb-btn is-sm" disabled={saving || !canGroup || !text.trim()}
      >{saving ? 'Grouping…' : 'Group draft'}</button
    >
    <button type="button" class="sb-btn is-sm" disabled={saving} on:click={() => dispatch('close')}
      >Cancel</button
    >
  </div>
</form>

<style>
  .text-group-panel {
    position: absolute;
    bottom: calc(var(--bottom-bar-height, 36px) + 8px);
    left: 50%;
    transform: translateX(-50%);
    z-index: 20;
    background: var(--color-white);
    border: var(--border-thick);
    border-radius: var(--sb-radius);
    box-shadow: var(--shadow-solid-sm);
    padding: 0.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: min(480px, calc(100vw - 2rem));
    font-size: 0.75rem;
  }
  .group-fields,
  .group-actions {
    display: flex;
    gap: 0.5rem;
  }
  textarea,
  select {
    min-width: 0;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    background: var(--color-bg);
    color: var(--color-text);
    padding: 0.3rem;
    font: inherit;
  }
  textarea {
    field-sizing: content;
    max-height: 35vh;
    overflow-y: auto;
    resize: vertical;
    overflow-wrap: anywhere;
    flex: 1;
  }
</style>
