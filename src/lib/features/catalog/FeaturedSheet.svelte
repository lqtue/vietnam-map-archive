<!--
  FeaturedSheet.svelte — the front page's featured sheet.

  One full scan at a readable size, its brief beside it, and a strip to switch
  between the featured maps. No OpenLayers: the front page shows the sheet, the
  viewer is one click away.

  The strip also carries one tile per survey (`series`), after the sheets. A
  survey is not a scan, so its plate is one of its own sheets as a sample, and
  its brief says what is held and links to the coverage page and the map.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { FeaturedSeries } from './homeCatalog';
  import { cellCamera, hasDenominator } from '$lib/data/maps/seriesSheets';
  import { atWidth } from '$lib/core/iiif/thumbUrl';
  import { mapHref, exploreHref } from '$lib/core/utils/mapSlug';

  export let maps: MapListItem[] = [];
  export let series: FeaturedSeries[] = [];
  /** IIIF thumbnail URLs the page already resolved, keyed by map id. */
  export let thumbnails: Map<string, string> = new Map();
  export let favoriteIds: string[] = [];
  export let showFavorite = false;

  const dispatch = createEventDispatcher<{ toggleFavorite: string }>();

  interface Tile {
    id: string;
    name: string;
    /** The stamp on the tile: a year, or "Survey". */
    stamp: string;
    small?: string;
    map?: MapListItem;
    series?: FeaturedSeries;
  }

  let selectedId: string | null = null;

  /* `thumbnails` is read here, not in a helper, so that a thumbnail arriving
     late repaints the tiles. */
  $: tiles = [
    ...maps.map((m): Tile => ({
      id: m.id,
      name: m.name,
      stamp: String(m.year ?? '\u2014'),
      small: thumbnails.get(m.id) ?? m.thumbnail ?? undefined,
      map: m,
    })),
    ...series.map((s): Tile => ({
      id: `series:${s.entry.key}`,
      name: s.entry.name,
      stamp: 'Survey',
      small: s.thumbnail,
      series: s,
    })),
  ];

  $: current = tiles.find((t) => t.id === selectedId) ?? tiles[0] ?? null;
  $: selected = current?.map ?? null;
  $: selectedSeries = current?.series ?? null;

  /** The plate: the one image on the page worth its own request. */
  const largeSrc = (small?: string) => atWidth(small, 1200);

  /**
   * The picker tiles are 132px wide, and the stored `thumbnail` column is
   * 800 — five of those was 715 kB of front page for five thumbnails. 400
   * still covers a 2x screen.
   */
  const tileSrc = (small?: string) => atWidth(small, 400);

  function fallbackToSmall(e: Event, small?: string) {
    const img = e.target as HTMLImageElement;
    if (small && img.src !== small) img.src = small;
  }

  /** The survey on the map, framed to its own sheets — `/explore`'s `?series=` deeplink. */
  function seriesMapHref(entry: FeaturedSeries['entry']): string {
    const c = cellCamera(entry.bounds);
    return (
      `/explore?series=${encodeURIComponent(entry.key)}` +
      `#@${c.lat.toFixed(4)},${c.lng.toFixed(4)},${c.zoom}z,0r`
    );
  }

  /* Most sheets carry no `dc_description` yet. The share page (/catalog/[id])
     synthesises the same one-liner rather than showing a hole; matching it keeps
     one sentence for one map across the site. */
  $: blurb = selected
    ? (firstParagraph(selected.dc_description) ??
      `${selected.name} — a historical map of ${selected.location ?? 'Vietnam'} in the Vietnam Map Archive.`)
    : '';

  /* The front page wants the intro, not the whole record. A description is
     written intro-first with the source note and the caveats after a blank
     line, so the first paragraph is the intro; /catalog/[id] shows all of it. */
  function firstParagraph(text: string | undefined): string | undefined {
    return text?.split(/\n\s*\n/)[0].trim() || undefined;
  }

  /** Everything we can say about the sheet without a second query.
      `collection` is deliberately not a fallback here: every row carries
      'Vietnam Map Archive', which names us, not where the scan came from. */
  $: facts = selected
    ? [
        selected.location,
        selected.map_type?.replace(/_/g, ' '),
        selected.holding_institution,
      ].filter(Boolean)
    : [];

  /* Who to credit for the scan. Thirteen published rows carry a `source_url`
     with no `holding_institution`, so the host stands in — 'gallica.bnf.fr'
     says where you are going, and cannot go stale the way a lookup table can. */
  function sourceLabel(m: MapListItem): string {
    if (m.holding_institution) return m.holding_institution;
    try {
      return new URL(m.source_url ?? '').hostname.replace(/^www\./, '');
    } catch {
      return 'the holding institution';
    }
  }
