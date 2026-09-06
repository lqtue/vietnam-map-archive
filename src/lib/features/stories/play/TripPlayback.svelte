<!--
  TripPlayback.svelte — trip player mounted in a SnapSheet for /trip.

  Peek shows progress + the next-stop chip; mid adds the current stop card with
  its challenge UI; full adds the itinerary (TripItinerary). The sheet mechanics
  — grip drag, tap-to-cycle, snap heights — live in $lib/ui/SnapSheet.

  Header chip shows live "distance · direction" to the current stop when
  GPS position is available.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Story, StoryProgress } from '$lib/features/stories/shared/types';
  import { haversineDistance } from '$lib/core/geo/geo';
  import { bearingDeg, compassLabel } from '$lib/core/geo/bearing';
  import {
    checkAnswer,
    createAnswerGate,
    derivePlaybackState,
    type AnswerStatus,
  } from '$lib/features/stories/shared/playbackState';
  import SnapSheet, { type Snap } from '$lib/ui/SnapSheet.svelte';
  import TripComplete from './TripComplete.svelte';
  import TripItinerary from './TripItinerary.svelte';

  const dispatch = createEventDispatcher<{
    markVisited: { storyId: string; pointId: string };
    advance: { direction: 'next' | 'prev' };
    done: void;
    share: void;
    save: void;
  }>();

  export let story: Story;
  export let progress: StoryProgress | null = null;
  /** Live GPS [lon, lat] — undefined when tracking is off / not yet acquired. */
  export let userPosition: [number, number] | null = null;
  export let walkedMeters = 0;
  export let canSaveProgress = false;

  $: playback = derivePlaybackState(story, progress);
  $: ({ currentIndex, completedIds, currentPoint, isFinished, total, progressFraction } = playback);
  $: startedAt = progress?.startedAt ?? Date.now();
  $: elapsedMinutes = Math.max(1, Math.round((Date.now() - startedAt) / 60_000));

  // ── Distance + direction chip ─────────────────────────────────────
  $: distInfo = (() => {
    if (!currentPoint || !userPosition) return null;
    const d = haversineDistance(userPosition, currentPoint.coordinates);
    const c = compassLabel(bearingDeg(userPosition, currentPoint.coordinates));
    const text = d >= 1000 ? `${(d / 1000).toFixed(1)} km` : `${Math.round(d)} m`;
    return { text, arrow: c.arrow, label: c.label, meters: d };
  })();

  let snap: Snap = 'peek';

  // ── Per-point challenge state ─────────────────────────────────────
  const answerGate = createAnswerGate();
  let answerDraft = '';
  // 'idle' before submit; 'wrong' on miss; 'right' after a correct submission
  // — stays for as long as the user is still on this stop (so the green
  // "Correct!" banner persists until they tap Next).
  let answerStatus: AnswerStatus = 'idle';
  $: if (answerGate.changed(currentPoint)) {
    answerDraft = '';
    answerStatus = 'idle';
    // New stop → bump back to mid so the user sees the card.
    if (snap === 'peek') snap = 'mid';
  }

  $: isCurrentVisited = !!currentPoint && completedIds.has(currentPoint.id);

  function markVisited() {
    if (!currentPoint) return;
    dispatch('markVisited', { storyId: story.id, pointId: currentPoint.id });
  }

  function submitAnswer() {
    if (!currentPoint || currentPoint.challenge?.type !== 'question') return;
    if (checkAnswer(currentPoint.challenge, answerDraft)) {
      answerStatus = 'right';
      markVisited(); // marks completed without advancing — user taps Next
    } else {
      answerStatus = 'wrong';
    }
  }

  function goNext() {
    if (!isCurrentVisited) return;
    dispatch('advance', { direction: 'next' });
  }
  function goPrev() {
    dispatch('advance', { direction: 'prev' });
  }

  // Auto-expand to full on completion so the celebration is visible.
  $: if (isFinished && snap !== 'full') snap = 'full';
</script>

<SnapSheet
  bind:snap
  locked={isFinished}
  label="Trip player"
  toggleLabel="Expand or collapse the trip player"
