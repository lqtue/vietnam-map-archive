<!--
  LegendEntryEditor.svelte — the open row's fields in the Legend tab. Every
  change is the draft at once, and while it is open a click on the map places
  the entry's point; closing it is selecting another row (or Escape). Saving is
  the panel's "Save all".

  "Find" starts empty — a place's name changed over the years, so the reader
  searches by whichever name they know. Picking a result only moves the map
  there; the point is the reader's click on the printed number.
-->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { getShellContext } from '$lib/map/shell/context';
  import { createLegendPointPicker } from '$lib/map/shell/legendPointPicker';
  import { toLonLat } from 'ol/proj';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';
  import {
    toDraft,
    type Bbox,
    type LegendDraft,
    type LegendFind,
    type LegendPoint,
  } from './legendDrafts';

  export let entry: LegendPoint & { id: string };
  export let draft: LegendDraft | null = null;
  const dispatch = createEventDispatcher<{
    draft: LegendDraft;
    locate: { lng: number; lat: number; label: string; bbox?: Bbox };
  }>();
  const { map: mapWritable } = getShellContext();
  let name = draft?.name ?? entry.name ?? '';
  let vn = draft?.vn ?? entry.vn ?? '';
  let grid = draft?.grid ?? entry.grid ?? '';
  let lng = (draft ? draft.lng : entry.lng) ?? undefined;
  let lat = (draft ? draft.lat : entry.lat) ?? undefined;
  let coordinateOverride = draft?.coordinateOverride ?? entry.src === 'manual';
  let error = '';
  let find = '';
  /** The last Find pick, waiting for the click that places the point. */
  let lastFind: LegendFind | null = null;
  /** The search behind the point as it stands; saved with it (mig 119). */
  let pointFind: LegendFind | null = draft?.find ?? null;
  let viewbox: string | null = null;
  let places: LocationSearch;
  let activeResult: string | null = null;
  function locate(
    e: CustomEvent<{
      lng: number;
      lat: number;
      label: string;
      bbox?: Bbox;
      osm?: { type: 'node' | 'way' | 'relation'; id: number };
    }>
  ) {
    const { lng, lat, label, bbox, osm } = e.detail;
    if (find.trim())
      lastFind = {
        query: find.trim().slice(0, 500),
        osmType: osm?.type ?? null,
        osmId: osm?.id ?? null,
        osmName: label.slice(0, 1000) || null,
        lng,
        lat,
      };
    find = '';
    dispatch('locate', { lng, lat, label, bbox });
  }
  const picker = createLegendPointPicker(
    (longitude, latitude) => {
      coordinateOverride = true;
      lng = longitude;
      lat = latitude;
      pointFind = lastFind ?? pointFind;
      commit();
    },
    () => {}
  );
  function commit() {
    picker.show(lng, lat);
    const next = toDraft(entry.id, {
      name,
      vn,
      grid,
      lng,
      lat,
      coordinateOverride,
      find: pointFind,
    });
    error = typeof next === 'string' ? next : '';
    if (typeof next !== 'string') dispatch('draft', next);
  }
  function editCoordinates() {
    coordinateOverride = true;
    commit();
  }
  function resetPoint() {
    coordinateOverride = false;
    lng = undefined;
    lat = undefined;
    pointFind = null;
    commit();
  }
  let armedOn: unknown = null;
  onMount(() =>
    mapWritable.subscribe((map) => {
      picker.attach(map);
      // Rank results inside what the reader is looking at, i.e. this sheet's city.
      const extent = map?.getView().calculateExtent(map.getSize());
      if (extent)
        viewbox = [...toLonLat(extent.slice(0, 2)), ...toLonLat(extent.slice(2))].join(',');
      picker.show(lng, lat);
      // `start` toggles, and a store re-set with the same map must not disarm it.
      if (map && map !== armedOn) picker.start(true);
      armedOn = map;
    })
  );
  onDestroy(() => picker.destroy());
</script>

<div class="legend-editor">
  <label>Name <input bind:value={name} required maxlength="1000" on:input={commit} /></label>
  <label>Vietnamese name <input bind:value={vn} maxlength="1000" on:input={commit} /></label>
  <label
    >Find on the map <input
      bind:value={find}
      type="search"
      placeholder="A place name, old or new"
      aria-activedescendant={activeResult}
      on:keydown={(e) => places?.keydown(e)}
    /></label
  >
  <LocationSearch
    bind:this={places}
    bind:activeId={activeResult}
    query={find}
    coordinates={false}
    {viewbox}
    on:pickLocation={locate}
  />
  <p>
    {coordinateOverride ? 'Manual point' : 'Automatic point from the sheet reference'} · click the map
    to place it
    {#if coordinateOverride}<button type="button" class="link" on:click={resetPoint}>reset</button
      >{/if}
  </p>
  <details>
    <summary>Grid and coordinates</summary>
    <label>Grid reference <input bind:value={grid} maxlength="1000" on:input={commit} /></label>
    <div class="coordinates">
      <label
        >Longitude <input
          type="number"
          min="-180"
          max="180"
          step="any"
          bind:value={lng}
          on:input={editCoordinates}
        /></label
      >
      <label
        >Latitude <input
          type="number"
          min="-90"
          max="90"
          step="any"
          bind:value={lat}
          on:input={editCoordinates}
        /></label
      >
    </div>
  </details>
  {#if error}<p role="alert">{error}</p>{/if}
</div>

<style>
  .legend-editor {
    margin: 0.4rem 0;
  }
  label,
  p {
    font-size: 0.75rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    margin-bottom: 0.4rem;
  }
  summary {
    cursor: pointer;
    font-size: 0.75rem;
    margin-bottom: 0.4rem;
  }
  input {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }
  .coordinates {
    display: flex;
    gap: 0.4rem;
  }
  .coordinates label {
    flex: 1;
  }
  .link {
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: var(--color-blue);
    text-decoration: underline;
    cursor: pointer;
  }
</style>
