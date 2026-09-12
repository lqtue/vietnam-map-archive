<!--
  LayerStackPanel.svelte — unified layer stack used by both the desktop sidebar
  and the mobile "Layers" drawer.

  Behavior:
    • Two lines per layer: name + actions on top, a native range slider for
      opacity underneath. The name is the zoom-to-overlay button. It was one
      line with the whole row as a drag surface until Sept 2026 — which cost
      every sheet its name to an ellipsis and gave the row three gestures.
    • Reorder via ▲ / ▼ buttons (works on touch and mouse).
    • Per-row eye toggles visibility (LayerRenderer honours `visible`);
      remove (×) drops the layer.
    • Display mode + Base picker live in LayerControlsPanel, not here; the
      "this sheet" action strip is TopSheetActions, in the right rail.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import { layersStore } from '$lib/map/stores/layersStore';
  import type { ViewMode } from '$lib/map/types';
  import type { MapListItem } from '$lib/data/maps/types';

  export let viewMode: ViewMode = 'overlay';
  /** Catalog list used to enrich rows with year. */
  export let mapList: MapListItem[] = [];
  /** When set, only layers for these map ids are listed — /explore's left rail
   *  passes the sheets its shared search bar still matches. Null (the default)
   *  is the whole stack. Same name and meaning as `ArchiveBrowser.filterIds`. */
  export let filterIds: string[] | null = null;

  // A raster archive has no catalogue row to look its extent up in, so it
  // carries its own bounds and hands them over with the request.
  const dispatch = createEventDispatcher<{
    zoomToOverlay: { mapId: string; bounds?: [number, number, number, number] };
  }>();

  $: state = $layersStore;
  $: isSideBySide = viewMode === 'dual';

  /** Rows carry their index in the *stack*, not in the filtered list: reorder,
   *  the disabled arrows and the Top/Bottom badges all mean stack position. */
  $: shown = filterIds ? new Set(filterIds) : null;
  $: rows = state.overlays
    .map((o, i) => ({ o, i }))
    .filter(({ o }) => !shown || shown.has(o.ref.mapId));

  $: yearByMapId = (() => {
    const m = new Map<string, number | string>();
    for (const item of mapList) if (item?.id && item.year != null) m.set(item.id, item.year as any);
    return m;
  })();

  function moveUp(i: number) {
    if (i > 0) layersStore.reorderOverlay(i, i - 1);
  }
  function moveDown(i: number) {
    if (i < state.overlays.length - 1) layersStore.reorderOverlay(i, i + 1);
  }
</script>

<div class="lsp">
  {#if state.overlays.length > 0}
    <div class="lsp-sub">{$t('Tap a name to zoom · drag for opacity · eye hides a layer')}</div>
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
        <li class="lsp-row" class:is-hidden={!o.visible}>
          <div class="lsp-reorder">
            <button
              type="button"
              class="sb-btn lsp-arrow"
              on:click={() => moveUp(i)}
              disabled={i === 0}
              aria-label="Move layer up"
              title={$t('Move up')}>▲</button
            >
            <button
              type="button"
              class="sb-btn lsp-arrow"
              on:click={() => moveDown(i)}
              disabled={i === state.overlays.length - 1}
              aria-label="Move layer down"
              title={$t('Move down')}>▼</button
            >
          </div>

          <div class="lsp-body">
            <div class="lsp-top">
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
                  dispatch('zoomToOverlay', {
                    mapId: o.ref.mapId,
                    bounds: o.ref.kind === 'raster' ? o.ref.bounds : undefined,
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

              <button
                type="button"
                class="sb-btn is-icon lsp-x"
                on:click={() => layersStore.removeOverlay(o.id)}
                aria-label="Remove layer"
                title={$t('Remove')}>×</button
              >
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
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
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

  .lsp-reorder {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  /* Size only — a stacked pair has to fit the two-line row. */
  .lsp-arrow {
    width: 28px;
    height: 22px;
    padding: 0;
    font-size: 0.7rem;
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

  /* The × keeps two things the shared button will not: a 28px touch target,
     and a press that reads red, because it destroys a layer. */
  .lsp-x {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    font-size: 1.05rem;
    color: var(--sb-text-meta);
  }
  .lsp-x:active {
    background: var(--sb-danger-bg);
    color: var(--sb-danger);
  }
</style>
