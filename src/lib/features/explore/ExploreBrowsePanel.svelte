<!--
  ExploreBrowsePanel.svelte — map list for /explore, with an in-place "show
  all" expansion.

  Default view: just the maps that cover the user's location (GPS coverage),
  with a big tick-circle first cell for add/remove. "Browse the full archive →"
  swaps in ArchiveBrowser (shared catalog engine + facets). Both modes
  render the same ArchiveMapRows — tap to add, tap again to remove.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import type { ResolvedMap } from './spatialLookup';
  import type { CatalogSearchController } from '$lib/features/shared/catalogSearch';
  import ArchiveMapRows from '$lib/features/shared/ArchiveMapRows.svelte';
  import ArchiveBrowser from '$lib/features/shared/ArchiveBrowser.svelte';
  import { onMount, tick } from 'svelte';
  import { layersStore, MAX_OVERLAY_LAYERS } from '$lib/map/stores/layersStore';
  import { fetchMapSeries } from '$lib/data/maps/service';
  import type { MapSeries } from '$lib/data/maps/types';
  import { L7014_OVERLAY } from '$lib/map/constants';
  import { buildSeriesRows } from './seriesRows';
  import type { RasterSeries, SeriesRow } from './seriesRows';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { replaceState } from '$app/navigation';

  const { supabase } = getSupabaseContext();

  export let matches: ResolvedMap[] = [];
  // Admins/mods may browse draft maps in the viewer; everyone else is
  // capped to public/featured (mirrors /catalog's role gating).
  export let role: 'user' | 'mod' | 'admin' = 'user';
  // When the parent's welcome-mode is "Show all maps", force-expand so the
  // user lands on the full archive immediately. When the parent's mode is
  // location-based, leave `expanded` user-controlled — never auto-expand on
  // empty matches, since that hides the location's "no map here" status
  // after the tour ends.
  export let forceExpanded = false;
  // The desktop rail owns one filter bar above its two tabs and hands the
  // engine down; the mobile drawer has no such bar, so null leaves the browser
  // to create and render its own.
  export let search: CatalogSearchController | null = null;

  let expanded = false;

  // Parent owns the "Show all maps" decision. When it flips on, expand;
  // when off, leave whatever the user chose manually.
  $: if (forceExpanded) expanded = true;

  // Oldest → newest, matching /catalog's default sort. Undated maps sink
  // to the bottom; ties break by name so the order is stable.
  function byYear(
    a: { year?: number | null; name?: string },
    b: { year?: number | null; name?: string }
  ): number {
    const ay = a.year ?? Infinity;
    const by = b.year ?? Infinity;
    if (ay !== by) return ay - by;
    return (a.name ?? '').localeCompare(b.name ?? '');
  }

  // Default view: maps covering the user's GPS spot. `matches` comes from the
  // RLS-readable map list (which leaks drafts), so role-gate it here too.
  $: canSeeDrafts = role === 'admin' || role === 'mod';
  $: visibleMatches = [...matches]
    .filter((m) => canSeeDrafts || m.status === 'public' || m.status === 'featured')
    .sort(byYear);

  // Sheet series — a whole survey as one layer. They sit above the sheet rows
  // rather than among them because they are not catalogue entries: no record
  // page, no year to sort by, no single scan behind them. Same gesture though
  // — tap to put it on the map, tap again to take it off.
  //
  // The rows themselves are built in `seriesRows.ts`: which surveys exist comes
  // from the `map_series` view (mig 082), so adding one is a matter of
  // ingesting sheets rather than editing this file, and only the L7014 raster
  // archive is hardcoded because it is the one survey that is not `maps` rows.
  /**
   * `sheets` is what the deployed archive holds, not what the survey has: 452
   * of the 627 cells in `work/l7014/index.geojson`. The rest are 93 PCL never
   * published, 62 with no usable georeference (the city sheets, which are the
   * `maps` rows `halfOf` folds in) and 11 off-grid. Read it off
   * `work/l7014/build/<build>.geojson`, whose name matches `L7014_PMTILES_URL`
   * — counting anything else is counting a survey rather than an archive.
   */
  const RASTER_SERIES: RasterSeries[] = [
    {
      ref: L7014_OVERLAY,
      name: 'AMS L7014 1:50,000',
      halfOf: 'series-l7014-vietnam-1-50-000',
      sheets: 452,
      note: '1963–89 · 1:50,000',
    },
  ];

  let dbSeries: MapSeries[] = [];
  // Nothing is offered until the view has answered. The raster archive is a
  // constant and could render at once, but it is HALF of L7014 — a tap in that
  // window would put the mosaic on the map without the city sheets that fill
  // its Saigon-shaped hole, which is the one state `toggleRow` exists to
  // prevent and which looks like a broken layer rather than a race.
  let loaded = false;
  onMount(async () => {
    // The view carries the visibility gate, so an unpublished series simply is
    // not in the answer for a reader who may not see it. There is no `draft`
    // flag here on purpose — that was one more fact about the data kept in the
    // code, and it went stale the moment a sheet was published.
    dbSeries = await fetchMapSeries(supabase);
    loaded = true;
    // `visibleSeries` is a reactive statement, so it is still the empty
    // pre-`loaded` array on this line — the deeplink has to wait for the
    // recompute it just triggered.
    await tick();
    applySeriesParam();
  });

  /**
   * `?series=<key>` puts a whole survey on the map from a link — the series
   * counterpart of `?map=<id>`, and the only way to hand someone a survey,
   * since the layer stack lives in localStorage and not in the URL.
   *
   * It carries no camera of its own, and does not fit the survey's bounds
   * either: `mapStore` is created per page rather than globally, so this panel
   * cannot reach the camera without a prop or a context it has no other use
   * for. A link that wants a view appends the `#@lat,lng,zoomz` hash urlStore
   * already reads — which is what the blog links do, and what ExplorePage's
   * `hasDeeplink` now protects by not asking a reader arriving on one how they
   * would like to start. Without a hash the survey lands on the reader's last
   * camera, which for a country-sized layer means seeing one corner of it.
   * ponytail: wire the bounds fit through if a bare `?series=` is ever shared.
   *
   * The key is either half of a folded row — the database series
   * (`series-l7014-vietnam-1-50-000`, which is also its coverage page's
   * address) or the raster archive (`l7014`) — because a reader copying a key
   * out of one of those URLs should not have to know which half they took.
   *
   * Consumed once: the param is dropped from the URL after it is applied, or a
   * reload would put back the survey the reader had just taken off.
   */
  function applySeriesParam() {
    const url = new URL(window.location.href);
    const key = url.searchParams.get('series');
    if (!key) return;
    url.searchParams.delete('series');
    replaceState(url, {});
    const row = visibleSeries.find((r) => r.key === key || r.seriesKey === key);
    // Already on the stack is not a failure — the reader has it; adding the
    // refs a second time would be a duplicate layer.
    if (!row || row.refs.some((r) => seriesOn.has(r.key))) return;
    if ($layersStore.overlays.length + row.refs.length > MAX_OVERLAY_LAYERS) return;
    for (const r of row.refs) layersStore.addOverlay(r);
  }

  /**
   * A row's layers go on and come off together. Half a survey on the stack is
   * worse than none — it is the mosaic's Saigon-shaped hole with nothing in it,
   * which reads as a broken layer rather than a partial pick — so the cap is
   * checked for the whole row before anything is added.
   */
  function toggleRow(row: SeriesRow) {
    if (row.refs.some((r) => seriesOn.has(r.key))) {
      for (const r of row.refs) layersStore.removeOverlayByMapId(r.mapId);
      return;
    }
    if ($layersStore.overlays.length + row.refs.length > MAX_OVERLAY_LAYERS) return;
    for (const r of row.refs) layersStore.addOverlay(r);
  }

  $: visibleSeries = loaded ? buildSeriesRows(dbSeries, canSeeDrafts, RASTER_SERIES) : [];
  $: seriesOn = new Set(
    $layersStore.overlays
      .filter((o) => o.ref.kind !== 'historical')
      .map((o) => (o.ref as { key: string }).key)
  );
