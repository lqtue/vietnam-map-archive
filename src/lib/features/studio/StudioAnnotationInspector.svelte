<!--
  StudioAnnotationInspector.svelte — /explore?mode=annotate's inspector card: name, notes,
  colour, and show/hide + zoom for the selected annotation.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { AnnotationSummary } from '$lib/map/types';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';

  const dispatch = createEventDispatcher<{
    rename: { id: string; label: string };
    updateDetails: { id: string; details: string };
    changeColor: { id: string; color: string };
    toggleVisibility: { id: string };
    zoomTo: { id: string };
    select: { id: string | null };
  }>();

  export let selected: AnnotationSummary | null = null;
  /** Position in the annotation list, used for the card title. -1 when none. */
  export let index = -1;

  $: title = selected ? `${index + 1}. ${selected.label || 'Untitled'}` : 'Inspector';
</script>

<SidebarCard {title} grow={3}>
  <svelte:fragment slot="head-actions">
    {#if selected}
      <button
        type="button"
        class="sb-btn is-sm is-ghost"
        on:click={() => dispatch('select', { id: null })}>Close</button
      >
    {/if}
  </svelte:fragment>

  {#if selected}
    <div class="insp">
      <label class="field">
        <span class="field-label">Name</span>
        <input
          type="text"
          value={selected.label}
          placeholder="Annotation name"
          on:input={(e) =>
            dispatch('rename', {
              id: selected!.id,
              label: (e.target as HTMLInputElement).value,
            })}
        />
      </label>

      <label class="field">
        <span class="field-label">Details</span>
        <textarea
          rows="4"
          value={selected.details ?? ''}
          placeholder="Optional notes"
          on:input={(e) =>
            dispatch('updateDetails', {
              id: selected!.id,
              details: (e.target as HTMLTextAreaElement).value,
            })}></textarea>
      </label>

      <div class="color-row">
        <span class="field-label">Colour</span>
        <input
          type="color"
          value={selected.color}
          on:input={(e) =>
            dispatch('changeColor', {
              id: selected!.id,
              color: (e.target as HTMLInputElement).value,
            })}
        />
        <button
          type="button"
          class="sb-btn is-sm is-ghost"
          on:click={() => dispatch('toggleVisibility', { id: selected!.id })}
        >
          {selected.hidden ? 'Show' : 'Hide'}
        </button>
        <button
          type="button"
          class="sb-btn is-sm is-ghost"
          on:click={() => dispatch('zoomTo', { id: selected!.id })}>Zoom</button
        >
      </div>
    </div>
  {:else}
    <div class="empty">
      <p>Select an annotation to edit its name, notes, and colour.</p>
    </div>
  {/if}
</SidebarCard>

<style>
  .insp {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .field-label {
    font-family: var(--sb-font-display);
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--sb-text);
    opacity: 0.7;
  }
  .field input[type='text'],
  .field textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 0.4rem 0.5rem;
    font-family: inherit;
    font-size: 0.85rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    color: var(--sb-text);
  }
  .field input[type='text']:focus,
  .field textarea:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--sb-accent);
  }
  .field textarea {
    resize: vertical;
    min-height: 60px;
  }
  .color-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .color-row input[type='color'] {
    width: 40px;
    height: 30px;
    padding: 0;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    cursor: pointer;
    overflow: hidden;
  }

  .empty {
    padding: 1rem 0.7rem;
    font-size: 0.85rem;
    color: var(--sb-text);
    opacity: 0.7;
    line-height: 1.5;
  }
</style>
