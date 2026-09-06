<!--
  /scan?mode=review — HITL review of SAM2 footprints.

  Picker first (maps that have `submitted` / `needs_review` polygons), then
  ReviewMode for the chosen map. `?map=<id>` opens that map straight away —
  that's the link the Segmentation panel of the triage mode hands out.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchMapsWithSubmittedFootprints } from '$lib/data/supabase/footprints';
  import ReviewMode from '$lib/features/contribute/review/ReviewMode.svelte';
  import StoryReviewPanel from '$lib/features/contribute/review/StoryReviewPanel.svelte';

  /** One queue per kind of contribution — footprints today, stories since mig 059. */
  let kind: 'footprints' | 'stories' =
    'stories' === $page.url.searchParams.get('kind') ? 'stories' : 'footprints';

  const { supabase } = getSupabaseContext();

  type ReviewMapRow = Awaited<ReturnType<typeof fetchMapsWithSubmittedFootprints>>[number];

  let maps: ReviewMapRow[] = [];
  let loading = true;
  let loadError = '';
  let selectedMapId: string | null = null;
  let selectedAllmapsId = '';
  let selectedIiifImage: string | null = null;

  function open(map: ReviewMapRow) {
    selectedMapId = map.id;
    selectedAllmapsId = map.allmapsId;
    selectedIiifImage = map.iiifImage;
  }

  onMount(async () => {
    try {
      maps = await fetchMapsWithSubmittedFootprints(supabase);
      const wanted = $page.url.searchParams.get('map');
      const match = wanted ? maps.find((m) => m.id === wanted) : null;
      if (match) open(match);
    } catch (e: any) {
      loadError = e.message;
    } finally {
      loading = false;
    }
  });

  function handleDone() {
    selectedMapId = null;
    selectedAllmapsId = '';
    selectedIiifImage = null;
    fetchMapsWithSubmittedFootprints(supabase).then((m) => {
      maps = m;
    });
  }
</script>

{#if selectedMapId}
  <ReviewMode
    mapId={selectedMapId}
    allmapsId={selectedAllmapsId}
    iiifImage={selectedIiifImage}
    on:done={handleDone}
  />
{:else}
  <div class="page">
    <header class="page-header">
      <a href="/contribute" class="back-link">← Contribute</a>
      <h1>Review contributions</h1>
      <p>
        {kind === 'footprints'
          ? 'Check the building polygons SAM2 (Segment Anything Model v2) pulled out of the map — approve the good ones, reject the rest.'
          : 'Stories submitted by contributors. Approving one makes it publicly visible.'}
      </p>
      <div class="queue-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={kind === 'footprints'}
          class:is-on={kind === 'footprints'}
          on:click={() => (kind = 'footprints')}
        >
          Footprints
        </button>
        <button
          role="tab"
          aria-selected={kind === 'stories'}
          class:is-on={kind === 'stories'}
          on:click={() => (kind = 'stories')}
        >
          Stories
        </button>
      </div>
    </header>

    {#if kind === 'stories'}
      <StoryReviewPanel />
    {:else}
      {#if loading}
        <div class="state-msg">Loading maps…</div>
      {:else if loadError}
        <div class="state-msg error">{loadError}</div>
      {:else if maps.length === 0}
        <div class="state-msg">Queue's clear — no footprints waiting on review.</div>
      {:else}
        <ul class="review-map-list">
          {#each maps as map (map.id)}
            <li>
              <button class="map-card" on:click={() => open(map)}>
                <span class="map-name">{map.name || map.id}</span>
                <span class="map-badge">{map.pendingCount} pending</span>
              </button>
            </li>
          {/each}
        </ul>
        <p class="hint">
          Pick a map to start. The canvas loads IIIF tiles straight from Internet Archive.
        </p>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .page {
    max-width: 680px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
    font-family: var(--font-body);
  }

  .page-header {
    margin-bottom: 2rem;
  }

  .queue-tabs {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .queue-tabs button {
    padding: 0.4rem 0.9rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    font: inherit;
    cursor: pointer;
  }

  .queue-tabs button.is-on {
    background: var(--accent);
    font-weight: 700;
  }

  .back-link {
    display: inline-block;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--ink-soft);
    text-decoration: none;
  }

  .back-link:hover {
    color: var(--ink);
  }

  h1 {
    font-family: var(--font-display);
    font-size: 2rem;
    font-weight: var(--w-semi);
    margin: 0 0 0.5rem;
  }

  p {
    color: var(--ink-soft);
    margin: 0;
  }

  .review-map-list {
    list-style: none;
    padding: 0;
    margin: 0 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .map-card {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    background: var(--ground-raised);
    border: 2px solid var(--rule);
    border-radius: var(--radius);
    cursor: pointer;
    text-align: left;
    transition:
      border-color 0.15s,
      box-shadow 0.15s;
  }

  .map-card:hover {
    border-color: var(--status-warn);
    box-shadow: 3px 3px 0 var(--status-warn);
  }

  .map-name {
    font-weight: var(--w-semi);
    font-size: 0.9375rem;
  }

  .map-badge {
    font-size: 0.8125rem;
    font-weight: var(--w-semi);
    background: color-mix(in srgb, var(--status-warn) 14%, var(--ground-raised));
    color: color-mix(in srgb, var(--status-warn) 60%, var(--ink));
    border: 1px solid color-mix(in srgb, var(--status-warn) 40%, var(--ground-raised));
    border-radius: var(--radius-pill);
    padding: 0.2rem 0.65rem;
  }

  .hint {
    font-size: 0.8125rem;
    color: var(--ink-soft);
    text-align: center;
    margin-top: 1rem;
  }
</style>
