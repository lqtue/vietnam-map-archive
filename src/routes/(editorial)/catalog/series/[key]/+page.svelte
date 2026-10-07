<!--
  /catalog/series/<key> — a survey and every sheet in it.

  Reads as coverage, not as a catalogue: the first thing on the page is how much
  of the survey the archive actually holds, because "9 sheets" over a survey of
  627 was the claim this page exists to replace.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import PageHero from '$lib/ui/PageHero.svelte';
  import DataTable from '$lib/ui/DataTable.svelte';
  import { matchesAllTerms } from '$lib/core/utils/unaccent';
  import { applySort, type SortState } from '$lib/core/utils/tableSort';
  import { cellCamera, hasDenominator, printing } from '$lib/data/maps/seriesSheets';
  import SeriesCoverageMap from '$lib/features/catalog/SeriesCoverageMap.svelte';
  import SeriesManage from '$lib/features/catalog/SeriesManage.svelte';
  import type { PageData } from './$types';
  import type { SeriesSheetView, SheetStatus } from '$lib/data/maps/seriesSheets';
  import type { SeriesNote } from './notes';

  export let data: PageData;

  $: series = data.series as {
    key: string;
    name: string;
    collection: string | null;
    sheets: number;
    published_sheets: number;
    first_year: number | null;
    last_year: number | null;
    bounds: number[] | null;
  };
  $: sheets = data.sheets as SeriesSheetView[];
  $: counts = data.counts as {
    partial?: boolean;
    total: number;
    held: number;
    obtainable: number;
    no_scan: number;
  };

  // Fit the sheets this archive actually serves.
  $: coverage = data.coverage as { bbox: number[] | null; status: SheetStatus }[];
  $: heldBoxes = coverage
    .filter((cell) => cell.status === 'held' && cell.bbox?.length === 4)
    .map((cell) => cell.bbox as number[]);
  $: mapBounds = heldBoxes.length
    ? [
        Math.min(...heldBoxes.map((box) => box[0])),
        Math.min(...heldBoxes.map((box) => box[1])),
        Math.max(...heldBoxes.map((box) => box[2])),
        Math.max(...heldBoxes.map((box) => box[3])),
      ]
    : series.bounds;
  $: camera = mapBounds ? cellCamera(mapBounds) : null;
  $: mapHref = camera
    ? `/explore?series=${encodeURIComponent(series.key)}&solo=1` +
      `#@${camera.lat.toFixed(4)},${camera.lng.toFixed(4)},${camera.zoom}z,0r`
    : `/explore?series=${encodeURIComponent(series.key)}&solo=1`;

  /**
   * The span of the survey, read off the sheets themselves.
   *
   * This used to come from `map_series.first_year/last_year`, an aggregate over
   * `maps` rows — and L7014 has 9 of those against a survey of 627, so the hero
   * read "catalogued 1966–1984" while the About panel on the same screen said
   * the sheets run 1963 to 1989. Both were true and the page contradicted
   * itself eight lines apart; the qualifying word "catalogued" was carrying an
   * explanation no reader can be expected to unpack.
   *
   * `series_sheets` carries a year per cell (mig 086), 446 of L7014's 627, so
   * the span is a min/max over rows already on the page and costs no query.
   * Cells with no recorded year are skipped rather than counted as a gap in the
   * range — 182 of them are unrecorded, which is honest and not a date.
   */
  $: years = sheets.map((s) => s.year).filter((y): y is number => typeof y === 'number');
  $: span = years.length
    ? Math.min(...years) === Math.max(...years)
      ? `${Math.min(...years)}`
      : `${Math.min(...years)}–${Math.max(...years)}`
    : '';

  $: known = hasDenominator(counts);
  $: description = `${series.name}: ${counts.held} published maps${counts.partial ? ` across ${counts.total} indexed cities; partial source index` : known ? ` of ${counts.total} indexed sheets` : ''}${span ? `; recorded dates ${span}` : ''}. Browse sheet records, scans and source institutions.`;
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
    { key: 'sheet_number', label: 'Sheet' },
    { key: 'name', label: 'Name' },
    { key: 'version', label: 'Version' },
    { key: 'status', label: 'Status' },
    { key: 'source', label: 'Source' },
  ];

  /* ── Finding one sheet in 627 ──────────────────────────────────────────
     The survey index is the one table in the app that ships whole: all 627
     rows are in the server-rendered HTML, because a sheet the archive does
     NOT hold still needs a URL and a crawler still needs to read it. So the
     search and the facets are client-side over an array already in memory —
     no `/api/search`, no request per keystroke, and the filtered view is a
     derived value rather than state anyone has to keep in step.

     `matchesAllTerms` is the catalogue's own folding, so "phu ly" finds
     "Phú Lý" and "quang" narrows rather than matching nothing; `applySort`
     and `SortHeader` are the same pair the other four tables use. Nothing
     here is new machinery. */
  let q = '';
  let statusFilter: string | null = null;
  let sort: SortState<string> = { key: 'sheet_number', asc: true };

  /** The cell a sort reads. `version` sorts by year, which is what a reader
      means by it — the printed edition string sorts "003" before "1-AMS". */
  const sortCell = (s: SeriesSheetView, key: string) =>
    key === 'version'
      ? (s.year ?? null)
      : ((s as unknown as Record<string, string | null>)[key] ?? null);

  $: byStatus = statusFilter ? sheets.filter((s) => s.status === statusFilter) : sheets;
  $: found = q.trim()
    ? byStatus.filter((s) =>
        matchesAllTerms(`${s.sheet_number} ${s.name ?? ''} ${s.source ?? ''}`, q)
      )
    : byStatus;
  $: visible = applySort(found, sort, sortCell);

  /** Facet counts over the whole survey, so a chip's number does not change
      as the search narrows — the chip says how big that slice of the survey
      is, not how much of it survives the current query. */
  $: statusCounts = {
    held: counts.held,
    obtainable: counts.obtainable,
    no_scan: counts.no_scan,
  } as Record<string, number>;

  function pickStatus(key: string) {
    statusFilter = statusFilter === key ? null : key;
  }

  /**
   * One printing of one cell. The shape `$lib/data/maps/sheetSources.ts` will
   * hand back for the printings the archive does *not* hold, declared here
   * rather than imported because that module is still being written; swapping
   * this for `import type { SheetPrinting }` is the whole integration on this
   * side. `rights` is the one field of that shape the load does not carry —
   * nothing on this page renders a licence.
   */
  interface SheetPrinting {
    /** Who holds it. Null on a held printing — see the load for why. */
    institution: string | null;
    year: number | null;
    edition: string | null;
    part: 'whole' | 'W' | 'E' | 'assemblage' | null;
    url: string | null;
    held: boolean;
    printingId?: string | null;
    unresolved?: boolean;
    title?: string | null;
    scans?: { url: string; name: string }[];
    institutions?: string[];
    sourceItems?: { institution: string | null; url: string | null; rights: string | null }[];
  }

  /**
   * Cells the archive publishes in more than one **printing**, `sheet_number`
   * to a count. The row itself can name only the printing it serves —
   * `series_sheets` is keyed one row per cell — so without this a sheet held
   * twice would look like a sheet held once, which is a claim about the archive
   * that is false.
   *
   * A printing is a map, not a record: the Indochine 1:25,000 issued most cells
   * as a west and an east half-sheet, and the two halves are one printing. The
   * rule lives in the load (`distinctPrintings`) and is deliberately not
   * repeated here — two spellings of one count is how the six false "2 editions"
   * badges this replaced would come back.
   */
  $: editions = (data.editions ?? {}) as Record<string, number>;

  /**
   * Every printing of the cells that have more than one record, `sheet_number`
   * to the list. Only those cells: a list of one against each of L7014's 627
   * sheets is a payload that says nothing.
   */
  $: printings = (data.printings ?? {}) as Record<string, SheetPrinting[]>;
  $: canonicalPrintings = data.canonicalPrintings ?? {};

  function canonicalLabel(number: string): string | null {
    const rows = canonicalPrintings[number] ?? [];
    if (!rows.length) return null;
    return rows
      .map((row) =>
        [
          row.printing_year ?? row.edition_year ?? row.content_year,
          row.edition_label ?? row.edition_statement,
          row.printed_title,
        ]
          .filter(Boolean)
          .join(' · ')
      )
      .filter(Boolean)
      .join(' / ');
  }

  const PART_LABEL: Record<string, string> = {
    whole: 'Whole sheet',
    W: 'Western half',
    E: 'Eastern half',
    assemblage: 'Assemblage',
  };

  /**
   * The years behind a cell whose own `series_sheets` row records no printing.
   *
   * Every half-sheet cell is in that state — migration 086's backfill follows
   * `series_sheets.map_id`, a single id, and for a cell cut in two it was left
   * null rather than made to pick a half. So those rows read "—" in the Version
   * column while the archive holds two dated scans of them, and cells 34, 39 and
   * "73 bis" pair halves 14, 19 and 22 years apart. That spread is the most
   * interesting thing about them and it was the thing not on the page.
   */
  function heldYears(cell: SheetPrinting[]): string | null {
    const years = [...new Set(cell.filter((p) => p.held).map((p) => p.year))]
      .filter((y): y is number => y !== null)
      .sort((a, b) => a - b);
    return years.length ? years.join(' / ') : null;
  }

  /**
   * What the survey is, from `notes.ts`. Undefined for a survey nobody has
   * written up yet, which renders nothing rather than an empty card.
   */
  $: note = data.note as SeriesNote | undefined;
