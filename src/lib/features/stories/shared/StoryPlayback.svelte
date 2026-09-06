<!--
  StoryPlayback.svelte — Floating preview/playback card anchored at the bottom
  of the map. Used by /explore (real playback) and /explore?mode=story (preview mode).
  Styled with sidebar.css tokens so it matches the right-pane editor.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Story, StoryPoint, StoryProgress } from '$lib/features/stories/shared/types';
  import {
    checkAnswer,
    createAnswerGate,
    derivePlaybackState,
    type AnswerStatus,
  } from '$lib/features/stories/shared/playbackState';

  const dispatch = createEventDispatcher<{
    navigatePoint: { index: number; point: StoryPoint };
    completePoint: { storyId: string; pointId: string };
    close: void;
    finish: { storyId: string };
  }>();

  export let story: Story;
  export let progress: StoryProgress | null = null;

  $: playback = derivePlaybackState(story, progress);
  $: ({ currentIndex, completedIds, currentPoint, isFinished, progressFraction } = playback);
  $: totalPoints = playback.total;

  function goToPoint(index: number) {
    if (index < 0 || index >= story.points.length) return;
    dispatch('navigatePoint', { index, point: story.points[index] });
  }

  function handleComplete() {
    if (!currentPoint) return;
    dispatch('completePoint', { storyId: story.id, pointId: currentPoint.id });
  }

  // Per-point challenge state. Resets when the active point changes.
  const answerGate = createAnswerGate();
  let answerDraft = '';
  let answerStatus: AnswerStatus = 'idle';
  $: if (answerGate.changed(currentPoint)) {
    answerDraft = '';
    answerStatus = 'idle';
  }

  function submitAnswer() {
    if (!currentPoint || currentPoint.challenge?.type !== 'question') return;
    if (checkAnswer(currentPoint.challenge, answerDraft)) {
      answerStatus = 'right';
      handleComplete();
    } else {
      answerStatus = 'wrong';
    }
  }
</script>

