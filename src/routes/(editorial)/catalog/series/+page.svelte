<!--
  /catalog/series — the surveys, and how much of each the archive holds.

  Deliberately not a coverage bar per row: that is the single-series page's
  job, and three segments repeated down a list is a chart of charts. A row
  says what the survey is, what it spans, and the one fraction that matters.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import type { PageData } from './$types';

  export let data: PageData;

  $: series = data.series;

  const span = (a: number | null, b: number | null) =>
    a && b && a !== b ? `${a}–${b}` : (a ?? b ?? '');

  const pct = (held: number, total: number) => (total ? Math.round((held / total) * 100) : 0);
</script>

<svelte:head>
  <title>Map series — Vietnam Map Archive</title>
  <meta
    name="description"
    content="The survey series the archive holds part of, and how much of each is held."
  />
</svelte:head>

<PageHero title="Map series" sub="Systematic surveys, sheet by sheet" />

<div class="page-wrap">
  <p class="lead">
    A survey is one map printed as many sheets. These are the ones the archive holds part of — each
    page lists every sheet the survey contains, held or not.
  </p>

  {#if series.length}
    <ul class="rows">
      {#each series as s (s.key)}
        {@const years = span(s.firstYear, s.lastYear)}
        <li>
          <a class="section-card is-sm is-link" href="/catalog/series/{encodeURIComponent(s.key)}">
            <span class="name">{s.name}</span>
            <span class="meta">
              <!-- Labelled, because it is not the survey's dates: the span is an
                   aggregate over `maps` rows, which for L7014 is 9 sheets against
                   a survey of 627 printed 1963–89. Wording follows the single
                   series page. It still flatters — the 452 mosaic cells are held
                   too and carry no year here — so it says what it counts. -->
              {#if years}<span>catalogued {years}</span>{/if}
              <span>
                {s.index.held} of {s.index.total} sheets — {pct(s.index.held, s.index.total)}%
              </span>
            </span>
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="lead">No series are published yet.</p>
  {/if}
</div>

<style>
  .page-wrap {
    max-width: 46rem;
    margin: 0 auto;
    padding-block: var(--space-lg);
    padding-inline: var(--space-md);
  }
  .lead {
    margin: 0 0 var(--space-md);
    color: var(--color-text-muted);
  }
  .rows {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }
  .name {
    display: block;
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 1.05rem;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    margin-top: 0.2rem;
    font-size: 0.85rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }
</style>
