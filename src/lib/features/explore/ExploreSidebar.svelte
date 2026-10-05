<!--
  ExploreSidebar.svelte — desktop left rail for /explore.

  One filter bar over two tabs (Sept 2026 — it was two stacked cards with a
  draggable splitter and persisted weights):

    ┌ Explore ──────────────────── ⇤ ┐
    │ 🔍 search · area · type · period │  one ArchiveFilters, shared
    │ ( All )  ( Picked 3 )            │  .sb-pill strip, as the right rail
    │ …the archive, or the layer stack… │
    └──────────────────────────────────┘

  The rail owns the search engine so both tabs answer to the same query: the
  All tab hands it to `ArchiveBrowser`, and the Picked tab narrows the layer
  stack to the sheets the query still matches (`filterIds`). With no query and
  no facet chosen, Picked shows the whole stack.

  Controls moved to the right rail (ExploreRightSidebar) in Sept 2026 — this
  rail is the archive, that one is the sheet on top of the stack. The frame
  both wear (`.sb-rail`, `.sb-rail-filters`, `.sb-rail-tabs`, `.sb-rail-body`)
  and the bar at the crown (`.sb-search`) live in `components/sidebar.css`: the
  two were identical scoped copies until they drifted into two heights.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher, onMount } from 'svelte';
  import { page } from '$app/stores';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { SeriesRef } from '$lib/map/stores/layersStore';
  import { layersStore } from '$lib/map/stores/layersStore';
  import ArchiveFilters from '$lib/features/shared/ArchiveFilters.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import LayerStackPanel from '$lib/features/shared/LayerStackPanel.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';
  import ExploreBrowsePanel from './ExploreBrowsePanel.svelte';
  import { createCatalogSearch, type LabelHit } from '$lib/features/shared/catalogSearch';
  import type { ResolvedMap } from './spatialLookup';

  const dispatch = createEventDispatcher<{
    toggleCollapse: void;
    pickMap: any;
    pickLabel: LabelHit;
    removeOverlay: { mapId: string };
    zoomToOverlay: { mapId: string; bounds?: [number, number, number, number] };
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
    inspectSeries: { ref: SeriesRef; tab: 'info' | 'legend' };
  }>();

  export let viewMode: ViewMode = 'overlay';
  export let mapList: MapListItem[] = [];
  /** Map ids whose traced fabric is drawn; owned by the page. */
  export let matches: ResolvedMap[] = [];
  export let role: 'user' | 'mod' | 'admin' = 'user';
  /** True while the product tour is pending or open. It sets `tab` itself, per
   *  step, so the auto-switch below must stand aside for it. */
  export let tourActive = false;

  type Tab = 'all' | 'picked';
  const TABS: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'picked', label: 'Picked' },
  ];
  // Labels are translated at render, not at definition: the array is a const
  // and the locale can change under it.
  $: localisedTabs = TABS.map((row) => ({ ...row, label: $t(row.label) }));
  /** Which tab is showing. Bound by the page so the product tour can point at
   *  the pane its step describes. */
  export let tab: Tab = 'all';

  /** Picked carries the size of the stack; a count reads better on the tab than
   *  in the pane, because it is the reason to go there. */
  $: tabsWithCount = localisedTabs.map((row) =>
    row.key === 'picked' && stackedMapIds.length
      ? { ...row, label: `${row.label} ${stackedMapIds.length}` }
      : row
  );

  /**
   * Arriving with sheets already on the map — a share link's `?map=`, or the
   * stack `layersStore` restored from localStorage — should land on them, not
   * on the archive. The stack does not exist yet when this mounts (the page
   * resolves `?map=` asynchronously), so this waits for the first non-empty
   * reading rather than checking once in `onMount`.
   *
   * Three things must not trigger it:
   *
   *   - the reader adding a sheet themselves. The rows are tap-to-add /
   *     tap-again-to-remove, so switching away would pull the list out from
   *     under the second tap;
   *   - the tour, which drives `tab` from the page through its own steps and
   *     owns it outright while running. That is what `tourActive` is for: the
   *     two assignments raced and made `tests/smoke.spec.ts:125` flap, passing
   *     or failing on whichever landed last;
   *   - anything at all after the first switch;
   *   - a `?series=` link. The browse panel is what applies it, so it has to
   *     mount, and a reader who already has a stack would otherwise land on
   *     Picked and never run it.
   */
  let tabSettled = $page.url.searchParams.has('series');
  function chooseTab(next: Tab) {
    tabSettled = true;
    tab = next;
  }
  function pickMap(detail: unknown) {
    tabSettled = true;
    dispatch('pickMap', detail);
  }

  // Only maps that can be laid on the world — the viewer can overlay nothing
  // else. `requireGeoref` therefore lives here rather than on the browser.
  const search = createCatalogSearch({ requireGeoref: true });
  const { query, results, selected } = search;
  onMount(() => search.start());

  $: filterActive =
    !!$query.trim() ||
    ($selected.area?.length ?? 0) > 0 ||
    ($selected.type?.length ?? 0) > 0 ||
    ($selected.year?.length ?? 0) > 0;

  $: stackedMapIds = $layersStore.overlays.map((o) => o.ref.mapId);
  $: matchedIds = new Set($results.map((r) => r.id));
  /** Null while nothing is filtered, so Picked shows the whole stack. */
  $: pickedFilterIds = filterActive ? [...matchedIds] : null;

  // Deliberately does not read `tab`, so assigning it cannot re-trigger this.
  $: if (!tabSettled && !tourActive && stackedMapIds.length) {
    tabSettled = true;
    tab = 'picked';
  }
</script>

<aside class="sb-rail">
  <div class="sb-bar">
    <span class="sb-bar-title">Explore</span>
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

  <div class="sb-rail-filters">
    <ArchiveFilters {search} />
  </div>

  <div class="sb-rail-tabs">
    <Tabs
      tone="rail"
      label="Archive panes"
      tabs={tabsWithCount}
      active={tab}
      on:change={(e) => chooseTab(e.detail.key as Tab)}
    />
  </div>

  <div class="sb-rail-body" data-tour={tab === 'all' ? 'browse' : 'layers'}>
    <SidebarCard grow={1} flush={true}>
      {#if tab === 'all'}
        <ExploreBrowsePanel
          {matches}
          {role}
          {search}
          on:pick={(e) => pickMap(e.detail)}
          on:pickLabel={(e) => dispatch('pickLabel', e.detail)}
          on:remove={(e) => dispatch('removeOverlay', e.detail)}
        />
      {:else}
        <LayerStackPanel
          inspectionInRail={true}
          {viewMode}
          {mapList}
          filterIds={pickedFilterIds}
          on:zoomToOverlay={(e) => dispatch('zoomToOverlay', e.detail)}
          on:inspectMap
          on:inspectSeries
        />
      {/if}
    </SidebarCard>
  </div>
</aside>

<style>
  /* The count rides the pill's own ink in both states, so it needs no colour
     of its own — only steady digit widths. */
</style>