>
  <svelte:fragment slot="head">
    {#if isFinished}
      <div class="head-line">
        <strong class="head-title">Trip complete</strong>
      </div>
    {:else}
      <div class="head-line">
        <span class="num" class:done={currentPoint && completedIds.has(currentPoint.id)}>
          {currentIndex + 1}
        </span>
        <div class="head-text">
          <div class="head-title">{currentPoint?.title ?? `Stop ${currentIndex + 1}`}</div>
          <div class="head-meta">
            {#if distInfo}
              <span
                class="dist-chip"
                title={distInfo.meters >= 30 ? 'Walk to this stop' : 'You’re here'}
              >
                <span class="arrow">{distInfo.arrow}</span>
                <span>{distInfo.text}</span>
                <span class="comp">{distInfo.label}</span>
              </span>
            {:else}
              <span class="dist-chip is-muted">Finding GPS…</span>
            {/if}
            <span class="counter">{completedIds.size} / {total}</span>
          </div>
        </div>
      </div>
      <div class="bar"><div class="bar-fill" style="width: {progressFraction * 100}%"></div></div>
    {/if}
  </svelte:fragment>

  {#if isFinished}
    <TripComplete
      {story}
      stopsVisited={completedIds.size}
      {walkedMeters}
      {elapsedMinutes}
      {canSaveProgress}
      on:done
      on:share
      on:save
    />
  {:else if currentPoint}
    {#if currentPoint.description}
      <p class="desc">{currentPoint.description}</p>
    {/if}

    {#if currentPoint.hint && !completedIds.has(currentPoint.id)}
      <p class="hint"><strong>Look around:</strong> {currentPoint.hint}</p>
    {/if}

    {#if currentPoint.challenge?.type === 'question' && !isCurrentVisited}
      <div class="challenge">
        <span class="challenge-label">Question</span>
        <p class="question">{currentPoint.challenge.question || '(no question set)'}</p>
        <form class="answer-row" on:submit|preventDefault={submitAnswer}>
          <input
            class="answer-input"
            type="text"
            bind:value={answerDraft}
            placeholder="Your answer"
            aria-label="Your answer"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
          />
          <button type="submit" class="answer-btn">Submit</button>
        </form>
        {#if answerStatus === 'wrong'}
          <p class="answer-wrong">Not quite — try again.</p>
        {/if}
      </div>
    {:else if currentPoint.challenge?.type === 'reach' && !isCurrentVisited}
      <div class="challenge">
        <span class="challenge-label">Reach</span>
        <p class="question">
          Walk within <strong>{currentPoint.challenge.triggerRadius ?? 15} m</strong> and you'll check
          in automatically.
        </p>
      </div>
    {/if}

    {#if isCurrentVisited}
      {#if currentPoint.challenge?.type === 'question' && answerStatus === 'right'}
        <div class="status-banner is-correct" role="status">
          <span class="status-icon">✓</span>
          <div>
            <strong>Correct!</strong>
            <span class="status-sub">The answer was “{currentPoint.challenge.answer}”.</span>
          </div>
        </div>
      {:else}
        <div class="status-banner is-visited" role="status">
          <span class="status-icon">✓</span>
          <div>
            <strong>Visited.</strong>
            <span class="status-sub">
              {#if currentIndex < total - 1}Tap Next to continue.{:else}Tap Next to finish.{/if}
            </span>
          </div>
        </div>
      {/if}
    {/if}

    <div class="actions">
      <button type="button" class="action-btn" disabled={currentIndex <= 0} on:click={goPrev}
        >← Prev</button
      >

      {#if !isCurrentVisited}
        <button type="button" class="action-btn is-primary" on:click={markVisited}
          >Mark visited</button
        >
      {:else}
        <button type="button" class="action-btn is-primary" on:click={goNext}>
          {currentIndex < total - 1 ? 'Next →' : 'Finish →'}
        </button>
      {/if}
    </div>

    {#if snap === 'full'}
      <TripItinerary points={story.points} {currentIndex} {completedIds} />
    {/if}
  {/if}
</SnapSheet>

<style>
  .head-line {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-width: 0;
  }
  .num {
    flex-shrink: 0;
    width: 30px;
    height: 30px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--sb-accent);
    color: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 50%;
    font-family: var(--sb-font-display);
    font-weight: 800;
    font-size: 0.85rem;
  }
  /* Literal fallback on purpose: this green is the story-marker `done`
     state, and it has to match the OL marker drawn on the map by
     markerPalette.ts, which cannot read a CSS custom property. */
  .num.done {
    background: var(
      --marker-done,
      #16a34a
    ); /* token-exempt: matches the done marker drawn on the map by markerPalette */
  }
  .head-text {
    min-width: 0;
    flex: 1;
  }
  .head-title {
    font-family: var(--sb-font-display);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .head-meta {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.15rem;
    font-size: 0.75rem;
  }
  .dist-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.15rem 0.5rem;
    background: var(--ground-raised);
    border: var(--sb-border);
    border-radius: 999px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .dist-chip.is-muted {
    color: var(--sb-text-muted);
    font-weight: 500;
  }
  .dist-chip .arrow {
    font-size: 0.9rem;
    line-height: 1;
  }
  .dist-chip .comp {
    color: var(--sb-text-meta);
    font-weight: 500;
    font-size: 0.7rem;
  }
  .counter {
    font-family: ui-monospace, SFMono-Regular, monospace;
    color: var(--sb-text-meta);
    font-size: 0.72rem;
  }
  .bar {
    margin-top: 0.55rem;
    height: 5px;
    background: color-mix(in srgb, var(--ink) 6%, transparent);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 99px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: var(--sb-accent);
    transition: width 0.3s ease;
  }

  .desc {
    margin: 0;
    font-size: 0.92rem;
    line-height: 1.5;
    color: var(--ink);
  }
  .hint {
    margin: 0;
    padding: 0.55rem 0.7rem;
    font-size: 0.85rem;
    background: color-mix(in srgb, var(--status-warn) 18%, var(--ground-raised));
    border: var(--sb-border);
    border-radius: 8px;
  }

  .challenge {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.65rem 0.75rem;
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 10px;
  }
  .challenge-label {
    font-family: var(--sb-font-display);
    font-size: 0.65rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--sb-accent);
  }
  .question {
    margin: 0;
    font-size: 0.9rem;
    line-height: 1.45;
  }
  .answer-row {
    display: flex;
    gap: 0.4rem;
  }
  .answer-input {
    flex: 1;
    padding: 0.55rem 0.7rem;
    border: var(--sb-border);
    border-radius: 8px;
    font-family: inherit;
    font-size: 0.9rem;
    background: var(--ground-raised);
  }
  .answer-btn {
    padding: 0.55rem 0.9rem;
    border: var(--rule-hair) solid var(--rule);
    background: var(--sb-accent);
    color: var(--ground-raised);
    border-radius: 8px;
    font-family: inherit;
    font-weight: 700;
    cursor: pointer;
  }
  .answer-btn:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--rule);
  }
  .answer-wrong {
    margin: 0;
    font-size: 0.78rem;
    color: var(--sb-danger);
    font-weight: 700;
  }

  .status-banner {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 0.85rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: 10px;
    font-size: 0.9rem;
  }
  .status-banner.is-correct {
    background: color-mix(in srgb, var(--status-ok) 20%, var(--ground-raised));
  }
  .status-banner.is-visited {
    background: color-mix(in srgb, var(--accent) 16%, var(--ground-raised));
  }
  .status-banner strong {
    display: block;
    font-weight: 800;
    font-size: 0.95rem;
  }
  .status-banner .status-sub {
    font-size: 0.78rem;
    color: var(--sb-text-meta);
  }
  .status-icon {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--ink);
    color: var(--ground-raised);
    border-radius: 50%;
    font-weight: 800;
  }

  .actions {
    display: flex;
    gap: 0.4rem;
    align-items: stretch;
  }
  .action-btn {
    flex: 1;
    padding: 0.7rem 0.6rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: 10px;
    background: var(--ground-raised);
    font-family: inherit;
    font-weight: 700;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .action-btn:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--rule);
  }
  .action-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .action-btn.is-primary {
    background: var(--sb-accent);
    color: var(--ground-raised);
    flex: 1.4;
  }
</style>
