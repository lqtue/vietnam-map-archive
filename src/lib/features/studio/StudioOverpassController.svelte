<!--
  StudioOverpassController.svelte — the whole "import from OpenStreetMap" flow
  for /explore?mode=annotate, lifted out of StudioMode.

  Owns: the dialog, the bbox the query runs against (viewport / search result /
  draw-on-map), the Overpass fetch, and the preview → Add | Discard step.

  The two map layers it drives (BboxSelector, OverpassPreviewLayer) stay in
  StudioMode's `map-children` slot — they need MapShell's context — and are wired
  through the bindable `pickerActive` / `pickerBbox` / `preview` props.

  Call `open()` (via bind:this) to raise the dialog.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { toLonLat } from 'ol/proj';
  import type { FeatureCollection } from 'geojson';
  import StudioOverpassDialog from './StudioOverpassDialog.svelte';
  import {
    buildQuery,
    fetchOverpass,
    overpassToGeoJson,
    type Bbox4,
    type OverpassPreset,
  } from './overpass';

  const dispatch = createEventDispatcher<{
    notice: { text: string; tone: 'info' | 'error' | 'success' };
  }>();

  /** The OL map, used to read the current viewport and to fit search results. */
  export let shellMap: import('ol/Map').default | null = null;
  /** Commit GeoJSON into the project's annotation layer. Returns the count added. */
  export let importGeoJson: (text: string) => Promise<number | undefined> | undefined;

  /** True while the user is dragging the bbox rectangle on the map. */
  export let pickerActive = false;
  /** Live bbox from the on-map rectangle (bound to BboxSelector). */
  export let pickerBbox: Bbox4 | null = null;
  /** Fetched-but-not-yet-committed features (bound to OverpassPreviewLayer). */
  export let preview: FeatureCollection | null = null;

  let open = false;
  let bbox: Bbox4 | null = null;
  let fetching = false;
  let error: string | null = null;

  $: resultCount = preview?.features.length ?? null;

  /** Raise the dialog, defaulting the bbox to the current viewport. */
  export function openDialog() {
    error = null;
    if (!bbox) bbox = currentViewportBbox();
    open = true;
  }

  function currentViewportBbox(): Bbox4 | null {
    if (!shellMap) return null;
    const view = shellMap.getView();
    const extent = view.calculateExtent(shellMap.getSize() ?? undefined);
    // OL extent is EPSG:3857; convert to lon/lat for Overpass.
    const [w, s] = toLonLat([extent[0], extent[1]]);
    const [e, n] = toLonLat([extent[2], extent[3]]);
    return [w, s, e, n];
  }

  function useViewportBbox() {
    bbox = currentViewportBbox();
  }

  function startBboxPicker() {
    pickerBbox = bbox ?? currentViewportBbox();
    pickerActive = true;
    open = false;
  }

  function confirmBboxPicker() {
    if (pickerBbox) bbox = pickerBbox;
    pickerActive = false;
    open = true;
  }

  function cancelBboxPicker() {
    pickerActive = false;
    open = true;
  }

  async function handlePickBboxFromSearch(event: CustomEvent<{ bbox: Bbox4; label: string }>) {
    bbox = event.detail.bbox;
    // Pan/zoom so the chosen area is on-screen — useful before tweaking via Draw on map.
    if (shellMap) {
      const { fromLonLat } = await import('ol/proj');
      const [w, s] = fromLonLat([bbox[0], bbox[1]]);
      const [e, n] = fromLonLat([bbox[2], bbox[3]]);
      shellMap.getView().fit([w, s, e, n], { duration: 400, padding: [40, 40, 40, 40] });
    }
  }

  async function runImport(event: CustomEvent<{ preset: OverpassPreset; customQuery: string }>) {
    if (!bbox) return;
    fetching = true;
    error = null;
    try {
      const query = buildQuery({
        preset: event.detail.preset,
        customQuery: event.detail.customQuery,
        bbox,
      });
      const data = await fetchOverpass(query);
      const geojson = overpassToGeoJson(data);
      if (geojson.features.length === 0) {
        error = 'No features returned for this area + query.';
        fetching = false;
        return;
      }
      // Show as a preview on the map; the Add button commits.
      preview = geojson;
    } catch (e) {
      console.error('Overpass import failed', e);
      error = e instanceof Error ? e.message : String(e);
    } finally {
      fetching = false;
    }
  }

  async function addResult() {
    if (!preview) return;
    const count = await importGeoJson?.(JSON.stringify(preview));
    dispatch('notice', {
      text: `Added ${count ?? 0} OSM feature${(count ?? 0) !== 1 ? 's' : ''}.`,
      tone: 'success',
    });
    preview = null;
    open = false;
  }

  function discardResult() {
    preview = null;
  }
</script>

{#if pickerActive}
  <div class="bbox-picker-bar">
    <span class="bbox-picker-label">Drag the rectangle corners to resize · drag inside to move</span
    >
    <code class="bbox-picker-coords">
      {pickerBbox
        ? `${pickerBbox[1].toFixed(4)}, ${pickerBbox[0].toFixed(4)} → ${pickerBbox[3].toFixed(4)}, ${pickerBbox[2].toFixed(4)}`
        : '—'}
    </code>
    <button type="button" class="sb-btn is-sm" on:click={cancelBboxPicker}>Cancel</button>
    <button
      type="button"
      class="sb-btn is-sm is-primary"
      on:click={confirmBboxPicker}
      disabled={!pickerBbox}
    >
      Use this bbox
    </button>
  </div>
{/if}

<StudioOverpassDialog
  {open}
  {bbox}
  isFetching={fetching}
  {error}
  {resultCount}
  on:close={() => {
    if (!fetching) {
      open = false;
      preview = null;
    }
  }}
  on:pickOnMap={startBboxPicker}
  on:useViewport={useViewportBbox}
  on:pickBbox={handlePickBboxFromSearch}
  on:previewLocation={(e) => (preview = e.detail.features)}
  on:submit={runImport}
  on:addResult={addResult}
  on:discardResult={discardResult}
/>

<style>
  /* Floating bbox-picker bar (top center of map) */
  .bbox-picker-bar {
    position: absolute;
    top: calc(var(--nav-height) + 0.75rem);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.75rem;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: 10px;
    z-index: 150;
    font-size: 0.85rem;
    max-width: calc(100vw - 2rem);
  }
  .bbox-picker-label {
    font-weight: 600;
  }
  .bbox-picker-coords {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
    padding: 0.2rem 0.4rem;
    background: var(--ground);
    border-radius: 4px;
  }
</style>
