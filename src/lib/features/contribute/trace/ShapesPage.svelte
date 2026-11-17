<!--
  /scan?mode=shapes — everything that is a shape rather than a word.

  Two tabs over one sheet and one ImageShell:

    Shapes   — one canvas tool (ShapeTool) for drawing and checking, with two
               views of the sheet's shapes:
                 To check — what waits on a verdict (ReviewSidebar), `?tab=validate`
                 Mine     — what this person drew (TraceSidebar), `?tab=draw`
    Segment  — the MapSAM2 launcher and its pipeline stage (SegSidebar)

  Draw and Validate were separate tabs until Nov 2026, each with its own canvas
  tool doing select-and-drag twice. Checking could not add the block the machine
  missed, and drawing could not see the machine's shapes. Both views now draw,
  edit and show every shape on the sheet; the view picks the list in the sidebar
  and which shapes a click can select. The old `tab=` values stay as the view
  names, so every link to `tab=validate` still opens the check list.

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
  import ShapeTool from './ShapeTool.svelte';
  import ShapeToolbar from './ShapeToolbar.svelte';
  import TraceSidebar from './TraceSidebar.svelte';
  import SegSidebar from './SegSidebar.svelte';
  import ReviewSidebar from '$lib/features/contribute/review/ReviewSidebar.svelte';
  import '$styles/layouts/tool-page.css';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { trackMeasurement } from '$lib/data/measurement';
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
  import type { FeatureType, FootprintSubmission } from '$lib/data/maps/footprintTypes';

  const { supabase, session } = getSupabaseContext();
  const userId = session?.user?.id ?? null;

  type View = 'check' | 'mine';
  /** `?tab=` carries both the tab and the Shapes view: validate · draw · segment. */
  $: rawTab = $page.url.searchParams.get('tab');
  $: tab = (rawTab === 'segment' ? 'segment' : 'shapes') as 'shapes' | 'segment';
  $: view = (rawTab === 'validate' ? 'check' : 'mine') as View;
  /** Keep the open sheet across a change — the tabs and views are links on this route. */
  const hrefFor = (key: string, mapId: string | undefined) =>
    `/scan?mode=shapes&tab=${key}${mapId ? `&map=${mapId}` : ''}`;
  $: tabLinks = [
    {
      key: 'shapes',
      label: 'Shapes',
      href: hrefFor(view === 'check' ? 'validate' : 'draw', currentMap?.id),
    },
    { key: 'segment', label: 'Segment', href: hrefFor('segment', currentMap?.id) },
  ];

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

  // ── Canvas tool ────────────────────────────────────────────────────────────
  type Tool = 'polygon' | 'line' | 'edit';
  /** Checking starts on Edit (click to select), drawing on Polygon; each view keeps its own. */
  let toolFor: Record<View, Tool> = { check: 'edit', mine: 'polygon' };
  $: tool = toolFor[view];
  /** Mine's selection; the check list's lives in the queue. */
  let mineSelectedId: string | null = null;

  // ── Layout ─────────────────────────────────────────────────────────────────
  let sidebarCollapsed = false;
  let rightSidebarCollapsed = false;
  let isMobile = false;
  let imageOpacity = 1;
  let showShapes = true;
  $: railLayers = [{ id: 'shapes', label: 'Shapes', on: showShapes }];

  // ── Derived ────────────────────────────────────────────────────────────────
  $: myFootprints = userId ? $trace.footprints.filter((f) => f.userId === userId) : [];
  $: traceCategories = currentMap?.categories?.length ? currentMap.categories : [];
  $: reviewed = $queue.total - $queue.footprints.length;
  /** The check view is a queue; the others are the archive. */
  $: railMaps =
    tab === 'shapes' && view === 'check'
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
  /**
   * Every shape on the sheet but the rejected, with the check list's local
   * copies (corners dragged, type changed, not yet decided) laid over the saved
   * ones. The queue's rows are added if the sheet-wide read missed them.
   */
  $: waitingById = new Map($queue.footprints.map((f) => [f.id, f]));
  $: sheetRows = mergeRows($trace.footprints, $queue.footprints, waitingById);
  $: canvasFootprints = showShapes ? sheetRows : [];
  $: listRows = view === 'check' ? $queue.footprints : myFootprints;
  $: activeIds = new Set(listRows.map((f) => f.id));
  $: selectedId = view === 'check' ? $queue.selectedId : mineSelectedId;

  function mergeRows(
    saved: FootprintSubmission[],
    waiting: FootprintSubmission[],
    byId: Map<string, FootprintSubmission>
  ): FootprintSubmission[] {
    const seen = new Set(saved.map((f) => f.id));
    return [
      ...saved.filter((f) => f.status !== 'rejected').map((f) => byId.get(f.id) ?? f),
      ...waiting.filter((f) => !seen.has(f.id)),
    ];
  }

  async function selectMap(m: LabelMapInfo) {
    if (currentMap?.id === m.id) return;
    currentMap = m;
    trackMeasurement('contribution_open', {
      surface: 'scan',
      workflow: 'shapes',
      map_id: m.id,
      mode: 'shapes',
      action: 'open',
    });
    iiifInfoUrl = null;
    mineSelectedId = null;
    trace.reset();
    queue.reset();
    segConfig = loadSegConfig(m.id, segConfig);
    markReviewedError = '';
    // resolveMapIiifInfoUrl prefers m.iiifImage, so R2-mirrored maps resolve too.
    const [url] = await Promise.all([resolveMapIiifInfoUrl(m), loadForTab()]);
    iiifInfoUrl = url;
  }

  /** Each tab wants a different thing about the same sheet; load it once, on arrival.
      Both Shapes views draw the whole sheet, so a view change loads nothing. */
  let loadedFor = '';
  async function loadForTab() {
    const id = currentMap?.id;
    if (!id) return;
    const key = `${id}:${tab}`;
    if (loadedFor === key) return;
    loadedFor = key;
    if (tab === 'segment') await loadPipeline();
    else await Promise.all([trace.load(), queue.open(id)]);
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

  async function decideFootprint(id: string, status: Verdict) {
    if (currentMap) trace.settle(await queue.decide(currentMap.id, id, status));
  }

  async function decideSelected(status: Verdict) {
    if (currentMap) trace.settle(await queue.decideMany(currentMap.id, $queue.selectedIds, status));
  }

  // ── Canvas events ──────────────────────────────────────────────────────────
  async function drawShape(
    pixelPolygon: FootprintSubmission['pixelPolygon'],
    geometry: 'Polygon' | 'LineString'
  ) {
    const row = await trace.draw(pixelPolygon, geometry);
    // New shapes are `submitted`: they wait on a verdict like the machine's.
    if (row) queue.add(row);
  }

  function selectShape(id: string | null) {
    if (view === 'check') queue.select(id);
    else mineSelectedId = id;
  }

  /** Your own shape saves at once; anyone else's is held for the verdict. */
  function modifyShape(id: string, pixelPolygon: FootprintSubmission['pixelPolygon']) {
    const mine = userId !== null && sheetRows.some((f) => f.id === id && f.userId === userId);
    if (mine) trace.modify(id, pixelPolygon);
    if (waitingById.has(id)) queue.edit(id, pixelPolygon);
  }

  function removeShape(id: string) {
    trace.remove(id);
    if (currentMap) queue.drop(currentMap.id, id);
    if (mineSelectedId === id) mineSelectedId = null;
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
            message={view === 'check'
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
        {:else}
          <nav class="view-chips" aria-label="Which shapes">
            <a
              class="chip"
              class:is-on={view === 'check'}
              aria-current={view === 'check' ? 'page' : undefined}
              href={hrefFor('validate', currentMap.id)}>To check · {$queue.footprints.length}</a
            >
            <a
              class="chip"
              class:is-on={view === 'mine'}
              aria-current={view === 'mine' ? 'page' : undefined}
              href={hrefFor('draw', currentMap.id)}>Mine · {myFootprints.length}</a
            >
          </nav>
          {#if view === 'mine'}
            <TraceSidebar
              {traceCategories}
              placedFootprints={myFootprints}
              drawMode={tool === 'edit' ? 'select' : 'trace'}
              newFootprintId={$trace.newId}
              on:removeFootprint={(e) => removeShape(e.detail.footprintId)}
              on:updateFootprintMeta={(e) =>
                trace.retitle(e.detail.footprintId, {
                  name: e.detail.name,
                  featureType: e.detail.featureType as FeatureType | undefined,
                  category: e.detail.category,
                })}
            />
          {:else if $queue.loading}
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
        {/if}

        <svelte:fragment slot="footer">
          <Tabs tone="rail" label="Shape tabs" tabs={tabLinks} active={tab} />
        </svelte:fragment>
      </ToolSidebarShell>
    </svelte:fragment>

    <!-- Image stage -->
    {#if currentMap && iiifInfoUrl}
      <ImageShell {iiifInfoUrl} footprints={canvasFootprints} {imageOpacity}>
        {#if tab === 'shapes'}
          <ShapeTool
            footprints={canvasFootprints}
            {activeIds}
            {selectedId}
            {tool}
            myUserId={userId}
            on:draw={(e) => drawShape(e.detail.pixelPolygon, e.detail.geometry)}
            on:select={(e) => selectShape(e.detail.id)}
            on:modify={(e) => modifyShape(e.detail.id, e.detail.pixelPolygon)}
            on:remove={(e) => removeShape(e.detail.id)}
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
        {#if mapsError || $queue.queueError}
          <p class="empty-state error">{mapsError || $queue.queueError}</p>
        {/if}
      </div>
    {:else}
      <div class="loading-stage">
        <div class="spinner"></div>
        <span>Loading map…</span>
      </div>
    {/if}
  </ToolLayout>

  <!-- The canvas tools: both Shapes views draw and edit. -->
  {#if currentMap && tab === 'shapes'}
    <ShapeToolbar {tool} on:change={(e) => (toolFor = { ...toolFor, [view]: e.detail.tool })} />
  {/if}
</div>

<style>
  .view-chips {
    display: flex;
    gap: 0.4rem;
    padding: 0.5rem 0.75rem;
  }
</style>
