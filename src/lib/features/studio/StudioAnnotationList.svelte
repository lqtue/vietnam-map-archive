<!--
  StudioAnnotationList.svelte — /explore?mode=annotate's "Annotations" card: the Clear /
  Export / Import / From-OSM actions, the Point · Line · Polygon draw toggles,
  the transient notice line, and the annotation rows themselves.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { AnnotationSummary, DrawingMode } from '$lib/map/types';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';

  const dispatch = createEventDispatcher<{
    setDrawingMode: { mode: DrawingMode | null };
    select: { id: string | null };
    zoomTo: { id: string };
    delete: { id: string };
    clear: void;
    exportGeoJSON: void;
    importFile: { file: File };
    importOSM: void;
  }>();

  export let annotations: AnnotationSummary[] = [];
  export let selectedAnnotationId: string | null = null;
  export let drawingMode: DrawingMode | null = null;
  /** Transient status line above the list, owned by StudioMode. */
  export let notice: { text: string; tone: 'info' | 'error' | 'success' } | null = null;

  function pickDrawMode(m: DrawingMode) {
    dispatch('setDrawingMode', { mode: drawingMode === m ? null : m });
  }

  function handleFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const [file] = input.files ?? [];
    if (!file) return;
    dispatch('importFile', { file });
    input.value = '';
  }

  function selectAnnotation(id: string) {
    dispatch('select', { id: id === selectedAnnotationId ? null : id });
  }

  function typeBadge(type: string): string {
    switch (type) {
      case 'Point':
        return 'Pt';
      case 'LineString':
        return 'Ln';
      case 'Polygon':
        return 'Pg';
      default:
        return '??';
    }
  }
  function typeClass(type: string): string {
    switch (type) {
      case 'Point':
        return 'type-point';
      case 'LineString':
        return 'type-line';
      case 'Polygon':
        return 'type-polygon';
      default:
        return '';
    }
  }
</script>

