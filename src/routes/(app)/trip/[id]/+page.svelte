<!--
  /trip/[id] — Tourist-grade mobile story player.

  The UX flow:
    1. Cold load → TripIntro bottom-sheet over the map.
    2. Tap Start → intro dismisses, TripPlayback peek bar appears.
    3. Walk → GPS auto-completes "reach" stops and reveals the next marker.
    4. Last stop completed → TripComplete in the same sheet.

  Progress is local-only (createStoryPlayerStore persists to localStorage),
  so QR-scan tourists with no account never see a login prompt unless they
  opt in at the end.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';

  import type { Story } from '$lib/features/stories/shared/types';
  import type { MapListItem } from '$lib/data/maps/types';

  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { createStoryPlayerStore } from '$lib/features/stories/shared/storyStore';
  import { createGeoMapStores } from '$lib/map/shell/geoMapSetup';
  import { fetchMaps } from '$lib/data/maps/service';
  import { fetchStoryById } from '$lib/data/supabase/stories';
  import { haversineDistance } from '$lib/core/geo/geo';
  import { applyPointOverlay, applyStoryPoint } from '$lib/features/stories/shared/applyPoint';
  import { derivePlaybackState } from '$lib/features/stories/shared/playbackState';
  import {
    createWalkTracker,
    isWithinTrigger,
    requestGeolocation,
  } from '$lib/features/stories/play/tripTracking';

  import MapShell from '$lib/map/shell/MapShell.svelte';
  import LayerRenderer from '$lib/map/shell/LayerRenderer.svelte';
  import GpsTracker from '$lib/map/shell/GpsTracker.svelte';
  import TripIntro from '$lib/features/stories/play/TripIntro.svelte';
  import TripPlayback from '$lib/features/stories/play/TripPlayback.svelte';
  import StoryMarkers from '$lib/features/stories/shared/StoryMarkers.svelte';

  const ctx = getSupabaseContext();
  const supabase = ctx.supabase;
  const { mapStore, layerStore } = createGeoMapStores();
  const storyPlayer = createStoryPlayerStore(supabase, ctx.session?.user?.id);

  $: storyId = $page.params.id;
  $: isLoggedIn = !!ctx.session?.user?.id;

  let story: Story | null = null;
  let mapList: MapListItem[] = [];
  let loading = true;
  let error: string | null = null;

  let gpsActive = true;
  let gpsError: string | null = null;
  let userPosition: [number, number] | null = null;
  let walkedMeters = 0;
  const walkTracker = createWalkTracker();

  // Intro visibility is decided after the story + progress load (see loadStory).
  // Default to true so we never flash the map before the intro on cold load.
  let showIntro = true;

  $: playerState = $storyPlayer;
  $: progress = story ? (playerState.progress[story.id] ?? null) : null;
  $: playback = derivePlaybackState(story, progress);
  $: ({ completedIds, currentIndex, currentPoint, isFinished } = playback);

  // ── Route length & estimated duration ─────────────────────────────
  $: routeMeters = story
    ? story.points.reduce((sum, pt, i, arr) => {
        if (i === 0) return 0;
        return sum + haversineDistance(arr[i - 1].coordinates, pt.coordinates);
      }, 0)
    : 0;
  // Walking pace 4 km/h + 4 min standing at each stop, rounded to nearest 5.
  $: estimatedMinutes = story
    ? Math.max(
        5,
        ((Math.round((routeMeters / 1000 / 4) * 60 + story.points.length * 4) / 5) * 5) | 0
      )
    : 0;

  // ── GPS handlers ──────────────────────────────────────────────────
  function handleGpsPosition(e: CustomEvent<{ lon: number; lat: number }>) {
    const pos: [number, number] = [e.detail.lon, e.detail.lat];
    walkedMeters = walkTracker.push(pos);
    userPosition = pos;

    if (!story || !currentPoint || completedIds.has(currentPoint.id)) return;
    // Auto check-in marks visited only — the user taps Next to advance.
    if (isWithinTrigger(pos, currentPoint)) storyPlayer.markVisited(story.id, currentPoint.id);
  }

  // ── TripPlayback events ───────────────────────────────────────────
  function handleMarkVisited(e: CustomEvent<{ storyId: string; pointId: string }>) {
    storyPlayer.markVisited(e.detail.storyId, e.detail.pointId);
  }

  function handleAdvance(e: CustomEvent<{ direction: 'next' | 'prev' }>) {
    if (!story) return;
    storyPlayer.advance(story.id, e.detail.direction, story.points.length);
  }

  function handleDone() {
    if (story) storyPlayer.stopStory();
    goto('/explore');
  }
  function handleShare() {
    /* no-op — TripComplete handles the share dialog */
  }
  function handleSave() {
    // Tourist opts in to keep their progress. Send them to login with a
    // return-to back to this trip.
    goto(`/login?next=${encodeURIComponent(`/trip/${storyId}`)}`);
  }

  // ── Intro events ──────────────────────────────────────────────────
  async function startTrip() {
    if (!story) return;
    // Ask for location BEFORE dismissing the intro so the prompt context is
    // clear ("Walk around Saigon needs your location to guide you").
    const perm = await requestGeolocation();
    if (perm === 'denied') {
      gpsError =
        'Location permission was denied. You can re-enable it in your browser settings, or continue without it.';
      gpsActive = false;
    } else if (perm === 'unavailable') {
      gpsError =
        'This device cannot share its location. The trip will work, but auto check-in is off.';
      gpsActive = false;
    }
    storyPlayer.startStory(story.id);
    showIntro = false;
    if (story.points[0]) applyPointOverlay(story.points[0], mapList);
  }

  async function resumeTrip() {
    const perm = await requestGeolocation();
    if (perm === 'denied') {
      gpsError = 'Location permission was denied. Auto check-in is off — use Mark visited instead.';
      gpsActive = false;
    } else if (perm === 'unavailable') {
      gpsActive = false;
    }
    showIntro = false;
    if (story && currentPoint) applyPointOverlay(currentPoint, mapList);
  }

  async function restartTrip() {
    if (!story) return;
    storyPlayer.resetProgress(story.id);
    walkTracker.reset();
    walkedMeters = 0;
    await startTrip();
  }

  // ── Re-frame map + swap overlay when current point changes ──────
  // Track the last point we framed so we only react to real changes.
  let lastFramedPointId: string | null = null;
  $: if (!showIntro && story && currentPoint && currentPoint.id !== lastFramedPointId) {
    lastFramedPointId = currentPoint.id;
    applyStoryPoint(currentPoint, mapList, mapStore);
  }

  async function loadStory() {
    loading = true;
    error = null;
    try {
      if (!storyId) throw new Error('Missing story id');
      story = await fetchStoryById(supabase, storyId);
      if (!story) throw new Error('Story not found');

      // Decide intro behavior based on existing progress:
      //   - finished trip → skip intro, go straight to completion screen
      //   - in-progress    → show intro with Resume/Restart
      //   - fresh          → show intro with Start
      const existing = storyId ? get(storyPlayer).progress[storyId] : null;
      if (existing?.completedAt) {
        showIntro = false;
        // Re-apply the last visited stop's overlay so the map matches.
        const last = story.points[story.points.length - 1];
        if (last) applyPointOverlay(last, mapList);
      }

      // Initial framing: region, else first point.
      if (story.region) {
        mapStore.setView({
          lng: story.region.center[0],
          lat: story.region.center[1],
          zoom: story.region.zoom,
        });
      } else if (story.points[0]) {
        mapStore.setView({
          lng: story.points[0].coordinates[0],
          lat: story.points[0].coordinates[1],
          zoom: 16,
        });
      }
    } catch (e: any) {
      console.error('[trip] failed to load story:', e);
      error = e?.message ?? 'Could not load this story.';
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    try {
      mapList = await fetchMaps(supabase);
    } catch (e) {
      console.error('[trip] failed to load maps:', e);
    }
    await loadStory();
  });
