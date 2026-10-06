<!--
  FacetControl.svelte — one facet, drawn. Toggle chips for `many`, a select for
  `one`, a floor slider for `min`. `FacetFilters` decides which facets and where;
  this only knows how to show one and say what was chosen.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Choice } from '$lib/core/utils/facets';

  export let label: string;
  export let kind: 'many' | 'one' | 'min';
  export let choices: Choice[] = [];
  export let chosen: string[] = [];
  /** `min` only. */
  export let min = 0;
  export let max = 1;
  export let step = 0.05;
  export let format: (n: number) => string = String;

  const dispatch = createEventDispatcher<{ toggle: string; set: string }>();

  $: floor = Number(chosen[0] ?? min);
</script>

{#if kind === 'many'}
  {#if choices.length}
    <div class="chips" role="group" aria-label={label}>
      {#each choices as c (c.value)}
        {@const on = chosen.includes(c.value)}
        <button
          type="button"
          class="sb-pill is-compact fc-chip"
          class:is-on={on}
          aria-pressed={on}
          style:--chip-color={c.color}
          style:--chip-ink={c.color ? 'var(--color-on-accent)' : undefined}
          on:click={() => dispatch('toggle', c.value)}
        >
          {c.label}
          <span class="n">{c.count}</span>
        </button>
      {/each}
    </div>
  {/if}
{:else if kind === 'one'}
  {#if choices.length > 1 || chosen.length}
    <select
      value={chosen[0] ?? ''}
      aria-label={label}
      on:change={(e) => dispatch('set', e.currentTarget.value)}
    >
      <option value="">{label}: all</option>
      {#each choices as c (c.value)}
        <option value={c.value}>{c.label}{c.count ? ` (${c.count})` : ''}</option>
      {/each}
    </select>
  {/if}
{:else}
  <label class="floor">
    <span>{label} ≥ {format(floor)}</span>
    <input
      type="range"
      {min}
      {max}
      {step}
      value={floor}
      on:input={(e) => dispatch('set', e.currentTarget.value)}
    />
  </label>
{/if}

<style>
  .chips {
    flex: 1 1 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    align-items: center;
  }
  /* `.sb-pill` stretches to fill its row; a facet chip is as wide as its word. */
  .fc-chip {
    flex: none;
    max-width: 100%;
  }
  .fc-chip.is-on {
    background: var(--chip-color, var(--sb-text));
    color: var(--chip-ink, var(--sb-card-bg));
  }
  .n {
    margin-left: 0.25rem;
    font-variant-numeric: tabular-nums;
    opacity: 0.7;
  }
  .floor {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex: 1 1 100%;
    font-size: 0.72rem;
    font-weight: var(--font-bold);
  }
  .floor span {
    min-width: 5.5rem;
  }
  .floor input {
    flex: 1;
    accent-color: var(--color-primary);
  }
</style>
