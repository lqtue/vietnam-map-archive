<!--
  AnnotateMode.svelte — the /explore?mode=annotate plugin on MapWorkspace.

  Desktop two-sidebar layout (mirrors /create):
    • Left sidebar  — Layers · Controls · Browse (MapViewerSidebar, shared)
    • Right sidebar — Project header · Annotations · Inspector (AnnotateRightPane)

  Mobile is intentionally unsupported here — the library view still works on
  mobile (read-only project list), but the editor itself is desktop-only.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import '$styles/layouts/create-mode.css';
  import '$styles/components/auth-gate.css';
  import '$styles/components/library.css';

  import type { SearchResult, AnnotationSet, DrawingMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';
  import { createGeoMapStores } from '$lib/map/shell/geoMapSetup';
  import {
    layersStore,
    isSheetLayer,
    toHistoricalRef,
    topOverlay,
  } from '$lib/map/stores/layersStore';
  import { createAnnotationHistoryStore } from '$lib/map/annotations/annotationHistory';
  import { createAnnotationStateStore } from '$lib/map/annotations/annotationState';
  import { setAnnotationContext } from '$lib/map/annotations/annotationContext';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { createMapPickHandlers } from '$lib/features/stories/shared/mapPickHandlers';
  import { createAnnotationProjectStore } from './annotationProjectStore';
  import { createTimelineStore } from './animation/timelineStore';
  import { playTimeline, applyKeyframeInstant, type PlaybackHandle } from './animation/playback';

  import MapWorkspace from '$lib/map/shell/MapWorkspace.svelte';
  import DrawTool from '$lib/map/shell/DrawTool.svelte';
  import MapViewerSidebar from '$lib/features/shared/MapViewerSidebar.svelte';
  import AnnotateRightPane from './AnnotateRightPane.svelte';
  import AnnotateOverpassController from './AnnotateOverpassController.svelte';
  import BboxSelector from './BboxSelector.svelte';
  import OverpassPreviewLayer from './OverpassPreviewLayer.svelte';
  import FootprintsLayer from '$lib/features/shared/FootprintsLayer.svelte';
  import LegendPointsLayer from '$lib/features/shared/LegendPointsLayer.svelte';
  import type { FeatureCollection } from 'geojson';
  import type { Bbox4 } from './overpass';
  import AuthGate from '$lib/ui/AuthGate.svelte';
  import LibraryGrid from '$lib/ui/LibraryGrid.svelte';

  const { supabase, session } = getSupabaseContext();
  const userId = session?.user?.id;

  // Annotation context — shared with DrawTool via Svelte context
  const annotationHistory = createAnnotationHistoryStore(100);
  const annotationState = createAnnotationStateStore();
  setAnnotationContext({ history: annotationHistory, state: annotationState });

  const { mapStore, layerStore } = createGeoMapStores();
  const projectStore = createAnnotationProjectStore(supabase, userId);
  const timelineStore = createTimelineStore();

  // Derived from annotation context (single source of truth)
  $: annotations = $annotationState.list;
  $: selectedAnnotationId = $annotationState.selectedId;

  // Only show projects owned by the current user
  $: myProjects = $projectStore.projects.filter((p) => p.authorId === userId);

  // Bound from MapWorkspace
  let mapList: MapListItem[] = [];
  let selectedMap: MapListItem | null = null;
  let shellMap: import('ol/Map').default | null = null;
  let sidebarCollapsed = false;
  let rightSidebarCollapsed = false;

  // Annotate-specific state
  let drawingMode: DrawingMode | null = null;
  let drawToolRef: DrawTool;
  let notice: { text: string; tone: 'info' | 'error' | 'success' } | null = null;
  let keydownHandler: ((event: KeyboardEvent) => void) | null = null;

  // Control / Legend / Info tabs — same "top of the stack" convention
  // ExplorePage uses for its right rail.
  $: activeOverlayMapId = $topOverlay?.mapId ?? null;
  $: activeOverlayMap = activeOverlayMapId
    ? (mapList.find((m) => m.id === activeOverlayMapId) ?? null)
    : null;
  let vectorMapIds: string[] = [];
  let showLegendPoints = false;
  let legendN: number | null = null;
  $: if (!activeOverlayMapId) showLegendPoints = false;

  function handleToggleVectors(e: CustomEvent<{ mapId: string }>) {
    const { mapId } = e.detail;
    vectorMapIds = vectorMapIds.includes(mapId)
      ? vectorMapIds.filter((id) => id !== mapId)
      : [...vectorMapIds, mapId];
  }

  // Library/Editor view state
  let activeView: 'library' | 'editor' = 'library';
  let projectsLoading = true;
  let currentProject: AnnotationSet | null = null;
  let isSaving = false;
  let saveSuccess = false;

  // Overpass import — the flow lives in AnnotateOverpassController; these three
  // are shared with the two map layers it drives.
  let overpassController: AnnotateOverpassController;
  let bboxPickerActive = false;
  let pickerBbox: Bbox4 | null = null;
  let overpassPreview: FeatureCollection | null = null;

  function handleSearchNavigate(event: CustomEvent<{ result: SearchResult }>) {
    drawToolRef?.zoomToSearchResult(event.detail.result);
  }

  const { handlePickMap, handleZoomToOverlay, handlePickLocation } = createMapPickHandlers({
    mapStore,
    mapList: () => mapList,
    shellMap: () => shellMap,
    // A Studio project can hold several maps — Browse adds to the stack
    // rather than swapping the one overlay out.
    stackOverlays: true,
  });

  /**
   * Restore the project's saved map stack once the catalog has loaded (it
   * hasn't, yet, when a project is opened from the library). Runs once per
   * project: `layersStore` is a global, persisted singleton, so it may still
   * carry whatever browse mode or the previous project left on it.
   */
  let restoredStackFor: string | null = null;
  function handleMapsLoaded(event: CustomEvent<{ maps: MapListItem[] }>) {
    if (!currentProject || restoredStackFor === currentProject.id) return;
    restoredStackFor = currentProject.id;
    const ids = currentProject.mapIds.length ? currentProject.mapIds : [currentProject.mapId];
    layersStore.clearOverlays();
    // addOverlay prepends, so add in reverse to land in saved order.
    for (const mapId of [...ids].reverse()) {
      const m = event.detail.maps.find((x) => x.id === mapId);
      if (m) layersStore.addOverlay(toHistoricalRef(m));
    }
  }

  // ── Annotation event handlers (delegate to DrawTool) ────────────────

  function handleSetDrawingMode(event: CustomEvent<{ mode: DrawingMode | null }>) {
    drawingMode = event.detail.mode;
    if (!drawingMode) drawToolRef?.deactivateDrawing();
  }

  function handleAnnotationClear() {
    drawToolRef?.clearAnnotations();
    notice = { text: 'All annotations cleared.', tone: 'info' };
  }
  function handleAnnotationExport() {
    drawToolRef?.exportAnnotationsAsGeoJSON();
    notice = { text: 'GeoJSON downloaded.', tone: 'success' };
  }
  async function handleAnnotationImport(event: CustomEvent<{ file: File }>) {
    try {
      const text = await event.detail.file.text();
      const count = await drawToolRef?.importGeoJsonText(text);
      notice = {
        text: `Imported ${count ?? 0} feature${(count ?? 0) !== 1 ? 's' : ''}.`,
        tone: 'success',
      };
    } catch (e) {
      console.error('GeoJSON import failed', e);
      notice = { text: 'Failed to import GeoJSON file.', tone: 'error' };
    }
  }

  async function handleSave() {
    if (!currentProject) return;
    isSaving = true;
    const features = drawToolRef?.exportAnnotationsAsGeoJsonObject?.() ?? {
      type: 'FeatureCollection' as const,
      features: [],
    };
    // isSheetLayer excludes series rows — their synthetic `series:<key>` id
    // wouldn't resolve back to a catalog map on reload.
    const mapIds = $layersStore.overlays.filter(isSheetLayer).map((o) => o.ref.mapId);
    await projectStore.saveFeatures(currentProject.id, features, mapIds);
    currentProject = { ...currentProject, mapIds };
    isSaving = false;
    saveSuccess = true;
    setTimeout(() => {
      saveSuccess = false;
    }, 2000);
  }

  function handleRenameProject(event: CustomEvent<{ title: string }>) {
    if (!currentProject) return;
    const title = event.detail.title;
    projectStore.updateProject(currentProject.id, { title });
    currentProject = { ...currentProject, title };
  }

  function handleUndo() {
    drawToolRef?.undoLastAction();
  }
  function handleRedo() {
    drawToolRef?.redoLastAction();
  }

  // ── Timeline / animation playback ────────────────────────────

  let playbackHandle: PlaybackHandle | null = null;

  function handleClearTimeline() {
    playbackHandle?.stop();
    playbackHandle = null;
    timelineStore.clear();
    timelineStore.setPlaying(false, null);
  }
  function handleJumpToKeyframe(e: CustomEvent<{ id: string }>) {
    if (!shellMap) return;
    const frame = $timelineStore.frames.find((f) => f.id === e.detail.id);
    if (frame) applyKeyframeInstant(shellMap, frame);
  }
  function handlePlayTimeline() {
    if (!shellMap) return;
    const frames = $timelineStore.frames;
    if (frames.length < 2) return;
    playbackHandle?.stop();
    timelineStore.setPlaying(true, 0);
    playbackHandle = playTimeline(shellMap, frames, {
      onFrameEnter: (i) => timelineStore.setCurrentIndex(i),
      onFinish: () => {
        timelineStore.setPlaying(false, null);
        playbackHandle = null;
      },
      onError: () => {
        timelineStore.setPlaying(false, null);
        playbackHandle = null;
      },
    });
  }
  function handleStopTimeline() {
    playbackHandle?.stop();
    playbackHandle = null;
    timelineStore.setPlaying(false, null);
  }

  $: canUndo = $annotationHistory.history.length > 0;
  $: canRedo = $annotationHistory.future.length > 0;

  // ── Library handlers ──────────────────────────────────────────

  function handleSelectProject(project: AnnotationSet) {
    restoredStackFor = null;
    currentProject = project;
    if (project.features?.features?.length) {
      setTimeout(() => {
        const text = JSON.stringify(project.features);
        drawToolRef?.importGeoJsonText(text);
      }, 500);
    }
    if (project.mapId) {
      const m = mapList.find((x) => x.id === project.mapId);
      mapStore.setActiveMap(project.mapId, m?.annotation_url ?? m?.allmaps_id);
    }
    activeView = 'editor';
  }

  function handleLibraryCreate(event: CustomEvent<{ title: string }>) {
    const mapId = $mapStore.activeMapId || '';
    const id = projectStore.createProject(event.detail.title, mapId);
    setTimeout(() => {
      const newProject = $projectStore.projects.find((p) => p.id === id);
      if (newProject) {
        currentProject = newProject;
        activeView = 'editor';
      }
    }, 50);
  }

  function handleLibraryRename(event: CustomEvent<{ item: AnnotationSet; title: string }>) {
    projectStore.updateProject(event.detail.item.id, { title: event.detail.title });
  }

  function handleBackToLibrary() {
    playbackHandle?.stop();
    playbackHandle = null;
    timelineStore.setPlaying(false, null);
    currentProject = null;
    drawingMode = null;
    activeView = 'library';
  }

  function featureCount(project: AnnotationSet): number {
    return project.features?.features?.length ?? 0;
  }

  onMount(() => {
    // annotate mode doesn't support side-by-side — snap back if state is stale from /view.
    if ($layerStore.viewMode === 'dual') layerStore.setViewMode('overlay');

    projectStore.loadFromSupabase().finally(() => {
      projectsLoading = false;
    });

    keydownHandler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target.tagName)))
        return;
      const meta = event.metaKey || event.ctrlKey;
      if (!meta) return;
      const key = event.key.toLowerCase();
      if (key === 'z' && !event.shiftKey && canUndo) {
        event.preventDefault();
        handleUndo();
      } else if ((key === 'z' && event.shiftKey) || key === 'y') {
        if (canRedo) {
          event.preventDefault();
          handleRedo();
        }
      }
    };
    window.addEventListener('keydown', keydownHandler);
  });

  onDestroy(() => {
    if (keydownHandler) {
      window.removeEventListener('keydown', keydownHandler);
      keydownHandler = null;
    }
    playbackHandle?.stop();
    playbackHandle = null;
  });
