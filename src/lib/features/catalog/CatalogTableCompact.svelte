<!--
  CatalogTableCompact — the sidebar variant of CatalogTable: Year + Name rows,
  no thumbnail, no header, no grouping.

  Previously this was the same <table> as the full view with columns hidden by
  `nth-child` display:none and reordered with flex `order`. It is a different
  layout, so it is now a different component.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import { layersStore, toggleOverlayFor } from '$lib/map/stores/layersStore';

  export let items: MapListItem[] = [];
  export let activeId: string | null = null;
  /** Show the "+ overlay" toggle (only on the /explore sidebar). */
  export let showLayerActions: boolean = false;

  const dispatch = createEventDispatcher();

  $: overlayMapIds = new Set($layersStore.overlays.map((o) => o.ref.mapId));
</script>

<ul class="ctc">
  {#each items as item (item.id)}
    {@const isScout = (item as any)._table === 'scout'}
    {@const isOverlay = overlayMapIds.has(item.id)}
    <li>
      <div
        class="ctc-row"
        class:scout-row={isScout}
        class:active-row={item.id === activeId}
        role="button"
        tabindex="0"
        on:click={() => dispatch('open', item)}
        on:keydown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') dispatch('open', item);
        }}
      >
        <span class="year">{item.year ?? '—'}</span>
        <span class="body">
          <span class="title-row">
            <span class="title-link">{item.name || '—'}</span>
            {#if showLayerActions && !isScout && (item as any).georef_done}
              <button
                type="button"
                class="cmp-btn"
                class:on={isOverlay}
                on:click|stopPropagation={() => toggleOverlayFor(item)}
                title={isOverlay ? 'Remove overlay' : 'Add as overlay'}
                aria-label={isOverlay ? 'Remove overlay' : 'Add as overlay'}
                >{isOverlay ? '✓' : '+'}</button
              >
            {/if}
          </span>
          {#if (item as any).creator}<span class="sub">{(item as any).creator}</span>{/if}
        </span>
      </div>
    </li>
  {/each}
</ul>

<style>
  .ctc {
    list-style: none;
    margin: 0;
    padding: 0;
    background: var(--ground-raised);
    border: 1.5px solid var(--rule);
    border-radius: var(--sb-radius-sm);
    font-family: var(--font-body);
    font-size: 0.85rem;
    overflow: hidden;
  }

  .ctc-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.45rem 0.55rem;
    border-bottom: 1px dashed var(--rule);
    cursor: pointer;
  }

  .ctc li:last-child .ctc-row {
    border-bottom: none;
  }

  .ctc-row:hover {
    background: var(--sb-row-hover);
  }

  .ctc-row:hover .title-link {
    text-decoration: underline;
  }

  /* Year: prominent label, not a filter chip. */
  .year {
    flex: 0 0 auto;
    min-width: 3rem;
    white-space: nowrap;
    font-size: 1rem;
    font-weight: var(--w-semi);
    color: var(--sb-accent);
    font-variant-numeric: tabular-nums;
  }

  .body {
    order: 2;
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.1rem;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
    max-width: 100%;
  }

  .title-link {
    font-size: 0.82rem;
    font-weight: var(--w-semi);
    color: var(--sb-text-meta);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    line-height: 1.25;
  }

  .sub {
    font-size: 0.68rem;
    color: var(--sb-text-muted);
  }

  .cmp-btn {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--ground-raised);
    color: var(--ink);
    border: 1.5px solid var(--rule);
    border-radius: var(--radius-pill);
    font: inherit;
    font-family: var(--font-body);
    font-size: 0.9rem;
    font-weight: var(--w-semi);
    line-height: 1;
    cursor: pointer;
    padding: 0;
  }

  .cmp-btn:hover {
    background: var(--sb-accent-yellow);
  }

  .cmp-btn.on {
    background: var(--ink);
    color: var(--ground-raised);
    font-size: 0.75rem;
  }

  .scout-row {
    background: var(--sb-scout-bg);
  }

  .active-row {
    background: var(--sb-accent-yellow);
    box-shadow: inset 3px 0 0 var(--rule);
  }

  .active-row:hover {
    background: var(--sb-accent-yellow-strong);
  }

  .active-row .title-link {
    text-decoration: underline;
  }
</style>
