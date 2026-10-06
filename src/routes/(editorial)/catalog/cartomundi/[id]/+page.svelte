<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import type { CartomundiSheet } from '$lib/data/maps/cartomundi';
  import type { PageData } from './$types';

  export let data: PageData;

  let query = '';
  let sheetQuery = '';

  $: search = query.trim().toLocaleLowerCase();
  $: sheets = data.sheets as CartomundiSheet[];
  $: sheetSearch = sheetQuery.trim().toLocaleLowerCase();
  $: visibleSheets = sheets.filter(
    (sheet) =>
      !sheetSearch ||
      [sheet.number, sheet.title, sheet.year, ...sheet.linkedItems.map((item) => item.doi)]
        .join(' ')
        .toLocaleLowerCase()
        .includes(sheetSearch)
  );
  $: visibleItems = data.items.filter(
    (item) =>
      !search ||
      [item.sheet, item.title, item.year, item.doi, item.license]
        .join(' ')
        .toLocaleLowerCase()
        .includes(search)
  );

  const number = new Intl.NumberFormat('en');

  function scaleLabel(scale: number | null): string {
    return scale ? `1:${number.format(scale)}` : 'Scale unrecorded';
  }

  function checkedAtLabel(value: string): string {
    if (!value) return 'Date unrecorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
  }
</script>

<svelte:head>
  <title>{data.series.title} — CartoMundi index — Vietnam Map Archive</title>
  <meta
    name="description"
    content={`CartoMundi catalogue details and linked Nakala item license checks for ${data.series.title}.`}
  />
</svelte:head>

