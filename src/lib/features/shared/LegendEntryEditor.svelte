<script context="module" lang="ts">
  export interface LegendDraft {
    id: string;
    name: string;
    vn: string | null;
    grid: string | null;
    lng: number | null;
    lat: number | null;
    coordinateOverride: boolean;
  }
</script>

<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';
  import { getShellContext } from '$lib/map/shell/context';
  import { createLegendPointPicker } from '$lib/map/shell/legendPointPicker';
  export let entry: {
    src?: 'manual' | 'grid' | 'numeral' | null;
    id: string;
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number | null;
    lat: number | null;
  };
  export let draft: LegendDraft | null = null;
  const dispatch = createEventDispatcher<{ close: void; draft: LegendDraft }>();
  const { map: mapWritable } = getShellContext();
  let name = draft?.name ?? entry.name ?? '';
  let vn = draft?.vn ?? entry.vn ?? '';
  let grid = draft?.grid ?? entry.grid ?? '';
  let lng = (draft ? draft.lng : entry.lng) ?? undefined;
  let lat = (draft ? draft.lat : entry.lat) ?? undefined;
  let coordinateOverride = draft?.coordinateOverride ?? entry.src === 'manual';
  let picking = false;
  let error = '';
  let destroyed = false;
  let mapReady = false;
  const picker = createLegendPointPicker(
    (longitude, latitude) => {
      coordinateOverride = true;
      lng = longitude;
      lat = latitude;
      showPoint();
    },
    (active) => (picking = active)
  );
  async function editCoordinates() {
    coordinateOverride = true;
    await tick();
    if (!destroyed) showPoint();
  }
  function showPoint() {
    picker.show(lng, lat);
  }
  function stopPicking() {
    picker.stop();
  }
  function startPicking() {
    picker.start();
  }
  function resetPoint() {
    coordinateOverride = false;
    stopPicking();
    lng = undefined;
    lat = undefined;
    showPoint();
  }
  function keepDraft() {
    stopPicking();
    error = '';
    if ([name, vn, grid].some((text) => /[;\r\n]/.test(text))) {
      error = 'Use plain text without semicolons or line breaks.';
      return;
    }
    if (!name.trim()) {
      error = 'Enter the legend name.';
      return;
    }
    if (
      (lng == null) !== (lat == null) ||
      (lng != null && (!Number.isFinite(lng) || Math.abs(lng) > 180)) ||
      (lat != null && (!Number.isFinite(lat) || Math.abs(lat) > 90))
    ) {
      error = 'Enter both longitude and latitude, or reset the point.';
      return;
    }
    dispatch('draft', {
      id: entry.id,
      name: name.trim(),
      vn: vn.trim() || null,
      grid: grid.trim() || null,
      lng: lng ?? null,
      lat: lat ?? null,
      coordinateOverride: coordinateOverride && lng != null && lat != null,
    });
  }
  onMount(() => {
    const unsubscribe = mapWritable.subscribe((map) => {
      picker.attach(map);
      mapReady = !!map;
      showPoint();
    });
    return unsubscribe;
  });
  onDestroy(() => {
    destroyed = true;
    picker.destroy();
  });
  function escape(event: KeyboardEvent) {
    if (event.key === 'Escape' && picking) {
      event.preventDefault();
      stopPicking();
    }
  }
</script>

<svelte:window on:keydown={escape} />
<form class="legend-editor" on:submit|preventDefault={keepDraft}>
  <fieldset>
    <legend>Edit legend №{entry.n}</legend>
    <label>Name <input bind:value={name} required maxlength="1000" /></label>
    <label>Vietnamese name <input bind:value={vn} maxlength="1000" /></label>
    <p>{coordinateOverride ? 'Manual point' : 'Automatic point from the sheet reference'}</p>
    <details>
      <summary>Grid and coordinates</summary>
      <label>Grid reference <input bind:value={grid} maxlength="1000" /></label>
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
    <div class="actions">
      <button
        type="button"
        class="sb-btn is-sm"
        class:is-on={picking}
        disabled={!mapReady}
        on:click={startPicking}>{picking ? 'Cancel point selection' : 'Set point on map'}</button
      ><button type="button" class="sb-btn is-sm" on:click={resetPoint}
        >Reset point to automatic</button
      >
    </div>
    {#if picking}<p role="status">
        Click the map to set this entry’s point. Escape cancels selection.
      </p>{/if}
    {#if error}<p role="alert">{error}</p>{/if}
    <div class="actions">
      <button type="submit" class="sb-btn is-sm">Keep draft</button><button
        type="button"
        class="sb-btn is-sm"
        on:click={() => dispatch('close')}>Cancel</button
      >
    </div>
  </fieldset>
</form>

<style>
  .legend-editor {
    margin: 0.4rem 0;
  }
  fieldset {
    border: var(--sb-border);
    padding: 0.5rem;
  }
  legend,
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
  details {
    margin-bottom: 0.5rem;
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
  .coordinates,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .coordinates label {
    flex: 1;
  }
</style>
