<!--
  SeriesList.svelte — the series band at the top of /catalog: every series as
  "Name (sheets held)", styled like the area and region bands beside it. The
  fraction against the series' own index is the link's title; the coverage bar
  and dates are the single-series page's job.

  A series with an imported index is an `<a>` with its real `href`, and that is
  the point: this band is the entry a crawler follows to the coverage pages, and
  cmd-click and middle-click keep working for a reader who wants the page rather
  than the summary. Only an unmodified left click is taken, to open the drawer.
  A series with no index has no coverage page — it 404s on purpose —
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
          title={fraction(s)}
          on:click={(e) => onRowClick(e, s)}>{s.name} ({s.sheets})</a
        >
      {:else}
        <button type="button" class="drow" title={fraction(s)} on:click={() => dispatch('open', s)}
          >{s.name} ({s.sheets})</button
        >
      {/if}
    </li>
  {/each}
</ul>

<style>
  /* The same wrapping row of "Name (count)" links as the area, region and institution bands
     beside it on /catalog; the fraction moved into the title. */
  .rows {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
  }
  .drow {
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    cursor: pointer;
  }
  .drow:hover {
    text-decoration: underline;
  }
</style>