</script>

<div class="ebp" class:is-expanded={expanded}>
  <div class="head">
    <strong class="title">
      {#if expanded}{$t('Browse the archive')}{:else if matches.length}
        {matches.length === 1
          ? $t('1 map covers this spot')
          : $t('{N} maps cover this spot', { N: matches.length })}
      {:else}{$t('No archival map here')}{/if}
    </strong>
    {#if !expanded && matches.length}
      <span class="hint">{$t('Tap a row to add it as a layer · tap again to remove.')}</span>
    {/if}
  </div>

  <ul class="series">
    {#each visibleSeries as s (s.key)}
      {@const on = s.refs.some((r) => seriesOn.has(r.key))}
      <li>
        <button
          type="button"
          class="series-row"
          class:is-on={on}
          aria-pressed={on}
          on:click={() => toggleRow(s)}
        >
          <span class="series-mark" aria-hidden="true">{on ? '✓' : '+'}</span>
          <span class="series-text">
            <span class="series-name">{s.name}</span>
            <span class="series-note">{s.label} · {s.note}</span>
          </span>
        </button>
        <!-- Beside the toggle, never inside it: the row is a button that puts
             two layers on the map, and a nested anchor would be invalid markup
             and would swallow that tap. This goes to the survey's coverage
             page, which is where its unheld sheets are — the ones the map
             cannot show, because we do not have them. -->
        {#if s.seriesKey}
          <a
            class="series-info"
            href="/catalog/series/{encodeURIComponent(s.seriesKey)}"
            title={$t('All sheets in this survey')}
            aria-label="{$t('All sheets in this survey')}: {s.name}"
          >
            <span aria-hidden="true">›</span>
          </a>
        {/if}
      </li>
    {/each}
  </ul>

  {#if expanded}
    <ArchiveBrowser
      sortRows={byYear}
      {search}
      showFilters={search === null}
      on:pick
      on:remove
      on:pickLabel
    />
  {:else if visibleMatches.length}
    <ArchiveMapRows rows={visibleMatches} on:pick on:remove />
  {/if}

  <button type="button" class="browse-toggle" on:click={() => (expanded = !expanded)}>
    {#if expanded}{$t('← Back to maps at this location')}{:else}{$t(
        'Browse the full archive →'
      )}{/if}
  </button>
</div>

<style>
  .series {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .series li {
    display: flex;
    align-items: stretch;
    gap: 0.25rem;
  }
  .series-row {
    /* The toggle takes the row; the link is a fixed tab beside it. */
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    background: var(--sb-card-bg);
    border: 1px solid var(--sb-border);
    border-radius: var(--sb-radius);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    color: var(--sb-text);
  }
  .series-row:hover {
    background: var(--sb-row-hover);
  }
  .series-row.is-on {
    border-color: var(--sb-accent);
  }
  .series-mark {
    flex: none;
    width: 1.4rem;
    height: 1.4rem;
    display: grid;
    place-items: center;
    border-radius: 50%;
    border: 1px solid var(--sb-border);
    font-size: 0.8rem;
    line-height: 1;
  }
  .series-row.is-on .series-mark {
    background: var(--sb-accent);
    border-color: var(--sb-accent);
    color: var(--color-on-accent);
  }
  .series-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .series-name {
    font-size: 0.82rem;
    font-weight: 600;
  }
  .series-note {
    font-size: 0.7rem;
    color: var(--sb-text-muted);
  }
  .series-info {
    flex: none;
    width: 1.75rem;
    display: grid;
    place-items: center;
    background: var(--sb-card-bg);
    border: 1px solid var(--sb-border);
    border-radius: var(--sb-radius);
    color: var(--sb-text-muted);
    text-decoration: none;
    font-size: 0.9rem;
    line-height: 1;
  }
  .series-info:hover {
    background: var(--sb-row-hover);
    color: var(--sb-text);
  }

  .ebp {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.6rem 0.7rem 0.8rem;
    font-family: var(--sb-font-base);
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .title {
    font-family: var(--sb-font-display);
    font-size: var(--text-base);
    font-weight: var(--font-extrabold);
  }
  .hint {
    color: var(--sb-text-meta);
    font-size: 0.78rem;
  }

  .browse-toggle {
    align-self: flex-start;
    margin-top: 0.3rem;
    padding: 0.45rem 0.7rem;
    background: transparent;
    border: none;
    color: var(--sb-accent);
    text-decoration: none;
    font-family: inherit;
    font-size: 0.84rem;
    font-weight: var(--font-bold);
    cursor: pointer;
    border-bottom: 1.5px dashed var(--sb-accent);
  }
  .browse-toggle:hover {
    color: var(--sb-accent-dark);
  }
</style>
