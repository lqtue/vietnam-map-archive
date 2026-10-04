<!--
  ExploreRightSidebar.svelte — desktop right rail for /explore.

  Mirrors ExploreSidebar exactly, and not by copy: the frame (`.sb-rail` +
  `is-right`, `.sb-rail-filters`, `.sb-rail-tabs`, `.sb-rail-body`) and the
  crown's bar (`.sb-search`) both live in `components/sidebar.css`. Crown, one
  search bar, a .sb-pill tab strip, one card that swaps its body. Left rail is
  the archive; this one is the sheet on top of the stack.

    ┌ This sheet ─────────────────── ⇥ ┐
    │ ⌕ Search a place…                │  PlaceSearchBar
    │ ◎ MY LOCATION                    │  .sb-more-btn, as the left rail's
    │ ( Info ) ( Legend ) ( Control )  │  FILTERS disclosure
    │ …metadata, legend rows, controls…│
    └──────────────────────────────────┘

  The search and "My location" are at the top rather than inside Control
  because they are how you get anywhere on the map — the same job the left
  rail's filter bar does for the archive, and My location wears that bar's
  FILTERS face (`.sb-more-btn`) in the same slot. `LayerControlsPanel`
  therefore takes `showSearch={false}` and `showGps={false}` here, or the
  Control tab would show a second of each.

  Info carries TopSheetActions (⬡ Traced · Scan · Studio · Share). Those four
  sat above the tab strip until Sept 2026, where they pushed the tabs down and
  belonged to no tab.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { SeriesRef } from '$lib/map/stores/layersStore';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import LayerControlsPanel from '$lib/features/shared/LayerControlsPanel.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';
  import SheetInfoPanel from '$lib/features/shared/SheetInfoPanel.svelte';
  import SheetLegendPanel from '$lib/features/shared/SheetLegendPanel.svelte';
  import PlaceSearchBar from '$lib/features/shared/PlaceSearchBar.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';

  const dispatch = createEventDispatcher<{
    toggleCollapse: void;
    changeViewMode: { mode: ViewMode };
    pickLocation: { lat: number; lng: number; label: string; zoom?: number };
    toggleGps: void;
    toggleLegendPoints: void;
    clearFocus: void;
    toggleVectors: { mapId: string };
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
  }>();

  export let viewMode: ViewMode = 'overlay';
  export let gpsActive = false;
  /** Top overlay's map id — what Legend and Info describe. */
  export let mapId: string | null = null;
  /** Same map, resolved against the loaded list, for the Info tab. */
  export let map: MapListItem | null = null;
  export let showLegendPoints = false;
  /** Whether the top sheet's traced fabric is drawn — owned by the page. */
  export let vectorsOn = false;

  type Tab = 'info' | 'legend' | 'control';
  const TABS: { key: Tab; label: string }[] = [
    { key: 'info', label: 'Info' },
    { key: 'legend', label: 'Legend' },
    { key: 'control', label: 'Control' },
  ];
  export let tab: Tab = 'info';
  export let series: SeriesRef | null = null;
  export let seriesMaps: MapListItem[] = [];
  export let seriesLoading = false;
  export let embedded = false;

  /**
   * The row the reader last flew to — the list's half of the map's pulse.
   * Bound by the page so Escape can clear both at once.
   */
  export let selectedN: number | null = null;
</script>

<aside class="sb-rail is-right" data-tour="controls" class:embedded>
  <div class="sb-bar">
    <span class="sb-bar-title">{series ? 'This series' : $t('This sheet')}</span>
    <button
      type="button"
      class="sb-btn is-icon is-ghost"
      on:click={() => dispatch('toggleCollapse')}
      aria-label="Collapse panel"
      title="Hide panel"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      >
        <path d="M9 3h10a2 2 0 012 2v14a2 2 0 01-2 2H9" /><path d="M5 8l4 4-4 4" />
      </svg>
    </button>
  </div>

  <div class="sb-rail-filters">
    <PlaceSearchBar on:pickLocation={(e) => dispatch('pickLocation', e.detail)} />
    <button
      type="button"
      class="sb-more-btn"
      class:is-on={gpsActive}
      on:click={() => dispatch('toggleGps')}
      aria-pressed={gpsActive}
      title={gpsActive ? 'Stop GPS tracking' : 'Use my location'}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
      </svg>
      {gpsActive ? 'GPS on' : 'My location'}
    </button>
  </div>

  {#if series}
    <div class="series-summary">
      <strong>{series.name}</strong>
      <p>{seriesLoading ? 'Loading sheets…' : `${seriesMaps.length} displayable sheets`}</p>
      <label
        >Inspect a sheet
        <select
          value={mapId ?? ''}
          on:change={(event) =>
            dispatch('inspectMap', {
              mapId: event.currentTarget.value,
              tab: tab === 'legend' ? 'legend' : 'info',
            })}
        >
          <option value="" disabled>Choose a sheet…</option>
          {#each seriesMaps as sheet (sheet.id)}<option value={sheet.id}>{sheet.name}</option
            >{/each}
        </select>
      </label>
      <p>Info and legends belong to individual sheets.</p>
    </div>
  {/if}
  <div class="sb-rail-tabs">
    <Tabs
      tone="rail"
      label="Sheet panes"
      tabs={TABS}
      active={tab}
      on:change={(e) => (tab = e.detail.key as Tab)}
    />
  </div>

  <div class="sb-rail-body">
    <SidebarCard grow={1} flush={true} padded={tab !== 'control'}>
      {#if tab === 'info'}
        <SheetInfoPanel
          {mapId}
          {map}
          {vectorsOn}
          on:toggleVectors={(e) => dispatch('toggleVectors', e.detail)}
        />
      {:else if tab === 'legend'}
        <SheetLegendPanel
          {mapId}
          {showLegendPoints}
          bind:selectedN
          on:toggleLegendPoints={() => dispatch('toggleLegendPoints')}
          on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
          on:clearFocus={() => dispatch('clearFocus')}
        />
      {:else}
        <!-- `showSearch={false}` / `showGps={false}`: the rail carries both at
             its crown.
             `legendPointsAvailable={false}`: the Legend tab carries that
             toggle, beside the list it switches on. -->
        <LayerControlsPanel
          {viewMode}
          {gpsActive}
          showSearch={false}
          showGps={false}
          legendPointsAvailable={false}
          on:changeViewMode={(e) => dispatch('changeViewMode', e.detail)}
          on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
          on:toggleGps={() => dispatch('toggleGps')}
        />
      {/if}
    </SidebarCard>
  </div>
</aside>

<style>
  .series-summary {
    padding: 0.75rem;
    border-bottom: var(--sb-border);
  }
  .series-summary p {
    margin: 0.4rem 0;
    font-size: 0.75rem;
    color: var(--sb-text-meta);
  }
  .series-summary label {
    display: grid;
    gap: 0.3rem;
  }
  .series-summary select {
    width: 100%;
    min-width: 0;
    background: var(--sb-bg);
    color: var(--sb-text);
    border: var(--sb-border);
  }
  .embedded {
    width: 100%;
    height: auto;
  }
</style>
