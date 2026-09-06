<!--
  DigitalizeBottomBar.svelte — the toolbar under the /scan?mode=triage
  canvas. Triage gets a hint only; the review phases add the draw and focus
  toggles. Purely presentational: every action is an event.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import SidebarToggleButton from '$lib/features/contribute/shared/SidebarToggleButton.svelte';
  import '$styles/layouts/tool-page.css';

  export let phase: 'triage' | 'ocr' | 'segmentation' = 'triage';
  export let drawMode = false;
  export let isolationMode = false;
  export let isMobile = false;
  export let sidebarCollapsed = false;

  const dispatch = createEventDispatcher<{
    toggleDraw: void;
    toggleIsolation: void;
    toggleSidebar: void;
  }>();
</script>

<footer class="bottom-bar">
  {#if phase === 'triage'}
    <div class="bar-hint">
      Drag the amber rectangle to set the neatline · click a tile to change its priority
    </div>
  {:else}
    <div class="bar-hint">
      {drawMode
        ? 'Drag a rectangle to add a bbox · Esc to cancel'
        : 'Click a bbox to edit it · drag to move it'}
    </div>
    <div class="bar-divider"></div>
    <button
      type="button"
      class="tool-btn"
      class:active={drawMode}
      on:click={() => dispatch('toggleDraw')}
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      >
        <rect x="3" y="3" width="18" height="18" rx="1" />
        <path d="M12 8v8M8 12h8" />
      </svg>
      <span>Add bbox</span>
    </button>
    <div class="bar-divider"></div>
    <button
      type="button"
      class="tool-btn"
      class:active={isolationMode}
      on:click={() => dispatch('toggleIsolation')}
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      >
        <circle cx="12" cy="12" r="3" /><path d="M3 12c0 1 2 5 9 5s9-4 9-5-2-5-9-5-9 4-9 5z" />
      </svg>
      <span>{isolationMode ? 'Focus On' : 'Focus'}</span>
    </button>
  {/if}
  {#if !isMobile}
    <div class="bar-divider"></div>
    <SidebarToggleButton collapsed={sidebarCollapsed} onClick={() => dispatch('toggleSidebar')} />
  {/if}
</footer>

<style>
  .bar-hint {
    font-size: 0.72rem;
    color: var(--ink);
    opacity: 0.45;
    padding: 0 0.5rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
