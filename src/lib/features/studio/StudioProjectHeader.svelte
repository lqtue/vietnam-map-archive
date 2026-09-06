<!--
  StudioProjectHeader.svelte — the one-line project strip under /explore?mode=annotate's top
  bar: inline-renameable title · selected map · autosave dot · Save button.
  Shown in both editor modes.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { AnnotationSet } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import InlineRename from '$lib/ui/InlineRename.svelte';

  const dispatch = createEventDispatcher<{
    renameProject: { title: string };
    save: void;
  }>();

  export let project: AnnotationSet | null = null;
  export let selectedMap: MapListItem | null = null;
  export let isSaving = false;
  export let saveSuccess = false;
</script>

<div class="sh-compact">
  <InlineRename
    compact
    value={project?.title ?? ''}
    fallback="Untitled project"
    placeholder="Project title"
    on:rename={(e) => dispatch('renameProject', { title: e.detail.title })}
  />
  {#if selectedMap}
    <span class="sh-map" title={selectedMap.name}>
      {selectedMap.name}{#if selectedMap.year}<span class="sh-year">
          · {selectedMap.year}</span
        >{/if}
    </span>
  {/if}
  <span class="sh-autosave" class:saved={saveSuccess} class:saving={isSaving}>
    {saveSuccess ? '✓' : isSaving ? '…' : '•'}
  </span>
  <button
    type="button"
    class="sb-btn is-sm"
    class:is-success={saveSuccess}
    on:click={() => dispatch('save')}
    disabled={isSaving || saveSuccess}
  >
    {saveSuccess ? 'Saved' : isSaving ? '…' : 'Save'}
  </button>
</div>

<style>
  .sh-compact {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.7rem;
    border-bottom: var(--sb-border);
    min-height: 36px;
  }
  .sh-map {
    flex: 1;
    min-width: 0;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--sb-text);
    opacity: 0.7;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sh-year {
    font-variant-numeric: tabular-nums;
  }
  .sh-autosave {
    width: 1.2em;
    font-size: 0.8rem;
    text-align: center;
    color: var(--sb-text);
    opacity: 0.5;
  }
  .sh-autosave.saved {
    color: var(--sb-success);
    opacity: 1;
  }
  .sh-autosave.saving {
    opacity: 0.8;
  }
</style>
