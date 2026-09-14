// Pure IIIF key arithmetic, kept apart from the Worker itself.
//
// index.ts reaches for Workers globals (R2Bucket, caches.default,
// ExecutionContext) that only exist under @cloudflare/workers-types. The app's
// type-check does not load those, so a test importing index.ts directly turned
// `npm run check` red. These two functions need none of it — they are string
// arithmetic — so they live here, where both the Worker and
// tests/tile-size-segment.spec.ts can import them.

function scaleFactorFor(regionW: number, width: number): number | null {
  // dzsave's factors are powers of two, and `ceil(regionW / sf)` is decreasing
  // in sf, so at most one shallow level answers to the width asked for. Testing
  // them is exact where arithmetic on the ratio is not: a narrow right-hand
  // column gives 604 / 76 = 7.947, and only the factor 8 reproduces the key.
  for (let sf = 1; sf <= regionW; sf *= 2) {
    if (Math.ceil(regionW / sf) === width) return sf;
  }
  return null;
}

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
 * Deriving the height rather than guessing it. dzsave's size at a level is
 * `ceil(region / scaleFactor)` on each axis independently — which is how
 * 2048 x 1705 at factor 8 is written `256,214` and not `256,213`. So the height
 * follows from the **scale factor**, and the scale factor is what has to be
 * recovered first: `scaleFactorFor` asks which power of two maps this region's
 * width onto the width that was requested.
 *
 * Scaling the height by the requested width instead — `regionH * w / regionW`,
 * which is what this did until 2026-09-14 — is wrong twice over, and the two
 * failures hid each other:
 *
 * - It rounded to nearest. Round is ceil only when the fraction is >= 0.5, and
 *   the one real key the test pinned (3758 * 256 / 4096 = 234.875) happens to
 *   land there, so it agreed with ceil and never discriminated. Every bottom-row
 *   tile whose fraction fell below .5 asked for a key that was never written.
 * - On a **corner** tile the width is itself already rounded up, so the ratio it
 *   carries is not the scale factor: 1705 * 76 / 604 = 214.56 overshoots 214,
 *   and ceil and round miss it alike. Only the factor gets it right.
 *
 * It reads as a rare off-by-one and is not, because of where inexact tiles sit.
 * Only the bottom row and the right column are ever inexact, so at full
 * resolution — hundreds of tiles, a one-tile border — the miss rate was 0%. It
 * climbs as the pyramid shortens: one level below the whole-sheet overview a
 * sheet is a 2 x 2 grid where three of the four tiles are edges, and across the
 * 83-sheet Indochine survey 58.6% of tiles at that level were unreachable.
 * That is a map which is flawless zoomed in and full of holes zoomed out, and
 * it is why this surfaced as "missing tile at zoom 9" rather than as a bad map.
 *
 * Only `x,y,w,h` regions are handled; `full`, `square` and `pct:` fall through
 * to the existing proxy, because for those dzsave writes one thumbnail rather
 * than a pyramid and there is nothing to compute against.
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
  const factor = scaleFactorFor(regionW, width);
  if (!factor) return null;
  const height = Math.ceil(regionH / factor);
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
