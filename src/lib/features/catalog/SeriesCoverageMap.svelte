<!--
  SeriesCoverageMap.svelte — a survey's index drawn where it sits on the ground:
  one rectangle per cell, tinted by whether the archive holds it.

  Plain SVG. Under the cells, when the survey has one, goes a picture of our own
  basemap (`scripts/gen-series-coverage-bg.mjs` crops it and writes
  `coverageBackdrops.json` with the picture's extent). The picture is
  web-mercator, so the cells are projected the same way — x is longitude, y the
  mercator ordinate in the same degree-sized units — which is what puts a cell
  on the coast it belongs to. A cell's `bbox` is the one the survey's own index
  assigns, not a georeference.

  The tints are the coverage bar's — green held, yellow located elsewhere, gray
  none — so the map and the bar read as one account.
-->
<script context="module" lang="ts">
  import type { SheetStatus } from '$lib/data/maps/seriesSheets';
  import backdrops from './coverageBackdrops.json';

  export interface CoverageCell {
    bbox: number[] | null;
    status: SheetStatus;
  }

  /** Mercator ordinate of a latitude, in degrees-equivalent so x and y share a scale. */
  const merc = (lat: number) =>
    (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI;
</script>

<script lang="ts">
  export let cells: CoverageCell[] = [];
  /** Names the backdrop in `coverageBackdrops.json`; none, and the cells draw on the page. */
  export let seriesKey = '';
  export let label = 'Coverage of the survey';

  /** Unheld first, so a held cell is never hidden under its neighbour's edge. */
  const ORDER: SheetStatus[] = ['no_scan', 'obtainable', 'held'];

  $: backdrop = (backdrops as Record<string, { file: string; bbox: number[] }>)[seriesKey];
  $: placed = cells.filter((c): c is CoverageCell & { bbox: number[] } => c.bbox?.length === 4);

  /** The frame: the picture's extent, or the cells' own with a margin. */
  $: frame = backdrop
    ? backdrop.bbox
    : [
        Math.min(...placed.map((c) => c.bbox[0])),
        Math.min(...placed.map((c) => c.bbox[1])),
        Math.max(...placed.map((c) => c.bbox[2])),
        Math.max(...placed.map((c) => c.bbox[3])),
      ];
  $: x0 = frame[0];
  $: y0 = -merc(frame[3]);
  $: w = frame[2] - frame[0];
  $: h = merc(frame[3]) - merc(frame[1]);
  $: pad = backdrop ? 0 : Math.max(w, h) * 0.03;
  $: drawn = ORDER.flatMap((status) => placed.filter((c) => c.status === status));
</script>

{#if placed.length}
  <svg
    class="cov"
    class:over={backdrop}
    viewBox="{x0 - pad} {y0 - pad} {w + 2 * pad} {h + 2 * pad}"
    role="img"
    aria-label={label}
  >
    {#if backdrop}
      <image href={backdrop.file} x={x0} y={y0} width={w} height={h} preserveAspectRatio="none" />
    {/if}
    {#each drawn as c, i (i)}
      <rect
        class={c.status}
        x={c.bbox[0]}
        y={-merc(c.bbox[3])}
        width={c.bbox[2] - c.bbox[0]}
        height={merc(c.bbox[3]) - merc(c.bbox[1])}
      />
    {/each}
  </svg>
{/if}

<style>
  .cov {
    display: block;
    width: 100%;
    height: 100%;
    max-height: 100%;
  }
  rect {
    stroke: var(--color-bg);
    stroke-width: 1px;
    vector-effect: non-scaling-stroke;
  }
  /* On a picture, the cells let it show through; the stroke keeps them apart. */
  .over rect {
    fill-opacity: 0.8;
  }
  .over image {
    opacity: 0.85;
  }
  .held {
    fill: var(--color-green);
  }
  .obtainable {
    fill: var(--color-yellow);
  }
  .no_scan {
    fill: var(--color-border);
  }
</style>