</script>

<svelte:head>
  <title>{story?.title ?? 'Trip'} — Vietnam Map Archive</title>
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1"
  />
</svelte:head>

<div class="trip">
  {#if loading}
    <div class="state">
      <div class="spinner" aria-hidden="true"></div>
      <p>Loading your trip…</p>
    </div>
  {:else if error || !story}
    <div class="state">
      <h2>Trip unavailable</h2>
      <p>{error ?? 'This story could not be loaded.'}</p>
      <button type="button" class="back-btn" on:click={() => goto('/explore')}
        >← Back to maps</button
      >
    </div>
  {:else}
    <MapShell {mapStore} {layerStore} disableUrlSync={true}>
      <LayerRenderer />
      <GpsTracker
        active={gpsActive && !showIntro}
        autoFollow={false}
        showTrack={true}
        on:position={handleGpsPosition}
        on:error={(e) => (gpsError = e.detail.message)}
      />
      {#if !showIntro}
        <StoryMarkers
          points={story.points}
          {currentIndex}
          {completedIds}
          revealUpTo={Math.min(currentIndex + 1, story.points.length)}
          showTrail
        />
        <TripPlayback
          {story}
          {progress}
          {userPosition}
          {walkedMeters}
          canSaveProgress={!isLoggedIn}
          on:markVisited={handleMarkVisited}
          on:advance={handleAdvance}
          on:done={handleDone}
          on:share={handleShare}
          on:save={handleSave}
        />
      {/if}
    </MapShell>

    {#if showIntro}
      <TripIntro
        {story}
        {estimatedMinutes}
        hasProgress={!!progress && !isFinished && completedIds.size > 0}
        on:start={() => (progress && !isFinished ? restartTrip() : startTrip())}
        on:resume={resumeTrip}
      />
    {:else}
      <button
        type="button"
        class="gps-toggle"
        class:is-on={gpsActive}
        on:click={() => {
          gpsActive = !gpsActive;
          gpsError = null;
        }}
        aria-label={gpsActive ? 'Pause location tracking' : 'Resume location tracking'}
        title={gpsActive ? 'Tracking on' : 'Tracking off'}
      >
        {gpsActive ? '📍' : '⊘'}
      </button>

      {#if gpsError}
        <div class="gps-error" role="alert">{gpsError}</div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .trip {
    position: fixed;
    inset: 0;
    top: 56px; /* leave room for the (app) NavBar */
    background: var(--ground);
    overflow: hidden;
  }

  .state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    height: 100%;
    padding: 1.5rem;
    text-align: center;
    color: var(--ink);
  }
  .state h2 {
    margin: 0;
    font-family: var(--sb-font-display, 'Spectral', serif);
    font-size: 1.4rem;
  }
  .state p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--ink-soft);
  }

  .back-btn {
    margin-top: 0.5rem;
    padding: 0.55rem 1rem;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--sb-radius, 10px);
    box-shadow: 3px 3px 0 var(--rule);
    font-weight: 700;
    cursor: pointer;
  }
  .back-btn:active {
    transform: translate(2px, 2px);
    box-shadow: 1px 1px 0 var(--rule);
  }

  .gps-toggle {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    width: 44px;
    height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: 50%;
    box-shadow: 3px 3px 0 var(--rule);
    font-size: 1.1rem;
    cursor: pointer;
    z-index: 110;
  }
  .gps-toggle.is-on {
    background: var(--accent);
    color: var(--on-accent);
  }
  .gps-toggle:active {
    transform: translate(2px, 2px);
    box-shadow: 1px 1px 0 var(--rule);
  }

  .gps-error {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    max-width: 80%;
    padding: 0.5rem 0.75rem;
    background: color-mix(in srgb, var(--status-warn) 18%, var(--ground-raised));
    border: var(--rule-thick) solid var(--status-warn);
    border-radius: var(--sb-radius-sm, 6px);
    font-size: 0.8rem;
    z-index: 110;
  }
</style>
