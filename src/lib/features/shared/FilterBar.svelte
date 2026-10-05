<!--
  FilterBar.svelte — the search box, the "Filters" disclosure and the reset
  link, as one component. `ArchiveFilters` (the map list) and the legend list
  both wear it, so the two rails of a /scan tool read as one design; before,
  the legend had a bare `<input type="search">` and a row of selects of its own.

  It owns no state. The query is two-way; the dropdowns are the default slot
  and are the caller's own `<select>`s (styled here with `:global`, because a
  slotted element is the caller's, not this component's).
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';

  export let query = '';
  export let placeholder = '';
  export let searchLabel = '';
  /** How many filters inside the disclosure are set — the number on the summary. */
  export let active = 0;
  /** Draw the search box. /catalog turns it off: its field is the page's own. */
  export let showSearch = true;
  /** Show the reset link. */
  export let resettable = false;

  const dispatch = createEventDispatcher<{ reset: void }>();
</script>

<div class="filters">
  {#if showSearch}
    <label class="sb-search">
      <svg
        viewBox="0 0 24 24"
        width="16"
        height="16"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        class="sb-search-input"
        type="search"
        {placeholder}
        aria-label={searchLabel || placeholder}
        bind:value={query}
      />
      {#if query}
        <button
          type="button"
          class="sb-search-clear"
          on:click={() => (query = '')}
          aria-label={$t('Clear')}>×</button
        >
      {/if}
    </label>
  {/if}
  <details class="sb-more">
    <summary
      >{$t('Filters')}{#if active}
        · {active}{/if}</summary
    >
    <div class="dropdowns"><slot /></div>
  </details>
</div>

{#if resettable}
  <div class="reset-row">
    <button type="button" class="reset" on:click={() => dispatch('reset')}
      >{$t('Reset filters')}</button
    >
  </div>
{/if}

<style>
  /* No `gap`: `.sb-more` brings its own vertical margin, and doubling the two
     is what separates the search box from the disclosure under it. */
  .filters {
    display: flex;
    flex-direction: column;
  }
  .dropdowns {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    padding-top: 0.3rem;
  }
  /* `max-width` because the same controls sit on a 1280px page as well as in a
     300px rail: without it each one grew to 400px of chrome around two words.
     The 110px basis is still what makes them wrap in the rail. */
  .dropdowns :global(select) {
    flex: 1 1 110px;
    max-width: 240px;
    padding: 0.35rem 0.45rem;
    font-family: inherit;
    font-size: 0.82rem;
    background: var(--sb-card-bg);
    border: var(--border-thin);
    border-radius: var(--sb-radius-sm);
    box-shadow: 1px 1px 0 var(--shadow-ink);
    cursor: pointer;
  }

  /* Its own row, so the link sits under the bar it resets whether or not the
     list beside it has a count to show. */
  .reset-row {
    display: flex;
    justify-content: flex-end;
  }
  .reset {
    background: transparent;
    border: none;
    padding: 0;
    font: inherit;
    font-size: 0.76rem;
    font-weight: var(--font-bold);
    color: var(--sb-accent);
    text-decoration: underline;
    cursor: pointer;
  }
</style>
