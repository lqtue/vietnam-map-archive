<!--
  TriageSidebar.svelte — Left panel for the Triage phase of /scan?mode=triage.

  Shows neatline config (x/y/w/h inputs), tile config (target calls, live stats),
  per-tile priority legend, run controls, and existing run history.

  All triage params are bound two-way from the parent page.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import '$styles/layouts/tool-page.css';
  import '$styles/components/tool-sidebar.css';
  import type { TileOverrides } from './tileParams';
  import { buildTileGrid } from './tileParams';
  import type { StoredTriage } from './triagePrefs';
  import {
    LAYOUT_CATEGORIES,
    LAYOUT_COLORS,
    LAYOUT_LABELS,
    type LayoutCategory,
    type LayoutRegion,
  } from '$lib/data/maps/triageTypes';

  export let imgWidth: number = 0;
  export let imgHeight: number = 0;
  export let iiifInfoUrl: string | null = null;

  // Two-way bound from parent
  export let neatline: [number, number, number, number] | null = null;
  export let runId: string = '';
  export let minConfidence: number = 0.5;

  // Two-way bound (direct user inputs)
  export let tileSize: number = 2400;
  export let overlap: number = 300;

  // Read-only from parent
  export let tileOverrides: TileOverrides = {};

  export let ocrRunning: boolean = false;
  export let ocrError: string = '';
  /** Set once the run is queued; a worker has to claim it before anything happens. */
  export let queuedJobId: string | null = null;
  export let runs: Record<string, { n: number; categories: Record<string, number> }> = {};

  /** What `maps.triage` holds for this map — null until someone saves one. */
  export let savedTriage: (StoredTriage & { saved_at?: string }) | null = null;
  export let savingTriage: boolean = false;
  export let saveTriageError: string = '';
  export let suggesting: boolean = false;
  export let suggestError: string = '';

  /** The layout pass: what the sheet is made of, for a person to correct. */
  export let layoutRegions: LayoutRegion[] = [];
  export let selectedRegion: number | null = null;
  export let showRegions: boolean = true;
  export let detectingLayout: boolean = false;
  export let layoutError: string = '';
  /** The `layout` pipeline_jobs row, while one is in flight. */
  export let layoutJob: { status: string; error?: string | null } | null = null;

  const dispatch = createEventDispatcher<{
    runOcr: void;
    saveTriage: void;
    suggestTriage: void;
    detectLayout: void;
    regionsChange: LayoutRegion[];
    selectRegion: number | null;
    loadRun: { runId: string };
  }>();

  function setCategory(idx: number, category: LayoutCategory) {
    dispatch(
      'regionsChange',
      layoutRegions.map((r, i) => (i === idx ? { ...r, category, source: 'human' as const } : r))
    );
  }

  function removeRegion(idx: number) {
    dispatch(
      'regionsChange',
      layoutRegions.filter((_, i) => i !== idx)
    );
    if (selectedRegion === idx) dispatch('selectRegion', null);
  }

  /** A new region starts as the middle half of the sheet — big enough to grab,
   *  small enough that it is obviously a placeholder to be dragged. */
  function addRegion() {
    const w = Math.round(imgWidth / 2);
    const h = Math.round(imgHeight / 2);
    const next: LayoutRegion[] = [
      ...layoutRegions,
      {
        category: 'legend',
        bbox: [Math.round(w / 2), Math.round(h / 2), w, h],
        confidence: 1,
        source: 'human',
      },
    ];
    dispatch('regionsChange', next);
    dispatch('selectRegion', next.length - 1);
  }

  function useAsNeatline(r: LayoutRegion) {
    neatline = [...r.bbox] as [number, number, number, number];
  }

  $: mainMap = layoutRegions.find((r) => r.category === 'main_map') ?? null;

  // Local neatline inputs (separate vars to avoid array reactivity issues)
  let nx = 0,
    ny = 0,
    nw = 0,
    nh = 0;

  // Sync local inputs from prop (when TriageTool updates via drag)
  // Guard prevents overwriting user's in-progress typing on every bind:neatline round-trip.
  $: if (
    neatline &&
    (neatline[0] !== nx || neatline[1] !== ny || neatline[2] !== nw || neatline[3] !== nh)
  ) {
    nx = neatline[0];
    ny = neatline[1];
    nw = neatline[2];
    nh = neatline[3];
  }

  function onNeatlineInput() {
    neatline = [Math.round(nx), Math.round(ny), Math.round(nw), Math.round(nh)];
  }

  function resetFullImage() {
    neatline = [0, 0, imgWidth, imgHeight];
  }

  $: neatlineValid =
    !neatline ||
    (neatline[0] >= 0 &&
      neatline[1] >= 0 &&
      neatline[0] + neatline[2] <= imgWidth &&
      neatline[1] + neatline[3] <= imgHeight &&
      neatline[2] > 0 &&
      neatline[3] > 0);

  // Tile count computed locally
  $: tileCount =
    neatline && tileSize > 0 ? buildTileGrid(...neatline, tileSize, overlap).length : 0;

  // Tile priority counts
  // Compared field by field rather than by JSON.stringify: tileOverrides key order
  // is insertion order, so two identical grids built by different click paths
  // stringify differently and would read as unsaved for ever.
  $: triageDirty =
    !savedTriage ||
    String(savedTriage.neatline) !== String(neatline) ||
    savedTriage.tile_size !== tileSize ||
    savedTriage.overlap !== overlap ||
    Object.keys(savedTriage.tile_overrides ?? {}).length !== Object.keys(tileOverrides).length ||
    Object.entries(tileOverrides).some(([k, v]) => savedTriage?.tile_overrides?.[k] !== v);

  $: lowResCount = Object.values(tileOverrides).filter((v) => v === 'low_res').length;
  $: skipCount = Object.values(tileOverrides).filter((v) => v === 'skip').length;
  $: normalCount = tileCount - lowResCount - skipCount;

  const LOW_RES_RENDER = 512;
  const TARGET_TILES = 12;

  function suggestTileParams() {
    if (!neatline) return;
    const area = neatline[2] * neatline[3];
    const raw = Math.sqrt(area / TARGET_TILES);
    tileSize = Math.max(512, Math.round(raw / 200) * 200);
    overlap = Math.max(0, Math.round((tileSize * 0.1) / 50) * 50);
  }
