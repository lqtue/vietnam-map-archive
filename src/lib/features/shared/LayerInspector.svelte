<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { SeriesRef } from '$lib/map/stores/layersStore';
  import { fetchMapsByIds, fetchSeriesSheets } from '$lib/data/maps/service';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import SheetInfoPanel from './SheetInfoPanel.svelte';
  import SheetLegendPanel from './SheetLegendPanel.svelte';
  export let mapId: string | null = null;
  export let series: SeriesRef | null = null;
  export let tab: 'info' | 'legend' = 'info';
  export let mapList: MapListItem[] = [];
  const { supabase } = getSupabaseContext();
  let maps: MapListItem[] = [];
  let selectedId = mapId ?? '';
  let loading = true;
  let error = '';
  let destroyed = false;
  onDestroy(() => {
    destroyed = true;
  });
  onMount(async () => {
    try {
      const sources = series
        ? (
            await Promise.all(
              series.parts.map((part) =>
                fetchSeriesSheets(supabase, part.seriesKey ?? series!.key, part.collection)
              )
            )
          ).flat()
        : [];
      const ids = mapId ? [mapId] : [...new Set(sources.map((source) => source.id))];
      const known = mapList.filter((map) => ids.includes(map.id));
      const missing = ids.filter((id) => !known.some((map) => map.id === id));
      const fetched: MapListItem[] = [];
      for (let start = 0; start < missing.length; start += 100)
        fetched.push(...(await fetchMapsByIds(supabase, missing.slice(start, start + 100))));
      if (!destroyed) {
        maps = [...known, ...fetched];
        selectedId = mapId ?? maps[0]?.id ?? '';
      }
    } catch {
      if (!destroyed) error = 'Could not load layer details.';
    } finally {
      if (!destroyed) loading = false;
    }
  });
  $: selectedMap = maps.find((map) => map.id === selectedId) ?? null;
</script>

<section class="layer-inspector" aria-label="Layer details">
  {#if series}
    <h3>{series.name}</h3>
    <p>{maps.length} map sheets. Choose a sheet to display its {tab}.</p>
    <label
      >Sheet <select bind:value={selectedId}
        ><option value="">Choose a sheet</option>{#each maps as map (map.id)}<option value={map.id}
            >{map.name}{map.year ? ` · ${map.year}` : ''}</option
          >{/each}</select
      ></label
    >
  {/if}
  {#if loading}<p class="sb-empty">Loading layer details…</p>
  {:else if error}<p class="sb-empty">{error}</p>
  {:else if tab === 'info'}<SheetInfoPanel
      mapId={selectedId || null}
      map={selectedMap}
      showVectorAction={false}
    />
  {:else}<SheetLegendPanel mapId={selectedId || null} mapActions={false} />{/if}
</section>

<style>
  .layer-inspector {
    padding: 0.6rem;
    margin-top: 0.5rem;
    border-top: 1px solid var(--rule);
  }
  h3 {
    margin: 0;
    font-size: 0.9rem;
  }
  p,
  label {
    font-size: 0.75rem;
  }
  select {
    width: 100%;
    margin: 0.35rem 0;
  }
</style>
