<!--
  LayerControlsPanel.svelte — shared map controls panel.

  Used by both the desktop sidebar and the mobile "Controls" drawer. Houses
  everything that isn't a layer row or a catalog row:
    • Display mode (Stacked / Lens / Side-by-side)
    • Base map (Maps / Satellite / None)
    • Location search (Nominatim)
    • My Location (GPS toggle)
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { layersStore } from '$lib/map/stores/layersStore';
  import type { ViewMode } from '$lib/map/types';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';
  import { getShellContext } from '$lib/map/shell/context';

  const { layerStore } = getShellContext();

  export let viewMode: ViewMode = 'overlay';
  export let gpsActive: boolean = false;
  /** When false, "Side-by-side" is hidden — used by tool pages (/explore?mode=annotate, /explore?mode=story). */
  export let allowDual: boolean = true;
  /** Show the "Legend points" toggle (only when the active overlay has legend data). */
  export let legendPointsAvailable: boolean = false;
  export let showLegendPoints: boolean = false;

  const dispatch = createEventDispatcher<{
    changeViewMode: { mode: ViewMode };
    pickLocation: {
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
    };
    toggleGps: void;
    toggleLegendPoints: void;
  }>();

  const ALL_DISPLAY_MODES: { mode: ViewMode; label: string; icon: string }[] = [
    { mode: 'overlay', label: 'Stacked', icon: '≡' },
    { mode: 'spy', label: 'Lens', icon: '◎' },
    { mode: 'dual', label: 'Side-by-side', icon: '⊟' },
  ];
  $: DISPLAY_MODES = allowDual
    ? ALL_DISPLAY_MODES
    : ALL_DISPLAY_MODES.filter((m) => m.mode !== 'dual');
  const BASE_CHOICES: { key: string; label: string }[] = [
    { key: 'g-streets', label: '🗺️ Maps' },
    { key: 'g-satellite', label: '🛰️ Satellite' },
    { key: 'g-custom', label: '🔗 Custom' },
  ];

  $: state = $layersStore;
  $: currentBaseKey = state.base.kind === 'basemap' ? state.base.key : 'g-streets';
  $: customUrl = $layerStore.customBaseUrl ?? '';

  function setBase(key: string) {
    layersStore.setBase({ kind: 'basemap', key });
  }

  let customUrlDraft = '';
  $: customUrlDraft = customUrl;

  function applyCustomUrl() {
    const v = customUrlDraft.trim();
    layerStore.setCustomBaseUrl(v || null);
    if (v) layersStore.setBase({ kind: 'basemap', key: 'g-custom' });
  }
  function clearCustomUrl() {
    customUrlDraft = '';
    layerStore.setCustomBaseUrl(null);
  }

  let locQuery = '';
  function onPickLocation(
    e: CustomEvent<{
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
    }>
  ) {
    dispatch('pickLocation', e.detail);
    locQuery = '';
  }
</script>

<div class="mcp">
  <div class="mcp-row">
    <span class="mcp-leader">Display</span>
    <div class="sb-pill-row mcp-grow">
      {#each DISPLAY_MODES as m}
        <button
          type="button"
          class="sb-pill is-compact"
          class:is-on={viewMode === m.mode}
          on:click={() => dispatch('changeViewMode', { mode: m.mode })}
          >{m.icon} <span class="mcp-lbl">{m.label}</span></button
        >
      {/each}
    </div>
  </div>

  <div class="mcp-row">
    <span class="mcp-leader">Base</span>
    <div class="sb-pill-row mcp-grow">
      {#each BASE_CHOICES as c}
        <button
          type="button"
          class="sb-pill is-compact"
          class:is-on={currentBaseKey === c.key}
          on:click={() => setBase(c.key)}>{c.label}</button
        >
      {/each}
    </div>
  </div>

  {#if currentBaseKey === 'g-custom'}
    <div class="mcp-row mcp-custom">
      <span class="mcp-leader">URL</span>
      <input
        class="mcp-url-input mcp-grow"
        type="url"
        placeholder={'https://…/{z}/{x}/{y}.png'}
        bind:value={customUrlDraft}
        on:change={applyCustomUrl}
        on:keydown={(e) => e.key === 'Enter' && applyCustomUrl()}
      />
      {#if customUrl}
        <button type="button" class="sb-btn is-sm" on:click={clearCustomUrl} title="Clear">×</button
        >
      {/if}
    </div>
  {/if}

  {#if legendPointsAvailable}
    <button
      type="button"
      class="sb-btn is-sm mcp-legend"
      class:is-on={showLegendPoints}
      on:click={() => dispatch('toggleLegendPoints')}
      title="Show numbered legend references on the map"
    >
      <span class="mcp-legend-dot">№</span>
      <span>{showLegendPoints ? 'Legend points on' : 'Legend points'}</span>
    </button>
  {/if}

  <div class="mcp-row">
    <button
      type="button"
      class="sb-btn is-sm mcp-gps"
      class:is-on={gpsActive}
      on:click={() => dispatch('toggleGps')}
      title={gpsActive ? 'Stop GPS tracking' : 'Use my location'}
    >
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
      </svg>
      <span>{gpsActive ? 'GPS on' : 'My location'}</span>
    </button>
    <label class="mo-search is-compact mcp-grow">
      <svg
        class="mo-search-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        class="mo-search-input"
        type="search"
        placeholder="Search a place…"
        bind:value={locQuery}
      />
      {#if locQuery}
        <button
          type="button"
          class="mo-search-clear"
          on:click={() => (locQuery = '')}
          aria-label="Clear">×</button
        >
      {/if}
    </label>
  </div>
  {#if locQuery}
    <LocationSearch query={locQuery} on:pickLocation={onPickLocation} />
  {/if}
</div>

<style>
  .mcp {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.5rem 0.55rem 0.55rem;
  }
  .mcp-row {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
  .mcp-leader {
    flex-shrink: 0;
    width: 44px;
    font-family: var(--sb-font-display);
    font-size: 0.62rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--sb-text-meta);
  }
  .mcp-grow {
    flex: 1;
    min-width: 0;
  }
  .mcp-gps {
    flex-shrink: 0;
  }
  .mcp-legend {
    width: 100%;
    justify-content: flex-start;
    margin-bottom: 0.4rem;
  }
  .mcp-legend-dot {
    font-family: var(--sb-font-display);
    font-weight: 800;
  }

  .mcp-url-input {
    flex: 1;
    min-width: 0;
    min-height: 28px;
    padding: 0.2rem 0.5rem;
    font-size: 0.74rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    border: var(--rule-hair) solid var(--rule);
    border-radius: 4px;
    background: var(--ground-raised);
    color: var(--ink);
  }
</style>
