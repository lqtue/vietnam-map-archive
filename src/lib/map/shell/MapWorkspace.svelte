<!--
  MapWorkspace.svelte — Unified map base for View/Create/Annotate (and future modes).

  Owns the shared chrome (ToolLayout + MapShell + LayerRenderer + MapModeOverlays)
  so that mode pages become thin plugin shells that supply only their differentiating bits.

  Slots
    sidebar         — desktop sidebar panel
    mobile-layers   — mobile "Layers" drawer body
    mobile-browse   — mobile "Browse" drawer body
    mobile-sidebar  — legacy single-drawer fallback for other modes
    floating        — extra bottom-right buttons
    map-children    — children injected inside MapShell's default slot
    dual-pane       — content rendered in the right pane when {dualPaneActive}
    map-overlay     — absolutely-positioned DOM above the map

  What this component owns
    • Mounting MapShell, LayerRenderer, MapModeOverlays
    • Loading mapList (`fetchMaps` + bounds backfill); deriving selectedMap
    • Forwarding view-mode changes to layerStore
    • "Zoom to Map" prompt for the spinner

  What it does NOT own
    • Auth gates (caller decides whether to render us)
    • Mode-specific stores (story, project, layer-stack, annotation)
    • URL parameter parsing (the route page reads params and seeds the stores)
-->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { writable } from 'svelte/store';
  import type Map from 'ol/Map';
  import type { SupabaseClient } from '@supabase/supabase-js';

  import type { MapListItem } from '$lib/data/maps/types';
  import type { createMapStore } from '$lib/map/stores/mapStore';
  import type { createLayerStore } from '$lib/map/stores/layerStore';
  import { createMapList } from '$lib/map/shell/useMapList';
  import { setShellContext } from '$lib/map/shell/context';

  import ToolLayout from '$lib/map/shell/ToolLayout.svelte';
  import MapShell from '$lib/map/shell/MapShell.svelte';
  import LayerRenderer from '$lib/map/shell/LayerRenderer.svelte';
  import MapModeOverlays from '$lib/map/shell/MapModeOverlays.svelte';

  // ── Props ────────────────────────────────────────────────────────

  /** Supabase client for the initial map-list fetch. Pass null to skip auto-load. */
  export let supabase: SupabaseClient | null = null;
  /** Selected metadata is supplied by bounded consumers such as Explore. */
  export let loadCatalog = true;
  /** When true, MapShell is wrapped in a half-width pane and the `dual-pane` slot is rendered alongside. */
  export let dualPaneActive: boolean = false;

  // ── Stores (caller-owned: route page creates via createGeoMapStores() and passes in) ──

  export let mapStore: ReturnType<typeof createMapStore>;
  export let layerStore: ReturnType<typeof createLayerStore>;

  // ── Bind targets exposed to caller ───────────────────────────────

  /** OL Map instance once mounted. */
  export let shellMap: Map | null = null;
  /** Responsive + sidebar state from ToolLayout. */
  export let sidebarCollapsed: boolean = false;
  export let isMobile: boolean = false;
  export let isCompact: boolean = false;
  /** Initial sidebar width and max-drag width — forwarded to ToolLayout. */
  export let sidebarWidth: number = 320;
  export let sidebarMaxWidth: number = 600;
  /** Width / max-drag / collapsed state of the optional right sidebar. */
  export let rightSidebarWidth: number = 360;
  export let rightSidebarMaxWidth: number = 560;
  export let rightSidebarCollapsed: boolean = false;
  /** Forwarded to ToolLayout — mobile tab order. */
  export let tabOrder: Array<'layers' | 'controls' | 'browse'> = ['layers', 'controls', 'browse'];
  /** Mobile drawer open state — bindable so callers can drive tabs. */
  export let openDrawer: 'none' | 'layers' | 'controls' | 'browse' | 'legacy' = 'none';
  /** Reactive map list. */
  export let mapList: MapListItem[] = [];
  /** Derived from mapList + activeMapId; read-only for callers. */
  export let selectedMap: MapListItem | null = null;

  // ── Events ───────────────────────────────────────────────────────

  const dispatch = createEventDispatcher<{
    mapsloaded: { maps: MapListItem[] };
  }>();

  // Set shell context up here so sidebar slot content (which renders as a
  // sibling of MapShell, not a descendant) can resolve `getShellContext()`.
  // MapShell still sets its own context for its real descendants.
  const mapWritable = writable<Map | null>(null);
  setShellContext({ map: mapWritable, mapStore, layerStore });
  // MapShell binds straight into the context store, so `shellMap` is a
  // derivation of it rather than a second copy pushed across by a `$:`.
  $: shellMap = $mapWritable;

  // ── Reactive store reads ─────────────────────────────────────────

  $: selectedMapId = $mapStore.activeMapId ?? '';
  $: viewMode = $layerStore.viewMode;
  $: lensRadius = $layerStore.lensRadius;

  $: selectedMap = selectedMapId ? (mapList.find((m) => m.id === selectedMapId) ?? null) : null;

  // ── Map list load ────────────────────────────────────────────────

  const listCtrl = createMapList();
  const { maps: mapsStore } = listCtrl;
  $: if (loadCatalog) mapList = $mapsStore;

  onMount(() => {
    if (supabase && loadCatalog) {
      listCtrl
        .loadMaps(supabase)
        .then((m) => dispatch('mapsloaded', { maps: m }))
        .catch((err) => {
          console.error('[MapWorkspace] Failed to load map list:', err);
        });
    }
  });
</script>

<ToolLayout
  bind:sidebarCollapsed
  bind:isMobile
  bind:isCompact
  bind:sidebarWidth
  {sidebarMaxWidth}
  bind:rightSidebarWidth
  {rightSidebarMaxWidth}
  bind:rightSidebarCollapsed
  hasRightSidebar={!!$$slots['right-sidebar']}
  {tabOrder}
  bind:openDrawer
>
  <svelte:fragment slot="sidebar">
    <slot name="sidebar" />
  </svelte:fragment>

  <svelte:fragment slot="right-sidebar">
    <slot name="right-sidebar" />
  </svelte:fragment>

  <!-- Map stage -->
  <div class="dual-container" class:dual-active={dualPaneActive}>
    <div class="dual-primary" class:dual-active={dualPaneActive}>
      <MapShell {mapStore} {layerStore} bind:map={$mapWritable}>
        <LayerRenderer />
        <slot name="map-children" />
      </MapShell>
    </div>
    {#if dualPaneActive}
      <div class="dual-divider"></div>
      <div class="dual-secondary">
        <slot name="dual-pane" />
      </div>
    {/if}
  </div>

  <slot name="map-overlay" />

  <MapModeOverlays
    {viewMode}
    {lensRadius}
    on:lensresize={(e) => layerStore.setLensRadius(e.detail.value)}
  />

  <!-- Floating controls (bottom-right) -->
  <svelte:fragment slot="floating">
    <slot name="floating" />

    {#if isMobile}
      <button
        type="button"
        class="btn is-icon"
        on:click={() => (sidebarCollapsed = !sidebarCollapsed)}
        title="Toggle panel"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>
    {/if}
  </svelte:fragment>

  <svelte:fragment slot="mobile-sidebar">
    <slot name="mobile-sidebar" />
  </svelte:fragment>

  <svelte:fragment slot="mobile-layers">
    <slot name="mobile-layers" />
  </svelte:fragment>

  <svelte:fragment slot="mobile-controls">
    <slot name="mobile-controls" />
  </svelte:fragment>

  <svelte:fragment slot="mobile-browse">
    <slot name="mobile-browse" />
  </svelte:fragment>
</ToolLayout>