</script>

<!-- Auth Gate: require login -->
{#if !session}
  <AuthGate
    {supabase}
    title="Sign in to annotate"
    body="Sign in with your Google account to create and manage annotation projects."
  />

  <!-- Project Library View -->
{:else if activeView === 'library'}
  <LibraryGrid
    items={myProjects}
    loading={projectsLoading}
    noun="Project"
    sub="Create annotation projects on historical maps"
    thumbIcon="📝"
    createLabel="+ New Project"
    emptyCtaLabel="Create Project"
    emptyTitle="Create your first project"
    emptyText="Draw points, lines, and polygons on historical maps, then save and share your annotations."
    on:select={(e) => handleSelectProject(e.detail.item)}
    on:create={handleLibraryCreate}
    on:rename={handleLibraryRename}
    on:remove={(e) => projectStore.deleteProject(e.detail.item.id)}
  >
    <svelte:fragment slot="title"
      >My <span class="text-highlight">Annotations.</span></svelte:fragment
    >

    <svelte:fragment slot="meta" let:item>
      <span class="badge-chip is-sm chip-gray"
        >{featureCount(item)} feature{featureCount(item) !== 1 ? 's' : ''}</span
      >
      <span class="badge-chip is-sm chip-gray"
        >{new Date(item.updatedAt).toLocaleDateString('en-GB')}</span
      >
    </svelte:fragment>

    <svelte:fragment slot="description" let:item>
      {item.mapId ? `Map: ${item.mapId.slice(0, 8)}...` : 'No map selected'}
    </svelte:fragment>
  </LibraryGrid>

  <!-- Editor View — desktop two-sidebar layout -->
{:else}
  <div class="annotate-mode">
    <MapWorkspace
      {supabase}
      {mapStore}
      {layerStore}
      rightSidebarWidth={380}
      bind:mapList
      bind:selectedMap
      bind:shellMap
      bind:sidebarCollapsed
      bind:rightSidebarCollapsed
      on:searchnavigate={handleSearchNavigate}
      on:mapsloaded={handleMapsLoaded}
    >
      <svelte:fragment slot="sidebar">
        <MapViewerSidebar
          {mapList}
          {selectedMap}
          allowDual={false}
          showControls={false}
          viewMode={$layerStore.viewMode}
          on:toggleCollapse={() => (sidebarCollapsed = true)}
          on:zoomToOverlay={handleZoomToOverlay}
          on:pickMap={handlePickMap}
          on:pickLocation={handlePickLocation}
          on:changeViewMode={(e) => layerStore.setViewMode(e.detail.mode)}
        />
      </svelte:fragment>

      <svelte:fragment slot="right-sidebar">
        <AnnotateRightPane
          project={currentProject}
          {annotations}
          {selectedAnnotationId}
          {selectedMap}
          {drawingMode}
          {isSaving}
          {saveSuccess}
          {notice}
          {timelineStore}
          viewMode={$layerStore.viewMode}
          mapId={activeOverlayMapId}
          map={activeOverlayMap}
          {showLegendPoints}
          vectorsOn={!!activeOverlayMapId && vectorMapIds.includes(activeOverlayMapId)}
          bind:selectedN={legendN}
          on:rename={(e) => drawToolRef?.updateAnnotationLabel(e.detail.id, e.detail.label)}
          on:changeColor={(e) => drawToolRef?.updateAnnotationColor(e.detail.id, e.detail.color)}
          on:updateDetails={(e) =>
            drawToolRef?.updateAnnotationDetails(e.detail.id, e.detail.details)}
          on:toggleVisibility={(e) => drawToolRef?.toggleAnnotationVisibility(e.detail.id)}
          on:select={(e) => annotationState.setSelected(e.detail.id)}
          on:delete={(e) => drawToolRef?.deleteAnnotation(e.detail.id)}
          on:zoomTo={(e) => drawToolRef?.zoomToAnnotation(e.detail.id)}
          on:setDrawingMode={handleSetDrawingMode}
          on:clear={handleAnnotationClear}
          on:exportGeoJSON={handleAnnotationExport}
          on:importFile={handleAnnotationImport}
          on:importOSM={() => overpassController?.openDialog()}
          on:save={handleSave}
          on:renameProject={handleRenameProject}
          on:backToLibrary={handleBackToLibrary}
          on:toggleCollapse={() => (rightSidebarCollapsed = true)}
          on:changeViewMode={(e) => layerStore.setViewMode(e.detail.mode)}
          on:pickLocation={handlePickLocation}
          on:toggleLegendPoints={() => (showLegendPoints = !showLegendPoints)}
          on:toggleVectors={handleToggleVectors}
          on:addKeyframe={() => timelineStore.addFromCurrent(mapStore)}
          on:removeKeyframe={(e) => timelineStore.remove(e.detail.id)}
          on:reorderKeyframe={(e) => timelineStore.reorder(e.detail.id, e.detail.delta)}
          on:updateKeyframe={(e) => timelineStore.update(e.detail.id, e.detail.patch)}
          on:clearTimeline={handleClearTimeline}
          on:jumpToKeyframe={handleJumpToKeyframe}
          on:play={handlePlayTimeline}
          on:stop={handleStopTimeline}
        />
      </svelte:fragment>

      <svelte:fragment slot="map-children">
        <DrawTool bind:this={drawToolRef} {drawingMode} editingEnabled={true} />
        <BboxSelector enabled={bboxPickerActive} bind:bbox={pickerBbox} />
        <OverpassPreviewLayer features={overpassPreview} />
        <LegendPointsLayer mapId={activeOverlayMapId} enabled={showLegendPoints} />
        <FootprintsLayer mapIds={vectorMapIds} />
      </svelte:fragment>
    </MapWorkspace>

    <AnnotateOverpassController
      bind:this={overpassController}
      {shellMap}
      importGeoJson={(text) => drawToolRef?.importGeoJsonText(text)}
      bind:pickerActive={bboxPickerActive}
      bind:pickerBbox
      bind:preview={overpassPreview}
      on:notice={(e) => (notice = e.detail)}
    />
  </div>
{/if}
