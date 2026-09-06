<!--
  CreateRightPane.svelte — right pane for /explore?mode=story.

  Split into three cards:
    • Story info  — title (dblclick to rename) + auto-save badge + Public toggle
    • Point tool  — Place / Preview + points list
    • Point edit  — selected point inspector (empty hint when none)

  Story info is auto-height; the other two cards share the remaining space
  ~40/60 so the inspector rarely needs to scroll. Edits auto-persist to
  localStorage via CreateMode's persistDraft reactive — there is no Save button.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Story, StoryPoint } from '$lib/features/stories/shared/types';
  import StoryHeaderPanel from './StoryHeaderPanel.svelte';
  import StoryPointsPanel from './StoryPointsPanel.svelte';
  import PointInspector from './PointInspector.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';

  const dispatch = createEventDispatcher<{
    toggleCollapse: void;
    close: void;
    backToLibrary: void;
  }>();

  export let story: Story | null = null;
  export let selectedPointId: string | null = null;
  export let placingPoint = false;
  export let previewMode = false;
  export let isPublishing = false;
  export let publishSuccess = false;
  export let topLayerName: string | null = null;
  export let selectedPoint: StoryPoint | null = null;
  export let selectedPointIndex = 0;
  export let movingPoint = false;
  export let pinnedLayerName: string | null = null;

  $: pointCardTitle = selectedPoint
    ? `Point ${selectedPointIndex + 1}${selectedPoint.title ? ' · ' + selectedPoint.title : ''}`
    : 'Point editor';
</script>

<aside class="right-panel">
  <div class="sb-bar">
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('backToLibrary')}
      aria-label="Back to library"
      title="Back to my stories">← Library</button
    >
    <span class="sb-bar-title">Story editor</span>
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

  <SidebarCard grow={0} padded={false}>
    <StoryHeaderPanel {story} {isPublishing} {publishSuccess} on:togglePublish on:renameStory />
  </SidebarCard>

  <SidebarCard title="Points" grow={2} padded={false}>
    <StoryPointsPanel
      {story}
      {selectedPointId}
      {placingPoint}
      {previewMode}
      {topLayerName}
      on:preview
      on:togglePlacing
      on:selectPoint
      on:zoomToPoint
      on:removePoint
      on:reorder
    />
  </SidebarCard>

  <SidebarCard title={pointCardTitle} grow={3}>
    <svelte:fragment slot="head-actions">
      {#if selectedPoint}
        <button
          type="button"
          class="sb-btn is-sm is-ghost"
          on:click={() => dispatch('close')}
          title="Deselect point"
          aria-label="Deselect point">Close</button
        >
      {/if}
    </svelte:fragment>
    {#if selectedPoint}
      <PointInspector
        point={selectedPoint}
        {movingPoint}
        {pinnedLayerName}
        on:updatePoint
        on:removePoint
        on:toggleMoving
      />
    {:else}
      <div class="sb-empty">
        Pick a point in the list to edit its title, description, challenge, and pinned layer.
      </div>
    {/if}
  </SidebarCard>
</aside>

<style>
  .right-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    min-height: 0;
    background: var(--sb-bg);
    border-left: var(--sb-border);
    overflow: hidden;
  }
</style>
