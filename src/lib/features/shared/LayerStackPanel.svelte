<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { getShellContext } from '$lib/map/shell/context';
  import { flip } from 'svelte/animate';
  import { createLayerFocus } from '$lib/map/shell/layerFocus';
  import LayerInspector from './LayerInspector.svelte';
  import LayerActionsMenu from './LayerActionsMenu.svelte';
  import SeriesLayerFolder from './SeriesLayerFolder.svelte';
  import type { SeriesRef, OverlayRef } from '$lib/map/stores/layersStore';
  import { layersStore } from '$lib/map/stores/layersStore';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';

  export let inspectionInRail = false;
  let draggedId: string | null = null;
  let announcement = '';
  let droppedId: string | null = null;
  let dropTimer: ReturnType<typeof setTimeout>;
  let inspection: {
    mapId: string | null;
    series: SeriesRef | null;
    tab: 'info' | 'legend';
  } | null = null;
  export let viewMode: ViewMode = 'overlay';
  /** Catalog list used to enrich rows with year. */
  export let mapList: MapListItem[] = [];
  /** When set, only layers for these map ids are listed — /explore's left rail
   *  passes the sheets its shared search bar still matches. Null (the default)
   *  is the whole stack. Same name and meaning as `ArchiveBrowser.filterIds`. */
  export let filterIds: string[] | null = null;

  const { map: shellMap } = getShellContext();
  const layerFocus = createLayerFocus(
    () => get(shellMap),
    () => mapList
  );
  onDestroy(() => {
    layerFocus.destroy();
    clearTimeout(dropTimer);
  });

  // A raster archive has no catalogue row to look its extent up in, so it
  // carries its own bounds and hands them over with the request.
  const dispatch = createEventDispatcher<{
    zoomToOverlay: { mapId: string; bounds?: [number, number, number, number] };
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
    inspectSeries: { ref: SeriesRef; tab: 'info' | 'legend' };
  }>();

  $: state = $layersStore;
  $: isSideBySide = viewMode === 'dual';

  // Stack indices are retained for the two pane badges.
  $: shown = filterIds ? new Set(filterIds) : null;
  function matchesFilter(ref: OverlayRef, matchingIds: Set<string> | null, maps: MapListItem[]) {
    if (!matchingIds || matchingIds.has(ref.mapId)) return true;
    if (ref.kind !== 'series') return false;
    return maps.some(
      (map) =>
        matchingIds.has(map.id) &&
        ref.parts.some((part) =>
          map.series_key
            ? map.series_key === (part.seriesKey ?? ref.key)
            : map.collection === part.collection
        )
    );
  }
  $: rows = state.overlays
    .map((o, i) => ({ o, i }))
    .filter(({ o }) => matchesFilter(o.ref, shown, mapList));

  $: yearByMapId = (() => {
    const m = new Map<string, number | string>();
    for (const item of mapList) if (item?.id && item.year != null) m.set(item.id, item.year);
    return m;
  })();

  function moveLayer(id: string, targetId: string) {
    const from = state.overlays.findIndex((layer) => layer.id === id);
    const to = state.overlays.findIndex((layer) => layer.id === targetId);
    if (from < 0 || to < 0 || from === to) return;
    const name = state.overlays[from].ref.name ?? 'Layer';
    layersStore.reorderOverlay(from, to);
    droppedId = id;
    clearTimeout(dropTimer);
    dropTimer = setTimeout(() => {
      droppedId = null;
    }, 1000);
    announcement = `${name} moved to position ${to + 1} of ${state.overlays.length}.`;
  }
  function reorderOneStep(id: string, direction: -1 | 1) {
    const index = state.overlays.findIndex((layer) => layer.id === id);
    const target = state.overlays[index + direction];
    if (target) moveLayer(id, target.id);
  }

  function inspect(ref: OverlayRef, tab: 'info' | 'legend') {
    if (!inspectionInRail) {
      inspection = {
        mapId: ref.kind === 'historical' ? ref.mapId : null,
        series: ref.kind === 'series' ? ref : null,
        tab,
      };
      return;
    }
    if (ref.kind === 'series') dispatch('inspectSeries', { ref, tab });
    else dispatch('inspectMap', { mapId: ref.mapId, tab });
  }
</script>

