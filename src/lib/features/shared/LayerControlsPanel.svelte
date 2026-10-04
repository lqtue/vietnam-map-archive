<!--
  LayerControlsPanel.svelte — shared map controls panel.

  Used by both the desktop sidebar and the mobile "Controls" drawer. Houses
  everything that isn't a layer row or a catalog row:
    • Display mode (Stacked / Lens / Side-by-side)
    • Base map (Maps / Satellite / None)
    • My Location (GPS toggle) — `showGps={false}` drops it, for the same
      reason as `showSearch`: /explore's right rail carries one at its crown
    • Location search (Nominatim) — `PlaceSearchBar`, and `showSearch={false}`
      drops it: /explore's right rail carries one at the top of the rail
      instead, so the Control tab would have shown a second.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import { layersStore } from '$lib/map/stores/layersStore';
  import type { ViewMode } from '$lib/map/types';
  import PlaceSearchBar from './PlaceSearchBar.svelte';
  import { getShellContext } from '$lib/map/shell/context';

  const { layerStore } = getShellContext();

  export let viewMode: ViewMode = 'overlay';
  export let gpsActive: boolean = false;
  /** When false, "Side-by-side" is hidden — used by tool pages (annotate, story). */
  export let allowDual: boolean = true;
  /** Show the "Legend points" toggle (only when the active overlay has legend data). */
  export let legendPointsAvailable: boolean = false;
  export let showLegendPoints: boolean = false;
  /** Render the place search. False where the caller already has one. */
  export let showSearch: boolean = true;
  /** Render the GPS toggle. False where the caller already has one. */
  export let showGps: boolean = true;

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
    { key: 'g-streets', label: 'OpenStreetMap' },
    { key: 'g-archive', label: 'Archive' },
    { key: 'g-satellite', label: 'Satellite' },
    { key: 'g-custom', label: 'Custom' },
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
</script>

<div class="mcp">
  <div class="mcp-row">
    <span class="mcp-leader">{$t('Display')}</span>
    <div class="sb-pill-row mcp-grow">
      {#each DISPLAY_MODES as m (m.mode)}
        <button
          type="button"
          class="sb-pill is-compact"
          class:is-on={viewMode === m.mode}
          title={m.label}
          aria-label={m.label}
          on:click={() => dispatch('changeViewMode', { mode: m.mode })}
          >{m.icon} <span class="mcp-lbl">{m.label}</span></button
        >
      {/each}
    </div>
  </div>

  <div class="mcp-row">
    <span class="mcp-leader">Base</span>
    <div class="sb-pill-row mcp-grow mcp-base">
      {#each BASE_CHOICES as c (c.key)}
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
        <button type="button" class="sb-btn is-sm" on:click={clearCustomUrl} title={$t('Clear')}
          >×</button
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
      title={$t('Show numbered legend references on the map')}
    >
      <span class="mcp-legend-dot">№</span>
      <span>{showLegendPoints ? 'Legend points on' : 'Legend points'}</span>
    </button>
  {/if}

  {#if showGps}
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
    </div>
  {/if}

  {#if showSearch}
    <PlaceSearchBar on:pickLocation={(e) => dispatch('pickLocation', e.detail)} />
  {/if}
</div>

<style>
  .mcp {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.5rem 0.55rem 0.55rem;
    /* The pill labels drop out by how much room this panel has, not by how
       wide the window is — it lives in a ~300px sidebar on a 1440px screen. */
    container-type: inline-size;
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
  .mcp-base {
    flex-wrap: wrap;
  }
  .mcp-base .sb-pill {
    flex-basis: 40%;
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
  .mcp-lbl {
    /* Hidden on a narrow sidebar; the icons stay readable. This used to be a
       @media (max-width: 320px), which reads the viewport — so on any desktop
       it never fired and "Side-by-side" pushed the pill row past the panel. */
    display: inline;
  }
  /* 340px, measured on .mcp: three labelled pills plus the 44px leader need
     ~330px, so the default desktop rail (317px of .mcp) drops to icons — each
     pill keeps its name in title/aria-label — while the mobile drawer and a
     rail the reader drags wider keep the words. */
  @container (max-width: 340px) {
    .mcp-lbl {
      display: none;
    }
  }

  .mcp-url-input {
    flex: 1;
    min-width: 0;
    min-height: 28px;
    padding: 0.2rem 0.5rem;
    font-size: 0.74rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    background: var(--sb-bg);
    color: var(--sb-text);
  }
</style>
