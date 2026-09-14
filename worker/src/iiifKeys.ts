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

// ── The optional version segment ──────────────────────────────────────────
//
// A re-tile cannot reuse a map's existing keys: the worker serves every
// derivative `Cache-Control: public, max-age=31536000, immutable`, so new bytes
// at an old URL reach no existing reader for a year. The answer is a new URL —
// `/iiif/<mapId>/v<N>/…`, mapping to `tiles/<mapId>/v<N>/…` — which is purely
// additive. The 155 maps and ~119,616 objects already under `tiles/<mapId>/…`
// are untouched and their URLs keep working unchanged.
//
// The peel has to happen *before* any of the key arithmetic above runs.
// `widthOnlySizeToExplicit` and `wholeRegionToFull` both anchor on `^\/` + the
// region, so behind a `/v2` prefix they silently match nothing — which is not a
// 404, it is the proxy path, i.e. every tile of a re-tiled map fetched from the
// originating library instead of from the copy we just made.

/**
 * A `/iiif/` pathname split into the three things a key is built from.
 *
 * `rest` is decoded, as it was before this function existed — a malformed
 * escape falls back to the raw text rather than throwing the request into a
 * 500, which is what `decodeURIComponent` does on `%ZZ`.
 *
 * `version` is `''` or `/v<N>`, and is *not* part of `rest`, so everything
 * downstream sees the same string it saw when no map had a version.
 */
export function splitIiifPath(
  pathname: string
): { mapId: string; version: string; rest: string } | null {
  const match = pathname.match(/^\/iiif\/([^/]+)(\/.*)?$/);
  if (!match) return null;
  let rest = match[2] || '';
  try {
    rest = decodeURIComponent(rest);
  } catch {
    // Keep the raw text: a bad escape is a bad request, not a crash.
  }
  const v = rest.match(/^\/v(\d+)(\/.*)?$/);
  return v
    ? { mapId: match[1], version: `/v${v[1]}`, rest: v[2] || '' }
    : { mapId: match[1], version: '', rest };
}

/**
 * The R2 key for a request. Unversioned requests must land on exactly the key
 * they landed on before — that is the whole compatibility promise.
 */
export function iiifR2Key(mapId: string, version: string, rest: string): string {
  return `tiles/${mapId}${version}${rest}`;
}

// ── What `full/` actually holds ───────────────────────────────────────────
//
// The `sizes` array used to be synthesised from `scaleFactors`, and every entry
// it produced was fiction: on 0775a31e it advertised `full/2652,3753`,
// `full/1326,1877`, `full/663,939` and `full/332,470`, all four of which 404,
// while the one `w,h` derivative that does exist — `full/166,235` — went
// unadvertised. So the array is now read out of the bucket instead.
//
// Two spellings live side by side under `full/`, because two different
// producers write there:
//
//  - `w,h` — `vips dzsave --layout iiif3` writes the top of the pyramid, the
//    level that fits in a single tile, under its own explicit size. The name
//    states the real pixel dimensions, so it needs no arithmetic.
//  - `w,` — `scripts/tile_map.sh` renders `full/200,`, `full/400,` and
//    `full/800,` with `vips thumbnail` for the OG image and the catalog cells.
//    The name states only the width.

export type FullSizeDir = {
  /** The directory name as it sits in R2 — the thing a key is built from. */
  name: string;
  width: number;
  /** null for the `w,` spelling, whose height the name does not record. */
  height: number | null;
};

/**
 * The `full/` derivatives an R2 `list({ delimiter: '/' })` found, widest last.
 *
 * Input is `delimitedPrefixes` — whole keys like `tiles/<id>/full/166,235/` —
 * because that is what the bucket hands back; only the last segment matters.
 * Names that are neither spelling (`max`, `pct:…`, anything else that ends up
 * there) are dropped rather than guessed at. Where both spellings exist for one
 * width the explicit one wins, since its height is read rather than derived.
 */
