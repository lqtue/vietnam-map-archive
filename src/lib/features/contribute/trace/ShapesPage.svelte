<!--
  /scan?mode=shapes — everything that is a shape rather than a word.

  Three tabs over one sheet and one ImageShell, chosen by `?tab=`:

    Draw      — trace polygons and lines by hand (TraceTool + TraceSidebar)
    Segment   — the MapSAM2 launcher and its pipeline stage (SegSidebar)
    Validate  — approve or reject what SAM2 drew (ReviewTool + ReviewSidebar)

  They were three places — /scan?mode=trace, the Segmentation phase of
  ?mode=triage, and /scan?mode=review — which is one sheet opened three times
  and the same canvas built three times. It is one loop: draw a few by hand,
  let the model do the rest, check what it did.

  The tabs are links, not state: same route, same component instance, so the
  canvas and the open sheet survive a tab change. The sheet list is the
  exception — Validate is a queue (sheets with shapes waiting, badged with how
  many), the other two are the archive.

  Writes live in `traceData.ts` and `review/reviewQueue.ts`; this file is layout.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import ToolLayout from '$lib/map/shell/ToolLayout.svelte';
  import ImageShell from '$lib/map/shell/ImageShell.svelte';
  import ScanLeftRail from '$lib/features/contribute/shared/ScanLeftRail.svelte';
  import ToolSidebarShell from '$lib/features/contribute/shared/ToolSidebarShell.svelte';
  import EmptyPanel from '$lib/features/contribute/shared/EmptyPanel.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import TraceTool from './TraceTool.svelte';
  import TraceSidebar from './TraceSidebar.svelte';
  import SegSidebar from './SegSidebar.svelte';
  import ReviewTool from '$lib/features/contribute/review/ReviewTool.svelte';
  import ReviewSidebar from '$lib/features/contribute/review/ReviewSidebar.svelte';
  import '$styles/layouts/tool-page.css';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { resolveMapIiifInfoUrl } from '$lib/features/contribute/shared/iiifSource';
  import { createTrace } from './traceData';
  import { createReviewQueue, type Verdict } from '$lib/features/contribute/review/reviewQueue';
  import { DEFAULT_SEG_CONFIG, loadSegConfig, saveSegConfig, type SegConfig } from './segCommand';
  import {
    fetchPipelineStatus,
    advancePipelineStage,
    type PipelineStatus,
    type HumanStage,
  } from '$lib/features/contribute/pipelineApi';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';
  import type { FeatureType } from '$lib/data/maps/footprintTypes';

  const { supabase, session } = getSupabaseContext();
  const userId = session?.user?.id ?? null;

  const TABS = [
    { key: 'draw', label: 'Draw' },
    { key: 'segment', label: 'Segment' },
    { key: 'validate', label: 'Validate' },
  ];
  $: tab = TABS.some((t) => t.key === $page.url.searchParams.get('tab'))
    ? ($page.url.searchParams.get('tab') as 'draw' | 'segment' | 'validate')
    : 'draw';
  /** Keep the open sheet across a tab change — the tabs are links on this route. */
  $: tabLinks = TABS.map((t) => ({
    ...t,
    href: `/scan?mode=shapes&tab=${t.key}${currentMap ? `&map=${currentMap.id}` : ''}`,
  }));

  // ── The sheet ──────────────────────────────────────────────────────────────
  let currentMap: LabelMapInfo | null = null;
  let iiifInfoUrl: string | null = null;
  let mapsError = '';

  const trace = createTrace({ supabase, userId, getMapId: () => currentMap?.id ?? null });
  const queue = createReviewQueue(supabase);

  // ── Segment ────────────────────────────────────────────────────────────────
  let segConfig: SegConfig = { ...DEFAULT_SEG_CONFIG };
  let pipeline: { status: PipelineStatus | null; loading: boolean; error: string } = {
    status: null,
    loading: false,
    error: '',
  };
  let markingReviewed = false;
  let markReviewedError = '';

  // ── Drawing mode ───────────────────────────────────────────────────────────
  let traceTool: 'polygon' | 'line' | 'edit' = 'polygon';
  $: drawMode = (traceTool === 'edit' ? 'select' : 'trace') as 'trace' | 'select';
  $: geometryMode = (traceTool === 'line' ? 'LineString' : 'Polygon') as 'Polygon' | 'LineString';

  // ── Layout ─────────────────────────────────────────────────────────────────
  let sidebarCollapsed = false;
  let rightSidebarCollapsed = false;
  let isMobile = false;
  let imageOpacity = 1;
  let showShapes = true;
  $: railLayers = [
    { id: 'shapes', label: tab === 'validate' ? 'Machine shapes' : 'Shapes', on: showShapes },
  ];

  // ── Derived ────────────────────────────────────────────────────────────────
  $: myFootprints = userId ? $trace.footprints.filter((f) => f.userId === userId) : [];
  $: traceCategories = currentMap?.categories?.length ? currentMap.categories : [];
  $: reviewed = $queue.total - $queue.footprints.length;
  /** Validate is a queue, the other tabs are the archive. */
  $: railMaps =
    tab === 'validate'
      ? $queue.queue.map((m): LabelMapInfo => ({
          id: m.id,
          name: m.name,
          allmapsId: m.allmapsId,
          iiifImage: m.iiifImage ?? undefined,
          legend: [],
          categories: [],
          triage: null,
          badge: `${m.pendingCount} pending`,
        }))
      : null;
  /** One canvas, two sources: what a person drew, or what the machine proposes. */
  $: canvasFootprints = !showShapes
    ? []
    : tab === 'validate'
      ? $queue.footprints
      : $trace.footprints;

  async function selectMap(m: LabelMapInfo) {
    if (currentMap?.id === m.id) return;
    currentMap = m;
    iiifInfoUrl = null;
    trace.reset();
    queue.reset();
    segConfig = loadSegConfig(m.id, segConfig);
    markReviewedError = '';
    // resolveMapIiifInfoUrl prefers m.iiifImage, so R2-mirrored maps resolve too.
    const [url] = await Promise.all([resolveMapIiifInfoUrl(m), loadForTab()]);
    iiifInfoUrl = url;
  }

  /** Each tab wants a different thing about the same sheet; load it once, on arrival. */
  let loadedFor = '';
  async function loadForTab() {
    const id = currentMap?.id;
    if (!id) return;
    const key = `${id}:${tab}`;
    if (loadedFor === key) return;
    loadedFor = key;
    if (tab === 'validate') await queue.open(id);
    else if (tab === 'segment') await loadPipeline();
    else await trace.load();
  }
  $: if (currentMap && tab) loadForTab();
  // The queue rail's list is ours, not the picker's, so `loaded` never fires there.
  $: if (railMaps) pickWanted(railMaps);

  $: if (currentMap?.id) saveSegConfig(currentMap.id, segConfig);

  async function loadPipeline() {
    if (!currentMap?.id) return;
    pipeline = { ...pipeline, loading: true, error: '' };
    try {
      pipeline.status = await fetchPipelineStatus(currentMap.id);
    } catch (e: any) {
      pipeline.error = e.message;
    } finally {
      pipeline.loading = false;
    }
  }

  function advanceSeg(stage: HumanStage) {
    if (!currentMap) return;
    advancePipelineStage(currentMap.id, stage)
      .then((status) => (pipeline.status = status))
      .catch((e) => (pipeline.error = e.message));
  }

  function decideFootprint(id: string, status: Verdict) {
    if (currentMap) queue.decide(currentMap.id, id, status);
  }

  function decideSelected(status: Verdict) {
    if (currentMap) queue.decideMany(currentMap.id, $queue.selectedIds, status);
  }

  async function markReviewed() {
    if (!currentMap) return;
    markingReviewed = true;
    markReviewedError = '';
    try {
      await advancePipelineStage(currentMap.id, 'seg_reviewed');
    } catch (e: any) {
      markReviewedError = e.message;
    } finally {
      markingReviewed = false;
    }
  }

  /**
   * `?map=` — the link the Segment tab hands out, and the one /admin?tab=status
   * points at. Resolved against whichever list the rail loaded, so it works on
   * the archive and on the queue alike; taken once, then left alone.
   */
  let wanted = '';
  function pickWanted(maps: LabelMapInfo[]) {
    if (!wanted) return;
    const row = maps.find((m) => m.id === wanted);
    if (!row) return;
    wanted = '';
    selectMap(row);
  }

  onMount(() => {
    wanted = $page.url.searchParams.get('map') ?? '';
    queue.loadQueue();
  });
