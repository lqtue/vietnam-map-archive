<!--
  SeriesDetailDrawer — the side panel a series row opens, the counterpart to
  `CatalogDetailDrawer` for a survey instead of a sheet.

  Same drawer furniture as the map one (backdrop, slide-in, sticky head and
  action row) because it is the same gesture on the same page, and a second
  panel design would read as a different kind of thing. What differs is the
  one thing a survey has that a sheet does not: coverage. So where a map's
  drawer opens with a thumbnail, this opens with the bar — a survey's picture
  is the shape of what is missing from it, which is why this row is worth
  opening at all rather than counting in the list.

  The bar is the `/catalog/series/<key>` page's bar, tint for tint. A reader who
  opens the drawer and then follows "All sheets" must not meet a second, differently
  coloured account of the same three numbers.

  Open by setting `series`; `close` fires and the parent nulls the binding.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { cellCamera } from '$lib/data/maps/seriesSheets';
  import type { SeriesIndexEntry } from '$lib/data/maps/seriesIndex';

  export let series: SeriesIndexEntry | null = null;

  const dispatch = createEventDispatcher<{ close: void; filter: SeriesIndexEntry }>();

  $: open = !!series;

  function close() {
    dispatch('close');
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }
  onMount(() => window.addEventListener('keydown', onKey));
  onDestroy(() => typeof window !== 'undefined' && window.removeEventListener('keydown', onKey));

  $: counts = series?.index ?? { total: 0, held: 0, obtainable: 0, no_scan: 0 };
  $: pct = counts.total ? Math.round((counts.held / counts.total) * 100) : 0;

  /**
   * "Open in map" — `?series=<key>` is /explore's own deeplink (see
   * `ExploreBrowsePanel`), and the key it wants is `map_series.key`, which is
   * the same key this row's coverage page is addressed by.
   *
   * The `#@lat,lng,zoomz,0r` half is the part worth doing carefully. The param
   * carries no camera, so without a hash the survey lands on whatever the
   * reader last looked at — and for a layer the size of Vietnam that means
   * opening on one corner of it and seeing nothing. Every existing link to
   * this deeplink (the home page, /about, two blog posts) hand-codes a camera
   * per survey, which is the ponytail note in `ExploreBrowsePanel` asking for
   * exactly this: `cellCamera` fits the survey's own bounds, so a survey
   * ingested tomorrow gets a correct camera with nobody editing a file.
   */
  $: camera = series ? cellCamera(series.bounds) : null;
  $: mapHref =
    series && camera
      ? `/explore?series=${encodeURIComponent(series.key)}` +
        `#@${camera.lat.toFixed(4)},${camera.lng.toFixed(4)},${camera.zoom}z,0r`
      : '';

  /**
   * "catalogued", never "printed": the span is an aggregate over the `maps`
   * rows we hold, which for L7014 is 9 sheets against a survey of 627 printed
   * 1963–89. The single-series page and the list row both use the same word
   * for the same number.
   */
  $: span =
    series?.firstYear && series?.lastYear && series.firstYear !== series.lastYear
      ? `${series.firstYear}–${series.lastYear}`
      : (series?.firstYear ?? series?.lastYear ?? '');

  /* `sheets` is the count the /explore layer draws — cells with a `maps` row —
     and it is nowhere near `counts.held` for a survey held mostly as mosaic
     cells (9 against 461). Both are true and they answer different questions,
     so the drawer says which is which rather than picking one. */
  $: fields = series
    ? ([
        [$t('Collection'), series.collection],
        [$t('Catalogued'), span ? String(span) : ''],
        [$t('Sheets with a catalogue record'), `${series.publishedSheets}`],
        [$t('Sheets in the survey'), `${counts.total}`],
      ].filter(([, v]) => v !== '') as [string, string][])
    : [];
</script>

