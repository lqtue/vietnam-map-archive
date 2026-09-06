<!--
  /explore?mode=browse — VMA's canonical map-viewing surface.

  Mounted by the /explore route dispatcher, which owns the <title> and the
  mode switcher. Everything below is the browse mode itself.

  Reuses the same MapWorkspace chrome as the (now-merged) /view route and
  adds:
    • a one-time welcome chooser (location vs. show-all),
    • coverage lookup at the user's GPS fix,
    • an interactive tour for first-time visitors,
    • ?map=/?story= deeplinks (preserved from legacy /view share links).

  Deeplinks bypass the welcome modal entirely.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import type Map from 'ol/Map';

  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { resolveMapRef } from '$lib/features/stories/shared/applyPoint';
  import { createGeoMapStores } from '$lib/map/shell/geoMapSetup';
  import type { Bbox } from '$lib/core/geo/mapBounds';
  import { layersStore, toHistoricalRef } from '$lib/map/stores/layersStore';
  import { fetchPublicStories } from '$lib/data/supabase/stories';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import { createStoryPlayerStore } from '$lib/features/stories/shared/storyStore';
  import type { Story, StoryPoint } from '$lib/features/stories/shared/types';

  import MapWorkspace from '$lib/map/shell/MapWorkspace.svelte';
  import DualMapPane from '$lib/map/shell/DualMapPane.svelte';
  import GpsTracker from '$lib/map/shell/GpsTracker.svelte';
  import StoryMarkers from '$lib/features/stories/shared/StoryMarkers.svelte';
  import LegendPointsLayer from '$lib/features/explore/LegendPointsLayer.svelte';
  import FocusPulse from '$lib/features/explore/FocusPulse.svelte';
  import FootprintsLayer from '$lib/features/explore/FootprintsLayer.svelte';
  import PressPanel from '$lib/features/explore/PressPanel.svelte';
  import StoryPlayback from '$lib/features/stories/shared/StoryPlayback.svelte';
  import LayerStackPanel from '$lib/features/shared/LayerStackPanel.svelte';
  import LayerControlsPanel from '$lib/features/shared/LayerControlsPanel.svelte';

  import ExploreSidebar from '$lib/features/explore/ExploreSidebar.svelte';
  import ExploreBrowsePanel from '$lib/features/explore/ExploreBrowsePanel.svelte';
  import ExplorePrivacyNotice from '$lib/features/explore/ExplorePrivacyNotice.svelte';
  import ExploreSheet from '$lib/features/explore/ExploreSheet.svelte';
  import ExploreTour, { shouldShowTour } from '$lib/features/explore/ExploreTour.svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import {
    SAIGON_CENTER,
    SAIGON_DEFAULT_ZOOM,
    type ResolvedMap,
  } from '$lib/features/explore/spatialLookup';
  import { createExploreCoverage } from '$lib/features/explore/useExploreCoverage';
  import { createExploreZoom } from '$lib/features/explore/exploreZoom';
  import {
    createExploreUrl,
    applyExploreUrlParams,
    LABEL_ZOOM,
  } from '$lib/features/explore/exploreUrl';
  import type { LabelHit } from '$lib/features/shared/catalogSearch';
  import { OPACITY_STEP, isTypingTarget, stepByYear } from '$lib/features/explore/exploreKeys';
  import '$styles/layouts/mode-shared.css';

  type Mode = 'location' | 'all';

  const { supabase, session } = getSupabaseContext();
  const { mapStore, layerStore } = createGeoMapStores();
  const storyPlayer = createStoryPlayerStore(supabase, session?.user?.id);

  // ── MapWorkspace-managed state ─────────────────────────────────
  let mapList: MapListItem[] = [];
  let shellMap: Map | null = null;
  let sidebarCollapsed = false;
  let isMobile = false;
  let openDrawer: 'none' | 'layers' | 'controls' | 'browse' | 'legacy' = 'none';

  // ── Explore-specific state ─────────────────────────────────────
  let choseMode = false;
  let mode: Mode | null = null;
  let userPosition: [number, number] | null = null;
  let matches: ResolvedMap[] = [];
  let loading = true;
  let gpsActive = false;
  let gpsAllowed = false;
  let gpsError: string | null = null;
  let stories: Story[] = [];
  let activeStory: Story | null = null;
  let role: 'user' | 'mod' | 'admin' = 'user';
  /**
   * The deeplink this page has already acted on, as `map|at|story`.
   *
   * It was a boolean, which latched: once anything had been applied — a shared
   * link on load, or just the first `syncMapParam` from tapping a row — the
   * guard below never opened again. So a command-palette pick made from /explore
   * itself changed the URL and nothing else, because SvelteKit reuses the
   * component for a same-route `goto`. Keying on the value means our own writes
   * still mark themselves applied (via `markApplied`), while a genuinely new
   * `?map=`/`?at=` re-opens the guard.
   */
  let appliedUrl = '';

  const { addMapOverlay, setViewFromBounds, zoomToMap } = createExploreZoom(mapStore);
  const { syncMapParam, syncAtParam, tallyMapOpen } = createExploreUrl({
    supabase,
    role: () => role,
    // Pin whatever $page.url currently holds, so our own shallow write is never
    // mistaken for a new inbound link. `syncMapParam` uses pushState, which
    // leaves $page.url alone — a real navigation is the only thing that moves it.
    markApplied: () => (appliedUrl = deeplinkKey),
  });
  const coverage = createExploreCoverage({
    getMapList: () => mapList,
    setMapList: (list) => (mapList = list),
    canSeeDrafts: () => canSeeDrafts,
    setLoading: (v) => (loading = v),
  });

  // ── Reactive derivations ───────────────────────────────────────
  $: viewMode = $layerStore.viewMode;
  $: basemapSelection = $layerStore.basemap;
  $: dualPaneActive = viewMode === 'dual';
  $: sideAlt = $layersStore.overlays[1] ?? null;
  $: stackCount = $layersStore.overlays.length;
  // Numbered-legend point overlay — gated to the active (top) overlay map.
  $: activeOverlayMapId = $layersStore.overlays[0]?.ref.mapId ?? null;
  let showLegendPoints = false;
  /** The spot a search hit sent us to, pulsed once so it is findable. */
  let focusPoint: { lng: number; lat: number } | null = null;
  /** Overlay maps whose reviewed footprints are drawn on the ground. */
  let vectorMapIds: string[] = [];
  /** The place and year the press panel is showing, if any. */
  let pressFor: { q: string; year: number | null } | null = null;
  $: if (!activeOverlayMapId) showLegendPoints = false;
  $: playerState = $storyPlayer;
  $: activeStoryProgress = activeStory ? (playerState.progress[activeStory.id] ?? null) : null;

  // URL deeplinks — auto-dismiss the welcome modal when present.
  $: paramMapId = $page.url.searchParams.get('map');
  $: paramAt = $page.url.searchParams.get('at');
  $: paramStoryId = $page.url.searchParams.get('story');
  $: hasDeeplink = !!(paramMapId || paramStoryId);
  $: if (hasDeeplink && !choseMode) {
    choseMode = true;
    mode = 'all';
  }

  // Reactive deeplink application — both `mapList` (from MapWorkspace) and
  // `stories` (from onMount fetch) arrive async, so a one-shot in onMount
  // races with whichever finishes second. Run once when both are ready.
  $: deeplinkKey = [paramMapId ?? '', paramAt ?? '', paramStoryId ?? ''].join('|');
  $: if (
    appliedUrl !== deeplinkKey &&
    mapList.length > 0 &&
    (paramMapId || (paramStoryId && stories.length > 0))
  ) {
    appliedUrl = deeplinkKey;
    void applyExploreUrlParams({
      mapId: paramMapId,
      at: paramAt,
      storyId: paramStoryId,
      maps: mapList,
      stories,
      addMapOverlay,
      tallyMapOpen,
      zoomToMap,
      setView: (v) => {
        mapStore.setView(v);
        focusPoint = { lng: v.lng, lat: v.lat };
      },
      startStory: (story) => {
        activeStory = story;
        storyPlayer.startStory(story.id);
      },
    });
  }

  // Admins/mods get draft maps in coverage too (mirrors the browse panel).
  $: canSeeDrafts = role === 'admin' || role === 'mod';

  // Coverage match runs whenever the user moves OR new bounds land. Pure
  // client-side filter — no Supabase round-trip.
  $: if (userPosition && mapList.length > 0) {
    matches = coverage.matchAt(userPosition[0], userPosition[1]);
    loading = coverage.pendingBoundsIds().length > 0;
  }

  // Trigger bounds resolution as new entries arrive. Re-runs when canSeeDrafts
  // flips (role lands after mount) so draft maps get their bounds backfilled
  // too. The attemptedBounds guard inside prevents re-fetching the same ids.
  $: if (mapList.length > 0) {
    void canSeeDrafts;
    void coverage.ensureBoundsResolved();
  }

  // ── Guided tour ────────────────────────────────────────────────
  // Wait for coverage to resolve so step 1 (Browse) shows location-relevant
  // rows in location mode. In all-mode the catalogue is enough.
  let tourOpen = false;
  let tourPending = false;
  $: if (tourPending && !tourOpen) {
    const ready = mode === 'all' ? mapList.length > 0 : userPosition !== null && !loading;
    if (ready) {
      tourPending = false;
      tourOpen = true;
    }
  }
  function requestTour() {
    if (shouldShowTour()) tourPending = true;
  }

  // ── GPS ────────────────────────────────────────────────────────
  function handleGpsPosition(e: CustomEvent<{ lon: number; lat: number }>) {
    const pos: [number, number] = [e.detail.lon, e.detail.lat];
    // Snap the camera on the first fix only — the user may have panned away by
    // the time later updates land.
    if (!userPosition) mapStore.setView({ lng: pos[0], lat: pos[1], zoom: 15 });
    userPosition = pos;
  }
  function handleGpsError(e: CustomEvent<{ message: string }>) {
    gpsError = e.detail.message;
  }
  function toggleGps() {
    gpsActive = !gpsActive;
    gpsError = null;
  }

  // ── Welcome chooser ────────────────────────────────────────────
  function chooseLocation() {
    choseMode = true;
    mode = 'location';
    gpsAllowed = true;
    gpsActive = true;
    requestTour();
  }
  function chooseShowAll() {
    choseMode = true;
    mode = 'all';
    gpsAllowed = false;
    gpsActive = false;
    mapStore.setView({ lng: SAIGON_CENTER[0], lat: SAIGON_CENTER[1], zoom: SAIGON_DEFAULT_ZOOM });
    requestTour();
  }

  // ── Sheet CTAs ─────────────────────────────────────────────────
  function jumpToSaigon() {
    userPosition = [SAIGON_CENTER[0], SAIGON_CENTER[1]];
    mapStore.setView({ lng: SAIGON_CENTER[0], lat: SAIGON_CENTER[1], zoom: SAIGON_DEFAULT_ZOOM });
  }

  // ── Catalog / sidebar event handlers ───────────────────────────
  function handlePickLocation(e: CustomEvent<{ lat: number; lng: number; bbox?: Bbox }>) {
    const { lat, lng, bbox } = e.detail;
    if (bbox) setViewFromBounds(bbox);
    else mapStore.setView({ lng, lat, zoom: 15 });
  }

  // Additive: tap a row → add to stack (if not on) + zoom to it. Never
  // clears — removal is explicit via Layers panel × or tap-again.
  async function handlePickMap(e: CustomEvent<any>) {
    const item = e.detail?.map ?? e.detail;
    if (!item?.id) return;
    const map = mapList.find((m) => m.id === item.id) ?? (item as MapListItem);
    addMapOverlay(map);
    syncMapParam(map.id);
    tallyMapOpen(map.id);
    await zoomToMap(map);
  }
  /** A label hit from the browse pane: stack its map, then land on the spot. */
  function handlePickLabel(e: CustomEvent<LabelHit>) {
    const h = e.detail;
    const map = mapList.find((m) => m.id === h.map_id);
    if (!map) return;
    addMapOverlay(map);
    syncMapParam(map.id);
    tallyMapOpen(map.id);
    if (h.lng != null && h.lat != null) {
      mapStore.setView({ lng: h.lng, lat: h.lat, zoom: LABEL_ZOOM });
      focusPoint = { lng: h.lng, lat: h.lat };
      syncAtParam(focusPoint);
      // The label names the place, the sheet it came from dates it.
      pressFor = { q: h.text, year: h.year ?? map.year ?? null };
    } else {
      void zoomToMap(map, { force: true });
    }
  }
  /**
   * Keyboard time scrubber: ← / → walk the top overlay through the years,
   * ↑ / ↓ move its opacity. The camera deliberately stays put — holding one
   * spot still while the years change is the point.
   */
  function handleKeydown(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
    const top = $layersStore.overlays[0];
    if (!top) return;

    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const next = stepByYear(mapList, top.ref.mapId, e.key === 'ArrowLeft' ? -1 : 1);
      if (!next) return;
      e.preventDefault();
      // Add first, then drop the old one, so the map never renders bare. A
      // refused add (the stack is at MAX_OVERLAY_LAYERS, or the map is already
      // on) must not remove anything: swapping a sheet for nothing is worse
      // than not swapping.
      if (!layersStore.addOverlay(toHistoricalRef(next), { opacity: top.opacity })) return;
      layersStore.removeOverlayByMapId(top.ref.mapId);
      syncMapParam(next.id);
      tallyMapOpen(next.id);
      return;
    }

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      const delta = e.key === 'ArrowUp' ? OPACITY_STEP : -OPACITY_STEP;
      layersStore.setOpacity(top.id, top.opacity + delta);
    }
  }

  function handleToggleVectors(e: CustomEvent<{ mapId: string }>) {
    const { mapId } = e.detail;
    vectorMapIds = vectorMapIds.includes(mapId)
      ? vectorMapIds.filter((id) => id !== mapId)
      : [...vectorMapIds, mapId];
  }

  function handleRemoveOverlay(e: CustomEvent<{ mapId: string }>) {
    // A removed sheet takes its fabric with it.
    vectorMapIds = vectorMapIds.filter((id) => id !== e.detail.mapId);
    layersStore.removeOverlayByMapId(e.detail.mapId);
    syncMapParam($layersStore.overlays[0]?.ref.mapId ?? null);
  }
  function handleZoomToOverlay(e: CustomEvent<{ mapId: string }>) {
    const m = mapList.find((x) => x.id === e.detail.mapId);
    if (m) void zoomToMap(m, { force: true });
  }

  // ── Stories ────────────────────────────────────────────────────
  function handleNavigatePoint(e: CustomEvent<{ index: number; point: StoryPoint }>) {
    const { point } = e.detail;
    if (point.coordinates) {
      mapStore.setView({ lng: point.coordinates[0], lat: point.coordinates[1], zoom: 17 });
    }
    if (point.overlayMapId) {
      const found = resolveMapRef(mapList, point.overlayMapId);
      if (found) addMapOverlay(found, { clear: true });
    }
  }
  function handleCompletePoint(e: CustomEvent<{ storyId: string; pointId: string }>) {
    if (!activeStory) return;
    storyPlayer.completePoint(e.detail.storyId, e.detail.pointId, activeStory.points.length);
  }
  function closeStory() {
    storyPlayer.stopStory();
    activeStory = null;
  }

  onMount(async () => {
    mapStore.setView({ lng: SAIGON_CENTER[0], lat: SAIGON_CENTER[1], zoom: SAIGON_DEFAULT_ZOOM });
    role = (await fetchUserRole(supabase, session?.user?.id)) ?? 'user';
    try {
      stories = await fetchPublicStories(supabase);
    } catch (err) {
      console.error('[explore] Failed to load stories:', err);
    }
  });
