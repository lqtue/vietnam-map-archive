<!--
  MapViewerSidebar.svelte — the left rail shared by the two-sidebar map
  editors (the story and annotate modes). Same frame as ExploreSidebar
  (`.sb-rail`, `.sb-rail-tabs`, `.sb-rail-body`, one `Tabs` strip) rather than
  three always-stacked cards — the two drifted apart when Studio grew its own
  right-rail Control tab, and this brings them back to one shape.

    ┌ Map viewer ─────────────────── ⇤ ┐
    │ ( Layers 2 )( Browse )( Controls )│  Controls only when `showControls`
    │ …stack, or the archive, or view…  │
    └──────────────────────────────────┘

  `showControls` is off for Studio, whose right rail already carries a
  Control tab (same reason Browse mode's own left rail carries no Controls
  pane at all — ExploreSidebar's doc comment). Create mode's right rail has
  no such tab, so it keeps the default.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import { layersStore } from '$lib/map/stores/layersStore';
  import Tabs from '$lib/ui/Tabs.svelte';
  import LayerStackPanel from './LayerStackPanel.svelte';
  import LayerControlsPanel from './LayerControlsPanel.svelte';
  import CatalogSidebarPanel from '$lib/features/catalog/shared/CatalogSidebarPanel.svelte';
  import SidebarCard from './SidebarCard.svelte';

  const dispatch = createEventDispatcher<{
    toggleCollapse: void;
    zoomToOverlay: { mapId: string };
    pickMap: MapListItem;
    pickLocation: {
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
    };
    changeViewMode: { mode: ViewMode };
  }>();

  export let mapList: MapListItem[] = [];
  export let selectedMap: MapListItem | null = null;
  export let viewMode: ViewMode = 'overlay';
  export let gpsActive = false;
  export let role: 'user' | 'mod' | 'admin' = 'user';
  /** When false, hides Side-by-side from the display-mode toggle. */
  export let allowDual: boolean = true;
  /** Off for a caller whose own right rail already has a Control tab. */
  export let showControls = true;

  type Tab = 'layers' | 'browse' | 'controls';
  $: tabs = [
    { key: 'layers' as Tab, label: $t('Layers') },
    { key: 'browse' as Tab, label: $t('Browse') },
    ...(showControls ? [{ key: 'controls' as Tab, label: 'Controls' }] : []),
  ];
  /** The stack's own size rides the tab, same as ExploreSidebar's Picked count. */
  $: stackedCount = $layersStore.overlays.length;
  $: tabsWithCount = tabs.map((row) =>
    row.key === 'layers' && stackedCount ? { ...row, label: `${row.label} ${stackedCount}` } : row
  );

  let tab: Tab = 'browse';
  /** Land on Layers once something is on the map, but only the first time —
   *  same rule and reason as ExploreSidebar's `tabSettled`. */
  let tabSettled = false;
  $: if (!tabSettled && stackedCount) {
    tabSettled = true;
    tab = 'layers';
  }
  function chooseTab(next: Tab) {
    tabSettled = true;
    tab = next;
  }
</script>

<aside class="sb-rail">
  <div class="sb-bar">
    <span class="sb-bar-title">{$t('Map viewer')}</span>
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
        <path d="M15 3H5a2 2 0 00-2 2v14a2 2 0 002 2h10" /><path d="M19 8l-4 4 4 4" />
      </svg>
    </button>
  </div>

  <div class="sb-rail-tabs">
    <Tabs
      tone="rail"
      label="Map viewer panes"
      tabs={tabsWithCount}
      active={tab}
      on:change={(e) => chooseTab(e.detail.key as Tab)}
    />
  </div>

  <div class="sb-rail-body">
    <SidebarCard grow={1} flush={true}>
      {#if tab === 'layers'}
        <LayerStackPanel
          {viewMode}
          {mapList}
          on:zoomToOverlay={(e) => dispatch('zoomToOverlay', e.detail)}
        />
      {:else if tab === 'browse'}
        <CatalogSidebarPanel
          {role}
          activeId={selectedMap?.id ?? null}
          requireGeoref={true}
          showLayerActions={true}
          showLocation={false}
          on:pick={(e) => dispatch('pickMap', e.detail)}
        />
      {:else}
        <LayerControlsPanel
          {viewMode}
          {gpsActive}
          {allowDual}
          on:changeViewMode={(e) => dispatch('changeViewMode', e.detail)}
          on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
        />
      {/if}
    </SidebarCard>
  </div>
</aside>