{#if open && series}
  <div class="drawer-backdrop" on:click={close} role="presentation"></div>
  <div class="drawer" role="dialog" aria-label={$t('Series details')}>
    <header class="drawer-head">
      <h2 class="drawer-title">{series.name}</h2>
      <button class="btn is-icon dr-close" on:click={close} aria-label={$t('Close')}>×</button>
    </header>

    <section class="coverage">
      <p class="lead">
        {$t('The archive holds {held} of this survey’s {total} sheets — {pct}%.', {
          held: counts.held,
          total: counts.total,
          pct,
        })}
      </p>
      <!-- A bar rather than three numbers: the point of a survey page is the
           shape of what is missing, and three integers do not have a shape. -->
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
        <li><span class="dot is-held"></span>{$t('{N} held', { N: counts.held })}</li>
        <li>
          <span class="dot is-obtainable"></span>{$t('{N} scan identified, not yet fetched', {
            N: counts.obtainable,
          })}
        </li>
        <li><span class="dot is-none"></span>{$t('{N} no known scan', { N: counts.no_scan })}</li>
      </ul>
    </section>

    <dl class="meta">
      {#each fields as [k, v] (k)}
        <div class="meta-row">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      {/each}
    </dl>

    <div class="actions">
      <!-- Three, in the order a reader wants them. The map is the thing the
           archive is for and the only one of the three that draws anything.
           The coverage page is next: it is the only place the sheets we do NOT
           hold are listed, and they are the reason a survey has a page at all.
           The filter is the weakest — it narrows this page to what we already
           hold, which is the question the catalog was answering anyway. -->
      <a class="chip is-primary act" href={mapHref}>{$t('Open in map')}</a>
      <a class="chip act" href="/catalog/series/{encodeURIComponent(series.key)}"
        >{$t('All sheets')}</a
      >
      <button type="button" class="chip act" on:click={() => dispatch('filter', series)}
        >{$t('Filter the catalog')}</button
      >
    </div>
  </div>
{/if}

<style>
  /* Drawer furniture, shared with `CatalogDetailDrawer` by being the same
     values rather than the same class: both are page-locked panels and neither
     is part of the component vocabulary. */
  .drawer-backdrop {
    position: fixed;
    inset: 0;
    background: var(--sb-scrim);
    /* Over `.top-nav`, which is sticky at 100 (editorial.css). At 50 the scrim
       stopped at the nav's bottom edge and left it lit and clickable above an
       open modal — so the page behind could be navigated away from without the
       drawer ever closing. Under NavBar's own fixed 299/300, which is its
       mobile menu and never open at the same time as this. */
    z-index: 150;
    animation: fade 0.15s ease-out;
  }
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(460px, 100vw);
    background: var(--color-white);
    border-left: 2.5px solid var(--color-border);
    box-shadow: -6px 0 0 var(--color-border);
    z-index: 151;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    animation: slidein 0.18s ease-out;
    font-family: var(--font-family-base);
  }
  .drawer-head {
    position: sticky;
    top: 0;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: var(--sb-head-bg);
    border-bottom: var(--border-thin);
    z-index: 1;
  }
  .drawer-title {
    flex: 1;
    margin: 0;
    font-family: var(--font-family-display);
    font-weight: var(--font-extrabold);
    font-size: 1.1rem;
    line-height: 1.25;
  }
  .dr-close {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    font-size: 1.3rem;
    line-height: 1;
  }

  .coverage {
    padding: 1.25rem 1.25rem 0;
  }
  .lead {
    margin: 0 0 0.75rem;
    font-size: 0.92rem;
    line-height: 1.5;
    color: var(--sb-text-meta);
  }
  /* Bar, segments and dots are `/catalog/series/<key>`'s, value for value —
     the drawer is a preview of that page and a reader crossing from one to the
     other must not meet the same three numbers in different colours. The one
     change is the legend, which stacks: three phrases abreast in a 460px panel
     wrapped into six ragged lines. */
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
    margin: var(--space-2) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.8rem;
    color: var(--color-gray-500);
    font-variant-numeric: tabular-nums;
  }
  .legend li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .dot {
    width: 0.6rem;
    height: 0.6rem;
    flex-shrink: 0;
    border-radius: 999px;
    display: inline-block;
  }

  .meta {
    margin: 1rem 0 0;
    padding: 0 1.25rem;
  }
  .meta-row {
    display: grid;
    grid-template-columns: 7rem 1fr;
    gap: 0.6rem;
    padding: 0.4rem 0;
    border-bottom: var(--sb-border-soft);
    font-size: 0.85rem;
  }
  .meta-row:last-child {
    border-bottom: none;
  }
  .meta-row dt {
    font-weight: var(--font-bold);
    color: var(--sb-text-meta);
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    align-self: center;
  }
  .meta-row dd {
    margin: 0;
    color: var(--color-text);
    word-break: break-word;
  }

  .actions {
    position: sticky;
    bottom: 0;
    margin-top: auto;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 1rem 1.25rem;
    background: var(--sb-head-bg);
    border-top: var(--border-thin);
  }
  /* 9rem, not the map drawer's 110px: three labels rather than up to five, and
     at 110 all three fitted one row at 134px against 128px of text — correct,
     and visibly cramped, with each chip's offset shadow landing on the panel
     edge. This wraps "Filter the catalog" onto its own full-width line, which
     is also the right order of importance. */
  .act {
    flex: 1;
    min-width: 9rem;
    text-align: center;
  }

  @keyframes slidein {
    from {
      transform: translateX(20px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (max-width: 600px) {
    .drawer {
      width: 100vw;
      border-left: none;
      box-shadow: none;
    }
  }
</style>
