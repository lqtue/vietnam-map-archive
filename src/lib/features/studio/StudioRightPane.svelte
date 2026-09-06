<!--
  StudioRightPane.svelte — right pane for /explore?mode=annotate. A mode switch, nothing more.

  Layout:
    • Top bar       — Back · Mode toggle (Annotate | Animate) · Collapse
    • Project strip — StudioProjectHeader (title + save state + selected map)
    • Mode body     — Annotate: StudioAnnotationList + StudioAnnotationInspector
                      Animate:  StudioAnimationPanel
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { AnnotationSummary, DrawingMode, AnnotationSet } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import StudioProjectHeader from './StudioProjectHeader.svelte';
  import StudioAnnotationList from './StudioAnnotationList.svelte';
  import StudioAnnotationInspector from './StudioAnnotationInspector.svelte';
  import StudioAnimationPanel from './StudioAnimationPanel.svelte';
  import type { TimelineStore } from './animation/timelineStore';

  const dispatch = createEventDispatcher<{
    setDrawingMode: { mode: DrawingMode | null };
    toggleCollapse: void;
    backToLibrary: void;
  }>();

  export let project: AnnotationSet | null = null;
  export let annotations: AnnotationSummary[] = [];
  export let selectedAnnotationId: string | null = null;
  export let selectedMap: MapListItem | null = null;
  export let drawingMode: DrawingMode | null = null;
  export let isSaving = false;
  export let saveSuccess = false;
  /** Transient status line above the annotation list, owned by StudioMode. */
  export let notice: { text: string; tone: 'info' | 'error' | 'success' } | null = null;
  export let timelineStore: TimelineStore;

  type Mode = 'annotate' | 'animate';
  let mode: Mode = 'annotate';

  $: selected = annotations.find((a) => a.id === selectedAnnotationId) ?? null;
  $: selectedIndex = selected ? annotations.findIndex((a) => a.id === selected!.id) : -1;

  // When entering Animate mode, clear active drawing.
  $: if (mode === 'animate' && drawingMode) {
    dispatch('setDrawingMode', { mode: null });
  }
</script>

<aside class="right-panel">
  <!-- Top bar with mode toggle -->
  <div class="sb-bar">
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('backToLibrary')}
      aria-label="Back to library"
      title="Back to my projects">← Library</button
    >

    <div class="mode-toggle" role="tablist" aria-label="Editor mode">
      <button
        type="button"
        class="mt-btn"
        class:is-on={mode === 'annotate'}
        role="tab"
        aria-selected={mode === 'annotate'}
        on:click={() => (mode = 'annotate')}>Annotate</button
      >
      <button
        type="button"
        class="mt-btn"
        class:is-on={mode === 'animate'}
        role="tab"
        aria-selected={mode === 'animate'}
        on:click={() => (mode = 'animate')}>Animate</button
      >
    </div>

    <button
      type="button"
      class="sb-btn is-icon is-ghost"
      on:click={() => dispatch('toggleCollapse')}
      aria-label="Collapse panel"
      title="Hide editor"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      >
        <path d="M9 3h10a2 2 0 012 2v14a2 2 0 01-2 2H9" /><path d="M5 8l4 4-4 4" />
      </svg>
    </button>
  </div>

  <StudioProjectHeader {project} {selectedMap} {isSaving} {saveSuccess} on:renameProject on:save />

  <!-- Mode body -->
  {#if mode === 'annotate'}
    <StudioAnnotationList
      {annotations}
      {selectedAnnotationId}
      {drawingMode}
      {notice}
      on:setDrawingMode
      on:select
      on:zoomTo
      on:delete
      on:clear
      on:exportGeoJSON
      on:importFile
      on:importOSM
    />

    <StudioAnnotationInspector
      {selected}
      index={selectedIndex}
      on:rename
      on:updateDetails
      on:changeColor
      on:toggleVisibility
      on:zoomTo
      on:select
    />
  {:else}
    <StudioAnimationPanel
      {timelineStore}
      on:addKeyframe
      on:removeKeyframe
      on:reorderKeyframe
      on:updateKeyframe
      on:play
      on:stop
      on:clearTimeline
      on:jumpToKeyframe
    />
  {/if}
</aside>

<style>
  .right-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  /* Mode toggle in the top bar */
  .mode-toggle {
    display: inline-flex;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    overflow: hidden;
    background: var(--sb-card-bg);
  }
  .mt-btn {
    appearance: none;
    border: none;
    background: transparent;
    color: var(--sb-text);
    font-family: var(--sb-font-display);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.25rem 0.7rem;
    cursor: pointer;
    transition: background 0.1s;
  }
  .mt-btn + .mt-btn {
    border-left: var(--sb-border);
  }
  .mt-btn:hover {
    background: var(--sb-accent-yellow);
  }
  .mt-btn.is-on {
    background: var(--sb-text);
    color: var(--sb-card-bg);
  }
</style>
