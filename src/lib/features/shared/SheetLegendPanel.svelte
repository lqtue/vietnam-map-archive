<!--
  SheetLegendPanel.svelte — the Legend tab body shared by /explore's right
  rail and Studio: fetches a sheet's numbered-legend references and lists
  them, each a fly-to. Extracted from ExploreRightSidebar (Sept 2026) so a
  second right-side tab strip does not re-fetch or re-derive this itself.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';

  /** Same zoom a label hit lands at — `LABEL_ZOOM` in explore/exploreUrl.ts,
   *  which this shared panel can't import (feature isolation). */
  const LABEL_ZOOM = 17;

  const dispatch = createEventDispatcher<{
    toggleLegendPoints: void;
    pickLocation: { lat: number; lng: number; label: string; zoom?: number };
    clearFocus: void;
  }>();

  export let mapId: string | null = null;
  export let showLegendPoints = false;
  /** The row the reader last flew to — bound by the caller so Escape can clear it. */
  export let selectedN: number | null = null;

  type LegendPoint = {
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number;
    lat: number;
    accuracy_m?: number;
  };

  let legend: LegendPoint[] = [];
  let legendFor = '';
  let legendLoading = false;

  async function loadLegend(id: string) {
    // ponytail: the same GET LegendPointsLayer makes, so a sheet with the tab
    // open fetches it twice. One small request per map — give it a store if a
    // third reader turns up.
    legendFor = id;
    legendLoading = true;
    try {
      const res = await fetch(`/api/maps/${id}/legend-points`);
      const data = res.ok ? await res.json() : null;
      if (legendFor === id) legend = (data?.points ?? []) as LegendPoint[];
    } catch {
      if (legendFor === id) legend = [];
    }
    legendLoading = false;
  }

  // `loadLegend` writes `legendFor`, which this statement reads, so it
  // re-enters once and then the guard is false — the guard is the termination
  // condition.
  $: if (mapId && mapId !== legendFor) void loadLegend(mapId);

  $: legendRows = mapId && mapId === legendFor ? legend : [];
  $: if (mapId !== legendFor) selectedN = null;

  function flyToLegend(p: LegendPoint) {
    // Tap the lit row again to put it out — the same gesture that lit it.
    if (selectedN === p.n) {
      selectedN = null;
      dispatch('clearFocus');
      return;
    }
    selectedN = p.n;
    // A legend number is a point on the sheet, so it lands at a label hit's
    // zoom rather than a Nominatim place's wider 15.
    dispatch('pickLocation', {
      lat: p.lat,
      lng: p.lng,
      label: p.name ?? `№${p.n}`,
      zoom: LABEL_ZOOM,
    });
  }
</script>

{#if !mapId}
  <p class="sb-empty">{$t('Add a map layer to read its legend.')}</p>
{:else if legendLoading}
  <p class="sb-empty">{$t('Reading the legend…')}</p>
{:else if legendRows.length === 0}
  <p class="sb-empty">{$t('This sheet has no numbered legend.')}</p>
{:else}
  <button
    type="button"
    class="sb-btn is-sm is-block"
    class:is-on={showLegendPoints}
    on:click={() => dispatch('toggleLegendPoints')}
    title={$t('Show numbered legend references on the map')}
  >
    {showLegendPoints ? 'Legend points on' : 'Show legend points'}
  </button>
  <ul class="lg-list">
    {#each legendRows as p (p.n)}
      <li>
        <button
          type="button"
          class="lg-row"
          class:is-on={selectedN === p.n}
          aria-current={selectedN === p.n ? 'true' : undefined}
          title={selectedN === p.n
            ? 'Clear this highlight'
            : p.accuracy_m
              ? `Within about ${p.accuracy_m} m`
              : 'Fly to this place'}
          on:click={() => flyToLegend(p)}
        >
          <span class="lg-n">{p.n}</span>
          <span class="lg-name">
            {p.name ?? '—'}{#if p.vn}<em> · {p.vn}</em>{/if}
          </span>
          {#if p.grid}<span class="lg-grid">{p.grid}</span>{/if}
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .lg-list {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .lg-row {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    width: 100%;
    padding: 0.25rem 0.2rem;
    background: none;
    border: 0;
    border-top: var(--sb-border);
    text-align: left;
    font-size: 0.78rem;
    color: var(--sb-text);
    cursor: pointer;
  }
  .lg-row:hover {
    background: var(--sb-row-hover);
  }
  /* Same yellow as the map's pulse ring, so the row and the spot read as one. */
  .lg-row.is-on {
    background: var(--sb-accent-yellow);
  }
  .lg-n {
    flex: 0 0 1.4rem;
    font-family: var(--sb-font-display);
    font-weight: 800;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-name {
    flex: 1;
    min-width: 0;
  }
  .lg-name em {
    font-style: normal;
    color: var(--sb-text-meta);
  }
  .lg-grid {
    flex: 0 0 auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
</style>
