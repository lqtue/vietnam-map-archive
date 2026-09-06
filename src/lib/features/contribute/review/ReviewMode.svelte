<!--
  ReviewMode.svelte — Orchestrator for HITL review of SAM2 needs_review footprints.
  Fetches footprint list, tracks selection, calls admin API to approve/reject.
-->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchSubmittedFootprints } from '$lib/data/supabase/footprints';
  import type { SamFootprint } from '$lib/data/supabase/footprints';
  import { resolveMapIiifInfoUrl } from '$lib/features/contribute/shared/iiifSource';
  import { advancePipelineStage } from '$lib/features/contribute/pipelineApi';
  import type { FeatureType } from '$lib/data/maps/footprintTypes';
  import '$styles/layouts/tool-page.css';
  import ImageShell from '$lib/map/shell/ImageShell.svelte';
  import ReviewTool from './ReviewTool.svelte';
  import ReviewSidebar from './ReviewSidebar.svelte';

  export let mapId: string;
  export let allmapsId: string = '';
  /** Preferred over allmapsId when the map row carries it (R2 mirrors). */
  export let iiifImage: string | null = null;

  const dispatch = createEventDispatcher<{ done: void }>();
  const { supabase } = getSupabaseContext();

  let footprints: SamFootprint[] = [];
  let selectedId: string | null = null;
  let loading = true;
  let loadError = '';
  let approving: string | null = null;
  let updateError = '';
  let markingReviewed = false;
  let markReviewedError = '';

  // Track pending geometry/type edits before approve
  let pendingEdits: Record<string, { pixelPolygon?: [number, number][]; featureType?: string }> =
    {};

  // Derived from the first footprint's iiifCanvas
  let iiifInfoUrl: string | null = null;

  // Progress tracking
  let initialTotal = 0;
  $: reviewed = initialTotal - footprints.length;

  onMount(async () => {
    try {
      footprints = await fetchSubmittedFootprints(supabase, mapId);
      initialTotal = footprints.length;
      selectedId = footprints[0]?.id ?? null;
      iiifInfoUrl = await resolveMapIiifInfoUrl({ iiifImage, allmapsId });
    } catch (e: any) {
      loadError = e.message;
    } finally {
      loading = false;
    }
  });

  function handleEdit(id: string, pixelPolygon: [number, number][]) {
    pendingEdits[id] = { ...pendingEdits[id], pixelPolygon };
  }

  function handleRetype(id: string, featureType: string) {
    pendingEdits[id] = { ...pendingEdits[id], featureType };
    // Update local array so sidebar swatch reflects the change
    footprints = footprints.map((f) =>
      f.id === id ? { ...f, featureType: featureType as FeatureType } : f
    );
  }

  async function handleApprove(id: string) {
    await updateStatus(id, 'submitted');
  }

  async function handleReject(id: string) {
    await updateStatus(id, 'rejected');
  }

  async function markReviewed() {
    markingReviewed = true;
    markReviewedError = '';
    try {
      await advancePipelineStage(mapId, 'seg_reviewed');
    } catch (e: any) {
      markReviewedError = e.message;
    } finally {
      markingReviewed = false;
    }
  }

  async function updateStatus(id: string, status: 'submitted' | 'rejected') {
    approving = id;
    updateError = '';
    try {
      const edits = pendingEdits[id];
      const body: Record<string, any> = { id, status };
      if (edits?.pixelPolygon) body.pixel_polygon = edits.pixelPolygon;
      if (edits?.featureType) body.feature_type = edits.featureType;

      const res = await fetch('/api/admin/footprints', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const { message } = await res.json().catch(() => ({ message: res.statusText }));
        updateError = `Could not ${status === 'rejected' ? 'reject' : 'approve'}: ${message}`;
        return;
      }
      // Remove from list; advance selection; clear pending edit
      const idx = footprints.findIndex((f) => f.id === id);
      footprints = footprints.filter((f) => f.id !== id);
      selectedId = footprints[idx]?.id ?? footprints[idx - 1]?.id ?? null;
      delete pendingEdits[id];
    } finally {
      approving = null;
    }
  }

  function handleSelect(id: string) {
    selectedId = id;
  }
</script>

{#if loading}
  <div class="tool-page fullscreen-state">
    <div class="spinner"></div>
    <span>Loading footprints…</span>
  </div>
{:else if loadError}
  <div class="tool-page fullscreen-state error">{loadError}</div>
{:else}
  <div class="tool-page review-layout">
    <header class="review-header">
      <button class="back-btn" on:click={() => dispatch('done')}>← Maps</button>
      <span class="header-title">
        HITL Review
        <span class="map-chip">{mapId.slice(0, 8)}…</span>
      </span>
      {#if updateError}
        <span class="update-error">{updateError}</span>
      {/if}
      <span class="progress-text">{reviewed} / {initialTotal} reviewed</span>
    </header>

    <div class="review-body">
      <div class="review-canvas">
        <ImageShell {iiifInfoUrl}>
          <ReviewTool
            {footprints}
            {selectedId}
            on:select={(e) => handleSelect(e.detail.id)}
            on:edit={(e) => handleEdit(e.detail.id, e.detail.pixelPolygon)}
          />
        </ImageShell>
      </div>
      <ReviewSidebar
        {footprints}
        {selectedId}
        total={initialTotal}
        {reviewed}
        {approving}
        {markingReviewed}
        {markReviewedError}
        on:select={(e) => handleSelect(e.detail.id)}
        on:approve={(e) => handleApprove(e.detail.id)}
        on:reject={(e) => handleReject(e.detail.id)}
        on:retype={(e) => handleRetype(e.detail.id, e.detail.featureType)}
        on:markReviewed={markReviewed}
      />
    </div>
  </div>
{/if}

<style>
  /* `.tool-page` (tool-page.css) owns the fixed shell — it insets by
     --nav-height so the (app) NavBar stays visible. */
  .fullscreen-state {
    align-items: center;
    justify-content: center;
    gap: 1rem;
    font-size: 0.9rem;
    opacity: 0.7;
  }

  .fullscreen-state.error {
    color: var(--status-bad);
    opacity: 1;
  }

  .review-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 1rem;
    background: var(--ground-raised);
    border-bottom: var(--rule-hair) solid var(--rule);
    height: 44px;
    flex-shrink: 0;
  }

  .back-btn {
    background: none;
    border: none;
    color: var(--ink-soft);
    font-size: 0.8125rem;
    cursor: pointer;
    font-family: inherit;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    transition:
      color 0.15s,
      background 0.15s;
  }

  .back-btn:hover {
    color: var(--ink);
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
  }

  .header-title {
    flex: 1;
    font-size: 0.875rem;
    font-weight: var(--w-semi);
    color: var(--ink);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .map-chip {
    font-size: 0.75rem;
    font-weight: var(--w-regular);
    color: var(--ink-soft);
    background: color-mix(in srgb, var(--ink) 6%, var(--ground));
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    font-family: ui-monospace, monospace;
  }

  .progress-text {
    font-size: 0.8125rem;
    color: var(--ink-soft);
  }

  .update-error {
    font-size: 0.8125rem;
    color: var(--status-bad);
  }

  .review-body {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  /* ImageShell is `position: absolute; inset: 0` — it needs a sized, positioned box. */
  .review-canvas {
    position: relative;
    flex: 1;
    min-width: 0;
  }
</style>
