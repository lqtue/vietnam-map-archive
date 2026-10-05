<!--
  NeatlineEditor.svelte — four-corner GCP editor for self-hosted maps.

  Viewport note: this deliberately keeps its own wheel-zoom / drag-pan over a
  single downscaled JPEG instead of using $lib/map/shell/ImageShell. ImageShell
  needs a IIIF info.json and an explicitly sized OL container; inside the modal
  body we only have the annotation's source id and a fluid height, and the
  four handles here are corner-constrained rather than free bbox handles. The
  maths lives in neatlineViewport.ts; the datum shift in neatlineDatum.ts.
-->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import '$styles/components/admin-modals.css';
  import DataTable, { type TableColumn } from '$lib/ui/DataTable.svelte';
  import { DATUM_PRESETS, shiftToWgs84 } from './neatlineDatum';
  import { clampPan, rescale, zoomAt, MIN_ZOOM, MAX_ZOOM, type Viewport } from './neatlineViewport';

  const gcpColumns = [
    { key: 'corner', label: 'Corner' },
    { key: 'px', label: 'Pixel X' },
    { key: 'py', label: 'Pixel Y' },
    { key: 'lng', label: 'Longitude' },
    { key: 'lat', label: 'Latitude' },
  ] satisfies TableColumn[];

  export let mapId: string;
  export let annotationUrl: string;

  const dispatch = createEventDispatcher<{ saved: void; error: string }>();

  // ── State ──────────────────────────────────────────────────────────────────
  let loading = true;
  let loadError = '';
  let saving = false;
  let saveMsg = '';

  let imgEl: HTMLImageElement;
  let viewportEl: HTMLDivElement; // overflow:hidden viewport

  // Native image dimensions from annotation source
  let nativeW = 0;
  let nativeH = 0;
  // Layout image dimensions (before CSS transform, after CSS width:100%)
  let dispW = 0;
  let dispH = 0;

  // GCP order: NW, NE, SE, SW
  const CORNERS = ['NW', 'NE', 'SE', 'SW'] as const;
  const CORNER_CLASS: Record<string, string> = {
    NW: 'corner-nw',
    NE: 'corner-ne',
    SE: 'corner-se',
    SW: 'corner-sw',
  };

  interface GCP {
    resourceCoords: [number, number];
    geo: [number, number];
  }

  let gcps: GCP[] = CORNERS.map(() => ({ resourceCoords: [0, 0], geo: [0, 0] }));
  let iiifSrc = '';

  // ── Zoom / Pan ─────────────────────────────────────────────────────────────
  let view: Viewport = { zoom: 1, panX: 0, panY: 0 };
  $: transform = `translate(${view.panX}px, ${view.panY}px) scale(${view.zoom})`;

  const vpWidth = () => viewportEl?.clientWidth ?? 0;
  const vpHeight = () => viewportEl?.clientHeight || dispH;

  function clamp() {
    if (!viewportEl) return;
    view = clampPan(view, vpWidth(), vpHeight(), dispW, dispH);
  }

  function stepZoom(factor: number) {
    view = { ...view, zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.zoom * factor)) };
    clamp();
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    if (!viewportEl) return;
    const rect = viewportEl.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.18 : 1 / 1.18;
    view = zoomAt(
      view,
      e.clientX - rect.left,
      e.clientY - rect.top,
      factor,
      vpWidth(),
      vpHeight(),
      dispW,
      dispH
    );
  }

  // ── Drag logic ────────────────────────────────────────────────────────────
  let dragging: number | null = null; // handle index being dragged
  let panning = false;
  let panStartX = 0;
  let panStartY = 0;

  function onViewportPointerDown(e: PointerEvent) {
    // Ignore if a handle already captured it
    if (dragging !== null) return;
    if ((e.target as Element).closest('.handle')) return;
    e.preventDefault();
    panning = true;
    panStartX = e.clientX - view.panX;
    panStartY = e.clientY - view.panY;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }

  function onHandlePointerDown(e: PointerEvent, idx: number) {
    e.preventDefault();
    e.stopPropagation();
    dragging = idx;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (panning) {
      view = { ...view, panX: e.clientX - panStartX, panY: e.clientY - panStartY };
      clamp();
      return;
    }
    if (dragging === null || !viewportEl) return;

    const rect = viewportEl.getBoundingClientRect();
    // Undo the canvas transform to get canvas-space position, clamped to the image
    const ix = (e.clientX - rect.left - view.panX) / view.zoom;
    const iy = (e.clientY - rect.top - view.panY) / view.zoom;
    gcps[dragging].resourceCoords = toNative(
      Math.max(0, Math.min(ix, dispW)),
      Math.max(0, Math.min(iy, dispH))
    );
    gcps = [...gcps];
  }

  function onPointerUp() {
    dragging = null;
    panning = false;
  }

  // ── Scale helpers ──────────────────────────────────────────────────────────
  function updateDisplaySize() {
    if (!imgEl) return;
    dispW = imgEl.clientWidth;
    dispH = imgEl.clientHeight;
  }

  const toDisp = (x: number, y: number) => rescale(x, y, nativeW, nativeH, dispW, dispH);

  function toNative(dx: number, dy: number): [number, number] {
    const [x, y] = rescale(dx, dy, dispW, dispH, nativeW, nativeH);
    return [Math.round(x), Math.round(y)];
  }

  // ── Input handlers ────────────────────────────────────────────────────────
  function handlePixelInput(idx: number, axis: 0 | 1, val: string) {
    const n = parseFloat(val);
    if (!isNaN(n)) {
      gcps[idx].resourceCoords[axis] = Math.round(n);
      gcps = [...gcps];
    }
  }

  function handleGeoInput(idx: number, axis: 0 | 1, val: string) {
    const n = parseFloat(val);
    if (!isNaN(n)) {
      gcps[idx].geo[axis] = n;
      gcps = [...gcps];
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────
  onMount(async () => {
    try {
      const bustUrl =
        annotationUrl + (annotationUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
      const res = await fetch(bustUrl, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const annotation = await res.json();

      const item = annotation.items?.[0];
      if (!item) throw new Error('No annotation items');

      const target = item.target;
      const source = typeof target === 'string' ? { id: target } : (target.source ?? target);
      const sourceId = typeof source === 'string' ? source : source.id;
      nativeW = source.width ?? 0;
      nativeH = source.height ?? 0;

      iiifSrc = `${sourceId}/full/,900/0/default.jpg`;

      const features: any[] = item.body?.features ?? [];
      if (features.length >= 4) {
        gcps = features.slice(0, 4).map((f: any) => ({
          resourceCoords: f.properties?.resourceCoords ?? [0, 0],
          geo: f.geometry?.coordinates ?? [0, 0],
        }));
      }
    } catch (e: any) {
      loadError = e.message;
    } finally {
      loading = false;
    }
  });

  // ── Datum correction ──────────────────────────────────────────────────────
  let selectedDatumIdx = 0;
  let datumApplied = false;

  function applyDatumCorrection() {
    const preset = DATUM_PRESETS[selectedDatumIdx];
    gcps = gcps.map((g) => ({ ...g, geo: shiftToWgs84(g.geo, preset) }));
    datumApplied = true;
  }

  // ── Save ──────────────────────────────────────────────────────────────────
  async function handleSave() {
    saving = true;
    saveMsg = '';
    try {
      const res = await fetch(`/api/admin/maps/${mapId}/annotation`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gcps }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        let msg = text;
        try {
          msg = JSON.parse(text).message ?? text;
        } catch {
          /* not JSON — use the raw body */
        }
        throw new Error(`${res.status}: ${msg}`);
      }
      saveMsg = 'Saved!';
      setTimeout(() => (saveMsg = ''), 3000);
      dispatch('saved');
    } catch (e: any) {
      saveMsg = `Error: ${e.message}`;
    } finally {
      saving = false;
    }
  }
</script>

<div class="neatline-editor">
  {#if loading}
    <p class="status-msg">Loading annotation…</p>
  {:else if loadError}
    <p class="status-msg error">Failed to load: {loadError}</p>
  {:else}
    <!-- Zoom toolbar -->
    <div class="zoom-bar">
      <button class="zoom-btn" on:click={() => stepZoom(1.5)} title="Zoom in">＋</button>
      <span class="zoom-label">{Math.round(view.zoom * 100)}%</span>
      <button class="zoom-btn" on:click={() => stepZoom(1 / 1.5)} title="Zoom out">－</button>
      <button
        class="zoom-btn reset"
        on:click={() => (view = { zoom: 1, panX: 0, panY: 0 })}
        title="Reset zoom">↺ Reset</button
      >
      <span class="zoom-hint">Scroll to zoom · Drag background to pan</span>
    </div>

    <!-- Viewport (clips the zoomed canvas) -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="viewport"
      class:is-panning={panning}
      class:is-zoomed={view.zoom > 1}
      bind:this={viewportEl}
      on:wheel={onWheel}
      on:pointerdown={onViewportPointerDown}
      on:pointermove={onPointerMove}
      on:pointerup={onPointerUp}
      on:pointercancel={onPointerUp}
    >
      <!-- Zoomable canvas -->
      <div class="canvas" style="transform: {transform}; transform-origin: 0 0;">
        <img
          src={iiifSrc}
          alt="Map preview"
          class="map-img"
          bind:this={imgEl}
          on:load={updateDisplaySize}
          draggable="false"
        />
        {#if dispW > 0}
          <svg class="overlay-svg" width={dispW} height={dispH} viewBox="0 0 {dispW} {dispH}">
            <!-- Neatline polygon -->
            <polygon
              class="neatline-poly"
              points={gcps
                .map((g) => toDisp(g.resourceCoords[0], g.resourceCoords[1]).join(','))
                .join(' ')}
              stroke-width={1.5 / view.zoom}
              stroke-dasharray="{6 / view.zoom} {3 / view.zoom}"
            />
            <!-- Corner handles -->
            {#each gcps as gcp, idx (idx)}
              {@const [dx, dy] = toDisp(gcp.resourceCoords[0], gcp.resourceCoords[1])}
              <g
                class="handle {CORNER_CLASS[CORNERS[idx]]}"
                transform="translate({dx},{dy})"
                on:pointerdown={(e) => onHandlePointerDown(e, idx)}
              >
                <circle class="handle-dot" r={10 / view.zoom} />
                <circle class="handle-ring" r={10 / view.zoom} stroke-width={1.5 / view.zoom} />
                <text class="handle-text" font-size={8 / view.zoom}>{CORNERS[idx]}</text>
              </g>
            {/each}
          </svg>
        {/if}
      </div>
    </div>

    <!-- GCP table -->
    <DataTable columns={gcpColumns} klass="gcp-table" wrapClass="gcp-table-wrap">
      {#each gcps as gcp, idx (idx)}
        <tr>
          <td>
            <span class="corner-badge {CORNER_CLASS[CORNERS[idx]]}">{CORNERS[idx]}</span>
          </td>
          {#each [0, 1] as axis (axis)}
            <td>
              <input
                type="number"
                class="coord-input"
                value={gcp.resourceCoords[axis]}
                on:change={(e) => handlePixelInput(idx, axis as 0 | 1, e.currentTarget.value)}
              />
            </td>
          {/each}
          {#each [0, 1] as axis (axis)}
            <td>
              <input
                type="number"
                class="coord-input"
                step="0.000001"
                value={gcp.geo[axis]}
                on:change={(e) => handleGeoInput(idx, axis as 0 | 1, e.currentTarget.value)}
              />
            </td>
          {/each}
        </tr>
      {/each}
    </DataTable>

    <!-- Datum correction panel -->
    <details class="datum-panel">
      <summary class="datum-summary">Datum correction (Indian → WGS84)</summary>
      <div class="datum-body">
        <p class="datum-desc">
          If GCP coordinates were read from the map's printed graticule (Indochina / UTM 48 grid),
          they are in the map's original datum — not WGS84 — and will be offset ~200–500 m. US Army
          AMS/Series-L maps of southern Vietnam (including Hà Tiên area) use <strong
            >Indian 1960, Everest Modified</strong
          >
          — select that preset and apply to shift all four GCP geo-coordinates to WGS84.
        </p>
        <label class="datum-label">
          Source datum
          <select class="datum-select" bind:value={selectedDatumIdx}>
            {#each DATUM_PRESETS as preset, i (preset.label)}
              <option value={i}>{preset.label}</option>
            {/each}
          </select>
        </label>
        <div class="datum-actions">
          <button class="btn" on:click={applyDatumCorrection}>Apply correction</button>
          {#if datumApplied}
            <span class="datum-ok">✓ Coordinates updated — review then save</span>
          {/if}
        </div>
      </div>
    </details>

    <div class="save-row">
      {#if saveMsg}
        <span class="save-msg" class:save-error={saveMsg.startsWith('Error')}>{saveMsg}</span>
      {/if}
      <button class="btn is-primary" on:click={handleSave} disabled={saving}>
        {saving ? 'Saving…' : 'Save GCPs'}
      </button>
    </div>
  {/if}
</div>
