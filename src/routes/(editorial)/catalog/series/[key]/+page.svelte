<!--
  /catalog/series/<key> — a survey and every sheet in it.

  Reads as coverage, not as a catalogue: the first thing on the page is how much
  of the survey the archive actually holds, because "9 sheets" over a survey of
  627 was the claim this page exists to replace.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import DataTable from '$lib/ui/DataTable.svelte';
  import { printing } from '$lib/data/maps/seriesSheets';
  import type { PageData } from './$types';
  import type { SeriesSheetView } from '$lib/data/maps/seriesSheets';
  import type { SeriesNote } from './notes';

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

  /**
   * The span of the sheets the archive has **catalogued**, not of the survey,
   * and not of everything it holds either. It comes from `map_series`, an
   * aggregate over `maps` rows, and L7014 has 9 of those against a survey of
   * 627 printed between 1963 and 1989 — so an unlabelled "1966–1984" beside
   * "627 sheets" reads as the survey's dates and is wrong by a decade at each
   * end. "held" was the first label and is still too strong: `counts.held` is
   * 461, and 452 of those are mosaic cells with no `maps` row and therefore no
   * year in the view at all. "catalogued" is true of exactly the rows the
   * number comes from. `/catalog/series` uses the same word.
   */
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

  // The chip tints are `editorial.css`'s own vocabulary, not an `is-<status>`
  // modifier — there is no such thing, and spelling one rendered all three
  // statuses as the same bare pill. Green/yellow/gray follows the bar above so
  // the column and the bar read as one thing; `chip-gray` is the nearest tint
  // the vocabulary has to the bar's `--color-border`.
  const STATUS_CHIP: Record<string, string> = {
    held: 'chip-green',
    obtainable: 'chip-yellow',
    no_scan: 'chip-gray',
  };

  const COLUMNS = [
    { key: 'sheet_number', label: 'Sheet', sortable: false },
    { key: 'name', label: 'Name', sortable: false },
    { key: 'version', label: 'Version', sortable: false },
    { key: 'status', label: 'Status', sortable: false },
    { key: 'source', label: 'Source', sortable: false },
  ];

  /**
   * Cells the archive publishes in more than one printing, `sheet_number` to a
   * count. The row itself can name only the printing it serves — `series_sheets`
   * is keyed one row per cell — so without this a sheet held twice would look
   * like a sheet held once, which is a claim about the archive that is false.
   */
  $: editions = (data.editions ?? {}) as Record<string, number>;

  /**
   * What the survey is, from `notes.ts`. Undefined for a survey nobody has
   * written up yet, which renders nothing rather than an empty card.
   */
  $: note = data.note as SeriesNote | undefined;
</script>

<svelte:head>
  <title>{series.name} — Vietnam Map Archive</title>
  <meta
    name="description"
    content="{series.name}: {counts.held} of {counts.total} sheets held{span
      ? `; the catalogued sheets date ${span}`
      : ''}."
  />
</svelte:head>

<PageHero
  title={series.name}
  sub={span ? `${counts.total} sheets · catalogued ${span}` : `${counts.total} sheets`}
/>

<div class="page-wrap">
  {#if note}
    <!-- What the survey is, before how much of it we hold. A reader who has
         landed on a sheet number needs to know what they are looking at first;
         the coverage bar answers a question they have not asked yet. -->
    <section class="section-card about">
      <h2>About this survey</h2>
      {#each note.summary as para}
        <p class="lead">{para}</p>
      {/each}

      <dl class="facts">
        {#each note.facts as fact (fact.label)}
          <div class="fact">
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        {/each}
      </dl>

      {#if note.correction}
        <p class="correction">
          <strong>Commonly stated, and wrong:</strong>
          {note.correction.claim} — {note.correction.actually}
        </p>
      {/if}
    </section>
  {/if}

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
        <td class="ver">
          {printing(sheet) ?? '—'}
          {#if editions[sheet.sheet_number] > 1}
            <span class="ver-more">{editions[sheet.sheet_number]} editions</span>
          {/if}
        </td>
        <td
          ><span class="badge-chip is-sm {STATUS_CHIP[sheet.status]}"
            >{STATUS_LABEL[sheet.status]}</span
          ></td
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
    padding-block: var(--space-6);
    padding-inline: var(--space-4);
  }
  .coverage {
    margin-bottom: var(--space-6);
  }
  .about {
    margin-bottom: var(--space-4);
  }
  .about .lead {
    max-width: 68ch;
  }
  /* Label above value, not beside it: several of these run to three lines, and
     a two-column definition list at phone width gives the value a 12ch track. */
  .facts {
    display: grid;
    gap: var(--space-3);
    margin: var(--space-4) 0 0;
  }
  @media (min-width: 40rem) {
    .facts {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      column-gap: var(--space-5);
    }
  }
  .fact dt {
    font-size: 0.78rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin-bottom: 0.15rem;
  }
  .fact dd {
    margin: 0;
    font-size: 0.92rem;
    line-height: 1.55;
  }
  .correction {
    margin: var(--space-4) 0 0;
    padding-left: var(--space-3);
    border-left: 2px solid var(--color-border);
    font-size: 0.92rem;
    color: var(--color-text-muted);
    max-width: 68ch;
  }
  .lead {
    font-size: 1.05rem;
    margin: 0 0 var(--space-2);
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
    gap: var(--space-4);
    padding: 0;
    margin: var(--space-2) 0 0;
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
  /* The printing, and whether the archive has more than one of it. Narrow and
     nowrap: it is "1984 · ed. 5-DMA" at its longest, and the Name column is
     the one that should take the slack. */
  .ver {
    white-space: nowrap;
    font-size: 0.85rem;
  }
  .ver-more {
    margin-left: 0.4rem;
    padding: 0.05rem 0.4rem;
    border-radius: var(--radius-pill);
    background: var(--color-bg);
    color: var(--color-text-muted);
    font-size: 0.78rem;
  }

  .src {
    color: var(--color-text-muted);
    font-size: 0.85rem;
  }
</style>
