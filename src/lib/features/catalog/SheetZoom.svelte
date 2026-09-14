<!--
  SheetZoom.svelte — the scan on the record page, still first, zoomable on demand.

  Two problems in one component:

  - **The still is small.** `maps.thumbnail` is whatever width the sheet was
    mirrored with — 157px on some rows — and the record page draws it across a
    56rem column. `atWidth`/`stepDown` ask for 800 and climb down only if that
    width was never written (see `core/iiif/thumbUrl.ts`; several sheets are
    level0 pyramids that 404 every size they did not mirror, `/full/max/`
    included, so there is no "just link the full image" to fall back on).
  - **A 4995px sheet is not readable at any single width.** The tiles are, so
    the zoom is `ImageShell` — the one IIIF canvas this repo owns — on the
    page's own `info.json`.

  ImageShell is **dynamically imported on the click**, not at module scope: it
  pulls OpenLayers, and /catalog/[id] is an editorial page that a reader may
  well never zoom on. The still is what the crawler and the first paint get.

  Full screen is a CSS state on the same instance, not a second surface. It is
  what `/scan?mode=inspect` had that this page did not, and the only reason that
  mode was still a public address — expanding the frame retired it (Sept 2026).
  `requestFullscreen()` would be the lower tier and is not used: it is refused
  for non-video elements on iOS Safari, where a sheet this size most wants the
  whole screen.
-->
<script lang="ts">
  import { tick } from 'svelte';
  import type OlMap from 'ol/Map';
  import { t } from '$lib/core/i18n';
  import { atWidth, stepDown } from '$lib/core/iiif/thumbUrl';
  import { toOlExtent } from '$lib/core/geo/rectUtils';

  /** Base IIIF Image API URL, no trailing slash. Null when the row has no scan. */
  export let iiifImage: string | null = null;
  /** Stored still, already at some width. Null when the row has neither. */
  export let preview: string | null = null;
  export let title: string;

  $: infoUrl = iiifImage ? `${iiifImage.replace(/\/$/, '')}/info.json` : null;
  $: previewSrc = (preview ? atWidth(preview, 800) : null) ?? preview;

  /** Set on the first click and kept, so closing and reopening does not refetch. */
  let shellPromise: Promise<typeof import('$lib/map/shell/ImageShell.svelte').default> | null =
    null;
  let zoomed = false;
  let full = false;

  /* Bound out of ImageShell so the sheet can be re-fitted when the frame
     changes size. OL keeps centre and resolution across a resize, which is
     right for a map and wrong here: expanding to full screen would leave the
     sheet the size it was, adrift in the middle of the viewport. */
  let olMap: OlMap | null = null;
  let imgWidth = 0;
  let imgHeight = 0;

  function openZoom() {
    if (!shellPromise)
      shellPromise = import('$lib/map/shell/ImageShell.svelte').then((m) => m.default);
    zoomed = true;
  }

  function closeZoom() {
    zoomed = false;
    full = false;
  }

  async function toggleFull() {
    full = !full;
    await tick(); // the frame has to have its new size before the fit reads it
    if (!olMap || !imgWidth || !imgHeight) return;
    olMap.updateSize();
    olMap.getView().fit(toOlExtent(0, 0, imgWidth, imgHeight), {
      padding: [24, 24, 24, 24],
      duration: 200,
    });
  }

  /* Escape leaves full screen, the way it leaves every other overlay here. It
     does not close the viewer: a reader who expanded a sheet and pressed Escape
     wants the page back, not the picture gone. */
  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && full) toggleFull();
  }
</script>

<svelte:window on:keydown={onKeydown} />

<figure class="sheet-zoom" class:is-full={full}>
  {#if zoomed && infoUrl}
    <div class="sheet-zoom-frame">
      {#await shellPromise}
        <p class="sheet-zoom-status">{$t('Loading the viewer…')}</p>
      {:then Shell}
        <svelte:component
          this={Shell}
          iiifInfoUrl={infoUrl}
          bind:map={olMap}
          bind:imgWidth
          bind:imgHeight
        />
      {:catch}
        <p class="sheet-zoom-status">{$t('The viewer failed to load.')}</p>
      {/await}
    </div>
  {:else if previewSrc}
    <button type="button" class="sheet-zoom-still" on:click={openZoom} disabled={!infoUrl}>
      <img src={previewSrc} alt={title} on:error={(e) => stepDown(e, preview ?? undefined)} />
      {#if infoUrl}
        <span class="sheet-zoom-hint">{$t('Zoom into the scan')}</span>
      {/if}
    </button>
  {/if}

  {#if infoUrl}
    <figcaption class="sheet-zoom-bar">
      {#if zoomed}
        <span class="sheet-zoom-note">{$t('Drag to pan, scroll to zoom.')}</span>
        <button type="button" class="sheet-zoom-link" on:click={toggleFull}>
          {full ? $t('Leave full screen') : $t('Full screen')}
        </button>
        <button type="button" class="sheet-zoom-link" on:click={closeZoom}>
          {$t('Close the viewer')}
        </button>
      {/if}
      <a
        class="sheet-zoom-link"
        href={infoUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={iiifImage}
      >
        {$t('IIIF image service')}
      </a>
    </figcaption>
  {/if}
</figure>

<style>
  .sheet-zoom {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* The still is the button, so the whole picture is the target. */
  .sheet-zoom-still {
    position: relative;
    display: block;
    width: 100%;
    padding: 0;
    border: var(--border-thin);
    border-radius: var(--radius-lg);
    background: var(--color-gray-100);
    overflow: hidden;
    cursor: zoom-in;
  }
  .sheet-zoom-still:disabled {
    cursor: default;
  }
  .sheet-zoom-still img {
    display: block;
    width: 100%;
  }
  .sheet-zoom-hint {
    position: absolute;
    right: var(--space-3);
    bottom: var(--space-3);
    padding: 2px var(--space-2);
    border-radius: var(--radius-pill);
    background: var(--color-white);
    border: var(--border-thin);
    font-size: var(--text-sm);
  }

  /* ImageShell is `position: absolute; inset: 0` — it needs a positioned box
     with a height of its own. */
  .sheet-zoom-frame {
    position: relative;
    height: min(70vh, 34rem);
    border: var(--border-thin);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  /* Full screen: the figure leaves the column and covers the viewport, frame
     and caption together, so the controls do not go with the page. OL reads its
     own container size, so there is nothing to tell it. */
  .sheet-zoom.is-full {
    position: fixed;
    inset: 0;
    /* Over the nav bar (300) and under nothing else: the modal layer is 9999
       and this is not a modal — a MapEditModal opened behind it would be
       unreachable. There is no z-index token; `docs/design-system.md` has the
       ladder. */
    z-index: 400;
    gap: 0;
    background: var(--color-white);
  }
  .sheet-zoom.is-full .sheet-zoom-frame {
    flex: 1;
    height: auto;
    border: 0;
    border-radius: 0;
  }
  .sheet-zoom.is-full .sheet-zoom-bar {
    padding: var(--space-2) var(--space-3);
    border-top: var(--border-thin);
  }
  .sheet-zoom-status {
    margin: 0;
    padding: var(--space-4);
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }

  .sheet-zoom-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-1) var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }
  .sheet-zoom-note {
    margin-right: auto;
  }
  .sheet-zoom-link {
    padding: 0;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .sheet-zoom-link:hover {
    color: var(--color-text);
  }
</style>
