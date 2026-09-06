<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  /** Each tab: { value: string; label: string } — label may include emoji. */
  export let tabs: { value: string; label: string }[];
  /** The currently active value. Two-way bindable via on:change. */
  export let active: string;
  /** Active tab background color. Defaults to blue; pass color-mix(in srgb, var(--accent) 55%, var(--status-bad)) for catalog. */
  export let activeColor: string = 'var(--accent)';

  const dispatch = createEventDispatcher<{ change: string }>();
</script>

<div class="chunky-tabs" style="--tab-active-bg: {activeColor}">
  {#each tabs as tab (tab.value)}
    <button
      class="chunky-tab"
      class:active={active === tab.value}
      on:click={() => dispatch('change', tab.value)}
    >
      {tab.label}
    </button>
  {/each}
</div>

<style>
  .chunky-tabs {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .chunky-tab {
    padding: 0.75rem 1.5rem;
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.1s;
  }

  .chunky-tab:hover {
    transform: translateY(-2px);
    box-shadow: 4px 4px 0px var(--rule);
  }

  .chunky-tab.active {
    background: var(--tab-active-bg, var(--accent));
    color: var(--on-accent);
    transform: translate(2px, 2px);
    box-shadow: 0 0 0 var(--rule);
  }
</style>
