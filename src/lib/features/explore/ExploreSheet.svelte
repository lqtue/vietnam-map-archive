<!--
  ExploreSheet.svelte — empty-state CTA card.

  Rendered only when the user is in location mode, GPS resolved, the
  catalogue is loaded, and no archival map covers the user's point. In
  every other state the Browse + Layers panels carry the meaning, so the
  sheet just adds noise — its only job here is to give the user a useful
  way out: suggest a map, or jump back to Saigon (which has dense coverage).
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let userLocation: [number, number] | null = null;

  const dispatch = createEventDispatcher<{ jumpToSaigon: void }>();

  $: scoutHref = userLocation
    ? `/admin?tab=scout?near=${userLocation[1].toFixed(5)},${userLocation[0].toFixed(5)}`
    : '/admin?tab=scout';
</script>

<div class="card">
  <strong class="title">No archival map of this exact spot — yet.</strong>
  <p class="hint">
    VMA's archive doesn't yet hold a map covering your point. Browse the full archive for maps
    elsewhere, or suggest a source we should add.
  </p>
  <div class="actions">
    <a class="btn primary" href={scoutHref}>Suggest a map here</a>
    <button type="button" class="btn ghost" on:click={() => dispatch('jumpToSaigon')}>
      Jump to Saigon
    </button>
  </div>
</div>

<style>
  .card {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    width: min(440px, calc(100vw - 1.5rem));
    background: var(--sb-card-bg);
    color: var(--sb-text);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--sb-radius);
    padding: 0.65rem 0.85rem 0.8rem;
    z-index: 90;
  }
  @media (min-width: 900px) {
    .card {
      left: auto;
      right: 1rem;
      top: 1rem;
      transform: none;
    }
  }

  .title {
    display: block;
    margin-bottom: 0.35rem;
    font-family: var(--sb-font-display);
    font-size: var(--t-md);
    font-weight: var(--w-semi);
    line-height: 1.25;
  }
  .hint {
    margin: 0 0 0.55rem;
    font-size: 0.86rem;
    line-height: 1.4;
    color: var(--sb-text-meta);
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .btn {
    flex: 1;
    padding: 0.55rem 0.7rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--sb-radius);
    font-family: inherit;
    font-size: 0.86rem;
    font-weight: var(--w-semi);
    cursor: pointer;
    text-decoration: none;
    text-align: center;
    color: var(--sb-text);
  }
  .btn.primary {
    background: var(--sb-accent-warm);
    color: var(--ground-raised);
  }
  .btn.ghost {
    background: var(--sb-card-bg);
  }
  .btn:active {
    transform: translate(2px, 2px);
    box-shadow: none;
  }
</style>
