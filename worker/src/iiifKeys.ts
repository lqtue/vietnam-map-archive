// Pure IIIF key arithmetic, kept apart from the Worker itself.
//
// index.ts reaches for Workers globals (R2Bucket, caches.default,
// ExecutionContext) that only exist under @cloudflare/workers-types. The app's
// type-check does not load those, so a test importing index.ts directly turned
// `npm run check` red. These two functions need none of it — they are string
// arithmetic — so they live here, where both the Worker and
// tests/tile-size-segment.spec.ts can import them.

/**
 * The same tile, spelled the way `vips dzsave` actually wrote it.
 *
 * `dzsave --layout iiif3` names every derivative with an explicit `w,h` size —
 * `0,0,4096,3758/256,235/0/default.jpg`. IIIF's canonical form for "this width,
 * proportional height" is width-only (`256,`), and that is what @allmaps/render
 * and OpenLayers ask for. So a width-only request misses R2 for **every** map
 * in the bucket, not just one: the maps that appear to work are the ones with a
 * `sources/` entry, which have been quietly proxying every tile to their origin
 * server while their mirrored copy sat unread. The maps without one — a scan
 * with no upstream, which is every self-hosted sheet — answer 404 and render as
 * nothing at all. That is the visible half of one bug.
 *
 * Deriving the height rather than guessing it: the region carries its own size,
 * so the height is `regionH * w / regionW`, rounded the way dzsave rounds
 * (3758 * 256 / 4096 = 234.875 -> 235). Only `x,y,w,h` regions are handled;
 * `full`, `square` and `pct:` fall through to the existing proxy, because for
 * those dzsave writes one thumbnail rather than a pyramid and there is nothing
 * to compute against.
 *
 * Pure, and exported for `tests/tile-size-segment.spec.ts`, which pins it
 * against real keys from the bucket — a wrong rounding here does not error, it
 * silently re-opens the 404.
 */
export function widthOnlySizeToExplicit(rest: string): string | null {
  const m = rest.match(/^\/(\d+),(\d+),(\d+),(\d+)\/(\d+),\/(.+)$/);
  if (!m) return null;
  const [, x, y, rw, rh, w, tail] = m;
  const regionW = Number(rw);
  const regionH = Number(rh);
  const width = Number(w);
  if (!regionW || !regionH || !width) return null;
  const height = Math.round((regionH * width) / regionW);
  if (!height) return null;
  return `/${x},${y},${rw},${rh}/${width},${height}/${tail}`;
}

/**
 * The same derivative, addressed as `full` instead of as a region covering
 * everything.
 *
 * `0,0,5001,3771/157,118/0/default.jpg` and `full/157,118/0/default.jpg` are
 * the same picture by the IIIF spec, and @allmaps/render asks for the first
 * while `dzsave` writes only the second. That request is the whole-image
 * overview — the first thing the renderer fetches for a map and the one it
 * needs before it can draw anything — so a map whose tiles are otherwise fine
 * still renders as nothing without this.
 *
 * The region is checked against the image's real dimensions rather than against
 * the size's aspect ratio. An aspect test looks sufficient and is not: a corner
 * tile like `0,0,1024,1024` asking for a square size would match `full`'s key
 * on some images and quietly serve the entire map in place of one tile.
 *
 * Pure; `width`/`height` come from the stored info.json.
 */
export function wholeRegionToFull(rest: string, width: number, height: number): string | null {
  const m = rest.match(/^\/0,0,(\d+),(\d+)\/(.+)$/);
  if (!m) return null;
  if (Number(m[1]) !== width || Number(m[2]) !== height) return null;
  return `/full/${m[3]}`;
}
