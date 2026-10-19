<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import type { SeriesRef } from '$lib/map/stores/layersStore';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { Selected } from './catalogFilters';
  import { fetchSeriesSheetPage, type SeriesSheetView } from '$lib/data/maps/seriesSheets';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import LayerActionsMenu from './LayerActionsMenu.svelte';
  import { resolveSeriesKeys } from '$lib/data/maps/seriesKeys';
  export let ref: SeriesRef;
  export let mapList: MapListItem[] = [];
  export let filterIds: string[] | null = null;
  export let searchQuery = '';
  export let searchFilters: Selected | null = null;
  export let matchingCount: number | null = null;
  const dispatch = createEventDispatcher<{
    zoomToOverlay: { mapId: string; bounds?: [number, number, number, number] };
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
  }>();
  const { supabase } = getSupabaseContext();
  const pageSize = 60;
  let sheets: MapListItem[] = [];
  let cells: SeriesSheetView[] = [];
  let mapCursors: (string | null)[] = [null];
  let cellCursors: (string | null)[] = [null];
  let page = 0;
  let indexPage = 0;
  let part = 0;
  let nextMap: string | null = null;
  let nextCell: string | null = null;
  let count: number | null = null;
  let resolvedKeys: string[][] | null = null;
  let loading = false;
  let loaded = false;
  let error = '';
  let destroyed = false;
  const abort = new AbortController();
  onDestroy(() => {
    destroyed = true;
    abort.abort();
  });
  $: filtered = searchFilters !== null || filterIds !== null;
  $: summaryCount = count ?? matchingCount;
  async function load(event?: Event) {
    if (event && (!(event.currentTarget as HTMLDetailsElement).open || loaded)) return;
    if (loading) return;
    loading = true;
    error = '';
    try {
      if (!resolvedKeys) {
        resolvedKeys = await resolveSeriesKeys(supabase, ref);
        if (destroyed) return;
      }
      if (filterIds !== null && searchFilters === null) {
        const allowed = new Set(filterIds);
        const local = mapList.filter(
          (map) =>
            allowed.has(map.id) &&
            ref.parts.some((p) =>
              map.series_key
                ? map.series_key === (p.seriesKey ?? ref.key)
                : map.collection === p.collection
            )
        );
        sheets = local.slice(page * pageSize, (page + 1) * pageSize);
        count = local.length;
        nextMap = (page + 1) * pageSize < local.length ? 'local' : null;
      } else {
        const keys = [...new Set(resolvedKeys.flat())];
        const selectedKeys = searchFilters?.series_key;
        const seriesKeys = selectedKeys?.length
          ? keys.filter((key) => selectedKeys.includes(key))
          : keys;
        const params = new URLSearchParams({
          q: searchQuery,
          filters: JSON.stringify({ ...searchFilters, series_key: seriesKeys }),
          limit: String(pageSize),
          sources: '1',
        });
        if (mapCursors[page]) params.set('cursor', mapCursors[page]!);
        if (!seriesKeys.length) {
          sheets = [];
          count = 0;
          nextMap = null;
        } else {
          const response = await fetch(`/api/explore/maps?${params}`, { signal: abort.signal });
          if (!response.ok) throw new Error('Sheet page failed');
          const result = await response.json();
          if (destroyed) return;
          sheets = result.maps;
          count = result.total.maps;
          nextMap = result.nextCursor;
        }
      }
      if (!filtered) {
        const result = await fetchSeriesSheetPage(
          supabase,
          resolvedKeys[part]?.[0] ?? ref.parts[part]?.seriesKey ?? ref.key,
          cellCursors[indexPage]
        );
        if (destroyed) return;
        cells = result.sheets;
        nextCell = result.next;
      }
      loaded = true;
    } catch {
      if (!destroyed) error = 'Could not load the sheet page. Try again.';
    } finally {
      if (!destroyed) loading = false;
    }
  }
  function mapPage(direction: number) {
    if (direction > 0) mapCursors = [...mapCursors.slice(0, page + 1), nextMap];
    page += direction;
    void load();
  }
  function coveragePage(direction: number) {
    if (direction > 0) cellCursors = [...cellCursors.slice(0, indexPage + 1), nextCell];
    indexPage += direction;
    void load();
  }
  function selectPart() {
    indexPage = 0;
    cellCursors = [null];
    void load();
  }
</script>

<details class="series-folder" on:toggle={load}>
  <summary
    >{summaryCount === null ? 'Map sheets' : `${summaryCount} map sheets`} · open folder</summary
  >
  {#if loading}<p class="sb-empty" role="status">Loading sheet page…</p>{/if}
  {#if error}<p class="sb-empty">
      {error} <button type="button" class="sb-btn is-sm" on:click={() => load()}>Retry</button>
    </p>{/if}
  {#if loaded}
    <ul aria-label="Map sheets">
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
    </ul>
    {#if !sheets.length}<p class="sb-empty">No map sheets found.</p>{/if}
    {#if page > 0 || nextMap}
      <nav aria-label="Map sheet pages">
        <button
          type="button"
          class="sb-btn is-sm"
          disabled={loading || page === 0}
          on:click={() => mapPage(-1)}>Previous</button
        >
        <span>Page {page + 1}</span>
        <button
          type="button"
          class="sb-btn is-sm"
          disabled={loading || !nextMap}
          on:click={() => mapPage(1)}>Next</button
        >
      </nav>
    {/if}
    {#if !filtered}
      <p>Survey coverage index</p>
      {#if ref.parts.length > 1}
        <select
          aria-label="Survey index"
          bind:value={part}
          on:change={selectPart}
          disabled={loading}
        >
          {#each ref.parts as entry, i (entry.seriesKey ?? entry.collection)}<option value={i}
              >{entry.collection}</option
            >{/each}
        </select>
      {/if}
      <ul aria-label="Survey coverage index">
        {#each cells as cell (`${cell.series_key}:${cell.sheet_number}`)}
          <li>
            <span class="sheet-name">{cell.sheet_number} {cell.name ?? ''}</span>
            <span class="unavailable"
              >{cell.status === 'held'
                ? 'Public scan held'
                : cell.status === 'obtainable'
                  ? 'Scan available elsewhere'
                  : 'No served scan'}</span
            >
          </li>
        {/each}
      </ul>
      {#if indexPage > 0 || nextCell}
        <nav aria-label="Coverage index pages">
          <button
            type="button"
            class="sb-btn is-sm"
            disabled={loading || indexPage === 0}
            on:click={() => coveragePage(-1)}>Previous</button
          >
          <span>Page {indexPage + 1}</span>
          <button
            type="button"
            class="sb-btn is-sm"
            disabled={loading || !nextCell}
            on:click={() => coveragePage(1)}>Next</button
          >
        </nav>
      {/if}
    {/if}
  {/if}
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
