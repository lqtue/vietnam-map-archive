<!--
  StudioOverpassDialog.svelte — Modal for importing OSM features via Overpass.

  Lets the user pick a preset (or paste a custom QL body), confirms the
  current viewport bbox, and runs the query. Result conversion + DrawTool
  ingestion is done by the parent so this stays presentational.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Bbox4, OverpassPreset } from './overpass';
  import { presetLabel } from './overpass';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';

  const dispatch = createEventDispatcher<{
    close: void;
    pickOnMap: void;
    useViewport: void;
    pickBbox: { bbox: Bbox4; label: string };
    previewLocation: { features: import('geojson').FeatureCollection };
    submit: { preset: OverpassPreset; customQuery: string };
    addResult: void;
    discardResult: void;
  }>();

  export let open = false;
  export let bbox: Bbox4 | null = null;
  export let isFetching = false;
  export let error: string | null = null;
  /** Number of features in the latest preview, or null if no preview yet. */
  export let resultCount: number | null = null;

  let preset: OverpassPreset = 'buildings';
  let customQuery = 'way["historic"];';
  let locationQuery = '';

  function onPickLocation(
    e: CustomEvent<{
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
      geojson?: import('geojson').Geometry;
    }>
  ) {
    const { bbox, label, lat, lng, geojson } = e.detail;
    // Fall back to a small box around the centre if Nominatim didn't return one.
    const finalBbox: Bbox4 = bbox ? bbox : [lng - 0.01, lat - 0.01, lng + 0.01, lat + 0.01];
    dispatch('pickBbox', { bbox: finalBbox, label });

    // Queue a preview feature. Prefer the real Nominatim geometry (polygon /
    // multipolygon / line); fall back to a bbox rectangle or a point.
    // Literal on purpose: `color` is annotation *data* the user can then edit,
    // and it ends up in an OL style, which cannot read a CSS custom property.
    const props = { label, color: '#d97706', hidden: false, source: 'nominatim' };
    let geometry: import('geojson').Geometry;
    if (geojson) {
      geometry = geojson;
    } else if (bbox) {
      geometry = {
        type: 'Polygon',
        coordinates: [
          [
            [finalBbox[0], finalBbox[1]],
            [finalBbox[2], finalBbox[1]],
            [finalBbox[2], finalBbox[3]],
            [finalBbox[0], finalBbox[3]],
            [finalBbox[0], finalBbox[1]],
          ],
        ],
      };
    } else {
      geometry = { type: 'Point', coordinates: [lng, lat] };
    }
    const feature: import('geojson').Feature = { type: 'Feature', geometry, properties: props };
    dispatch('previewLocation', {
      features: { type: 'FeatureCollection', features: [feature] },
    });
    locationQuery = '';
  }

  const PRESETS: OverpassPreset[] = [
    'buildings',
    'roads',
    'waterways',
    'parks',
    'railways',
    'amenities',
    'custom',
  ];

  $: bboxText = bbox
    ? `${bbox[1].toFixed(4)}, ${bbox[0].toFixed(4)} → ${bbox[3].toFixed(4)}, ${bbox[2].toFixed(4)}`
    : 'No map view yet';
  $: canSubmit = !!bbox && !isFetching && (preset !== 'custom' || customQuery.trim().length > 0);

  function submit() {
    if (!canSubmit) return;
    dispatch('submit', { preset, customQuery });
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && !isFetching) dispatch('close');
  }
</script>

