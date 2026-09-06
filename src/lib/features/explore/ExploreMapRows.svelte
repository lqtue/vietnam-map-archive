<!--
  ExploreMapRows.svelte — the tap-to-toggle map row list shared by both
  /explore browse modes (GPS coverage and the full archive browser).

  Rows behave identically in both: tap to add as a layer, tap again to remove.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { layersStore } from '$lib/map/stores/layersStore';

  export let rows: any[] = [];

  const dispatch = createEventDispatcher<{
    pick: { map: any };
    remove: { mapId: string };
  }>();

  $: stackedIds = new Set($layersStore.overlays.map((o) => o.ref.mapId));

  // Stable colour per map_type so the type chip is scannable. Hashes the
  // string to a hue (golden-angle stepped to keep adjacent types distinct).
  function hueFor(t: string | undefined): number {
    if (!t) return 50;
    let h = 0;
    for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0;
    return Math.abs(h * 137) % 360;
  }
  function typeStyle(t: string | undefined): string {
    if (!t) return '';
    const h = hueFor(t);
    return `background: hsl(${h} 70% 88%); border-color: hsl(${h} 45% 30%); color: hsl(${h} 50% 22%);`;
  }

  function onRowClick(map: any) {
    if (stackedIds.has(map.id)) dispatch('remove', { mapId: map.id });
    else dispatch('pick', { map });
  }
</script>

<ul class="rows">
  {#each rows as m (m.id)}
    {@const on = stackedIds.has(m.id)}
    <li>
      <button type="button" class="row" class:is-on={on} on:click={() => onRowClick(m)}>
        <span class="tick" aria-hidden="true" class:on>
          {#if on}
            <svg
              viewBox="0 0 24 24"
              width="22"
              height="22"
              fill="none"
              stroke="currentColor"
              stroke-width="3.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M5 12.5l5 5L20 7" />
            </svg>
          {:else}
            <svg
              viewBox="0 0 24 24"
              width="22"
              height="22"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
          {/if}
        </span>
        <span class="year-cell">{m.year ?? '—'}</span>
        <span class="name">{m.name}</span>
        <span class="type-cell">
          {#if m.map_type}
            <span class="type-chip" style={typeStyle(m.map_type)}>{m.map_type}</span>
          {/if}
        </span>
      </button>
    </li>
  {/each}
</ul>

<style>
  .rows {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }
  .row {
    display: grid;
    grid-template-columns: 32px 3rem 1fr auto;
    align-items: center;
    gap: var(--s-2);
    width: 100%;
    min-height: 52px;
    text-align: left;
    padding: 0.55rem;
    background: var(--sb-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    font-family: inherit;
    cursor: pointer;
  }
  .row:active {
    background: var(--sb-row-active);
  }
  .row.is-on {
    background: var(--sb-success-bg);
  }

  .tick {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--sb-text);
    flex-shrink: 0;
  }
  .tick.on {
    background: var(--sb-success);
    color: var(--ground-raised);
    border-color: var(--sb-success-dark);
  }

  .year-cell {
    font-size: 0.82rem;
    font-weight: var(--w-semi);
    color: var(--sb-accent);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  .name {
    font-size: 0.85rem;
    line-height: 1.3;
    color: var(--sb-text);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-width: 0;
  }
  .type-cell {
    display: flex;
    justify-content: flex-end;
    min-width: 0;
  }
  .type-chip {
    padding: 0.15rem var(--s-2);
    background: var(--sb-accent-yellow);
    border: var(--sb-border);
    border-radius: var(--sb-radius-pill);
    font-size: 0.7rem;
    font-weight: var(--w-semi);
    text-transform: capitalize;
    white-space: nowrap;
  }
</style>
