<!--
  StoryPointsPanel.svelte — Point-tool card (middle of right pane).
  Owns the Place / Preview actions and the points list with reorder + remove.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Story } from '$lib/features/stories/shared/types';

  const dispatch = createEventDispatcher<{
    preview: void;
    togglePlacing: void;
    selectPoint: { pointId: string | null };
    zoomToPoint: { pointId: string };
    removePoint: { pointId: string };
    reorder: { from: number; to: number };
  }>();

  export let story: Story | null = null;
  export let selectedPointId: string | null = null;
  export let placingPoint = false;
  export let previewMode = false;
  export let topLayerName: string | null = null;

  $: points = story?.points ?? [];
  $: canPreview = points.length > 0;

  function moveUp(i: number) {
    if (i > 0) dispatch('reorder', { from: i, to: i - 1 });
  }
  function moveDown(i: number) {
    if (i < points.length - 1) dispatch('reorder', { from: i, to: i + 1 });
  }
</script>

<div class="pt">
  <div class="pt-actions">
    <button
      type="button"
      class="sb-btn is-primary is-block"
      class:is-on={placingPoint}
      on:click={() => dispatch('togglePlacing')}
    >
      {placingPoint ? 'Tap map to place…' : '＋ Place point'}
    </button>
    <button
      type="button"
      class="sb-btn"
      class:is-on={previewMode}
      on:click={() => dispatch('preview')}
      disabled={!canPreview && !previewMode}
      title={previewMode ? 'Stop preview' : 'Preview the story'}
    >
      {previewMode ? '■ Stop preview' : '▶ Preview'}
    </button>
  </div>

  {#if placingPoint && topLayerName}
    <p class="sb-subtitle">New points pin to <strong>{topLayerName}</strong>.</p>
  {:else if placingPoint}
    <p class="sb-subtitle">No historical layer active — point uses base map.</p>
  {/if}

  <div class="pt-section">
    <span class="sb-section-label">Points · {points.length}</span>
    {#if points.length === 0}
      <div class="sb-empty">
        Tap <strong>Place point</strong>, then click the map to add your first stop.
      </div>
    {:else}
      <ul class="pt-list">
        {#each points as p, i (p.id)}
          <li class="pt-row" class:selected={p.id === selectedPointId}>
            <div class="pt-reorder">
              <button
                type="button"
                class="sb-btn is-sm is-icon"
                on:click={() => moveUp(i)}
                disabled={i === 0}
                aria-label="Move up"
                title="Move up">▲</button
              >
              <button
                type="button"
                class="sb-btn is-sm is-icon"
                on:click={() => moveDown(i)}
                disabled={i === points.length - 1}
                aria-label="Move down"
                title="Move down">▼</button
              >
            </div>
            <button
              type="button"
              class="pt-body"
              on:click={() => {
                dispatch('selectPoint', { pointId: p.id });
                dispatch('zoomToPoint', { pointId: p.id });
              }}
            >
              <span class="pt-num">{i + 1}</span>
              <span class="pt-name" title={p.title}>{p.title || `Point ${i + 1}`}</span>
            </button>
            <button
              type="button"
              class="sb-btn is-icon"
              title="Remove point"
              aria-label="Remove point"
              on:click={() => dispatch('removePoint', { pointId: p.id })}>×</button
            >
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>

<style>
  .pt {
    display: flex;
    flex-direction: column;
    padding: 0.6rem 0.7rem 0.7rem;
    gap: 0.55rem;
    min-height: 0;
    height: 100%;
  }
  .pt-actions {
    display: flex;
    gap: 0.4rem;
  }
  .pt-actions > .sb-btn {
    flex: 1;
  }

  .pt-section {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    min-height: 0;
    flex: 1;
  }

  .pt-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    overflow-y: auto;
    min-height: 0;
  }
  .pt-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.45rem;
    background: var(--sb-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
  }
  .pt-row.selected {
    background: var(--sb-accent-yellow);
    box-shadow: 0 0 0 var(--rule-thick) color-mix(in srgb, var(--accent) 35%, transparent);
  }
  .pt-reorder {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .pt-reorder .sb-btn {
    width: 26px;
    height: 20px;
    font-size: 0.65rem;
    padding: 0;
  }

  .pt-body {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: none;
    border: none;
    padding: 0.1rem 0;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }
  .pt-num {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--sb-accent);
    color: var(--ground-raised);
    border-radius: 50%;
    font-size: 0.72rem;
    font-weight: 800;
  }
  .pt-row.selected .pt-num {
    background: var(--sb-accent-warm);
  }
  .pt-name {
    flex: 1;
    min-width: 0;
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--sb-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
