<!--
  PointInspector.svelte — Point view of /explore?mode=story's right pane.

  Lives inside a titled SidebarCard ("Point N · title") with a ← Back button
  in head-actions (owned by CreateRightPane). This panel renders the editor
  body + a Delete-point footer. Reuses ChallengeConfig.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { StoryPoint, PointChallenge } from '$lib/features/stories/shared/types';
  import ChallengeConfig from './ChallengeConfig.svelte';
  import { layersStore } from '$lib/map/stores/layersStore';

  const dispatch = createEventDispatcher<{
    updatePoint: { pointId: string; updates: Partial<StoryPoint> };
    removePoint: { pointId: string };
    toggleMoving: void;
  }>();

  export let point: StoryPoint;
  export let movingPoint = false;
  export let pinnedLayerName: string | null = null;

  // Pin options come from every active historical overlay in layersStore
  // (top first). The author may also pin to a map that's no longer in the
  // stack (e.g. seeded earlier and then removed from the layer list); we
  // surface that as a "(not loaded)" entry so the select stays valid.
  $: pinOptions = $layersStore.overlays
    .filter((o) => o.ref.kind === 'historical')
    .map((o, i) => {
      const r = o.ref as Extract<typeof o.ref, { kind: 'historical' }>;
      return {
        mapId: r.mapId,
        label: `${r.name ?? r.mapId}${i === 0 ? ' (top)' : ''}`,
      };
    });
  $: hasOrphanPin =
    !!point.overlayMapId && !pinOptions.some((opt) => opt.mapId === point.overlayMapId);

  function update(updates: Partial<StoryPoint>) {
    dispatch('updatePoint', { pointId: point.id, updates });
  }
  function onChallenge(e: CustomEvent<{ challenge: PointChallenge }>) {
    update({ challenge: e.detail.challenge });
  }
  function onPinChange(e: Event) {
    const v = (e.target as HTMLSelectElement).value;
    update({ overlayMapId: v || undefined });
  }
</script>

<div class="pi" aria-label="Edit point">
  <div class="pi-body">
    <label class="sb-section">
      <span class="sb-section-label">Title</span>
      <input
        type="text"
        class="sb-input"
        value={point.title}
        placeholder="Point title"
        on:input={(e) => update({ title: (e.target as HTMLInputElement).value })}
      />
    </label>

    <label class="sb-section">
      <span class="sb-section-label">Description (shown on arrival)</span>
      <textarea
        rows="3"
        class="sb-textarea"
        value={point.description}
        placeholder="What should the reader notice here?"
        on:input={(e) => update({ description: (e.target as HTMLTextAreaElement).value })}
      ></textarea>
    </label>

    <label class="sb-section">
      <span class="sb-section-label">Hint (shown before arrival)</span>
      <input
        type="text"
        class="sb-input"
        value={point.hint ?? ''}
        placeholder="Optional hint"
        on:input={(e) => update({ hint: (e.target as HTMLInputElement).value || undefined })}
      />
    </label>

    <div class="sb-section">
      <span class="sb-section-label">Challenge</span>
      <ChallengeConfig challenge={point.challenge} on:change={onChallenge} />
    </div>

    <div class="sb-section">
      <span class="sb-section-label">Position</span>
      <div class="sb-row">
        <code class="sb-coords sb-grow">
          {point.coordinates[1].toFixed(5)}, {point.coordinates[0].toFixed(5)}
        </code>
        <button
          type="button"
          class="sb-btn is-sm"
          class:is-on={movingPoint}
          on:click={() => dispatch('toggleMoving')}
        >
          {movingPoint ? 'Tap map…' : 'Move'}
        </button>
      </div>
    </div>

    <div class="sb-section">
      <span class="sb-section-label">Pinned historical layer</span>
      {#if pinOptions.length === 0 && !hasOrphanPin}
        <p class="sb-subtitle">Add a historical overlay from the left sidebar to pin one here.</p>
      {:else}
        <select
          class="sb-input pi-pin-select"
          value={point.overlayMapId ?? ''}
          on:change={onPinChange}
          aria-label="Pinned historical layer"
        >
          <option value="">— none —</option>
          {#each pinOptions as opt}
            <option value={opt.mapId}>{opt.label}</option>
          {/each}
          {#if hasOrphanPin}
            <option value={point.overlayMapId}
              >{pinnedLayerName ?? point.overlayMapId} (not loaded)</option
            >
          {/if}
        </select>
      {/if}
    </div>
  </div>

  <footer class="pi-foot">
    <button
      type="button"
      class="sb-btn is-block is-danger"
      on:click={() => dispatch('removePoint', { pointId: point.id })}
    >
      Delete point
    </button>
  </footer>
</div>

<style>
  .pi {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: var(--sb-card-bg);
  }
  .pi-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0.7rem 0.65rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }
  .pi-pin-select {
    appearance: auto;
    cursor: pointer;
  }
  .pi-foot {
    display: flex;
    gap: 0.4rem;
    padding: 0.55rem 0.65rem;
    border-top: var(--sb-border);
    background: var(--sb-bg);
  }
</style>
