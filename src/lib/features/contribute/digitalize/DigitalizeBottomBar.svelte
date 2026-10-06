<!--
  DigitalizeBottomBar.svelte — the toolbar under the /scan?mode=prepare and
  ?mode=text canvas. Prepare gets a hint only; Text adds the draw and focus
  toggles. Purely presentational: every action is an event.

  It carried a panel toggle until the rails were split. With a left rail and a
  right one, "the sidebar" stopped naming a single thing, and ToolLayout already
  gives each rail its own collapse chevron and its own re-open pill — so one
  ambiguous button was doing badly what two unambiguous ones already did.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import '$styles/layouts/tool-page.css';

  export let mode: 'prepare' | 'text' = 'prepare';
  export let drawMode = false;
  export let isolationMode = false;
  export let selectedText: string | null = null;
  /** Current canvas rotation, signed degrees. 0 hides the reset button. */
  export let rotationDeg = 0;

  const dispatch = createEventDispatcher<{
    toggleDraw: void;
    toggleIsolation: void;
    rotate: { deg: number };
    resetRotation: void;
  }>();
</script>

<footer class="bottom-bar">
  {#if mode === 'prepare'}
    <div class="bar-hint">Drag the amber box · click a tile to set its priority</div>
  {:else}
    <div class="bar-hint" class:selected-text={selectedText !== null && !drawMode}>
      {drawMode
        ? 'Drag a rectangle to add a bbox · Esc to cancel'
        : (selectedText ?? 'Click to edit · Shift-click to group')}
    </div>
    <div class="bar-divider"></div>
    <button
      type="button"
      class="sb-btn is-sm"
      class:is-on={drawMode}
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
      class="sb-btn is-sm"
      class:is-on={isolationMode}
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
  <div class="bar-divider"></div>
  <button
    type="button"
    class="sb-btn is-sm icon-only"
    on:click={() => dispatch('rotate', { deg: -90 })}
    title="Rotate left 90° (Shift+R) · [ and ] turn 5°"
    aria-label="Rotate left"
  >
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
    </svg>
  </button>
  <button
    type="button"
    class="sb-btn is-sm icon-only"
    on:click={() => dispatch('rotate', { deg: 90 })}
    title="Rotate right 90° (R) · [ and ] turn 5°"
    aria-label="Rotate right"
  >
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  </button>
  {#if rotationDeg !== 0}
    <button
      type="button"
      class="sb-btn is-sm"
      on:click={() => dispatch('resetRotation')}
      title="Back to upright (0)"
    >
      <span class="rot-deg">{rotationDeg}°</span>
    </button>
  {/if}
</footer>

<style>
  .bottom-bar {
    height: auto;
    min-height: 46px;
    max-height: 40vh;
    overflow-y: auto;
    padding-block: 0.5rem;
    flex-wrap: wrap;
  }
  .icon-only {
    padding-inline: 0.4rem;
  }
  .rot-deg {
    font-variant-numeric: tabular-nums;
    font-size: 0.72rem;
  }
  .bar-hint {
    flex: 1 1 20rem;
    min-width: 0;
    font-size: 0.72rem;
    color: var(--color-text);
    opacity: 0.45;
    padding: 0 0.5rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .selected-text {
    font-size: 0.85rem;
    line-height: 1.5;
    opacity: 1;
  }
</style>
