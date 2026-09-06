<!--
  TripComplete.svelte — Celebration body shown at end of the trip.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Story } from '$lib/features/stories/shared/types';

  export let story: Story;
  export let stopsVisited: number;
  export let walkedMeters: number;
  export let elapsedMinutes: number;
  export let canSaveProgress = false;

  const dispatch = createEventDispatcher<{
    done: void;
    share: void;
    save: void;
  }>();

  $: km = walkedMeters / 1000;
  $: distanceLabel = km >= 1 ? `${km.toFixed(2)} km` : `${Math.round(walkedMeters)} m`;

  async function handleShare() {
    const url = typeof window !== 'undefined' ? window.location.href : '';
    const text = `I just walked "${story.title}" on Vietnam Map Archive.`;
    if (typeof navigator !== 'undefined' && (navigator as any).share) {
      try {
        await (navigator as any).share({ title: story.title, text, url });
        dispatch('share');
        return;
      } catch {
        // user cancelled — fall through
      }
    }
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        /* ignore */
      }
    }
    dispatch('share');
  }
</script>

<div class="complete" data-testid="trip-complete">
  <div class="emoji" aria-hidden="true">🎉</div>
  <h2>You made it.</h2>
  <p class="subtitle">{story.title}</p>

  <div class="stats">
    <div class="stat">
      <span class="value">{stopsVisited}</span>
      <span class="label">stops</span>
    </div>
    <div class="stat">
      <span class="value">{distanceLabel}</span>
      <span class="label">walked</span>
    </div>
    <div class="stat">
      <span class="value">{elapsedMinutes}</span>
      <span class="label">minutes</span>
    </div>
  </div>

  {#if canSaveProgress}
    <button type="button" class="save-row" on:click={() => dispatch('save')}>
      <span class="save-icon">💾</span>
      <span>
        <strong>Save your trip</strong><br />
        <small>Log in to keep this on your profile.</small>
      </span>
    </button>
  {/if}

  <div class="actions">
    <button type="button" class="btn is-primary" on:click={handleShare}>Share</button>
    <button type="button" class="btn is-ghost" on:click={() => dispatch('done')}>Done</button>
  </div>
</div>

<style>
  .complete {
    padding: 0.4rem 0.2rem 0.6rem;
    color: var(--sb-text);
  }
  .emoji {
    font-size: 2.4rem;
    line-height: 1;
  }
  h2 {
    margin: 0.4rem 0 0.15rem;
    font-family: var(--sb-font-display);
    font-size: 1.45rem;
    font-weight: 800;
  }
  .subtitle {
    margin: 0 0 1rem;
    color: var(--sb-text-meta);
    font-size: 0.92rem;
  }

  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin-bottom: 0.9rem;
  }
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.1rem;
    padding: 0.75rem 0.25rem;
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 12px;
  }
  .stat .value {
    font-family: var(--sb-font-display);
    font-size: 1.2rem;
    font-weight: 800;
    line-height: 1;
  }
  .stat .label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--sb-text-meta);
  }

  .save-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    width: 100%;
    text-align: left;
    padding: 0.7rem 0.85rem;
    margin-bottom: 0.85rem;
    background: color-mix(in srgb, var(--accent) 14%, var(--ground-raised));
    border: var(--rule-hair) solid var(--rule);
    border-radius: 12px;
    cursor: pointer;
    font-family: inherit;
    color: var(--ink);
  }
  .save-icon {
    font-size: 1.3rem;
  }
  .save-row small {
    color: var(--sb-text-meta);
    font-size: 0.78rem;
  }
  .save-row:active {
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--rule);
  }

  .actions {
    display: flex;
    gap: 0.5rem;
  }
  .btn {
    flex: 1;
    padding: 0.85rem 0.8rem;
    border-radius: 12px;
    border: var(--rule-hair) solid var(--rule);
    font-family: inherit;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 3px 3px 0 var(--rule);
  }
  .btn.is-primary {
    background: var(--sb-accent);
    color: var(--ground-raised);
  }
  .btn.is-ghost {
    background: var(--ground-raised);
    color: var(--ink);
  }
  .btn:active {
    transform: translate(2px, 2px);
    box-shadow: 1px 1px 0 var(--rule);
  }
</style>
