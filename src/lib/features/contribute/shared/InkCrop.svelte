<!--
  InkCrop.svelte — a small crop of the sheet's own ink around one bounding box,
  so a reviewer sees the pixels behind a claim without leaving the list.

  The IIIF server here is Image API 3, profile level0: there is no region
  endpoint, only tile-aligned full-resolution requests. So this fetches the
  256px tiles that cover the (padded) bbox and composites them into a canvas,
  clipped and scaled to fit. Tiles are cached module-wide by URL — adjacent
  rows on a sheet share tiles, and a j/k walk re-visits the same row's tiles
  constantly.

  A junk bbox (a mis-drawn polygon spanning a big chunk of the sheet) is not
  hidden — it renders as a plain-language note, because "the crop looks wrong"
  is itself a finding a reviewer has no other way to see today.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  /** IIIF image base, e.g. https://iiif.maparchive.vn/iiif/<id> — no /info.json. */
  export let iiifBase: string | null | undefined;
  /** Bounding box, in full-resolution source-image pixels (IIIF convention: y+ = down). */
  export let x: number;
  export let y: number;
  export let w: number;
  export let h: number;
  /** The source image's own dimensions — needed to size the edge tiles correctly. */
  export let imageWidth: number;
  export let imageHeight: number;
  /** Target height for the common (squarish/landscape) case. A tall, narrow crop
   *  floats past this rather than collapse to a sliver — see fitDims. */
  export let displayHeight = 40;

  const TILE = 256;
  const PAD = 6; // source px of headroom, so ink isn't cropped flush to the glyphs
  const MAX_TILES = 9;
  const MAX_SPAN = 1024; // source px, either axis
  const MAX_DISPLAY_W = 220; // cap a short-but-wide junk box from blowing out the row
  const MAX_DISPLAY_H = 96; // ditto for a tall one: 1024px of span must not own the row
  const MIN_DIM = 16; // floor so a tall/narrow crop never collapses to a sliver
  /** A decoded 256×256 tile costs ~256 kB of bitmap, and one sheet's review
   *  queue runs to ~900 rows, so an unbounded cache is a session-long leak.
   *  Insertion-ordered eviction — plain FIFO, not LRU; a reviewer walks the
   *  list in order, so the oldest entry is also the furthest from the eye. */
  const MAX_CACHED_TILES = 300;

  /** Tile image cache, module-wide: many rows on one sheet share tiles. */
  const tileCache = new Map<string, Promise<HTMLImageElement | null>>();

  function loadTile(url: string): Promise<HTMLImageElement | null> {
    let p = tileCache.get(url);
    if (p) return p;
    p = new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null); // a 404'd tile just leaves that patch blank
      img.src = url;
    });
    tileCache.set(url, p);
    if (tileCache.size > MAX_CACHED_TILES) {
      const oldest = tileCache.keys().next().value;
      if (oldest) tileCache.delete(oldest);
    }
    return p;
  }

  /** "Contain", with a floor: fit the common case by height, but never let
   *  either axis end up under MIN_DIM (a 42×309 vertical street label, scaled
   *  to a fixed 40px height, would otherwise land at a 4px-wide sliver). */
  function fitDims(srcW: number, srcH: number) {
    let scale = displayHeight / srcH;
    if (srcW * scale > MAX_DISPLAY_W) scale = MAX_DISPLAY_W / srcW;
    if (srcW * scale < MIN_DIM) scale = MIN_DIM / srcW;
    if (srcH * scale < MIN_DIM) scale = MIN_DIM / srcH;
    // Last word: the floors above can enlarge, and a 17×1024 box would
    // otherwise claim a 963px-tall row.
    if (srcH * scale > MAX_DISPLAY_H) scale = MAX_DISPLAY_H / srcH;
    return {
      scale,
      outW: Math.max(1, Math.round(srcW * scale)),
      outH: Math.max(1, Math.round(srcH * scale)),
    };
  }

  let canvasEl: HTMLCanvasElement | undefined;
  let note = '';
  let label = '';
  /** Bumped on every load and on destroy, so a load that resolves late — after
   *  the props moved on, or after the component is gone — is a no-op instead
   *  of painting a stale crop into a recycled canvas. */
  let seq = 0;

  async function refresh(
    base: string | null | undefined,
    bx: number,
    by: number,
    bw: number,
    bh: number,
    imgW: number,
    imgH: number
  ) {
    const mySeq = ++seq;
    note = '';
    if (!base || !imgW || !imgH || !(bw > 0) || !(bh > 0)) return;

    const x0 = Math.max(0, bx - PAD);
    const y0 = Math.max(0, by - PAD);
    const x1 = Math.min(imgW, bx + bw + PAD);
    const y1 = Math.min(imgH, by + bh + PAD);
    const spanW = x1 - x0;
    const spanH = y1 - y0;
    if (spanW <= 0 || spanH <= 0) return;

    label = `Crop of the sheet at (${Math.round(bx)}, ${Math.round(by)}), ${Math.round(bw)}×${Math.round(bh)} px`;

    const tx0 = Math.floor(x0 / TILE);
    const ty0 = Math.floor(y0 / TILE);
    const tx1 = Math.floor((x1 - 1) / TILE);
    const ty1 = Math.floor((y1 - 1) / TILE);
    const tileCount = (tx1 - tx0 + 1) * (ty1 - ty0 + 1);

    if (spanW > MAX_SPAN || spanH > MAX_SPAN || tileCount > MAX_TILES) {
      note = 'Box too large to preview';
      return;
    }

    const { scale, outW, outH } = fitDims(spanW, spanH);

    const tiles: { tx: number; ty: number; url: string }[] = [];
    for (let ty = ty0; ty <= ty1; ty++) {
      for (let tx = tx0; tx <= tx1; tx++) {
        const tileX = tx * TILE;
        const tileY = ty * TILE;
        const tw = Math.min(TILE, imgW - tileX);
        const th = Math.min(TILE, imgH - tileY);
        tiles.push({
          tx: tileX,
          ty: tileY,
          url: `${base}/${tileX},${tileY},${tw},${th}/${tw},/0/default.jpg`,
        });
      }
    }

    const images = await Promise.all(tiles.map((t) => loadTile(t.url)));
    if (mySeq !== seq || !canvasEl) return; // superseded, or torn down mid-flight

    canvasEl.width = outW;
    canvasEl.height = outH;
    canvasEl.style.width = `${outW}px`;
    canvasEl.style.height = `${outH}px`;

    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, outW, outH);
    ctx.save();
    ctx.scale(scale, scale);
    ctx.translate(-x0, -y0);
    tiles.forEach((t, i) => {
      const img = images[i];
      if (img) ctx.drawImage(img, t.tx, t.ty);
    });
    ctx.restore();
  }

  /** One sheet's review queue runs to ~900 rows, and mounting them all would
   *  fire every row's tile requests at once. Nothing is fetched until the row
   *  is near the viewport; once it has been, it stays live. */
  let hostEl: HTMLElement | undefined;
  let inView = false;

  onMount(() => {
    if (typeof IntersectionObserver === 'undefined' || !hostEl) {
      inView = true;
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        inView = true;
        io.disconnect();
      },
      { rootMargin: '200px' }
    );
    io.observe(hostEl);
    return () => io.disconnect();
  });

  $: if (inView) void refresh(iiifBase, x, y, w, h, imageWidth, imageHeight);

  onDestroy(() => {
    seq++; // invalidate any load still in flight
  });
</script>

<span class="ink-crop" bind:this={hostEl}>
  {#if note}
    <span class="ink-crop-note">{note}</span>
  {:else}
    <canvas bind:this={canvasEl} aria-label={label || 'Crop of the sheet'}></canvas>
  {/if}
</span>

<style>
  /* Always in the DOM, even before the tiles are asked for: it is what the
     viewport observer watches. */
  .ink-crop {
    display: block;
    min-height: 1px;
  }

  canvas {
    display: block;
    border-radius: var(--sb-radius-sm);
    background: var(--color-gray-100);
  }

  .ink-crop-note {
    display: block;
    margin: 0;
    font-size: 0.68rem;
    font-style: italic;
    color: var(--sb-text-meta);
  }
</style>
