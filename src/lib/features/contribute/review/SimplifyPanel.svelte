<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { SamFootprint } from '$lib/data/supabase/footprints';
  import { geometryKind } from '$lib/data/maps/footprintTypes';
  import type { SimplifyPreview } from './reviewQueue';

  export let footprint: SamFootprint | null = null;
  export let preview: SimplifyPreview | null = null;
  export let busy = false;
  export let canUndo = false;
  let tolerance = 2;
  const tolerances = [2, 4, 6];
  const dispatch = createEventDispatcher<{
    preview: { id: string; tolerance: number };
    cancel: void;
    accept: void;
    undo: { id: string };
  }>();
  $: supported =
    footprint && geometryKind(footprint.featureType, footprint.pixelPolygon) === 'Polygon';
  $: trial = preview?.id === footprint?.id ? preview : null;
</script>

{#if footprint && supported}
  <fieldset class="simplify-panel">
    <legend>Simplify outline</legend>
    <label for="simplify-tolerance">Tolerance in image pixels</label>
    <div class="sb-row">
      <select id="simplify-tolerance" class="sb-input" bind:value={tolerance} disabled={busy}>
        {#each tolerances as value (value)}
          <option {value}>{value} px</option>
        {/each}
      </select>
      <button
        class="sb-btn is-sm"
        disabled={busy}
        on:click={() => footprint && dispatch('preview', { id: footprint.id, tolerance })}
        >Preview</button
      >
    </div>
    {#if trial}
      <p aria-live="polite">
        {trial.trial.beforeVertices} → {trial.trial.afterVertices} vertices · area {trial.trial.areaChangePercent.toFixed(
          1
        )}% · boundary movement ≤ {trial.trial.boundaryMovement.toFixed(1)} px
      </p>
      {#if !trial.trial.valid}
        <p role="alert">{trial.trial.reason}</p>
      {:else if trial.overlaps.length}
        <p role="alert">
          This would introduce overlap with {trial.overlaps.length} other shape(s) in this layer.
        </p>
      {/if}
      <div class="sb-row">
        <button
          class="sb-btn is-sm"
          disabled={busy ||
            !trial.trial.valid ||
            !!trial.overlaps.length ||
            trial.trial.afterVertices >= trial.trial.beforeVertices}
          on:click={() => dispatch('accept')}>Use outline</button
        >
        <button class="sb-btn is-sm" disabled={busy} on:click={() => dispatch('cancel')}
          >Cancel preview</button
        >
      </div>
    {/if}
    {#if canUndo}
      <button
        class="sb-btn is-sm"
        disabled={busy}
        on:click={() => footprint && dispatch('undo', { id: footprint.id })}
        >Undo outline edit</button
      >
    {/if}
    <p>Outline edits save when you approve or reject. The dashed outline is the preview.</p>
  </fieldset>
{/if}

<style>
  .simplify-panel {
    margin: 0.6rem 1rem;
    padding: 0.6rem 0;
    border: 0;
    border-top: 1px solid var(--color-border);
  }
  legend {
    font-size: 0.8rem;
    font-weight: var(--font-semibold);
    color: var(--color-text);
  }
  label,
  p {
    font-size: 0.75rem;
    color: var(--sb-text-meta);
  }
</style>
