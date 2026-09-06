<!--
  TripItinerary.svelte — the full stop list shown when the trip sheet is
  expanded. Stops past the current one stay hidden ("Stop n · ???") so the
  walk keeps its reveal.
-->
<script lang="ts">
  import type { StoryPoint } from '$lib/features/stories/shared/types';

  export let points: StoryPoint[] = [];
  export let currentIndex = 0;
  export let completedIds: Set<string> = new Set();
</script>

<div class="itinerary" aria-label="All stops">
  <h3>Itinerary</h3>
  <ol>
    {#each points as pt, i (pt.id)}
      {@const done = completedIds.has(pt.id)}
      {@const isCur = i === currentIndex}
      {@const revealed = i <= currentIndex}
      <li class:done class:current={isCur}>
        <span class="li-num" class:done class:current={isCur}>
          {done ? '✓' : i + 1}
        </span>
        <span class="li-title">
          {#if revealed}{pt.title}{:else}Stop {i + 1} · ???{/if}
        </span>
        {#if isCur}<span class="li-tag">now</span>{/if}
      </li>
    {/each}
  </ol>
</div>

<style>
  .itinerary {
    margin-top: 0.5rem;
  }
  .itinerary h3 {
    margin: 0 0 0.4rem;
    font-family: var(--sb-font-display);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--sb-text-meta);
  }
  .itinerary ol {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .itinerary li {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.5rem 0.65rem;
    background: var(--ground-raised);
    border: 1.5px solid var(--rule);
    border-radius: 10px;
    font-size: 0.9rem;
  }
  /* The live stop is the one selected row in the list. */
  .itinerary li.current {
    border-color: var(--accent);
  }
  .itinerary li.done {
    opacity: 0.75;
  }
  .li-num {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--sb-accent);
    color: var(--ground-raised);
    border: var(--sb-border);
    border-radius: 50%;
    font-weight: 800;
    font-size: 0.72rem;
  }
  /* Literal fallback on purpose: this green is the story-marker `done`
     state, and it has to match the OL marker drawn on the map by
     markerPalette.ts, which cannot read a CSS custom property. */
  .li-num.done {
    background: var(
      --marker-done,
      #16a34a
    ); /* token-exempt: matches the done marker drawn on the map by markerPalette */
  }
  .li-num.current {
    background: var(--sb-accent);
  }
  .li-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .li-tag {
    flex-shrink: 0;
    padding: 0.1rem 0.5rem;
    background: var(--sb-accent);
    color: var(--ground-raised);
    border-radius: 99px;
    font-size: 0.65rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
</style>
