<!--
  SeriesList.svelte — the band at the top of /catalog: every series as one line,
  its name and the one fraction that matters.

  Deliberately not a coverage bar per row: that is the single-series page's job,
  and three segments repeated down a list is a chart of charts. The dates are on
  that page too.

  A series with an imported index is an `<a>` with its real `href`, and that is
  the point: this band is the entry a crawler follows to the coverage pages, and
  cmd-click and middle-click keep working for a reader who wants the page rather
  than the summary. Only an unmodified left click is taken, to open the drawer.
  A series with no index (AMS L909) has no coverage page — it 404s on purpose —
  so its row is a button that opens the drawer alone.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { SeriesIndexEntry } from '$lib/data/maps/seriesIndex';
  import { hasDenominator } from '$lib/data/maps/seriesSheets';

  export let series: SeriesIndexEntry[] = [];

  const dispatch = createEventDispatcher<{ open: SeriesIndexEntry }>();

  function onRowClick(e: MouseEvent, s: SeriesIndexEntry) {
    // A new tab, a new window, a saved link — all of those want the page.
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    dispatch('open', s);
  }

  const pct = (held: number, total: number) => (total ? Math.round((held / total) * 100) : 0);

  /** The one fraction that matters. Without an index there is no total to divide by. */
  const fraction = (s: SeriesIndexEntry) =>
    s.index.total === 0
      ? $t('{held} sheets held', { held: s.sheets })
      : hasDenominator(s.index)
        ? $t('{held} of {total} sheets — {pct}%', {
            held: s.index.held,
            total: s.index.total,
            pct: pct(s.index.held, s.index.total),
          })
        : $t('{held} sheets held', { held: s.index.held });
</script>

<ul class="rows">
  {#each series as s (s.key)}
    <li>
      {#if s.index.total > 0}
        <a
          class="drow"
          href="/catalog/series/{encodeURIComponent(s.key)}"
          on:click={(e) => onRowClick(e, s)}
        >
          <span class="name">{s.name}</span>
          <span class="frac">{fraction(s)}</span>
        </a>
      {:else}
        <button type="button" class="drow" on:click={() => dispatch('open', s)}>
          <span class="name">{s.name}</span>
          <span class="frac">{fraction(s)}</span>
        </button>
      {/if}
    </li>
  {/each}
</ul>

<style>
  /* One bordered list, not a card per series: it sits above a live search and should
     read as a table of contents, not as the page's content. */
  .rows {
    list-style: none;
    padding: 0;
    margin: 0;
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
    background: var(--color-white);
    overflow: hidden;
  }
  .drow {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    width: 100%;
    padding: 0.45rem 0.8rem;
    border: 0;
    background: none;
    font: inherit;
    text-align: left;
    color: inherit;
    text-decoration: none;
    cursor: pointer;
  }
  li + li .drow {
    border-top: 1px dashed var(--color-border);
  }
  .drow:hover .name {
    text-decoration: underline;
  }
  .name {
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 0.95rem;
  }
  .frac {
    font-size: 0.78rem;
    color: var(--color-gray-500);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
</style>
