<!--
  SeriesList.svelte — survey rows: what each one is, what it spans, and the one
  fraction that matters.

  Deliberately not a coverage bar per row: that is the single-series page's
  job, and three segments repeated down a list is a chart of charts. Shared by
  `/catalog/series`, which lists every survey, and the band at the top of
  `/catalog`, which is the way in to it — so the two cannot say the fraction
  differently, which is the only thing a reader would carry between them.

  `dense` is the band: the same row at a padding that lets three of them sit
  above a live search without pushing it off the screen.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { SeriesIndexEntry } from '$lib/data/maps/seriesIndex';

  export let series: SeriesIndexEntry[] = [];
  export let dense: boolean = false;
  /**
   * Open a drawer on click instead of following the row.
   *
   * The row stays an `<a>` with its real `href` either way, and that is the
   * point: /catalog's band is the entry a crawler follows to the coverage
   * pages, and cmd-click and middle-click keep working for a reader who wants
   * the page rather than the summary. Only an unmodified left click is taken,
   * which is the same bargain the catalog's own rows strike.
   */
  export let drawer: boolean = false;

  const dispatch = createEventDispatcher<{ open: SeriesIndexEntry }>();

  function onRowClick(e: MouseEvent, s: SeriesIndexEntry) {
    if (!drawer) return;
    // A new tab, a new window, a saved link — all of those want the page.
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    dispatch('open', s);
  }

  const span = (a: number | null, b: number | null) =>
    a && b && a !== b ? `${a}–${b}` : (a ?? b ?? '');

  const pct = (held: number, total: number) => (total ? Math.round((held / total) * 100) : 0);
</script>

<ul class="rows" class:dense>
  {#each series as s (s.key)}
    {@const years = span(s.firstYear, s.lastYear)}
    <li>
      <a
        class="section-card is-sm is-link"
        href="/catalog/series/{encodeURIComponent(s.key)}"
        on:click={(e) => onRowClick(e, s)}
      >
        <span class="name">{s.name}</span>
        <span class="meta">
          <!-- Labelled, because it is not the survey's dates: the span is an
               aggregate over `maps` rows, which for L7014 is 9 sheets against
               a survey of 627 printed 1963–89. Wording follows the single
               series page. It still flatters — the 452 mosaic cells are held
               too and carry no year here — so it says what it counts. -->
          {#if years}<span>{$t('catalogued {years}', { years })}</span>{/if}
          <span>
            {$t('{held} of {total} sheets — {pct}%', {
              held: s.index.held,
              total: s.index.total,
              pct: pct(s.index.held, s.index.total),
            })}
          </span>
        </span>
      </a>
    </li>
  {/each}
</ul>

<style>
  .rows {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  /* `--card-pad` is the knob `.section-card` documents for exactly this: the
     band is the same card at a third of the padding, not a fifth card. */
  .rows.dense {
    gap: 0.5rem;
  }
  .rows.dense :global(.section-card) {
    --card-pad: 0.7rem 0.9rem;
  }
  .name {
    display: block;
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 1.05rem;
  }
  .rows.dense .name {
    font-size: 0.95rem;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: 0.2rem;
    font-size: 0.85rem;
    color: var(--color-gray-500);
    font-variant-numeric: tabular-nums;
  }
  .rows.dense .meta {
    margin-top: 0.1rem;
    font-size: 0.78rem;
  }
</style>