</script>

<svelte:window on:keydown={handleKeydown} />

<svelte:head>
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1"
  />
</svelte:head>

<div class="explore-mode" class:mobile={isMobile}>
  <MapWorkspace
    {supabase}
    {mapStore}
    {layerStore}
    tabOrder={['browse', 'layers', 'controls']}
    {dualPaneActive}
    bind:mapList
    bind:shellMap
    bind:sidebarCollapsed
    bind:isMobile
    bind:openDrawer
  >
    <svelte:fragment slot="sidebar">
      <ExploreSidebar
        {viewMode}
        {mapList}
        {vectorMapIds}
        {gpsActive}
        {matches}
        {role}
        legendPointsAvailable={!!activeOverlayMapId}
        {showLegendPoints}
        forceBrowseExpanded={mode === 'all'}
        on:zoomToOverlay={handleZoomToOverlay}
        on:toggleVectors={handleToggleVectors}
        on:pickMap={handlePickMap}
        on:pickLabel={handlePickLabel}
        on:removeOverlay={handleRemoveOverlay}
        on:pickLocation={handlePickLocation}
        on:changeViewMode={(e) => layerStore.setViewMode(e.detail.mode)}
        on:toggleGps={toggleGps}
        on:toggleLegendPoints={() => (showLegendPoints = !showLegendPoints)}
        on:toggleCollapse={() => (sidebarCollapsed = true)}
      />
    </svelte:fragment>

    <svelte:fragment slot="mobile-layers">
      <div class="mobile-pane" data-tour="layers-mobile">
        <LayerStackPanel
          {viewMode}
          {mapList}
          {vectorMapIds}
          on:zoomToOverlay={handleZoomToOverlay}
          on:toggleVectors={handleToggleVectors}
        />
      </div>
    </svelte:fragment>

    <svelte:fragment slot="mobile-controls">
      <div class="mobile-pane" data-tour="controls-mobile">
        <LayerControlsPanel
          {viewMode}
          {gpsActive}
          legendPointsAvailable={!!activeOverlayMapId}
          {showLegendPoints}
          on:changeViewMode={(e) => layerStore.setViewMode(e.detail.mode)}
          on:pickLocation={handlePickLocation}
          on:toggleGps={toggleGps}
          on:toggleLegendPoints={() => (showLegendPoints = !showLegendPoints)}
        />
      </div>
    </svelte:fragment>

    <svelte:fragment slot="mobile-browse">
      <div class="mobile-pane" data-tour="browse-mobile">
        <ExploreBrowsePanel
          {matches}
          {role}
          forceExpanded={mode === 'all'}
          on:pick={handlePickMap}
          on:pickLabel={handlePickLabel}
          on:remove={handleRemoveOverlay}
        />
      </div>
    </svelte:fragment>

    <svelte:fragment slot="map-children">
      <GpsTracker
        active={gpsActive && gpsAllowed}
        on:position={handleGpsPosition}
        on:error={handleGpsError}
      />
      <LegendPointsLayer mapId={activeOverlayMapId} enabled={showLegendPoints} />
      <FocusPulse point={focusPoint} />
      <FootprintsLayer mapIds={vectorMapIds} />
      {#if activeStory}
        <StoryMarkers
          points={activeStory.points}
          currentIndex={activeStoryProgress?.currentPointIndex ?? 0}
        />
        <StoryPlayback
          story={activeStory}
          progress={activeStoryProgress}
          on:navigatePoint={handleNavigatePoint}
          on:completePoint={handleCompletePoint}
          on:close={closeStory}
          on:finish={closeStory}
        />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="dual-pane">
      {#if dualPaneActive && shellMap}
        <DualMapPane
          primaryMap={shellMap}
          basemap={basemapSelection}
          showOverlay={!!sideAlt}
          overlayOpacity={sideAlt?.opacity ?? 1}
          activeAllmapsId={sideAlt?.ref.allmapsId ?? ''}
        />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="map-overlay">
      {#if choseMode && mode === 'location' && userPosition && !loading && matches.length === 0 && stackCount === 0}
        <ExploreSheet userLocation={userPosition} on:jumpToSaigon={jumpToSaigon} />
      {/if}
      {#if tourPending || (loading && mode === 'location' && choseMode)}
        <div class="resolving" role="status">
          <span class="spinner" aria-hidden="true"></span>
          {mode === 'location' ? 'Looking up maps at your location…' : 'Loading archive…'}
        </div>
      {/if}
      {#if gpsError}
        <div class="gps-error" role="alert">{gpsError}</div>
      {/if}
      <PressPanel
        q={pressFor?.q ?? null}
        year={pressFor?.year ?? null}
        on:close={() => (pressFor = null)}
      />
    </svelte:fragment>
  </MapWorkspace>

  {#if !hasDeeplink}
    <ExplorePrivacyNotice on:allow={chooseLocation} on:skip={chooseShowAll} />
  {/if}
  <ExploreTour
    open={tourOpen}
    {mapStore}
    {layerStore}
    {isMobile}
    on:close={() => (tourOpen = false)}
    on:setDrawer={(e) => (openDrawer = e.detail.drawer)}
  />
</div>
