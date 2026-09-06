<!--
  ToolMapPicker.svelte — the floating map picker shared by the contribute
  IIIF-canvas tools (/scan?mode=triage, /scan?mode=trace).

  Owns the map list: loads it via fetchLabelMaps() and adapts LabelMapInfo to
  the MapListItem shape MapSearchBar expects, so callers need neither a
  loadMaps() copy nor an `as any` cast.

  Dispatches:
    loaded { maps }        — after the list arrives
    select { map }         — the LabelMapInfo the user picked
    error  { message }     — the list could not be loaded
-->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import MapSearchBar from '$lib/features/shared/search/MapSearchBar.svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchLabelMaps } from '$lib/data/supabase/footprints';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';
  import type { MapListItem } from '$lib/data/maps/types';

  /** Currently selected map id, for the search bar's active state. */
  export let selectedMapId: string | null = null;

  const dispatch = createEventDispatcher<{
    loaded: { maps: LabelMapInfo[] };
    select: { map: LabelMapInfo };
    error: { message: string };
  }>();

  const { supabase } = getSupabaseContext();

  let maps: LabelMapInfo[] = [];

  // LabelMapInfo → the MapListItem fields MapSearchBar actually reads.
  // `year`, `location` and `dc_description` are what SearchMapsTab filters and
  // badges on; leaving them out (as this did until 2026-09-04) made the
  // "Filter by title, city, or year" box silently unable to match two of the
  // three, and meant no badge ever drew.
  $: listItems = maps.map((m): MapListItem => ({
    id: m.id,
    name: m.name,
    allmaps_id: m.allmapsId,
    iiif_image: m.iiifImage,
    year: m.year,
    location: m.location,
    dc_description: m.description,
    _triaged: !!m.triage,
    _ocrd: m.hasOcr,
  }));

  function handleSelect(e: CustomEvent<{ map: MapListItem }>) {
    const picked = maps.find((m) => m.id === e.detail.map.id);
    if (picked) dispatch('select', { map: picked });
  }

  onMount(async () => {
    try {
      maps = await fetchLabelMaps(supabase);
      dispatch('loaded', { maps });
    } catch (err: any) {
      dispatch('error', { message: err?.message ?? 'Failed to load maps' });
    }
  });
</script>

<!-- showCompare={false}: the ⇄ button adds to `layersStore`, the /explore layer
     stack. These tools run on an ImageShell and have no geo map, so it was a
     dead control taking a third of every row. -->
<MapSearchBar
  maps={listItems}
  {selectedMapId}
  mapsOnly
  showCompare={false}
  on:selectMap={handleSelect}
/>
