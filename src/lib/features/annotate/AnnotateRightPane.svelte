<!--
  AnnotateRightPane.svelte — right rail for Studio.

  Mirrors ExploreRightSidebar's frame exactly (`.sb-rail.is-right`,
  `.sb-rail-tabs`, `.sb-rail-body`, the same `Tabs` component) rather than
  /scan's ToolSidebarShell — Studio is an /explore mode, and its sibling
  Browse mode is the rail this one should read as an extension of: the same
  Control / Legend / Info tabs Browse has, plus the two Studio adds.

    ┌ Studio ─────────────────────── ⇥ ┐
    │ ← Library  Title…            •Save│  AnnotateProjectHeader
    │ (Annotate)(Animate)(Control)(Legend)(Info)
    │ …tab body…                        │
    └────────────────────────────────────┘

  Control / Legend / Info reuse the exact components Browse mode's right rail
  uses (`LayerControlsPanel`, `SheetLegendPanel`, `SheetInfoPanel`), read off
  the map on top of the project's stack — the same "this sheet" convention
  Browse and Animate's keyframes already share.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { AnnotationSummary, DrawingMode, AnnotationSet, ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import { t } from '$lib/core/i18n';
  import Tabs from '$lib/ui/Tabs.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';
  import LayerControlsPanel from '$lib/features/shared/LayerControlsPanel.svelte';
  import SheetInfoPanel from '$lib/features/shared/SheetInfoPanel.svelte';
  import SheetLegendPanel from '$lib/features/shared/SheetLegendPanel.svelte';
  import AnnotateProjectHeader from './AnnotateProjectHeader.svelte';
  import AnnotateAnnotationList from './AnnotateAnnotationList.svelte';
  import AnnotateAnnotationInspector from './AnnotateAnnotationInspector.svelte';
  import AnnotateAnimationPanel from './AnnotateAnimationPanel.svelte';
  import type { TimelineStore } from './animation/timelineStore';

  const dispatch = createEventDispatcher<{
    setDrawingMode: { mode: DrawingMode | null };
    toggleCollapse: void;
    backToLibrary: void;
    changeViewMode: { mode: ViewMode };
    pickLocation: { lat: number; lng: number; label: string; zoom?: number };
    toggleLegendPoints: void;
    clearFocus: void;
    toggleVectors: { mapId: string };
  }>();

  export let project: AnnotationSet | null = null;
  export let annotations: AnnotationSummary[] = [];
  export let selectedAnnotationId: string | null = null;
  export let selectedMap: MapListItem | null = null;
  export let drawingMode: DrawingMode | null = null;
  export let isSaving = false;
  export let saveSuccess = false;
  /** Transient status line above the annotation list, owned by AnnotateMode. */
  export let notice: { text: string; tone: 'info' | 'error' | 'success' } | null = null;
  export let timelineStore: TimelineStore;

  // Control / Legend / Info — all describe the map on top of the project's
  // stack, the same "this sheet" AnnotateMode already derives for Animate.
  export let viewMode: ViewMode = 'overlay';
  export let mapId: string | null = null;
  export let map: MapListItem | null = null;
  export let showLegendPoints = false;
  export let vectorsOn = false;
  /** Bound so Escape (owned by the page) can clear the lit legend row too. */
  export let selectedN: number | null = null;

  type Tab = 'annotate' | 'animate' | 'control' | 'legend' | 'info';
  const TABS: { key: Tab; label: string }[] = [
    { key: 'annotate', label: 'Annotate' },
    { key: 'animate', label: 'Animate' },
    { key: 'control', label: 'Control' },
    { key: 'legend', label: 'Legend' },
    { key: 'info', label: 'Info' },
  ];
  let tab: Tab = 'annotate';

  $: selected = annotations.find((a) => a.id === selectedAnnotationId) ?? null;
  $: selectedIndex = selected ? annotations.findIndex((a) => a.id === selected!.id) : -1;

  // Leaving Annotate clears active drawing — same rule the old mode toggle had.
  $: if (tab !== 'annotate' && drawingMode) {
    dispatch('setDrawingMode', { mode: null });
  }
</script>

<aside class="sb-rail is-right">
  <div class="sb-bar">
    <span class="sb-bar-title">{$t('Studio')}</span>
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
    <AnnotateProjectHeader
      {project}
      {selectedMap}
      {isSaving}
      {saveSuccess}
      on:backToLibrary
      on:renameProject
      on:save
    />
  </div>

  <div class="sb-rail-tabs">
    <Tabs
      tone="rail"
      label="Studio panes"
      tabs={TABS}
      active={tab}
      on:change={(e) => (tab = e.detail.key as Tab)}
    />
  </div>

  <div class="sb-rail-body">
    {#if tab === 'annotate'}
      <div class="stack-body">
        <AnnotateAnnotationList
          {annotations}
          {selectedAnnotationId}
          {drawingMode}
          {notice}
          on:setDrawingMode
          on:select
          on:zoomTo
          on:delete
          on:clear
          on:exportGeoJSON
          on:importFile
          on:importOSM
        />

        <AnnotateAnnotationInspector
          {selected}
          index={selectedIndex}
          on:rename
          on:updateDetails
          on:changeColor
          on:toggleVisibility
          on:zoomTo
          on:select
        />
      </div>
    {:else if tab === 'animate'}
      <AnnotateAnimationPanel
        {timelineStore}
        on:addKeyframe
        on:removeKeyframe
        on:reorderKeyframe
        on:updateKeyframe
        on:play
        on:stop
        on:clearTimeline
        on:jumpToKeyframe
      />
    {:else}
      <SidebarCard grow={1} flush={true} padded={tab !== 'control'}>
        {#if tab === 'control'}
          <!-- `legendPointsAvailable={false}`: the Legend tab carries that
               toggle, beside the list it switches on — same rule as
               ExploreRightSidebar's Control tab. -->
          <LayerControlsPanel
            {viewMode}
            gpsActive={false}
            allowDual={false}
            legendPointsAvailable={false}
            on:changeViewMode={(e) => dispatch('changeViewMode', e.detail)}
            on:pickLocation={(e) => dispatch('pickLocation', e.detail)}
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
          <SheetInfoPanel
            {mapId}
            {map}
            {vectorsOn}
            on:toggleVectors={(e) => dispatch('toggleVectors', e.detail)}
          />
        {/if}
      </SidebarCard>
    {/if}
  </div>
</aside>

<style>
  /* Same recipe as AnnotateAnimationPanel's `.anim-mode` — a column flex
     context for the two stacked SidebarCards (list, inspector). */
  .stack-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