</script>

<svelte:head>
  <title>{series.name} — Vietnam Map Archive</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={series.name} />
  <meta property="og:description" content={description} />
</svelte:head>

<PageHero
  title={series.name}
  sub={span ? `${counts.total} sheets · ${span}` : `${counts.total} sheets`}
>
  <a slot="actions" class="btn is-lg is-primary" href={mapHref}>{$t('Open in map')}</a>
</PageHero>

<div class="page-wrap">
  {#if note}
    <!-- What the survey is, before how much of it we hold. A reader who has
         landed on a sheet number needs to know what they are looking at first;
         the coverage bar answers a question they have not asked yet. -->
    <section class="section-card about">
      <h2>About this survey</h2>
      {#each note.summary as para (para)}
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
    {#if counts.partial}
      <p class="lead">
        The archive holds <strong>{counts.held}</strong> of the <strong>{counts.total}</strong> sheets
        currently indexed. This is a partial list; the full historical series total is not established.
      </p>
    {:else if known}
      <p class="lead">
        The archive holds <strong>{counts.held}</strong> of this survey's
        <strong>{counts.total}</strong> sheets — {pct}%.
      </p>
    {:else}
      <p class="lead">
        The archive holds <strong>{counts.held}</strong> sheets of this survey. Its full sheet list is
        not imported yet, so how much that is of the whole is not known.
      </p>
    {/if}
    <!-- Where the cells sit, tinted like the bar below. A held-only index still
         draws: it is the footprint of what the archive has. -->
    {#if coverage.some((cell) => cell.bbox)}
      <div class="cov-map">
        <SeriesCoverageMap
          cells={coverage}
          seriesKey={series.key}
          label="{series.name}: where the sheets are"
        />
      </div>
      <p class="cov-credit">Basemap © OpenStreetMap contributors, Protomaps</p>
    {/if}
    <!-- A bar rather than three numbers: the point of this page is the shape of
         what is missing, and three integers do not have a shape. -->
    {#if known}
      <div
        class="bar"
        role="img"
        aria-label="{counts.held} held, {counts.obtainable} located elsewhere but not served, {counts.no_scan} with no known scan"
      >
        <span class="seg is-held" style:flex-grow={counts.held}></span>
        <span class="seg is-obtainable" style:flex-grow={counts.obtainable}></span>
        <span class="seg is-none" style:flex-grow={counts.no_scan}></span>
      </div>
      <ul class="legend">
        <li><span class="dot is-held"></span>{counts.held} held</li>
        <!-- "Scan located elsewhere" is a scan the archive has or knows of but does not serve yet:
           TTU sheets not yet placed on the ground, and plain scans awaiting review. -->
        <li>
          <span class="dot is-obtainable"></span>{counts.obtainable} scan located elsewhere, not served
          here
        </li>
        <li><span class="dot is-none"></span>{counts.no_scan} no known scan</li>
      </ul>
    {/if}
  </section>

  <SeriesManage seriesKey={series.key} cellCount={counts.total} />

  <div class="sheet-tools">
    <label class="sb-search is-page">
      <input
        class="sb-search-input"
        type="search"
        aria-label="Search this survey"
        bind:value={q}
        placeholder="Search by sheet number, name or source…"
      />
    </label>
    <div class="facets">
      {#each ['held', 'obtainable', 'no_scan'] as key (key)}
        <button
          type="button"
          class="badge-chip is-sm {STATUS_CHIP[key]}"
          class:is-off={statusFilter !== null && statusFilter !== key}
          aria-pressed={statusFilter === key}
          on:click={() => pickStatus(key)}
        >
          {STATUS_LABEL[key]}
          <span class="facet-n">{statusCounts[key]}</span>
        </button>
      {/each}
    </div>
    <p class="found">
      {visible.length === counts.total
        ? `${counts.total} sheets`
        : `${visible.length} of ${counts.total} sheets`}
    </p>
  </div>

  <DataTable columns={COLUMNS} bind:sort>
    {#each visible as sheet (sheet.sheet_number)}
      {@const cell = printings[sheet.sheet_number]}
      {@const count = editions[sheet.sheet_number] ?? 0}
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
          {#if cell}
            {@const heldHere = cell.filter((p) => p.held)}
            {@const elsewhere = cell.filter(
              (p) => !p.held && (!!p.institution || !!p.url || !!p.institutions?.length)
            )}
            {@const unservedCanonical = cell.filter(
              (p) =>
                !p.held && !!p.printingId && !p.institution && !p.url && !p.institutions?.length
            )}
            <!-- A `<details>`, not a modal and not a second table: the question
                 ("which two?") is asked of one row at a time and the answer is
                 four lines long. The disclosure is the Version cell itself, so
                 closed the row is the line it always was — 627 of them, and a
                 taller row here is a taller table everywhere. -->
            <details>
              <summary>
                {canonicalLabel(sheet.sheet_number) ?? printing(sheet) ?? heldYears(cell) ?? '—'}
                <!-- Three different facts, and the badge has to say which one
                     it is counting. `cell` holds our printings AND everyone
                     else's since the merge, so a bare `cell.length` called two
                     whole sheets at Perry-Castañeda and Texas Tech "2
                     half-sheets" on a cell the archive does not hold at all —
                     wrong about the paper and wrong about whose it is. -->
                <span class="ver-more">
                  {#if count > 1}{count} printings{:else if heldHere.length > 0}{heldHere.reduce(
                      (n, p) => n + (p.scans?.length ?? 1),
                      0
                    )}
                    scans{:else if elsewhere.length}{elsewhere.length} elsewhere{:else if unservedCanonical.length}verified
                    printing, no linked scan{:else}unresolved{/if}
                </span>
              </summary>

              <ul class="printings">
                {#each heldHere as p, i (i)}
                  <li>
                    <span class="p-when"
                      >{p.year ?? '—'}{p.edition ? ` · ed. ${p.edition}` : ''}</span
                    >
                    {#if p.title}<span class="p-meta">{p.title}</span>{/if}
                    <span class="p-meta">
                      {p.part ? PART_LABEL[p.part] : 'Part unknown'}
                      {#if p.institutions?.length}<span>{p.institutions.join(', ')}</span>{/if}
                      <span class="badge-chip is-sm {STATUS_CHIP.held}">{STATUS_LABEL.held}</span>
                    </span>
                    {#if p.unresolved}<span class="p-meta">Printing unresolved</span>{/if}
                    {#if p.scans?.length}
                      {#each p.scans as scan (scan.url)}<a href={scan.url}>Scan: {scan.name} →</a
                        >{/each}
                    {:else if p.url}<a href={p.url}>Open record →</a>{/if}
                    {#each p.sourceItems ?? [] as source (source.url ?? source.institution)}
                      {#if source.url}<a href={source.url} rel="noreferrer external"
                          >{source.institution ?? 'Institution source'} →</a
                        >{/if}
                      {#if source.rights}<span class="p-meta">Rights: {source.rights}</span>{/if}
                    {/each}
                  </li>
                {/each}
              </ul>

              {#if elsewhere.length}
                <p class="p-head">Known elsewhere</p>
                <ul class="printings">
                  {#each elsewhere as p, i (i)}
                    <li>
                      <span class="p-when"
                        >{p.year ?? '—'}{p.edition ? ` · ed. ${p.edition}` : ''}</span
                      >
                      <span class="p-meta">
                        {p.part ? PART_LABEL[p.part] : 'Part unknown'}
                        {#if p.unresolved}<span class="p-meta">Printing unresolved</span
                          >{:else if p.url || p.sourceItems?.some((source) => source.url)}<span
                            class="badge-chip is-sm {STATUS_CHIP.obtainable}"
                            >{STATUS_LABEL.obtainable}</span
                          >{:else}<span class="p-meta">Catalogued; digitized copy unknown</span
                          >{/if}
                      </span>
                      {#if p.url}
                        <a href={p.url} rel="noreferrer external">{p.institution ?? 'Source'} →</a>
                      {:else if p.institution}
                        <span class="p-meta">{p.institution}</span>
                      {/if}
                      {#each p.sourceItems ?? [] as source (source.url ?? source.institution)}
                        {#if source.url}<a href={source.url} rel="noreferrer external"
                            >{source.institution ?? 'Institution source'} →</a
                          >{/if}
                        {#if source.rights}<span class="p-meta">Rights: {source.rights}</span>{/if}
                      {/each}
                    </li>
                  {/each}
                </ul>
              {/if}
              {#if unservedCanonical.length}
                <p class="p-head">Verified printings with no linked scan</p>
                <ul class="printings">
                  {#each unservedCanonical as p (p.printingId)}
                    <li>
                      <span class="p-when">{p.year ?? '—'}{p.edition ? ` · ${p.edition}` : ''}</span
                      >
                      {#if p.title}<span class="p-meta">{p.title}</span>{/if}
                      <span class="p-meta"
                        >{p.part ? PART_LABEL[p.part] : 'Part unknown'} · verified identity; no archive
                        scan linked</span
                      >
                    </li>
                  {/each}
                </ul>
              {/if}
            </details>
          {:else}
            {printing(sheet) ?? '—'}
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
    <svelte:fragment slot="after">
      {#if !visible.length}
        <p class="table-empty">No sheet in this survey matches.</p>
      {/if}
    </svelte:fragment>
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
  /* Search, facets and count on one row, wrapping to three at phone width.
     The count sits last so it is next to the table it describes. */
  .sheet-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    margin-bottom: var(--space-3);
  }
  .sheet-tools .sb-search {
    flex: 1 1 18rem;
  }
  .facets {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  /* A chip is a choice, so these are real buttons — the status column uses the
     same three tints, which is what ties a chip to the rows it selects. */
  .facets button {
    cursor: pointer;
    border: none;
    font: inherit;
  }
  /* Dimmed, not hidden: the unselected facets still say how big the survey's
     other slices are, which is the number a reader is comparing against. */
  .facets button.is-off {
    opacity: 0.45;
  }
  .facet-n {
    margin-left: 0.3rem;
    font-variant-numeric: tabular-nums;
    opacity: 0.75;
  }
  .found {
    margin: 0;
    margin-left: auto;
    font-size: 0.88rem;
    color: var(--color-gray-500);
    font-variant-numeric: tabular-nums;
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
      column-gap: var(--space-6);
    }
  }
  .fact dt {
    font-size: 0.78rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-gray-500);
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
    color: var(--color-gray-500);
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
  .cov-map {
    height: clamp(320px, 65vh, 640px);
  }
  .cov-credit {
    margin: var(--space-1) 0 var(--space-4);
    font-size: var(--text-xs);
    color: var(--color-gray-500);
    text-align: right;
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
    color: var(--color-gray-500);
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
    color: var(--color-gray-500);
    font-size: 0.78rem;
  }

  /* The badge is the affordance. The native triangle would indent the whole
     summary by a marker's width and put a second control beside a pill that
     already reads as one, so it is suppressed and the caret rides the badge —
     the closed row then looks exactly like the row that has no disclosure. */
  .ver summary {
    display: block;
    list-style: none;
    cursor: pointer;
  }
  .ver summary::-webkit-details-marker {
    display: none;
  }
  .ver summary .ver-more::after {
    content: ' ▸';
  }
  .ver details[open] summary .ver-more::after {
    content: ' ▾';
  }

  /* The panel stacks inside the cell and the row grows while it is open.
     Floating it out — absolute, or a popover — puts it under `.table-wrap`'s
     `overflow: auto` clip and the links inside become unreachable; the scout
     table learned that the expensive way (`admin-scout.css` .sd-ask).

     `min-width` rather than `width`: the column keeps the width its 627 closed
     rows give it, and an open panel widens it by about two characters instead
     of reflowing the whole table. `.ver` is nowrap for the closed line, so the
     panel has to say otherwise for itself. */
  .printings {
    list-style: none;
    margin: 0.45rem 0 0;
    padding: 0;
    min-width: 11rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    white-space: normal;
  }
  .printings li {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    line-height: 1.35;
  }
  .p-when {
    font-weight: var(--font-bold);
  }
  .p-meta {
    color: var(--color-gray-500);
    font-size: 0.78rem;
  }
  .p-head {
    margin: 0.6rem 0 0;
    padding-top: 0.5rem;
    border-top: var(--border-thin);
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-gray-500);
  }

  .src {
    color: var(--color-gray-500);
    font-size: 0.85rem;
  }
</style>