{#if open}
  <div class="backdrop" on:click={() => !isFetching && dispatch('close')} role="presentation"></div>
  <div
    class="dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="overpass-title"
    tabindex="-1"
    on:keydown={onKey}
  >
    <header class="head">
      <h3 id="overpass-title">Import from OpenStreetMap</h3>
      <button
        type="button"
        class="sb-btn is-sm is-ghost"
        on:click={() => dispatch('close')}
        disabled={isFetching}
        aria-label="Close">×</button
      >
    </header>

    <div class="body">
      <label class="field">
        <span class="field-label">Layer</span>
        <select bind:value={preset} disabled={isFetching}>
          {#each PRESETS as p}
            <option value={p}>{presetLabel(p)}</option>
          {/each}
        </select>
      </label>

      {#if preset === 'custom'}
        <label class="field">
          <span class="field-label">Overpass QL (statement body only)</span>
          <textarea
            rows="4"
            bind:value={customQuery}
            placeholder={'way["historic"];'}
            disabled={isFetching}></textarea>
          <span class="field-hint">
            Bbox is applied globally — write only the filter statements.
          </span>
        </label>
      {/if}

      <div class="bbox">
        <span class="field-label">Bbox (S, W → N, E)</span>
        <code>{bboxText}</code>
        <div class="bbox-actions">
          <button
            type="button"
            class="sb-btn is-sm"
            on:click={() => dispatch('pickOnMap')}
            disabled={isFetching}
          >
            📐 Draw on map
          </button>
          <button
            type="button"
            class="sb-btn is-sm is-ghost"
            on:click={() => dispatch('useViewport')}
            disabled={isFetching}
          >
            Use viewport
          </button>
        </div>
      </div>

      <div class="field">
        <span class="field-label">Or search a place</span>
        <input
          type="search"
          bind:value={locationQuery}
          placeholder="e.g. District 1, Hue, Cholon…"
          disabled={isFetching}
        />
        <LocationSearch query={locationQuery} on:pickLocation={onPickLocation} />
      </div>

      {#if error}
        <p class="error">{error}</p>
      {/if}
    </div>

    <footer class="foot">
      {#if resultCount !== null && resultCount > 0}
        <span class="result-summary">
          Preview on map: <strong>{resultCount}</strong> feature{resultCount === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          class="sb-btn"
          on:click={() => dispatch('discardResult')}
          disabled={isFetching}>Discard</button
        >
        <button
          type="button"
          class="sb-btn is-primary"
          on:click={() => dispatch('addResult')}
          disabled={isFetching}
        >
          + Add to project
        </button>
      {:else}
        <button
          type="button"
          class="sb-btn"
          on:click={() => dispatch('close')}
          disabled={isFetching}>Cancel</button
        >
        <button type="button" class="sb-btn is-primary" on:click={submit} disabled={!canSubmit}>
          {isFetching ? 'Fetching…' : 'Search'}
        </button>
      {/if}
    </footer>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: var(--scrim);
    z-index: 200;
  }
  .dialog {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(520px, 92vw);
    max-height: 86vh;
    display: flex;
    flex-direction: column;
    background: var(--sb-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-lg, 12px);
    z-index: 201;
    overflow: hidden;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.7rem 0.9rem;
    border-bottom: var(--sb-border);
    background: var(--sb-card-bg);
  }
  .head h3 {
    margin: 0;
    font-family: var(--sb-font-display, inherit);
    font-size: 1rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .body {
    padding: 0.9rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .field-label {
    font-family: var(--sb-font-display, inherit);
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.7;
  }
  .field-hint {
    font-size: 0.72rem;
    opacity: 0.6;
  }
  .field input[type='search'] {
    width: 100%;
    box-sizing: border-box;
    padding: 0.45rem 0.55rem;
    font-family: inherit;
    font-size: 0.85rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm, 6px);
    color: var(--sb-text);
  }
  .field input[type='search']:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--sb-accent);
  }
  .field select,
  .field textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 0.45rem 0.55rem;
    font-family: inherit;
    font-size: 0.85rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm, 6px);
    color: var(--sb-text);
  }
  .field textarea {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    resize: vertical;
  }
  .field select:focus,
  .field textarea:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--sb-accent);
  }
  .bbox {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.55rem 0.65rem;
    background: var(--sb-card-bg);
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm, 6px);
  }
  .bbox code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
  }
  .bbox-actions {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.35rem;
  }
  .error {
    margin: 0;
    padding: 0.55rem 0.7rem;
    background: var(--sb-danger-bg);
    color: var(--sb-danger);
    border: 1.5px solid var(--sb-danger);
    border-radius: var(--sb-radius-sm, 6px);
    font-size: 0.8rem;
  }
  .foot {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    justify-content: flex-end;
    padding: 0.7rem 0.9rem;
    border-top: var(--sb-border);
    background: var(--sb-card-bg);
  }
  .result-summary {
    flex: 1;
    font-size: 0.82rem;
    color: var(--sb-text);
  }
  .result-summary strong {
    font-family: var(--sb-font-display, inherit);
    font-weight: 800;
  }
</style>