</script>

<div class="triage-sidebar">
  <!-- Image info -->
  <div class="tool-section">
    <div class="tool-section-title">Image</div>
    <div class="tool-row">
      <span class="tool-label">Dimensions</span>
      <span class="tool-value tool-mono">{imgWidth} × {imgHeight} px</span>
    </div>
    {#if iiifInfoUrl}
      <div class="tool-row ts-url-row">
        <span class="tool-label">IIIF</span>
        <span class="tool-value tool-mono ts-url" title={iiifInfoUrl}
          >{iiifInfoUrl.replace('/info.json', '').split('/').slice(-2).join('/')}</span
        >
      </div>
    {/if}
  </div>

  <!-- Layout -->
  <div class="tool-section">
    <div class="tool-section-header">
      <div class="tool-section-title"><span class="ts-step">1</span> Layout</div>
      <button
        class="tool-ghost-btn"
        on:click={() => dispatch('detectLayout')}
        disabled={detectingLayout || !imgWidth}
      >
        {detectingLayout ? 'Queued…' : layoutRegions.length ? 'Re-detect' : 'Detect'}
      </button>
    </div>

    <p class="ts-hint">
      What the sheet is made of. A worker asks the model once, at low resolution; the answer lands
      here for you to correct. Dashed edges are its proposal, solid ones yours.
    </p>

    {#if layoutJob && ['queued', 'claimed', 'running'].includes(layoutJob.status)}
      <p class="ts-note">
        Layout job {layoutJob.status} — nothing happens until a worker claims it.
      </p>
    {:else if layoutJob?.status === 'failed'}
      <p class="tool-error">Layout job failed: {layoutJob.error ?? 'no reason recorded'}</p>
    {/if}
    {#if layoutError}<p class="tool-error">{layoutError}</p>{/if}

    {#if layoutRegions.length}
      <label class="ts-toggle">
        <input type="checkbox" bind:checked={showRegions} />
        <span>Show on the map</span>
      </label>

      <ul class="ts-regions">
        {#each layoutRegions as r, i (i)}
          <li class:selected={selectedRegion === i}>
            <button
              class="ts-region-row"
              on:click={() => dispatch('selectRegion', selectedRegion === i ? null : i)}
            >
              <span class="ts-swatch" style="background: {LAYOUT_COLORS[r.category]}"></span>
              <select
                value={r.category}
                on:click|stopPropagation
                on:change={(e) => setCategory(i, e.currentTarget.value as LayoutCategory)}
                class="ts-region-cat"
              >
                {#each LAYOUT_CATEGORIES as c}
                  <option value={c}>{LAYOUT_LABELS[c]}</option>
                {/each}
              </select>
              <span class="ts-region-size">{r.bbox[2]}×{r.bbox[3]}</span>
              {#if r.source === 'model'}
                <span class="ts-region-conf" title="model confidence"
                  >{Math.round(r.confidence * 100)}%</span
                >
              {/if}
            </button>
            <button
              class="ts-region-del"
              title="Remove this region"
              on:click={() => removeRegion(i)}>×</button
            >
          </li>
        {/each}
      </ul>

      <div class="ts-region-actions">
        <button class="tool-ghost-btn" on:click={addRegion} disabled={!imgWidth}>Add region</button>
        {#if mainMap}
          <button class="tool-ghost-btn" on:click={() => useAsNeatline(mainMap)}>
            Main map → neatline
          </button>
        {/if}
      </div>
    {:else if !detectingLayout}
      <div class="ts-region-actions">
        <button class="tool-ghost-btn" on:click={addRegion} disabled={!imgWidth}
          >Add one by hand</button
        >
      </div>
    {/if}
  </div>

  <!-- Neatline -->
  <div class="tool-section">
    <div class="tool-section-header">
      <div class="tool-section-title"><span class="ts-step">2</span> Neatline crop</div>
      <button
        class="tool-ghost-btn"
        on:click={() => dispatch('suggestTriage')}
        disabled={suggesting || !imgWidth}
      >
        {suggesting ? 'Reading…' : 'Suggest'}
      </button>
      <button class="tool-ghost-btn" on:click={resetFullImage} disabled={!imgWidth}
        >Full image</button
      >
    </div>
    <div class="tool-coord-grid">
      <label class="tool-coord-label">
        <span>X</span>
        <input
          type="number"
          bind:value={nx}
          on:change={onNeatlineInput}
          class="tool-num-input"
          min="0"
          max={imgWidth}
        />
      </label>
      <label class="tool-coord-label">
        <span>Y</span>
        <input
          type="number"
          bind:value={ny}
          on:change={onNeatlineInput}
          class="tool-num-input"
          min="0"
          max={imgHeight}
        />
      </label>
      <label class="tool-coord-label">
        <span>W</span>
        <input
          type="number"
          bind:value={nw}
          on:change={onNeatlineInput}
          class="tool-num-input"
          min="1"
          max={imgWidth}
        />
      </label>
      <label class="tool-coord-label">
        <span>H</span>
        <input
          type="number"
          bind:value={nh}
          on:change={onNeatlineInput}
          class="tool-num-input"
          min="1"
          max={imgHeight}
        />
      </label>
    </div>
    {#if !neatlineValid}
      <div class="tool-error">Neatline exceeds image bounds.</div>
    {/if}
    {#if suggestError}
      <div class="tool-error">{suggestError}</div>
    {/if}
    <div class="tool-hint">
      Drag the amber rectangle on the canvas to adjust, or type coords. From the HTML neatline tool:
      paste x,y,w,h above.
    </div>
  </div>

  <!-- Tile config -->
  <div class="tool-section">
    <div class="tool-section-header">
      <div class="tool-section-title">
        <span class="ts-step">3</span> Tiles
        <span class="tool-hint-inline tool-mono">({tileCount})</span>
      </div>
      <button class="tool-ghost-btn" on:click={suggestTileParams} disabled={!neatline}
        >Suggest</button
      >
    </div>
    <div class="tool-coord-grid">
      <label class="tool-coord-label">
        <span>Size</span>
        <input
          type="number"
          bind:value={tileSize}
          class="tool-num-input"
          min="512"
          max="8192"
          step="100"
        />
      </label>
      <label class="tool-coord-label">
        <span>Overlap</span>
        <input
          type="number"
          bind:value={overlap}
          class="tool-num-input"
          min="0"
          max="1200"
          step="50"
        />
      </label>
    </div>
    <div class="ts-priority-caption">Priority — click tiles on the map</div>
    <div class="ts-priority-legend">
      <div class="ts-priority-row">
        <span class="ts-swatch ts-swatch--normal"></span>
        <span class="ts-priority-label">Normal</span>
        <span class="ts-priority-count">{normalCount > 0 ? normalCount : '–'}</span>
        <span class="ts-priority-detail">full res</span>
      </div>
      <div class="ts-priority-row">
        <span class="ts-swatch ts-swatch--low-res"></span>
        <span class="ts-priority-label">Low-res</span>
        <span class="ts-priority-count">{lowResCount > 0 ? lowResCount : '–'}</span>
        <span class="ts-priority-detail">{LOW_RES_RENDER}px · title, legend</span>
      </div>
      <div class="ts-priority-row">
        <span class="ts-swatch ts-swatch--skip"></span>
        <span class="ts-priority-label">Skip</span>
        <span class="ts-priority-count">{skipCount > 0 ? skipCount : '–'}</span>
        <span class="ts-priority-detail">empty / border</span>
      </div>
    </div>
    <div class="tool-hint">Click a tile once → Low-res · twice → Skip · three times → Normal</div>
  </div>

  <!-- Save triage -->
  <div class="tool-section">
    <div class="tool-section-title"><span class="ts-step">4</span> Save triage</div>
    {#if saveTriageError}
      <div class="tool-error">{saveTriageError}</div>
    {/if}
    <div class="tool-hint">
      {#if !savedTriage}
        Not saved yet. Until you save, this triage lives only in this browser and the enqueue script
        cannot see it.
      {:else if triageDirty}
        Changed since you saved{savedTriage.saved_at
          ? ` (${savedTriage.saved_at.slice(0, 16).replace('T', ' ')})`
          : ''}.
      {:else}
        Saved{savedTriage.saved_at ? ` ${savedTriage.saved_at.slice(0, 16).replace('T', ' ')}` : ''} —
        ready to queue.
      {/if}
    </div>
    <button
      class:tool-run-btn={triageDirty}
      class:tool-ghost-btn={!triageDirty}
      on:click={() => dispatch('saveTriage')}
      disabled={savingTriage || !neatlineValid || !neatline}
    >
      {savingTriage ? 'Saving…' : savedTriage ? 'Update saved triage' : 'Save triage'}
    </button>
  </div>

  <!-- Run config -->
  <div class="tool-section">
    <div class="tool-section-title"><span class="ts-step">5</span> Run OCR</div>
    <label class="tool-field">
      <span class="tool-label">Run ID</span>
      <input
        type="text"
        bind:value={runId}
        class="tool-text-input tool-mono"
        placeholder="auto-generated"
      />
    </label>
    <label class="tool-field">
      <span class="tool-label">Min confidence <strong>{minConfidence.toFixed(2)}</strong></span>
      <input
        type="range"
        bind:value={minConfidence}
        min="0"
        max="1"
        step="0.05"
        class="tool-range"
      />
    </label>

    {#if ocrError}
      <div class="tool-error">{ocrError}</div>
    {/if}

    {#if queuedJobId}
      <div class="tool-hint">
        Queued as job <code>{queuedJobId.slice(0, 8)}</code>. A worker has to claim it:
        <code>python work/worker/vma_worker.py --kinds ocr</code>
      </div>
    {/if}

    <!-- Exactly one primary button at a time, and it is whichever step is next:
         Save while the triage is unsaved, Run once it is on the server. -->
    <button
      class:tool-run-btn={!triageDirty}
      class:tool-ghost-btn={triageDirty}
      on:click={() => dispatch('runOcr')}
      disabled={ocrRunning || !neatlineValid || !imgWidth}
    >
      {#if ocrRunning}
        <span class="spinner on-ink"></span> Queueing…
      {:else}
        Run OCR
      {/if}
    </button>
    <div class="tool-hint">Queues a job — a worker runs it and the stage flips to ocr_done.</div>
  </div>

  <!-- Run history -->
  {#if Object.keys(runs).length > 0}
    <div class="tool-section">
      <div class="tool-section-title">Existing runs</div>
      {#each Object.entries(runs).reverse() as [rid, info]}
        <div class="ts-run-row">
          <div class="ts-run-meta">
            <code class="ts-run-id">{rid}</code>
            <span class="ts-run-n">{info.n} items</span>
          </div>
          <button class="tool-ghost-btn" on:click={() => dispatch('loadRun', { runId: rid })}>
            Review →
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  /* A small ordinal, so the panel reads as five steps rather than eight
     equally-weighted boxes of readouts and controls. */
  .ts-step {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.15rem;
    height: 1.15rem;
    margin-right: 0.3rem;
    border-radius: 50%;
    background: var(--ink);
    color: var(--ground-raised);
    font-size: 0.68rem;
    font-weight: 700;
  }

  /* ── Layout regions ───────────────────────────────────────────────────── */
  .ts-hint {
    margin: 0 0 0.5rem;
    font-size: 0.72rem;
    line-height: 1.45;
    opacity: 0.65;
  }
  .ts-note {
    margin: 0 0 0.5rem;
    padding: 0.4rem 0.5rem;
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
    font-size: 0.72rem;
  }
  .ts-toggle {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
    font-size: 0.74rem;
    cursor: pointer;
  }
  .ts-regions {
    list-style: none;
    margin: 0 0 0.5rem;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .ts-regions li {
    display: flex;
    align-items: center;
    border-radius: var(--radius);
  }
  .ts-regions li.selected {
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
  }
  .ts-region-row {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
    padding: 0.25rem 0.3rem;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .ts-swatch {
    flex: none;
    width: 9px;
    height: 9px;
    border-radius: 2px;
  }
  .ts-region-cat {
    flex: 1;
    min-width: 0;
    border: 1px solid transparent;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    font: inherit;
    font-size: 0.74rem;
    cursor: pointer;
  }
  .ts-region-cat:hover {
    border-color: var(--rule);
  }
  .ts-region-size,
  .ts-region-conf {
    flex: none;
    font-size: 0.66rem;
    font-variant-numeric: tabular-nums;
    opacity: 0.55;
  }
  .ts-region-del {
    flex: none;
    width: 1.4rem;
    padding: 0;
    border: none;
    background: none;
    color: inherit;
    font-size: 1rem;
    line-height: 1;
    opacity: 0.4;
    cursor: pointer;
  }
  .ts-region-del:hover {
    opacity: 1;
    color: var(--status-bad);
  }
  .ts-region-actions {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
  }

  .ts-priority-caption {
    margin: 0.6rem 0 0.3rem;
    font-size: 0.72rem;
    font-weight: 600;
    opacity: 0.6;
  }

  /* Section / field / button primitives live in $styles/components/tool-sidebar.css
     (`.tool-*`). Only the triage-specific pieces are declared here. */
  .triage-sidebar {
    display: flex;
    flex-direction: column;
    gap: 0;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .ts-url-row {
    align-items: flex-start;
  }
  .ts-url {
    font-size: 0.68rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
    opacity: 0.6;
  }

  .ts-priority-legend {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .ts-priority-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.75rem;
  }

  .ts-swatch {
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1.5px solid;
    flex-shrink: 0;
  }

  /* Swatch colours mirror TriageTool's OpenLayers tile styles verbatim —
     they are canvas parity, not theme, so they stay literal. */
  .ts-swatch--normal {
    background: transparent;
    border-color: rgba(245, 158, 11, 0.35);
  }
  .ts-swatch--low-res {
    background: rgba(245, 158, 11, 0.18);
    border-color: #f59e0b; /* token-exempt: legend swatch, mirrors the OL tile style in TriageTool */
  }
  .ts-swatch--skip {
    background: rgba(107, 114, 128, 0.28);
    border-color: #6b7280; /* token-exempt: legend swatch, mirrors the OL tile style in TriageTool */
  }

  .ts-priority-label {
    font-weight: var(--w-semi);
    min-width: 56px;
  }
  .ts-priority-count {
    font-family: ui-monospace, monospace;
    min-width: 24px;
    font-size: 0.72rem;
  }
  .ts-priority-detail {
    opacity: 0.5;
    font-size: 0.68rem;
  }

  .ts-run-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.3rem 0;
  }

  .ts-run-meta {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .ts-run-id {
    font-size: 0.7rem;
    opacity: 0.7;
  }
  .ts-run-n {
    font-size: 0.7rem;
    opacity: 0.5;
  }
</style>