<div class="lsp">
  <span class="lsp-announcement" aria-live="polite" aria-atomic="true">{announcement}</span>
  {#if state.overlays.length > 0}
    <div class="lsp-sub">
      {$t('Hold and drag the three dots to reorder · tap for layer actions')}
    </div>
  {/if}

  {#if state.overlays.length === 0}
    <div class="sb-empty">
      Nothing stacked yet. Open <strong>Browse</strong> and tap <strong>+</strong> on a map to add it.
    </div>
  {:else if rows.length === 0}
    <div class="sb-empty">{$t('No stacked map matches those filters.')}</div>
  {:else}
    <ul class="lsp-list">
      {#each rows as { o, i } (o.id)}
        <li
          class="lsp-row"
          class:is-hidden={!o.visible}
          class:is-dragging={draggedId === o.id}
          class:is-dropped={droppedId === o.id}
          animate:flip={{ duration: droppedId === o.id ? 0 : 160 }}
          data-layer-id={o.id}
        >
          <div class="lsp-body">
            <div class="lsp-top" data-layer-heading>
              {#if isSideBySide && (i === 0 || i === 1)}
                <span
                  class="badge-chip is-sm lsp-pane"
                  class:chip-blue={i === 0}
                  class:chip-orange={i === 1}>{i === 0 ? 'Top' : 'Bottom'}</span
                >
              {/if}
              {#if yearByMapId.get(o.ref.mapId) != null}
                <span class="lsp-year">{yearByMapId.get(o.ref.mapId)}</span>
              {/if}
              <button
                type="button"
                class="lsp-name"
                on:click={() =>
                  layerFocus.focus({
                    mapId: o.ref.mapId,
                    bounds: o.ref.kind === 'historical' ? undefined : o.ref.bounds,
                  })}
                title="Zoom to {o.ref.name ?? 'this layer'}"
                >{o.ref.name ?? o.ref.mapId.slice(0, 8)}</button
              >

              <button
                type="button"
                class="sb-btn is-icon lsp-eye"
                class:is-on={o.visible}
                on:click={() => layersStore.setVisible(o.id, !o.visible)}
                aria-label={o.visible ? 'Hide layer' : 'Show layer'}
                aria-pressed={o.visible}
                title={o.visible ? 'Hide this layer' : 'Show this layer'}
              >
                <!-- A real eye, not a glyph: ◉/◌ said nothing, and a tooltip
                     is no help on a touch screen. -->
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  aria-hidden="true"
                >
                  <path
                    d="M1.5 12S5.2 5.5 12 5.5 22.5 12 22.5 12 18.8 18.5 12 18.5 1.5 12 1.5 12z"
                  />
                  <circle cx="12" cy="12" r="3" />
                  {#if !o.visible}
                    <path d="M3 21 21 3" />
                  {/if}
                </svg>
              </button>

              <LayerActionsMenu
                name={o.ref.name ?? 'layer'}
                drag={{ id: o.id, onDrag: (id) => (draggedId = id), onMove: moveLayer }}
                on:reorder={(event) => reorderOneStep(o.id, event.detail.direction)}
                removable
                on:zoom={() =>
                  layerFocus.focus({
                    mapId: o.ref.mapId,
                    bounds: o.ref.kind === 'series' ? o.ref.bounds : undefined,
                  })}
                on:info={() => inspect(o.ref, 'info')}
                on:legend={() => inspect(o.ref, 'legend')}
                on:remove={() => layersStore.removeOverlay(o.id)}
              />
            </div>

            <div class="lsp-bottom">
              <input
                class="lsp-range"
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={o.opacity}
                aria-label={$t('Opacity')}
                on:input={(e) => layersStore.setOpacity(o.id, Number(e.currentTarget.value))}
              />
              <span class="lsp-pct">{Math.round(o.opacity * 100)}%</span>
            </div>
            {#if o.ref.kind === 'series'}
              <SeriesLayerFolder
                ref={o.ref}
                {mapList}
                {filterIds}
                on:zoomToOverlay={(event) => void layerFocus.focus(event.detail)}
                on:inspectMap={(event) =>
                  inspect(
                    { kind: 'historical', mapId: event.detail.mapId, allmapsId: '' },
                    event.detail.tab
                  )}
              />
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
  {#if inspection}
    <button type="button" class="sb-btn is-sm" on:click={() => (inspection = null)}
      >Close details</button
    >
    {#key `${inspection.mapId ?? inspection.series?.mapId}:${inspection.tab}`}
      <LayerInspector
        mapId={inspection.mapId}
        series={inspection.series}
        tab={inspection.tab}
        {mapList}
      />
    {/key}
  {/if}
</div>

<style>
  .lsp-announcement {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .lsp-row.is-dragging {
    visibility: hidden;
  }
  .lsp-row.is-dropped {
    outline: 2px solid var(--sb-accent);
  }

  .lsp {
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0.6rem 0.6rem;
    font-family: var(--sb-font-base);
  }
  .lsp-sub {
    font-size: 0.66rem;
    font-weight: var(--font-medium);
    color: var(--sb-text-muted);
    margin: 0 0 0.4rem;
  }
  .lsp-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .lsp-row {
    display: flex;
    align-items: stretch;
    gap: 0.5rem;
    padding: 0.5rem;
    background: var(--sb-bg);
    border: 1.5px solid var(--color-border);
    border-radius: var(--radius-sm);
  }
  /* A hidden layer keeps its name, slider and % — the row is still the
     control, so it dims rather than disappearing. */
  .lsp-row.is-hidden .lsp-body {
    opacity: 0.45;
  }

  .lsp-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .lsp-top {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
  }
  /* The zoom target is the name itself, so it is a button that looks like
     text — the row is no longer a click surface. */
  .lsp-name {
    flex: 1;
    min-width: 0;
    text-align: left;
    padding: 0;
    border: none;
    background: none;
    font: inherit;
    font-size: 0.88rem;
    font-weight: var(--font-bold);
    color: var(--sb-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: zoom-in;
  }
  .lsp-name:hover {
    color: var(--sb-accent);
  }
  .lsp-year {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    font-size: 0.82rem;
    font-weight: var(--font-extrabold);
    color: var(--sb-accent);
  }
  /* Layout only — the pane tag holds its width against a long sheet name. */
  .lsp-pane {
    flex-shrink: 0;
  }

  .lsp-bottom {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .lsp-range {
    flex: 1;
    min-width: 0;
    margin: 0;
    accent-color: var(--sb-accent);
  }
  .lsp-pct {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    font-size: 0.72rem;
    font-weight: var(--font-extrabold);
    color: var(--sb-text-meta);
    min-width: 4ch;
    text-align: right;
  }

  .lsp-eye {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
  }
</style>
