<!--
  /catalog/series/<key>/<number> — one sheet of a survey.

  Says three things in order: which cell of the survey this is, whether the
  archive holds it and by what route, and where to see it. A sheet we do not
  hold says so plainly and names where a scan was last seen, which is the whole
  value of having a page for it.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import type { PageData } from './$types';
  import type { SeriesSheetView } from '$lib/data/maps/seriesSheets';

  export let data: PageData;

  $: series = data.series as { key: string; name: string };
  $: sheet = data.sheet as SeriesSheetView;
  $: maps = data.maps as { id: string; name: string; year: number | null; half: string | null }[];
  $: camera = data.camera as { lng: number; lat: number; zoom: number } | null;

  $: title = sheet.name
    ? `${sheet.name} — sheet ${sheet.sheet_number}`
    : `Sheet ${sheet.sheet_number}`;

  const STATUS_TEXT: Record<string, string> = {
    held: 'In the archive',
    obtainable: 'Not held — a scan has been identified',
    no_scan: 'Not held — no scan located anywhere',
  };

  /**
   * Where to look at it. A sheet with its own `maps` row opens as that map; a
   * mosaic cell has no id to open, so the camera goes in the hash and the
   * reader arrives over the right ground with the mosaic already drawn.
   */
  $: exploreHref = maps.length
    ? `/explore?map=${maps[0].id}`
    : camera
      ? `/explore#@${camera.lat.toFixed(5)},${camera.lng.toFixed(5)},${camera.zoom}z,0r`
      : null;

  const fmt = (v: number) => v.toFixed(4).replace(/\.?0+$/, '');
</script>

<svelte:head>
  <title>{title} · {series.name} — Vietnam Map Archive</title>
  <meta name="description" content="{title} of {series.name}. {STATUS_TEXT[sheet.status]}." />
  <!-- A page whose whole content is "nobody has found this" is thin, and there
       are 166 of them in L7014 alone. Useful to a researcher, not something to
       compete in search with the sheets that exist. -->
  {#if sheet.status !== 'held'}
    <meta name="robots" content="noindex" />
  {/if}
</svelte:head>

<PageHero {title} sub={series.name} />

<div class="page-wrap">
  <p class="crumb">
    <a href="/catalog/series/{encodeURIComponent(series.key)}">← All sheets in this survey</a>
  </p>

  <section class="section-card">
    <h2>Status</h2>
    <p class="status is-{sheet.status}">{STATUS_TEXT[sheet.status]}</p>
    {#if sheet.heldAs}
      <p class="muted">{sheet.heldAs}.</p>
    {/if}
    {#if sheet.note}
      <p class="muted">{sheet.note}</p>
    {/if}

    {#if maps.length === 1}
      <p>
        This sheet has its own catalogue record:
        <a href="/catalog/{maps[0].id}">{maps[0].name}{maps[0].year ? ` (${maps[0].year})` : ''}</a
        >.
      </p>
    {:else if maps.length > 1}
      <!-- A cell held more than once: two printings of the sheet, or the two
           half-sheets it was cut into. Both are records in their own right and
           each needs its own link — listing one and calling it "the" record is
           how the other came to be reachable from nowhere. -->
      <p>
        The archive holds {maps.length} records of this sheet:
      </p>
      <ul class="records">
        {#each maps as m (m.id)}
          <li>
            <a href="/catalog/{m.id}">{m.name}</a>
            {#if m.year}<span class="muted">{m.year}</span>{/if}
            {#if m.half === 'W'}<span class="muted">western half</span>
            {:else if m.half === 'E'}<span class="muted">eastern half</span>{/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if sheet.status !== 'held' && sheet.source}
      <p>
        A copy is recorded at <strong>{sheet.source}</strong>{#if sheet.source_ref}:
          <a href={sheet.source_ref} rel="noreferrer external">{sheet.source_ref}</a>{/if}.
      </p>
    {/if}
  </section>

  <section class="section-card">
    <h2>Cell</h2>
    <!-- The survey's own index assigns this rectangle. It is not a
         georeference: nothing should be warped against it. -->
    <dl>
      <dt>Sheet number</dt>
      <dd>{sheet.sheet_number}</dd>
      {#if sheet.name}
        <dt>Name</dt>
        <dd>{sheet.name}</dd>
      {/if}
      {#if sheet.bbox}
        <dt>West–east</dt>
        <dd>{fmt(sheet.bbox[0])}° – {fmt(sheet.bbox[2])}°</dd>
        <dt>South–north</dt>
        <dd>{fmt(sheet.bbox[1])}° – {fmt(sheet.bbox[3])}°</dd>
      {/if}
    </dl>
    <p class="muted">The cell the survey's index assigns this sheet, not a georeference.</p>
  </section>

  {#if exploreHref}
    <p class="cta"><a class="btn is-primary is-lg" href={exploreHref}>Open on the map</a></p>
  {/if}
</div>

<style>
  .records {
    margin: 0.4rem 0 0;
    padding-left: 1.1rem;
  }
  .records li {
    margin-bottom: 0.2rem;
  }
  .records .muted {
    margin-left: 0.35rem;
  }
  .page-wrap {
    max-width: 46rem;
    margin: 0 auto;
    padding-block: var(--space-lg);
    padding-inline: var(--space-md);
  }
  .crumb {
    margin: 0 0 var(--space-md);
    font-size: 0.9rem;
  }
  .section-card + .section-card {
    margin-top: var(--space-md);
  }
  .status {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 0 0 var(--space-xs);
  }
  .status.is-held {
    color: var(--color-green);
  }
  .status.is-obtainable {
    color: var(--color-text);
  }
  .status.is-no_scan {
    color: var(--color-text-muted);
  }
  .muted {
    color: var(--color-text-muted);
    font-size: 0.9rem;
    margin: 0 0 var(--space-xs);
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.35rem var(--space-md);
    margin: 0 0 var(--space-sm);
  }
  dt {
    font-weight: 600;
    color: var(--color-text-muted);
  }
  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  .cta {
    margin-top: var(--space-lg);
  }
</style>