<div class="pb">
  <header class="pb-head">
    <button
      type="button"
      class="sb-btn is-icon is-ghost"
      on:click={() => dispatch('close')}
      aria-label="Close preview"
      title="Close">×</button
    >
    <div class="pb-title">
      <h3>{story.title}</h3>
      <a class="sb-btn is-sm is-ghost" href="/trip/{story.id}" title="Walk this story on mobile"
        >Walk</a
      >
    </div>
    <div class="pb-progress" title="{completedIds.size} / {totalPoints} visited">
      <div class="pb-progress-bar">
        <div class="pb-progress-fill" style="width: {progressFraction * 100}%"></div>
      </div>
      <span class="pb-progress-text">{completedIds.size} / {totalPoints}</span>
    </div>
  </header>

  {#if isFinished}
    <div class="pb-body">
      <h4>Story complete</h4>
      <p>You visited all {totalPoints} points in this story.</p>
      <button
        type="button"
        class="sb-btn is-on is-block"
        on:click={() => dispatch('finish', { storyId: story.id })}>Finish</button
      >
    </div>
  {:else if currentPoint}
    <div class="pb-body">
      <div class="pb-point-head">
        <span class="pb-num" class:is-done={completedIds.has(currentPoint.id)}
          >{currentIndex + 1}</span
        >
        <h4>{currentPoint.title || `Point ${currentIndex + 1}`}</h4>
      </div>
      {#if currentPoint.description}
        <p class="pb-desc">{currentPoint.description}</p>
      {/if}
      {#if currentPoint.hint && !completedIds.has(currentPoint.id)}
        <p class="pb-hint"><strong>Hint:</strong> {currentPoint.hint}</p>
      {/if}

      {#if currentPoint.challenge?.type === 'question' && !completedIds.has(currentPoint.id)}
        <div class="pb-challenge">
          <span class="pb-challenge-label">Question</span>
          <p class="pb-question">{currentPoint.challenge.question || '(no question set)'}</p>
          <form class="pb-answer-row" on:submit|preventDefault={submitAnswer}>
            <input
              class="sb-input"
              type="text"
              bind:value={answerDraft}
              placeholder="Your answer"
              aria-label="Your answer"
            />
            <button type="submit" class="sb-btn is-sm is-primary">Submit</button>
          </form>
          {#if answerStatus === 'wrong'}
            <p class="pb-answer-wrong">Not quite — try again.</p>
          {/if}
        </div>
      {:else if currentPoint.challenge?.type === 'reach' && !completedIds.has(currentPoint.id)}
        <div class="pb-challenge">
          <span class="pb-challenge-label">Reach</span>
          <p class="pb-question">
            Walk within <strong>{currentPoint.challenge.triggerRadius ?? 15} m</strong> of this
            point. Tap <em>Mark visited</em> to simulate arrival in preview.
          </p>
        </div>
      {/if}

      <div class="pb-actions">
        <button
          type="button"
          class="sb-btn is-sm"
          disabled={currentIndex <= 0}
          on:click={() => goToPoint(currentIndex - 1)}>← Prev</button
        >
        {#if !completedIds.has(currentPoint.id)}
          <button type="button" class="sb-btn is-sm is-primary pb-cta" on:click={handleComplete}
            >Mark visited</button
          >
        {:else}
          <span class="pb-done">✓ Visited</span>
        {/if}
        <button
          type="button"
          class="sb-btn is-sm"
          disabled={currentIndex >= totalPoints - 1}
          on:click={() => goToPoint(currentIndex + 1)}>Next →</button
        >
      </div>
    </div>
  {/if}
</div>

<style>
  .pb {
    position: absolute;
    bottom: calc(env(safe-area-inset-bottom) + 1.25rem);
    left: 50%;
    transform: translateX(-50%);
    width: min(92%, 480px);
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius);
    z-index: 100;
    pointer-events: auto;
    color: var(--sb-text);
    font-family: var(--sb-font-base);
    overflow: hidden;
  }
  @media (max-width: 900px) {
    .pb {
      bottom: calc(env(safe-area-inset-bottom) + 6.5rem);
    }
  }

  .pb-head {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.55rem 0.7rem;
    background: var(--sb-head-bg);
    border-bottom: var(--sb-border);
  }
  .pb-title {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .pb-title h3 {
    margin: 0;
    font-family: var(--sb-font-display);
    font-size: 0.85rem;
    font-weight: 800;
    color: var(--sb-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pb-progress {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
  }
  .pb-progress-bar {
    width: 60px;
    height: 6px;
    background: var(--sb-bg);
    border: 1px solid var(--rule);
    border-radius: var(--sb-radius-pill);
    overflow: hidden;
  }
  .pb-progress-fill {
    height: 100%;
    background: var(--sb-accent);
    transition: width 0.25s ease;
  }
  .pb-progress-text {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.7rem;
    color: var(--sb-text-meta);
  }

  .pb-body {
    padding: 0.7rem 0.8rem 0.8rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .pb-point-head {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }
  .pb-num {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--sb-accent);
    color: var(--ground-raised);
    border: var(--sb-border);
    border-radius: 50%;
    font-family: var(--sb-font-display);
    font-size: 0.75rem;
    font-weight: 800;
  }
  .pb-num.is-done {
    background: var(--sb-success);
  }
  .pb-point-head h4 {
    margin: 0;
    font-family: var(--sb-font-display);
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--sb-text);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pb-desc {
    margin: 0;
    font-size: 0.84rem;
    line-height: 1.45;
    color: var(--sb-text);
  }
  .pb-hint {
    margin: 0;
    padding: 0.4rem 0.55rem;
    font-size: 0.78rem;
    color: var(--sb-text-meta);
    background: var(--sb-accent-yellow);
    border: var(--sb-border-soft);
    border-radius: var(--sb-radius-sm);
  }

  .pb-challenge {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.55rem 0.65rem;
    background: var(--sb-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
  }
  .pb-challenge-label {
    font-family: var(--sb-font-display);
    font-size: 0.62rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--sb-accent);
  }
  .pb-question {
    margin: 0;
    font-size: 0.84rem;
    line-height: 1.4;
    color: var(--sb-text);
  }
  .pb-answer-row {
    display: flex;
    gap: 0.4rem;
  }
  .pb-answer-row .sb-input {
    flex: 1;
  }
  .pb-answer-wrong {
    margin: 0;
    font-size: 0.74rem;
    color: var(--sb-danger);
    font-weight: 700;
  }
  .pb-actions {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    padding-top: 0.1rem;
  }
  .pb-cta {
    flex: 1;
  }
  .pb-done {
    flex: 1;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--sb-success);
  }

  .pb-body h4 {
    margin: 0;
    font-family: var(--sb-font-display);
    font-size: 1rem;
    font-weight: 800;
    color: var(--sb-text);
  }
  .pb-body p {
    margin: 0;
    font-size: 0.85rem;
    color: var(--sb-text);
  }
</style>
