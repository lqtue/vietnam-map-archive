<!--
  InlineRename.svelte — double-click (or Enter / F2) a title to edit it in
  place; Enter or blur commits, Escape cancels. Shared by the /explore?mode=story story
  header and the /explore?mode=annotate project header.

  The idle state is a real <button> so it is focusable and keyboard-operable
  without an ARIA role override.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{ rename: { title: string } }>();

  export let value = '';
  export let placeholder = 'Title';
  export let fallback = 'Untitled';
  /** One-line variant used in the /explore?mode=annotate header strip. */
  export let compact = false;

  let editing = false;
  let draft = '';
  let inputEl: HTMLInputElement | null = null;

  function startEdit() {
    draft = value;
    editing = true;
    requestAnimationFrame(() => {
      inputEl?.focus();
      inputEl?.select();
    });
  }
  function commitEdit() {
    if (!editing) return;
    const next = draft.trim();
    editing = false;
    if (next && next !== value) dispatch('rename', { title: next });
  }
  function cancelEdit() {
    editing = false;
  }
  function onTitleKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelEdit();
    }
  }
</script>

{#if editing}
  <input
    class="sh-title-input"
    class:compact
    bind:this={inputEl}
    bind:value={draft}
    on:blur={commitEdit}
    on:keydown={onTitleKey}
    {placeholder}
  />
{:else}
  <button
    type="button"
    class="sh-title"
    class:compact
    title="Double-click to rename"
    on:dblclick={startEdit}
    on:keydown={(e) => {
      if (e.key === 'Enter' || e.key === 'F2') startEdit();
    }}
  >
    {value || fallback}
  </button>
{/if}

<style>
  .sh-title {
    appearance: none;
    display: -webkit-box;
    text-align: left;
    background: transparent;
    border: none;
    margin: -2px -4px;
    padding: 2px 4px;
    font-family: var(--sb-font-display);
    font-size: 1.05rem;
    font-weight: 800;
    line-height: 1.2;
    color: var(--sb-text);
    overflow: hidden;
    text-overflow: ellipsis;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    cursor: text;
    user-select: none;
    border-radius: var(--sb-radius-sm);
  }
  .sh-title.compact {
    display: block;
    flex: 0 1 auto;
    max-width: 50%;
    font-size: 0.9rem;
    white-space: nowrap;
  }
  .sh-title:hover {
    background: var(--sb-accent-yellow, color-mix(in srgb, var(--accent) 12%, transparent));
  }
  .sh-title:focus {
    outline: 2px solid var(--sb-accent);
    outline-offset: -1px;
  }

  .sh-title-input {
    width: 100%;
    box-sizing: border-box;
    margin: -2px -4px;
    padding: 2px 4px;
    font-family: var(--sb-font-display);
    font-size: 1.05rem;
    font-weight: 800;
    line-height: 1.2;
    color: var(--sb-text);
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
  }
  .sh-title-input.compact {
    width: auto;
    flex: 1;
    margin: 0;
    padding: 0.2rem 0.35rem;
    font-size: 0.9rem;
  }
  .sh-title-input:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--sb-accent);
  }
</style>
