<!--
  /catalog/series/<key> — a survey and every sheet in it.

  Reads as coverage, not as a catalogue: the first thing on the page is how much
  of the survey the archive actually holds, because "9 sheets" over a survey of
  627 was the claim this page exists to replace.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import DataTable from '$lib/ui/DataTable.svelte';
  import type { PageData } from './$types';
  import type { SeriesSheetView } from '$lib/data/maps/seriesSheets';

  export let data: PageData;

  $: series = data.series as {
    key: string;
    name: string;
    sheets: number;
    published_sheets: number;
    first_year: number | null;
    last_year: number | null;
  };
  $: sheets = data.sheets as SeriesSheetView[];
  $: counts = data.counts as {
    total: number;
    held: number;
    obtainable: number;
    no_scan: number;
  };

  $: span =
    series.first_year && series.last_year && series.first_year !== series.last_year
      ? `${series.first_year}–${series.last_year}`
      : (series.first_year ?? series.last_year ?? '');

  $: pct = counts.total ? Math.round((counts.held / counts.total) * 100) : 0;

  const STATUS_LABEL: Record<string, string> = {
    held: 'Held',
    obtainable: 'Scan identified',
    no_scan: 'No known scan',
  };

  const COLUMNS = [
    { key: 'sheet_number', label: 'Sheet', sortable: false },
    { key: 'name', label: 'Name', sortable: false },
    { key: 'status', label: 'Status', sortable: false },
    { key: 'source', label: 'Source', sortable: false },
  ];
</script>

<svelte:head>
  <title>{series.name} — Vietnam Map Archive</title>
  <meta
    name="description"
    content="{series.name}: {counts.held} of {counts.total} sheets held{span ? `, ${span}` : ''}."
  />
</svelte:head>

<PageHero
  title={series.name}
  sub={span ? `${span} · ${counts.total} sheets` : `${counts.total} sheets`}
/>

<div class="page-wrap">
  <section class="section-card coverage">
    <h2>Coverage</h2>
    <p class="lead">
      The archive holds <strong>{counts.held}</strong> of this survey's
      <strong>{counts.total}</strong> sheets — {pct}%.
    </p>
    <!-- A bar rather than three numbers: the point of this page is the shape of
         what is missing, and three integers do not have a shape. -->
    <div
      class="bar"
      role="img"
      aria-label="{counts.held} held, {counts.obtainable} identified but not fetched, {counts.no_scan} with no known scan"
    >
      <span class="seg is-held" style:flex-grow={counts.held}></span>
      <span class="seg is-obtainable" style:flex-grow={counts.obtainable}></span>
      <span class="seg is-none" style:flex-grow={counts.no_scan}></span>
    </div>
    <ul class="legend">
      <li><span class="dot is-held"></span>{counts.held} held</li>
      <li>
        <span class="dot is-obtainable"></span>{counts.obtainable} scan identified, not yet fetched
      </li>
      <li><span class="dot is-none"></span>{counts.no_scan} no known scan</li>
    </ul>
  </section>

  <DataTable columns={COLUMNS}>
    {#each sheets as sheet (sheet.sheet_number)}
      <tr>
        <td class="num">
          <a
            href="/catalog/series/{encodeURIComponent(series.key)}/{encodeURIComponent(
              sheet.sheet_number
            )}">{sheet.sheet_number}</a
          >
        </td>
        <td>{sheet.name ?? '—'}</td>
        <td><span class="badge-chip is-sm is-{sheet.status}">{STATUS_LABEL[sheet.status]}</span></td
        >
        <td class="src">{sheet.source ?? '—'}</td>
      </tr>
    {/each}
  </DataTable>
</div>

<style>
  .page-wrap {
    max-width: 60rem;
    margin: 0 auto;
    padding-block: var(--space-lg);
    padding-inline: var(--space-md);
  }
  .coverage {
    margin-bottom: var(--space-lg);
  }
  .lead {
    font-size: 1.05rem;
    margin: 0 0 var(--space-sm);
  }
  .bar {
    display: flex;
    height: 0.75rem;
    border-radius: 999px;
    overflow: hidden;
    background: var(--color-border);
  }
  .seg {
    display: block;
    flex-basis: 0;
  }
  .seg.is-held,
  .dot.is-held {
    background: var(--color-green);
  }
  .seg.is-obtainable,
  .dot.is-obtainable {
    background: var(--color-yellow);
  }
  .seg.is-none,
  .dot.is-none {
    background: var(--color-border);
  }
  .legend {
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
    padding: 0;
    margin: var(--space-sm) 0 0;
    font-size: 0.85rem;
    color: var(--color-text-muted);
  }
  .legend li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .dot {
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 999px;
    display: inline-block;
  }
  .num {
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .src {
    color: var(--color-text-muted);
    font-size: 0.85rem;
  }
</style>