<div class="page cartomundi-series-page">
  <PageHero
    eyebrow="CartoMundi series"
    title={data.series.title}
    sub={`${data.series.zone} · ${scaleLabel(data.series.scale)}`}
  />

  <main class="editorial-main">
    <a class="back-link" href="/catalog/institutions/cartomundi">All CartoMundi series</a>

    <section class="section-card" aria-labelledby="series-about">
      <div class="section-card-header">
        <h2 id="series-about" class="section-title-sm">About this series</h2>
      </div>
      <dl class="facts">
        <div>
          <dt>Catalogue region</dt>
          <dd>{data.series.zone}</dd>
        </div>
        <div>
          <dt>Vietnam coverage</dt>
          <dd>{data.series.scope}</dd>
        </div>
        <div>
          <dt>Scale</dt>
          <dd>{scaleLabel(data.series.scale)}</dd>
        </div>
        {#if data.series.date}<div>
            <dt>Dates</dt>
            <dd>{data.series.date}</dd>
          </div>{/if}
        {#if data.series.holdingInstitution}
          <div>
            <dt>Holding institution</dt>
            <dd>{data.series.holdingInstitution}</dd>
          </div>
        {/if}
        <div>
          <dt>CartoMundi catalogue</dt>
          <dd>{number.format(data.series.cataloguedSheets)} sheets declared</dd>
        </div>
        <div>
          <dt>Sheet records indexed here</dt>
          <dd>{number.format(sheets.length)}</dd>
        </div>
        <div>
          <dt>Linked items checked</dt>
          <dd>{number.format(data.series.checkedItems)}</dd>
        </div>
      </dl>
      <div class="source-links">
        <a href={data.series.url} target="_blank" rel="noopener noreferrer">View on CartoMundi ↗</a>
        {#if data.archiveHref}
          <a href={data.archiveHref}>View this survey in Vietnam Map Archive</a>
        {/if}
      </div>
    </section>

    <section class="section-card" aria-labelledby="rights-about">
      <div class="section-card-header">
        <h2 id="rights-about" class="section-title-sm">How to read the rights information</h2>
      </div>
      <p>
        The licenses below are posted on individual Nakala records linked from our local source
        index. A posted license does not establish that the depositor had authority over every right
        in the scan and underlying map. Check the source record before reuse.
      </p>
      <p>
        CartoMundi's declared sheet count, the sheet records indexed here, and the number of linked
        items checked are separate counts. A sheet without linked items has no item-level rights
        result in this index.
      </p>
    </section>

    <section class="section-card" aria-labelledby="catalogue-sheets">
      <div class="section-card-header">
        <h2 id="catalogue-sheets" class="section-title-sm">CartoMundi catalogue sheets</h2>
        <p>Sheet records for this series, including those without a linked Nakala rights check.</p>
      </div>

      {#if sheets.length}
        <div class="search-field">
          <label for="sheet-search">Search catalogue sheets</label>
          <input
            id="sheet-search"
            type="search"
            placeholder="Number, title, year, linked DOI"
            bind:value={sheetQuery}
          />
        </div>
        <p class="result-count" aria-live="polite">
          {number.format(visibleSheets.length)} of {number.format(sheets.length)} sheet records
        </p>
        {#if visibleSheets.length}
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Sheet</th>
                  <th scope="col">Title</th>
                  <th scope="col">Year</th>
                  <th scope="col">Rights evidence</th>
                </tr>
              </thead>
              <tbody>
                {#each visibleSheets as sheet (sheet.fkey)}
                  <tr>
                    <td>{sheet.number || '—'}</td>
                    <td>{sheet.title || 'Untitled'}</td>
                    <td>{sheet.year ?? '—'}</td>
                    <td>
                      {#if sheet.linkedItems.length}
                        <ul class="rights-list">
                          {#each sheet.linkedItems as linkedItem (linkedItem.doi)}
                            <li>
                              <span>{linkedItem.license || 'License not recorded'}</span>
                              ·
                              <a
                                href={`https://doi.org/${linkedItem.doi}`}
                                target="_blank"
                                rel="noopener noreferrer">{linkedItem.doi} ↗</a
                              >
                            </li>
                          {/each}
                        </ul>
                      {:else}
                        Rights not checked here
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="empty">No catalogue sheets match this search.</p>
        {/if}
      {:else}
        <p class="empty">No CartoMundi sheet records have been indexed for this series yet.</p>
      {/if}
    </section>

    <section class="section-card" aria-labelledby="linked-items">
      <div class="section-card-header">
        <h2 id="linked-items" class="section-title-sm">Linked Nakala items</h2>
        <p>Item-level source records and their posted licenses.</p>
      </div>

      {#if data.items.length}
        <div class="search-field">
          <label for="item-search">Search linked items</label>
          <input
            id="item-search"
            type="search"
            placeholder="Sheet, title, year, DOI, license"
            bind:value={query}
          />
        </div>
        <p class="result-count" aria-live="polite">
          {number.format(visibleItems.length)} of {number.format(data.items.length)} linked items
        </p>
        {#if visibleItems.length}
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Sheet</th>
                  <th scope="col">Title</th>
                  <th scope="col">Year</th>
                  <th scope="col">Posted license</th>
                  <th scope="col">Source record</th>
                </tr>
              </thead>
              <tbody>
                {#each visibleItems as item (item.doi)}
                  <tr>
                    <td>{item.sheet || '—'}</td>
                    <td>{item.title || 'Untitled'}</td>
                    <td>{item.year ?? '—'}</td>
                    <td>
                      {#if item.license === 'CC-BY-4.0'}
                        <a
                          href="https://creativecommons.org/licenses/by/4.0/"
                          target="_blank"
                          rel="noopener noreferrer">CC BY 4.0 ↗</a
                        >
                      {:else}
                        <span>{item.license || 'Not recorded'}</span>
                      {/if}
                      {#if item.checkedAt}
                        <small>Checked {checkedAtLabel(item.checkedAt)}</small>
                      {/if}
                    </td>
                    <td
                      ><a
                        href={`https://doi.org/${item.doi}`}
                        target="_blank"
                        rel="noopener noreferrer">{item.doi} ↗</a
                      ></td
                    >
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="empty">No linked items match this search.</p>
        {/if}
      {:else}
        <p class="empty">
          No Nakala items from this series are in our local rights index yet. This does not mean
          CartoMundi has no scans or that the series has no reusable items; its sheets have not been
          checked here.
        </p>
      {/if}
    </section>
  </main>
</div>

<style>
  .back-link {
    display: inline-block;
    margin-bottom: var(--space-4);
  }
  .facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
    gap: var(--space-3) var(--space-4);
    margin: 0;
  }
  .facts div {
    min-width: 0;
  }
  dt,
  label {
    font-family: var(--font-family-display);
    font-weight: var(--font-semibold);
  }
  dt,
  .result-count,
  small {
    color: var(--color-gray-500);
    font-size: 0.875rem;
  }
  dd {
    margin: var(--space-1) 0 0;
    overflow-wrap: anywhere;
  }
  .source-links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    margin-top: var(--space-4);
  }
  a {
    color: var(--color-blue);
  }
  p {
    max-width: 72ch;
  }
  .search-field {
    display: grid;
    gap: var(--space-1);
    max-width: 30rem;
    margin-bottom: var(--space-3);
  }
  input {
    width: 100%;
    min-height: 2.75rem;
    padding: var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    background: var(--color-white);
    color: var(--color-text);
    font: inherit;
  }
  .result-count {
    margin: 0 0 var(--space-2);
  }
  .table-scroll {
    max-width: 100%;
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  th,
  td {
    padding: var(--space-2) var(--space-3);
    border-bottom: var(--border-thin);
    vertical-align: top;
  }
  th:first-child,
  td:first-child {
    padding-left: 0;
  }
  th:last-child,
  td:last-child {
    padding-right: 0;
  }
  td a {
    overflow-wrap: anywhere;
  }
  .rights-list {
    display: grid;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  small {
    display: block;
    margin-top: var(--space-1);
  }
  .empty {
    margin: var(--space-3) 0 0;
  }
  @media (max-width: 600px) {
    table {
      min-width: 42rem;
    }
  }
</style>