</script>

<svelte:head>
  <title>{currentMap ? `${currentMap.name} — Shapes` : 'Shapes'} — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Trace building footprints and road networks on historical maps, and check the ones the model drew."
  />
</svelte:head>

<div class="tool-page">
  <ToolLayout
    bind:sidebarCollapsed
    bind:rightSidebarCollapsed
    bind:isMobile
    hasRightSidebar
    tabOrder={['browse', 'controls']}
  >
    <!-- Left: which sheet. Same rail, same place, in every /scan mode. -->
    <svelte:fragment slot="sidebar">
      <ScanLeftRail
        mode="shapes"
        maps={railMaps}
        layers={railLayers}
        selectedMapId={currentMap?.id ?? null}
        bind:imageOpacity
        onCollapse={() => (sidebarCollapsed = true)}
        on:select={(e) => selectMap(e.detail.map)}
        on:loaded={(e) => pickWanted(e.detail.maps)}
        on:error={(e) => (mapsError = e.detail.message)}
        on:toggle={(e) => (showShapes = e.detail.on)}
      />
    </svelte:fragment>

    <!-- Right: the shape work, whichever kind this tab is. -->
    <svelte:fragment slot="right-sidebar">
      <ToolSidebarShell title="Shapes" onCollapse={() => (rightSidebarCollapsed = true)}>
        {#if !currentMap}
          <EmptyPanel
            message={tab === 'validate'
              ? 'Pick a sheet from the queue to start checking.'
              : 'Select a map to start tracing.'}
          />
        {:else if tab === 'segment'}
          <SegSidebar
            mapId={currentMap.id}
            status={pipeline.status}
            loading={pipeline.loading}
            error={pipeline.error}
            bind:config={segConfig}
            on:advance={(e) => advanceSeg(e.detail.stage)}
            on:refresh={loadPipeline}
          />
        {:else if tab === 'validate'}
          {#if $queue.loading}
            <EmptyPanel message="Loading footprints…" />
          {:else if $queue.error}
            <EmptyPanel message={$queue.error} />
          {:else}
            <ReviewSidebar
              footprints={$queue.footprints}
              selectedId={$queue.selectedId}
              selectedIds={$queue.selectedIds}
              total={$queue.total}
              {reviewed}
              approving={$queue.deciding}
              {markingReviewed}
              {markReviewedError}
              reviewTags={$queue.feedback.tags}
              reviewNote={$queue.feedback.note}
              iiifBase={$queue.iiifBase}
              imageWidth={$queue.imageWidth}
              imageHeight={$queue.imageHeight}
              on:select={(e) => queue.select(e.detail.id, e.detail.mode)}
              on:approve={(e) => decideFootprint(e.detail.id, 'approved')}
              on:reject={(e) => decideFootprint(e.detail.id, 'rejected')}
              on:approveSelected={() => decideSelected('approved')}
              on:rejectSelected={() => decideSelected('rejected')}
              on:selectAll={queue.selectAll}
              on:clearSelection={queue.clearSelection}
              on:retype={(e) => queue.retype(e.detail.id, e.detail.featureType)}
              on:feedback={(e) =>
                queue.setFeedback(e.detail.id, { tags: e.detail.tags, note: e.detail.note })}
              on:markReviewed={markReviewed}
            />
          {/if}
        {:else}
          <TraceSidebar
            {traceCategories}
            placedFootprints={myFootprints}
            {drawMode}
            newFootprintId={$trace.newId}
            on:removeFootprint={(e) => trace.remove(e.detail.footprintId)}
            on:updateFootprintMeta={(e) =>
              trace.retitle(e.detail.footprintId, {
                name: e.detail.name,
                featureType: e.detail.featureType as FeatureType | undefined,
                category: e.detail.category,
              })}
          />
        {/if}

        <svelte:fragment slot="footer">
          <Tabs tone="rail" label="Shape tabs" tabs={tabLinks} active={tab} />
        </svelte:fragment>
      </ToolSidebarShell>
    </svelte:fragment>

    <!-- Image stage -->
    {#if currentMap && iiifInfoUrl}
      <ImageShell {iiifInfoUrl} footprints={canvasFootprints} {imageOpacity}>
        {#if tab === 'validate'}
          <ReviewTool
            footprints={canvasFootprints}
            selectedId={$queue.selectedId}
            on:select={(e) => queue.select(e.detail.id)}
            on:edit={(e) => queue.edit(e.detail.id, e.detail.pixelPolygon)}
          />
        {:else if tab === 'draw'}
          <TraceTool
            {drawMode}
            {geometryMode}
            placingEnabled={drawMode === 'trace'}
            myUserId={userId}
            on:drawPolygon={(e) => trace.draw(e.detail.pixelPolygon, geometryMode)}
            on:modifyFootprint={(e) => trace.modify(e.detail.footprintId, e.detail.pixelPolygon)}
            on:removeFootprint={(e) => trace.remove(e.detail.footprintId)}
          />
        {/if}
      </ImageShell>
    {:else if !currentMap}
      <div class="empty-stage">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.25"
        >
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
        </svg>
        <p>
          {tab === 'validate'
            ? $queue.queue.length === 0 && !$queue.queueError
              ? "Queue's clear — no shapes waiting on review."
              : 'Pick a sheet from the queue to start checking.'
            : 'Pick a map to start tracing.'}
        </p>
        {#if mapsError || $queue.queueError}
          <p class="empty-state error">{mapsError || $queue.queueError}</p>
        {/if}
        <a href="/catalog" class="catalog-link">Browse the catalog →</a>
      </div>
    {:else}
      <div class="loading-stage">
        <div class="spinner"></div>
        <span>Loading map…</span>
      </div>
    {/if}
  </ToolLayout>

  <!-- Drawing is the only tab with tools of its own under the canvas. -->
  {#if currentMap && tab === 'draw'}
    <footer class="bottom-bar">
      <button
        type="button"
        class="sb-btn is-sm"
        class:is-on={traceTool === 'polygon'}
        on:click={() => (traceTool = 'polygon')}
        title="Polygon — for buildings and closed shapes"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
        </svg>
        <span>Polygon</span>
      </button>

      <button
        type="button"
        class="sb-btn is-sm"
        class:is-on={traceTool === 'line'}
        on:click={() => (traceTool = 'line')}
        title="Line — for roads and waterways"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="4 19 8 10 14 14 20 5" />
        </svg>
        <span>Line</span>
      </button>

      <button
        type="button"
        class="sb-btn is-sm"
        class:is-on={traceTool === 'edit'}
        on:click={() => (traceTool = 'edit')}
        title="Select and edit a shape"
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
        </svg>
        <span>Edit</span>
      </button>
    </footer>
  {/if}
</div>
