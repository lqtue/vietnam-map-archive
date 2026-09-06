<!--
  StudioAnimationPanel.svelte — Animate-mode body for the Studio right pane.

  Takes the full height of the mode body:
    • Big keyframe list (thumb + label + transition fields + per-row actions)
    • Pinned bottom action bar: + Keyframe · ▶ Play / ■ Stop · Clear
-->
<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import type { TimelineStore } from './animation/timelineStore';

  const dispatch = createEventDispatcher<{
    addKeyframe: void;
    removeKeyframe: { id: string };
    reorderKeyframe: { id: string; delta: 1 | -1 };
    updateKeyframe: {
      id: string;
      patch: {
        label?: string;
        duration_ms?: number;
        hold_ms?: number;
        overlay_transition?: 'cut' | 'crossfade';
      };
    };
    play: void;
    stop: void;
    clearTimeline: void;
    jumpToKeyframe: { id: string };
  }>();

  export let timelineStore: TimelineStore;

  $: state = $timelineStore;
  $: hasFrames = state.frames.length > 0;

  let listEl: HTMLDivElement | null = null;

  // Auto-scroll the active row into view during playback.
  $: if (state.isPlaying && state.currentIndex !== null && listEl) {
    tick().then(() => {
      const node = listEl?.querySelector<HTMLElement>(`[data-kf-index="${state.currentIndex}"]`);
      node?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  function thumbStyle(frame: (typeof state.frames)[number]): string {
    const top = frame.layers.overlays[0];
    if (top?.thumbnail) return `background-image: url("${top.thumbnail}")`;
    if (frame.layers.base.kind === 'historical' && frame.layers.base.thumbnail) {
      return `background-image: url("${frame.layers.base.thumbnail}")`;
    }
    return '';
  }

  function describeFrame(frame: (typeof state.frames)[number]): string {
    const overlays = frame.layers.overlays;
    if (overlays.length === 0) {
      return frame.layers.base.kind === 'historical'
        ? (frame.layers.base.name ?? 'Historical base')
        : 'Modern basemap';
    }
    if (overlays.length === 1) return overlays[0].name ?? 'Map';
    return `${overlays[0].name ?? 'Map'} +${overlays.length - 1}`;
  }
</script>

<div class="anim-mode">
  <div class="anim-list" bind:this={listEl}>
    {#if hasFrames}
      {#each state.frames as f, i (f.id)}
        <div class="kf" class:active={state.currentIndex === i} data-kf-index={i}>
          <span class="kf-idx">{i + 1}</span>
          <div class="kf-thumb" style={thumbStyle(f)}>
            {#if !thumbStyle(f)}
              <span class="kf-thumb-fallback"
                >{f.layers.overlays.length || (f.layers.base.kind === 'historical' ? 1 : 0)}</span
              >
            {/if}
          </div>
          <div class="kf-body">
            <input
              class="kf-label"
              type="text"
              value={f.label}
              on:change={(e) =>
                dispatch('updateKeyframe', {
                  id: f.id,
                  patch: { label: (e.target as HTMLInputElement).value },
                })}
            />
            <div class="kf-desc" title={describeFrame(f)}>{describeFrame(f)}</div>
            <div class="kf-fields">
              <label class="kf-field" title="Camera transition into this keyframe (ms)">
                <span>in</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={f.duration_ms}
                  on:change={(e) =>
                    dispatch('updateKeyframe', {
                      id: f.id,
                      patch: {
                        duration_ms: Math.max(0, Number((e.target as HTMLInputElement).value) || 0),
                      },
                    })}
                />
                <span class="unit">ms</span>
              </label>
              <label class="kf-field" title="Hold after arriving (ms)">
                <span>hold</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={f.hold_ms}
                  on:change={(e) =>
                    dispatch('updateKeyframe', {
                      id: f.id,
                      patch: {
                        hold_ms: Math.max(0, Number((e.target as HTMLInputElement).value) || 0),
                      },
                    })}
                />
                <span class="unit">ms</span>
              </label>
              <button
                type="button"
                class="kf-transition"
                class:is-fade={(f.overlay_transition ?? 'cut') === 'crossfade'}
                title="Overlay transition: cut = instant, fade = tween opacity"
                on:click={() =>
                  dispatch('updateKeyframe', {
                    id: f.id,
                    patch: {
                      overlay_transition:
                        (f.overlay_transition ?? 'cut') === 'cut' ? 'crossfade' : 'cut',
                    },
                  })}
              >
                {(f.overlay_transition ?? 'cut') === 'crossfade' ? 'fade' : 'cut'}
              </button>
            </div>
          </div>
          <div class="kf-actions">
            <button
              type="button"
              class="sb-btn is-sm is-ghost"
              on:click={() => dispatch('reorderKeyframe', { id: f.id, delta: -1 })}
              disabled={i === 0}
              title="Move up">▲</button
            >
            <button
              type="button"
              class="sb-btn is-sm is-ghost"
              on:click={() => dispatch('reorderKeyframe', { id: f.id, delta: 1 })}
              disabled={i === state.frames.length - 1}
              title="Move down">▼</button
            >
            <button
              type="button"
              class="sb-btn is-sm is-ghost"
              on:click={() => dispatch('jumpToKeyframe', { id: f.id })}
              title="Apply this keyframe instantly">Jump</button
            >
            <button
              type="button"
              class="sb-btn is-sm is-danger"
              on:click={() => dispatch('removeKeyframe', { id: f.id })}
              title="Delete keyframe">×</button
            >
          </div>
        </div>
      {/each}
    {:else}
      <div class="empty">
        <p><strong>Make a flythrough.</strong></p>
        <p>
          Set up the map — pick an overlay, set its opacity, frame the camera — then press <strong
            >+ Keyframe</strong
          > below.
        </p>
        <p>
          Add at least two keyframes (different overlays or viewports), then press <strong
            >▶ Play</strong
          > to glide between them.
        </p>
      </div>
    {/if}
  </div>

  <div class="anim-bar">
    <button type="button" class="sb-btn is-sm is-block" on:click={() => dispatch('addKeyframe')}
      >+ Keyframe</button
    >
    {#if state.isPlaying}
      <button
        type="button"
        class="sb-btn is-sm is-block is-danger"
        on:click={() => dispatch('stop')}>■ Stop</button
      >
    {:else}
      <button
        type="button"
        class="sb-btn is-sm is-block is-primary"
        on:click={() => dispatch('play')}
        disabled={state.frames.length < 2}>▶ Play</button
      >
    {/if}
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('clearTimeline')}
      disabled={!hasFrames}>Clear</button
    >
  </div>
</div>

<style>
  .anim-mode {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .anim-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.6rem 0.7rem 0.8rem;
  }

  .kf {
    display: grid;
    grid-template-columns: auto 56px 1fr auto;
    grid-template-areas: 'idx thumb body actions';
    align-items: stretch;
    gap: 0.5rem;
    padding: 0.5rem 0.55rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    transition:
      box-shadow 0.15s,
      transform 0.15s;
  }
  .kf.active {
    box-shadow: 0 0 0 2px var(--sb-accent);
    transform: translate(-1px, -1px);
  }
  .kf-idx {
    grid-area: idx;
    align-self: center;
    font-family: var(--sb-font-display);
    font-size: 0.78rem;
    font-weight: 700;
    opacity: 0.6;
    min-width: 1.4em;
    text-align: right;
  }

  .kf-thumb {
    grid-area: thumb;
    width: 56px;
    height: 56px;
    background: var(--sb-bg);
    background-size: cover;
    background-position: center;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .kf-thumb-fallback {
    font-family: var(--sb-font-display);
    font-size: 1rem;
    font-weight: 800;
    opacity: 0.55;
  }

  .kf-body {
    grid-area: body;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    min-width: 0;
  }
  .kf-label {
    padding: 0.2rem 0.35rem;
    font: inherit;
    font-size: 0.88rem;
    font-weight: 700;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--sb-radius-sm);
    color: var(--sb-text);
    width: 100%;
    box-sizing: border-box;
    margin: -0.2rem -0.35rem 0;
  }
  .kf-label:hover {
    background: color-mix(in srgb, var(--ink) 6%, transparent);
  }
  .kf-label:focus {
    outline: none;
    border-color: var(--sb-accent);
    background: var(--ground-raised);
  }

  .kf-desc {
    font-size: 0.72rem;
    color: var(--sb-text);
    opacity: 0.7;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .kf-fields {
    display: flex;
    gap: 0.5rem;
  }
  .kf-field {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.8;
  }
  .kf-field input {
    width: 4em;
    padding: 0.15rem 0.3rem;
    font: inherit;
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0;
    background: var(--ground-raised);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
  }
  .kf-field .unit {
    opacity: 0.6;
  }

  .kf-transition {
    appearance: none;
    padding: 0.18rem 0.45rem;
    font: inherit;
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background: var(--sb-bg);
    color: var(--sb-text);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    cursor: pointer;
    transition:
      background 0.12s,
      color 0.12s;
  }
  .kf-transition:hover {
    background: var(--sb-accent-yellow);
  }
  .kf-transition.is-fade {
    background: var(--sb-text);
    color: var(--sb-card-bg);
  }

  .kf-actions {
    grid-area: actions;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    justify-content: space-between;
  }

  .empty {
    padding: 1.2rem 0.8rem;
    font-size: 0.88rem;
    color: var(--sb-text);
    opacity: 0.78;
    line-height: 1.5;
  }
  .empty p {
    margin: 0 0 0.6rem;
  }
  .empty p:last-child {
    margin-bottom: 0;
  }

  /* Pinned action bar */
  .anim-bar {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 0.4rem;
    padding: 0.6rem 0.7rem;
    border-top: var(--sb-border);
    background: var(--sb-card-bg);
    flex-shrink: 0;
  }
</style>