<SidebarCard title="Annotations" grow={2} padded={false}>
  <svelte:fragment slot="head-actions">
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('clear')}
      disabled={!annotations.length}>Clear</button
    >
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('exportGeoJSON')}
      disabled={!annotations.length}>Export</button
    >
    <label class="sb-btn is-sm is-ghost upload">
      Import
      <input
        type="file"
        accept="application/geo+json,.geojson,.json"
        on:change={handleFileChange}
      />
    </label>
    <button
      type="button"
      class="sb-btn is-sm is-ghost"
      on:click={() => dispatch('importOSM')}
      title="Import features from OpenStreetMap via Overpass"
    >
      From OSM
    </button>
  </svelte:fragment>

  <div class="draw-controls">
    <button
      type="button"
      class="sb-btn is-block"
      class:is-on={drawingMode === 'point'}
      on:click={() => pickDrawMode('point')}
    >
      <span class="dot dot-point" aria-hidden="true"></span>
      {drawingMode === 'point' ? 'Placing…' : 'Point'}
    </button>
    <button
      type="button"
      class="sb-btn is-block"
      class:is-on={drawingMode === 'line'}
      on:click={() => pickDrawMode('line')}
    >
      <span class="dot dot-line" aria-hidden="true"></span>
      {drawingMode === 'line' ? 'Drawing…' : 'Line'}
    </button>
    <button
      type="button"
      class="sb-btn is-block"
      class:is-on={drawingMode === 'polygon'}
      on:click={() => pickDrawMode('polygon')}
    >
      <span class="dot dot-polygon" aria-hidden="true"></span>
      {drawingMode === 'polygon' ? 'Drawing…' : 'Polygon'}
    </button>
  </div>

  {#if notice}
    <p
      class="notice"
      class:errored={notice.tone === 'error'}
      class:success={notice.tone === 'success'}
    >
      {notice.text}
    </p>
  {/if}

  <div class="ann-list">
    {#if annotations.length}
      {#each annotations as a, i (a.id)}
        <div
          class="row"
          class:selected={a.id === selectedAnnotationId}
          on:click={() => selectAnnotation(a.id)}
          on:keydown={(e) => {
            if (e.key === 'Enter') selectAnnotation(a.id);
          }}
          role="button"
          tabindex="0"
        >
          <span class="row-idx">{i + 1}</span>
          <span class="type-badge {typeClass(a.type)}">{typeBadge(a.type)}</span>
          <span class="row-label">{a.label || 'Untitled'}</span>
          <div class="row-actions">
            <button
              type="button"
              class="sb-btn is-sm is-ghost"
              on:click|stopPropagation={() => dispatch('zoomTo', { id: a.id })}>Zoom</button
            >
            <button
              type="button"
              class="sb-btn is-sm is-danger"
              on:click|stopPropagation={() => dispatch('delete', { id: a.id })}>×</button
            >
          </div>
        </div>
      {/each}
    {:else}
      <div class="empty">
        <p><strong>Draw on the map:</strong></p>
        <ul>
          <li>Click <strong>Point</strong>, <strong>Line</strong>, or <strong>Polygon</strong></li>
          <li>Then click on the map to draw</li>
          <li>Or <strong>Import</strong> a GeoJSON file</li>
        </ul>
      </div>
    {/if}
  </div>
</SidebarCard>

<style>
  /* Draw controls */
  .draw-controls {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
    padding: 0.6rem 0.7rem;
    border-bottom: var(--sb-border);
  }
  .draw-controls :global(.sb-btn) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
  }
  .dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1.5px solid currentColor;
    flex-shrink: 0;
  }
  .dot-point {
    border-radius: 50%;
    background: currentColor;
  }
  .dot-line {
    width: 14px;
    height: 2px;
    background: currentColor;
    border: none;
  }
  .dot-polygon {
    background: transparent;
  }

  .notice {
    padding: 0.5rem 0.7rem;
    margin: 0;
    font-size: 0.78rem;
    background: var(--sb-card-bg);
    border-bottom: var(--sb-border);
  }
  .notice.success {
    background: var(--sb-success-bg);
    color: var(--sb-success);
  }
  .notice.errored {
    background: var(--sb-danger-bg);
    color: var(--sb-danger);
  }

  /* Annotation list */
  .ann-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.6rem 0.7rem;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.45rem 0.55rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    cursor: pointer;
    transition: all 0.1s;
  }
  .row:hover {
    transform: translate(-1px, -1px);
  }
  .row.selected {
    box-shadow: 0 0 0 2px var(--sb-accent);
  }
  .row-idx {
    font-family: var(--sb-font-display);
    font-size: 0.7rem;
    font-weight: 700;
    opacity: 0.6;
    min-width: 1.2em;
    text-align: right;
  }
  .row-label {
    flex: 1;
    font-size: 0.85rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .row-actions {
    display: flex;
    gap: 0.25rem;
  }

  .type-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-size: 0.6rem;
    font-weight: 800;
    color: var(--ground-raised);
    border: var(--sb-border);
    flex-shrink: 0;
  }
  /* Feature-type badges: gold / green / violet, matching the OSM import palette.
     Literal on purpose — these encode which geometry a feature is, not a UI
     role, and they have to stay in step with the colours the OL layers use. */
  .type-point {
    background: #d4af37; /* token-exempt: geometry-type badge, must match the OSM import layer */
  }
  .type-line {
    background: #5b8a72; /* token-exempt: geometry-type badge, must match the OSM import layer */
  }
  .type-polygon {
    background: #7b6b9e; /* token-exempt: geometry-type badge, must match the OSM import layer */
  }

  .empty {
    padding: 1rem 0.7rem;
    font-size: 0.85rem;
    color: var(--sb-text);
    opacity: 0.7;
    line-height: 1.5;
  }
  .empty ul {
    padding-left: 1.2rem;
    margin: 0.4rem 0 0;
  }
  .empty li {
    margin-bottom: 0.3rem;
  }

  .upload {
    cursor: pointer;
  }
  .upload input {
    display: none;
  }
</style>
