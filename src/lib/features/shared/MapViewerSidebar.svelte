<!--
  MapViewerSidebar.svelte — the Layers · Controls · Browse left sidebar shared
  by the two-sidebar map editors (/explore?mode=story, /explore?mode=annotate). Mirrors ViewSidebar.
  Tool-specific authoring lives in each mode's right pane.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import LayerStackPanel from './LayerStackPanel.svelte';
  import LayerControlsPanel from './LayerControlsPanel.svelte';
  import CatalogSidebarPanel from '$lib/features/catalog/shared/CatalogSidebarPanel.svelte';
  import SidebarCard from './SidebarCard.svelte';
  import '$styles/layouts/tool-page.css';

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
</script>

<aside class="panel">
  <div class="sb-bar">
    <span class="sb-bar-title">Map viewer</span>
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

  <SidebarCard title="My layers" grow={3}>
    <LayerStackPanel
      {viewMode}
      {mapList}
      on:zoomToOverlay={(e) => dispatch('zoomToOverlay', e.detail)}
    />
  </SidebarCard>

  <SidebarCard title="Controls" grow={0} scroll={false}>
    <LayerControlsPanel
      {viewMode}
      {gpsActive}
      {allowDual}
      on:changeViewMode={(e) => dispatch('changeViewMode', e.detail)}
      on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
    />
  </SidebarCard>

  <SidebarCard title="Browse the archive" grow={5}>
    <CatalogSidebarPanel
      {role}
      activeId={selectedMap?.id ?? null}
      requireGeoref={true}
      showLayerActions={true}
      showLocation={false}
      on:pick={(e) => dispatch('pickMap', e.detail)}
    />
  </SidebarCard>
</aside>
