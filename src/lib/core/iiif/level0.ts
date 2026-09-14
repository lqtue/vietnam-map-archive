/**
 * Addressing a fixed IIIF tile pyramid (a level0 server).
 *
 * Our own R2 host renders nothing — it maps a IIIF path onto an R2 key and
 * serves only the tiles `vips dzsave` wrote, so an arbitrary region at an
 * arbitrary scale is a 404. Since 2026-09-14 its `info.json` says so — `profile`
 * is `level0` and `sizes` is listed from what the bucket actually holds, rather
 * than the synthesised array whose every entry 404'd. The field is now worth
 * trusting; these rules are still needed, because a truthful advertisement of a
 * fixed pyramid is still a fixed pyramid. `work/ocr/scripts/iiif_tiles.py` holds
 * the Python twin of these rules — keep the two in step.
 */

export type Level0Tile = {
  url: string;
  /** Where this tile lands in the assembled canvas, in canvas pixels. */
  dx: number;
  dy: number;
};

export type Level0Plan = {
  tiles: Level0Tile[];
  /** Canvas size the tiles assemble into. */
  width: number;
  height: number;
  /** Downscale from source pixels to canvas pixels. */
  scaleFactor: number;
};

/**
 * The one URL a dzsave pyramid actually holds for this tile.
 *
 * The rendered size is `ceil(regionW / sf),ceil(regionH / sf)` — both halves,
 * and not a constant tile size. Two separate traps:
 *
 *  - A clipped edge tile is narrower, so asking for the full width there 404s.
 *  - `--layout iiif3` names every size segment `w,h`; the bare `w,` form IIIF
 *    also allows is never written. Requesting `w,` misses R2 and the worker
 *    then proxies the tile to the originating library — so the whole pyramid we
 *    mirrored went unused, and a parallel run failed as upstream rate-limiting.
 *    Verified against the live bucket: `256,256`, `82,256`, `256,167`.
 */
export function level0TileUrl(
  base: string,
  x: number,
  y: number,
  w: number,
  h: number,
  sf: number,
  quality = 'default'
): string {
  return `${base}/${x},${y},${w},${h}/${Math.ceil(w / sf)},${Math.ceil(h / sf)}/0/${quality}.jpg`;
}

/** Coarsest advertised factor that still delivers at least `targetWidth` across. */
export function pickScaleFactor(
  scaleFactors: number[],
  fullWidth: number,
  targetWidth: number
): number {
  const factors = [...(scaleFactors.length ? scaleFactors : [1])].sort((a, b) => a - b);
  let chosen = factors[0];
  for (const f of factors) {
    if (fullWidth / f >= targetWidth) chosen = f;
    else break;
  }
  return chosen;
}

/**
 * Every tile needed to cover the whole image at roughly `targetWidth` pixels.
 *
 * Callers fetch these in parallel and paste each at (dx, dy). A tile that fails
 * is simply skipped — a pyramid often advertises a scale factor it never wrote,
 * and a hole in the overview costs accuracy, not correctness.
 */
export function planOverview(
  base: string,
  fullWidth: number,
  fullHeight: number,
  scaleFactors: number[],
  tileSize: number,
  targetWidth: number,
  quality = 'default'
): Level0Plan {
  const sf = pickScaleFactor(scaleFactors, fullWidth, targetWidth);
  const step = tileSize * sf;
  const tiles: Level0Tile[] = [];
  for (let y = 0; y < fullHeight; y += step) {
    for (let x = 0; x < fullWidth; x += step) {
      const w = Math.min(step, fullWidth - x);
      const h = Math.min(step, fullHeight - y);
      tiles.push({
        url: level0TileUrl(base, x, y, w, h, sf, quality),
        dx: Math.floor(x / sf),
        dy: Math.floor(y / sf),
      });
    }
  }
  return {
    tiles,
    width: Math.ceil(fullWidth / sf),
    height: Math.ceil(fullHeight / sf),
    scaleFactor: sf,
  };
}
