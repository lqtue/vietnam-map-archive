<!--
  SegSidebar.svelte — the Segment tab of /scan?mode=shapes.

  Shows the pipeline stage, the gate to the next stage, the MapSAM2 command
  configuration, and the Colab command itself. Segmentation runs on a GPU
  elsewhere, so this panel is a launcher and a status readout — it never
  starts anything itself.

  It sat in `?mode=triage` beside the OCR steps until Sept 2026, which put the
  machine that draws shapes in the mode that reads words.

  `compact` is the mobile drawer variant: stage badge + command only.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import CliCommandBlock from '$lib/features/contribute/shared/CliCommandBlock.svelte';
  import { buildSegCommand, type SegConfig } from './segCommand';
  import type { PipelineStatus, HumanStage } from '$lib/features/contribute/pipelineApi';
  import '$styles/layouts/tool-page.css';

  export let mapId: string;
  export let status: PipelineStatus | null = null;
  export let loading = false;
  export let error = '';
  export let config: SegConfig;
  export let compact = false;

  const dispatch = createEventDispatcher<{ advance: { stage: HumanStage }; refresh: void }>();

  /* The pipeline stage's tone on the shared dense badge. Anything unmapped
     (idle, ocr_queued, seg_queued's neighbours) stays grey. */
  const STAGE_TONE: Record<string, string> = {
    ocr_done: 'chip-orange',
    reviewed: 'chip-orange',
    seg_queued: 'chip-blue',
    seg_done: 'chip-green',
    seg_reviewed: 'chip-green',
  };

  $: stage = status?.stage ?? 'idle';
  $: stageTone = STAGE_TONE[stage] ?? 'chip-gray';
  $: command = buildSegCommand(mapId, status?.ocr_run_id, config);
</script>

<div class="seg-panel">
  <div class="seg-status">
    <span class="seg-stage-label">Stage</span>
    <span class="badge-chip is-sm {stageTone}">{stage}</span>
  </div>

  {#if compact}
    {#if command}
      <CliCommandBlock {command} label="Colab command" />
    {/if}
    {#if error}
      <p class="empty-state error">{error}</p>
    {/if}
  {:else}
    {#if stage === 'ocr_done' || stage === 'reviewed'}
      {#if stage === 'ocr_done'}
        <button class="sb-btn is-block" on:click={() => dispatch('advance', { stage: 'reviewed' })}>
          Mark ready for segmentation
        </button>
      {:else}
        <p class="seg-hint">Ready. Run the Colab command below, then come back here.</p>
      {/if}
    {:else if stage === 'seg_done' || stage === 'seg_reviewed'}
      <a class="sb-btn is-block" href="/scan?mode=shapes&tab=validate&map={mapId}">
        Review footprints &rarr;
      </a>
    {:else if stage === 'idle'}
      <p class="seg-hint">
        Finish OCR review first. The segmentation step needs validated toponyms to run.
      </p>
    {/if}

    {#if command}
      <div class="seg-config">
        <div class="sb-section-label">Command config</div>
        <label class="seg-field">
          <span>Checkpoint</span>
          <input
            type="text"
            bind:value={config.checkpointPath}
            placeholder="/content/drive/MyDrive/…"
          />
        </label>
        {#if status?.ocr_run_id || config.priorPath}
          <label class="seg-field">
            <span>MapSAM2 dir</span>
            <input type="text" bind:value={config.mapsam2Dir} placeholder="/content/MapSAM2" />
          </label>
        {/if}
        <label class="seg-field">
          <span>Colour-block prior (optional)</span>
          <input type="text" bind:value={config.priorPath} placeholder="/content/blocks.geojson" />
        </label>
        <div class="seg-row">
          <label class="seg-field seg-field--inline">
            <span>Encoder</span>
            <select bind:value={config.encoder}>
              <option value="vit_t">vit_t (tiny)</option>
              <option value="vit_s">vit_s (small)</option>
              <option value="vit_b">vit_b (base)</option>
              <option value="vit_l">vit_l (large)</option>
            </select>
          </label>
        </div>
        <div class="seg-row seg-row--checks">
          <label class="seg-check">
            <input type="checkbox" bind:checked={config.useTextMask} />
            Text mask
          </label>
          <label class="seg-check">
            <input type="checkbox" bind:checked={config.useWatershed} />
            Watershed
          </label>
        </div>
      </div>
      <CliCommandBlock {command} label="Colab command" />
    {/if}

    {#if status?.seg_started_at || status?.seg_finished_at}
      <div class="seg-meta">
        <span>Run: <code>{status.seg_run_id ?? '—'}</code></span>
        {#if status.seg_started_at}
          <span>Started: {new Date(status.seg_started_at).toLocaleString()}</span>
        {/if}
        {#if status.seg_finished_at}
          <span>Finished: {new Date(status.seg_finished_at).toLocaleString()}</span>
        {/if}
      </div>
    {/if}

    {#if error}
      <p class="empty-state error">{error}</p>
    {/if}

    <button
      class="sb-btn is-sm seg-refresh"
      on:click={() => dispatch('refresh')}
      disabled={loading}
    >
      {loading ? 'Loading…' : 'Refresh status'}
    </button>
  {/if}
</div>

<style>
  .seg-panel {
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .seg-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
  }
  .seg-stage-label {
    opacity: 0.55;
  }
  .seg-config {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.55rem 0.6rem;
    background: var(--color-gray-100);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--sb-radius-sm);
  }
  .seg-field {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .seg-field span {
    font-size: 0.68rem;
    font-weight: var(--font-semibold);
    opacity: 0.6;
  }
  .seg-field input,
  .seg-field select {
    font-family: ui-monospace, monospace;
    font-size: 0.68rem;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    padding: 0.25rem 0.4rem;
    background: var(--color-white);
    width: 100%;
  }
  .seg-field--inline {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
  }
  .seg-field--inline span {
    white-space: nowrap;
  }
  .seg-field--inline select {
    flex: 1;
  }
  .seg-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .seg-row--checks {
    gap: 0.75rem;
  }
  .seg-check {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    cursor: pointer;
  }
  .seg-check input[type='checkbox'] {
    cursor: pointer;
  }
  .seg-meta {
    font-size: 0.7rem;
    opacity: 0.6;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  /* Layout only — `.sb-btn` supplies the face. */
  .seg-refresh {
    align-self: flex-start;
  }
  .seg-hint {
    font-size: 0.75rem;
    opacity: 0.6;
    margin: 0;
  }
</style>