</script>

{#if current}
  <div class="fs">
    <div class="fs-main">
      <figure class="fs-plate">
        {#key current.id}
          {#if largeSrc(current.small)}
            <img
              src={largeSrc(current.small)}
              alt={current.name}
              on:error={(e) => fallbackToSmall(e, current?.small)}
            />
          {:else}
            <figcaption class="empty-state">No scan preview for this sheet yet.</figcaption>
          {/if}
        {/key}
      </figure>

      <div class="fs-brief">
        {#if selectedSeries}
          {@const entry = selectedSeries.entry}
          <div class="fs-heading">
            <span class="fs-year">Survey</span>
            <h3 class="fs-name">{entry.name}</h3>
          </div>

          <!-- "N of N" when the index is only what we hold says nothing: see
               `hasDenominator`. -->
          <p class="fs-facts">
            {#if hasDenominator(entry.index)}
              {entry.index.held} of {entry.index.total} sheets held
            {:else}
              {entry.index.held} sheets held
            {/if}
          </p>

          <p class="fs-desc">
            A survey rather than a single sheet: its sheets are drawn together on the map, and the
            coverage page shows where they sit and which are held. The picture is one sheet from it.
          </p>

          <div class="fs-actions">
            <a class="chip is-primary" href={seriesMapHref(entry)}>Open on the map</a>
            <a class="chip" href="/catalog/series/{encodeURIComponent(entry.key)}">Coverage</a>
          </div>
        {:else if selected}
          <div class="fs-heading">
            {#if selected.year}
              <span class="fs-year">{selected.year}</span>
            {/if}
            <h3 class="fs-name">{selected.name}</h3>
          </div>

          {#if facts.length}
            <p class="fs-facts">{facts.join(' · ')}</p>
          {/if}

          <p class="fs-desc" class:fs-desc-stand-in={!selected.dc_description}>{blurb}</p>

          <div class="fs-actions">
            <a class="chip is-primary" href={exploreHref(selected)}>Open in the viewer</a>
            <a class="chip" href={mapHref(selected)}>Record</a>
            {#if selected.source_url}
              <a
                class="fs-source"
                href={selected.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View at {sourceLabel(selected)}<span aria-hidden="true"> ↗</span>
              </a>
            {/if}
          </div>
        {/if}
      </div>
    </div>

    <div class="fs-strip">
      {#each tiles as tile (tile.id)}
        <div class="fs-tile-wrap">
          <button
            class="fs-tile"
            class:active={tile.id === current.id}
            aria-pressed={tile.id === current.id}
            title={tile.name}
            on:click={() => (selectedId = tile.id)}
          >
            <span class="fs-plate-sm">
              {#if tileSrc(tile.small)}
                <img
                  src={tileSrc(tile.small)}
                  alt=""
                  loading="lazy"
                  on:error={(e) => fallbackToSmall(e, tile.small)}
                />
              {/if}
              <span class="fs-tile-year">{tile.stamp}</span>
            </span>
            <span class="fs-tile-name">{tile.name}</span>
          </button>
          {#if showFavorite && tile.map}
            <button
              class="fs-fav"
              class:on={favoriteIds.includes(tile.id)}
              aria-label={favoriteIds.includes(tile.id)
                ? 'Remove from favorites'
                : 'Add to favorites'}
              on:click={() => dispatch('toggleFavorite', tile.id)}
            >
              {favoriteIds.includes(tile.id) ? '\u2665' : '\u2661'}
            </button>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .fs {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .fs-main {
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(250px, 1fr);
    gap: var(--space-6);
    align-items: start;
  }

  .fs-plate {
    margin: 0;
    height: clamp(300px, 46vh, 460px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-3);
    background: var(--color-gray-100);
    /* A hairline, not the house 3px: the home page around it no longer draws
       boxes, and a thick frame on the one big image is the whole card look
       coming back through the side door. The plate still needs *an* edge —
       a scan on a near-matching ground has no boundary of its own. */
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .fs-plate img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    display: block;
  }

  .fs-brief {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .fs-heading {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    align-items: flex-start;
  }

  /* The year is stamped on the sheet, not badged beside it: `.fs-year` and
     `.fs-tile-year` are one gesture at two sizes, and the app badge's offset
     shadow would lift the stamp off the plate. */
  .fs-year {
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: var(--text-sm);
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    padding: 0.1rem 0.7rem;
  }

  .fs-name {
    font-family: var(--font-family-display);
    font-size: var(--text-xl);
    font-weight: var(--font-bold);
    line-height: 1.25;
    margin: 0;
  }

  .fs-facts {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }

  .fs-desc {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.6;
    /* A lede is one or two sentences (mig 074); six lines is the longest of the
       five with room to spare. The record page has the rest. */
    display: -webkit-box;
    -webkit-line-clamp: 6;
    line-clamp: 6;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .fs-desc-stand-in {
    color: var(--color-gray-500);
  }

  .fs-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: center;
    margin-top: auto;
  }

  .fs-source {
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
    color: var(--color-gray-500);
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .fs-source:hover {
    color: var(--color-text);
  }

  .fs-strip {
    display: flex;
    gap: var(--space-4);
    overflow-x: auto;
    /* Room for the tiles' offset shadow and the heart that sits outside them. */
    padding: var(--space-2) var(--space-2) var(--space-3);
    scroll-snap-type: x proximity;
  }

  .fs-tile-wrap {
    position: relative;
    flex: 0 0 auto;
    scroll-snap-align: start;
  }

  .fs-tile {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: 132px;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
    font-family: inherit;
    color: inherit;
    text-align: left;
  }

  /* The tile is the sheet: the scan is the thing you recognise, the year is
     stamped on it, and the name is the caption underneath. */
  .fs-plate-sm {
    position: relative;
    display: block;
    aspect-ratio: 4 / 3;
    background: var(--color-gray-100);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    overflow: hidden;
    transition:
      transform 0.15s ease,
      box-shadow 0.15s ease,
      border-color 0.15s ease;
  }

  /* `contain`, not `cover`: a cropped corner of a map sheet is unrecognisable,
     which is the one job a picker tile has. The letterbox reads as a mat. */
  .fs-plate-sm img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
    padding: 3px;
    box-sizing: border-box;
  }

  .fs-tile:hover .fs-plate-sm {
    transform: translate(-2px, -2px);
    box-shadow: var(--shadow-solid-xs);
  }

  .fs-tile.active .fs-plate-sm {
    border-color: var(--color-blue);
    border-width: 3px;
    box-shadow: var(--shadow-solid-xs);
  }

  .fs-tile:focus-visible .fs-plate-sm {
    outline: 2px solid var(--color-blue);
    outline-offset: 2px;
  }

  .fs-tile-year {
    position: absolute;
    left: var(--space-1);
    bottom: var(--space-1);
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: var(--text-xs);
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    padding: 0 0.45rem;
  }

  .fs-tile-name {
    font-size: var(--text-xs);
    line-height: 1.35;
    color: var(--color-gray-500);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .fs-tile.active .fs-tile-name {
    color: var(--color-text);
    font-weight: var(--font-semibold);
  }

  /* Not the row toggle: its `.is-on` fills the button, and a favourite here reads as
     a filled heart glyph on the same white face. */
  .fs-fav {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 24px;
    height: 24px;
    line-height: 1;
    background: var(--color-white);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    cursor: pointer;
    color: var(--color-gray-500);
    padding: 0;
  }

  .fs-fav.on {
    color: var(--color-primary);
  }

  @media (max-width: 800px) {
    .fs-main {
      grid-template-columns: 1fr;
    }
  }
</style>
