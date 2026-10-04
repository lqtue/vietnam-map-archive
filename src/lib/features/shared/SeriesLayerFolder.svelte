<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import type { SeriesRef } from '$lib/map/stores/layersStore';
  import type { MapListItem } from '$lib/data/maps/types';
  import { fetchSeriesSheetIndex, type SeriesSheetView } from '$lib/data/maps/seriesSheets';
  import { fetchSeriesSheets, fetchMapsByIds } from '$lib/data/maps/service';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import LayerActionsMenu from './LayerActionsMenu.svelte';
  export let ref: SeriesRef;
  export let mapList: MapListItem[] = [];
  export let filterIds: string[] | null = null;
  const dispatch = createEventDispatcher<{
    zoomToOverlay: { mapId: string; bounds?: [number, number, number, number] };
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
  }>();
  const { supabase } = getSupabaseContext();
  let cells: SeriesSheetView[] = [];
  let extraMaps: MapListItem[] = [];
  let sourceIds: Set<string> | null = null;
  let loading = false;
  let loaded = false;
  let error = '';
  let destroyed = false;
  onDestroy(() => {
    destroyed = true;
  });
  $: allMaps = [...new Map([...mapList, ...extraMaps].map((map) => [map.id, map])).values()];
  $: sheets = allMaps
    .filter((map) =>
      sourceIds
        ? sourceIds.has(map.id)
        : ref.parts.some((part) =>
            map.series_key
              ? map.series_key === (part.seriesKey ?? ref.key)
              : map.collection === part.collection
          )
    )
    .filter((map) => !filterIds || filterIds.includes(map.id));
  $: displayedIds = new Set(sheets.map((sheet) => sheet.id));
  $: missingCells = cells.filter(
    (cell) => (!cell.map_id || !displayedIds.has(cell.map_id)) && !filterIds
  );
  async function loadCells(event: Event) {
    if (!(event.currentTarget as HTMLDetailsElement).open || loaded || loading) return;
    loading = true;
    error = '';
    try {
      const [results, sources] = await Promise.all([
        Promise.all(
          ref.parts.map((part) => fetchSeriesSheetIndex(supabase, part.seriesKey ?? ref.key))
        ),
        Promise.all(
          ref.parts.map((part) =>
            fetchSeriesSheets(supabase, part.seriesKey ?? ref.key, part.collection)
          )
        ),
      ]);
      const ids = [...new Set(sources.flat().map((sheet) => sheet.id))];
      const missingIds = ids.filter((id) => !mapList.some((map) => map.id === id));
      const fetched: MapListItem[] = [];
      for (let start = 0; start < missingIds.length; start += 100) {
        fetched.push(...(await fetchMapsByIds(supabase, missingIds.slice(start, start + 100))));
      }
      if (!destroyed) {
        extraMaps = fetched;
        cells = results.flat();
        sourceIds = new Set(sources.flat().map((sheet) => sheet.id));
        loaded = true;
      }
    } catch {
      if (!destroyed) error = 'Could not load the sheet index.';
    } finally {
      if (!destroyed) loading = false;
    }
  }
</script>

<details class="series-folder" on:toggle={loadCells}>
  <summary>{sheets.length} map sheets · open folder</summary>
  {#if loading}<p class="sb-empty">Loading sheet index…</p>{/if}
  {#if error}<p class="sb-empty">{error}</p>{/if}
  <ul>
    {#each sheets as sheet (sheet.id)}
      <li>
        <span class="sheet-name">{sheet.name}{sheet.year ? ` · ${sheet.year}` : ''}</span>
        <LayerActionsMenu
          name={sheet.name}
          on:zoom={() =>
            dispatch('zoomToOverlay', { mapId: sheet.id, bounds: sheet.bounds ?? sheet.bbox })}
          on:info={() => dispatch('inspectMap', { mapId: sheet.id, tab: 'info' })}
          on:legend={() => dispatch('inspectMap', { mapId: sheet.id, tab: 'legend' })}
        />
      </li>
    {/each}
    {#each missingCells as cell (`${cell.series_key}:${cell.sheet_number}`)}
      <li>
        <span class="sheet-name">{cell.sheet_number} {cell.name ?? ''}</span><span
          class="unavailable"
          >{cell.map_id
            ? 'Not displayed on map'
            : cell.status === 'obtainable'
              ? 'Scan available elsewhere'
              : 'No served scan'}</span
        >
      </li>
    {/each}
  </ul>
  {#if loaded && !sheets.length && !missingCells.length}<p class="sb-empty">
      No sheets found.
    </p>{/if}
</details>

<style>
  .series-folder {
    font-size: 0.75rem;
    margin-top: 0.35rem;
  }
  summary {
    cursor: pointer;
    color: var(--sb-text-meta);
  }
  ul {
    margin: 0.35rem 0 0;
    padding: 0 0 0 0.5rem;
    list-style: none;
    border-left: 1px solid var(--rule);
  }
  li {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0;
  }
  .sheet-name {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .unavailable {
    color: var(--sb-text-muted);
    font-size: 0.65rem;
  }
</style>
