<!--
  OcrFilterBar.svelte — the confidence floor + category chips above the OCR
  review table. Filtering is client-side, so both values are bound straight
  back to the sidebar rather than round-tripping through the API.
-->
<script lang="ts">
  import { OCR_CATEGORIES, CAT_COLORS } from '../shared/constants';

  /** Minimum confidence, 0–1. */
  export let minConf = 0;
  /** Categories currently shown. Mutated in place, then reassigned for reactivity. */
  export let categories: Set<string>;

  function toggle(cat: string) {
    if (categories.has(cat)) categories.delete(cat);
    else categories.add(cat);
    categories = categories;
  }
</script>

<div class="ocr-filters">
  <div class="conf-filter">
    <span class="filter-label">Conf ≥ {(minConf * 100).toFixed(0)}%</span>
    <input type="range" min="0" max="1" step="0.05" bind:value={minConf} class="conf-slider" />
  </div>
  <div class="cat-toggles">
    <div class="cat-bulk-actions">
      <button
        type="button"
        class="bulk-link"
        on:click={() => (categories = new Set(OCR_CATEGORIES))}
      >
        All
      </button>
      <span class="bulk-sep">·</span>
      <button type="button" class="bulk-link" on:click={() => (categories = new Set())}>
        None
      </button>
    </div>
    {#each OCR_CATEGORIES as cat}
      <button
        type="button"
        class="cat-chip"
        class:active={categories.has(cat)}
        on:click={() => toggle(cat)}
        style="--cat-color: {CAT_COLORS[cat]}"
      >
        {cat}
      </button>
    {/each}
  </div>
</div>

<style>
  .ocr-filters {
    padding: 0.6rem 0.75rem;
    background: var(--ground-raised);
    border-bottom: var(--rule-hair) solid var(--rule);
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .conf-filter {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .filter-label {
    font-size: 0.68rem;
    font-weight: var(--w-semi);
    color: var(--ink);
    width: 64px;
    flex-shrink: 0;
  }
  .conf-slider {
    flex: 1;
    height: 4px;
    accent-color: var(--accent);
  }
  .cat-toggles {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    align-items: center;
  }
  .cat-bulk-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-right: 0.4rem;
    padding-right: 0.4rem;
    border-right: 1px solid var(--rule);
    line-height: 1;
  }
  .bulk-link {
    background: none;
    border: none;
    padding: 0;
    font-size: 0.65rem;
    font-weight: var(--w-semi);
    color: var(--accent);
    cursor: pointer;
    opacity: 0.6;
  }
  .bulk-link:hover {
    opacity: 1;
    text-decoration: underline;
  }
  .bulk-sep {
    font-size: 0.65rem;
    opacity: 0.3;
  }
  .cat-chip {
    border: 1.5px solid var(--cat-color);
    background: transparent;
    color: var(--ink);
    font-size: 0.64rem;
    font-weight: var(--w-semi);
    padding: 0.15rem 0.45rem;
    border-radius: 1rem;
    cursor: pointer;
    transition: all 0.1s;
    opacity: 0.45;
  }
  .cat-chip:hover {
    opacity: 0.8;
    transform: translateY(-1px);
  }
  .cat-chip.active {
    opacity: 1;
    background: var(--cat-color);
    color: var(--ground-raised);
  }
</style>