export function parseFullSizeDirs(delimitedPrefixes: string[]): FullSizeDir[] {
  const byWidth = new Map<number, FullSizeDir>();
  for (const prefix of delimitedPrefixes) {
    const name = prefix.replace(/\/+$/, '').split('/').pop() ?? '';
    const both = name.match(/^(\d+),(\d+)$/);
    const widthOnly = name.match(/^(\d+),$/);
    let dir: FullSizeDir | null = null;
    if (both && Number(both[1]) > 0 && Number(both[2]) > 0) {
      dir = { name, width: Number(both[1]), height: Number(both[2]) };
    } else if (widthOnly && Number(widthOnly[1]) > 0) {
      dir = { name, width: Number(widthOnly[1]), height: null };
    }
    if (!dir) continue;
    const seen = byWidth.get(dir.width);
    if (!seen || (seen.height === null && dir.height !== null)) byWidth.set(dir.width, dir);
  }
  return [...byWidth.values()].sort((a, b) => a.width - b.width);
}

/**
 * The size to advertise for one `full/` directory.
 *
 * For `w,h` the name is the answer. For `w,` the height has to be derived, and
 * **it cannot be derived exactly** — which is worth stating plainly, because
 * the obvious rules are all wrong some of the time. Measured over 81 live
 * derivatives (27 maps x 200/400/800): `ceil` reproduces 47, `round` 68,
 * `floor` 36. No rule reproduces all of them, because `vips thumbnail` shrinks
 * on load first (a ceil of its own) and then resizes with `rint` against the
 * already-shrunk size, so the rounding is a function of an intermediate the
 * name does not record. `round` is used here as the best of the three.
 *
 * A derived height that is one pixel off is harmless, but only because
 * `explicitFullSizeToWidthOnly` below catches the request it produces. Without
 * that, advertising `full/200,284` where the bucket holds `full/200,` would be
 * the same class of bug as the synthesised array this replaces.
 *
 * `--size down` means a requested width wider than the image leaves the image
 * alone, so the advertised size is clamped to the image rather than promising
 * an upscale nothing will perform.
 */
export function fullSizeOf(
  dir: FullSizeDir,
  imageWidth: number,
  imageHeight: number
): { width: number; height: number } | null {
  if (dir.height !== null) return { width: dir.width, height: dir.height };
  if (!(imageWidth > 0) || !(imageHeight > 0)) return null;
  const width = Math.min(dir.width, imageWidth);
  const height =
    width === imageWidth ? imageHeight : Math.round((imageHeight * width) / imageWidth);
  return height > 0 ? { width, height } : null;
}

/**
 * The same `full/` derivative, spelled width-only.
 *
 * The mirror image of `widthOnlySizeToExplicit`, and needed for the same
 * reason in the other direction: `sizes` advertises `w,h` for every derivative
 * (that is the syntax the spec asks the array to be given in), but three of the
 * four `full/` directories on a typical map are named `w,`. Without this a
 * client that does the one thing `info.json` invites it to do — request a size
 * off the list — misses R2 and falls through to the proxy.
 *
 * Only `full/` is rewritten. A region request's `w,h` is dzsave's own spelling
 * and is never a width-only key.
 */
export function explicitFullSizeToWidthOnly(rest: string): string | null {
  const m = rest.match(/^\/full\/(\d+),\d+\/(.+)$/);
  if (!m) return null;
  return `/full/${m[1]},/${m[2]}`;
}

/**
 * `full/max/...` re-pointed at a derivative that exists.
 *
 * `full/max/0/default.jpg` is the one request a level0 service is required to
 * answer, and it 404s today: nothing writes a key called `max`. Image API 3.0
 * lets a service cap what `max` means with `maxWidth` ("the maximum width in
 * pixels supported for this image"), so declaring the widest derivative we hold
 * and serving it here is the compliant reading rather than a fudge.
 */
export function fullMaxToSize(rest: string, sizeName: string): string | null {
  const m = rest.match(/^\/full\/max\/(.+)$/);
  if (!m) return null;
  return `/full/${sizeName}/${m[1]}`;
}
