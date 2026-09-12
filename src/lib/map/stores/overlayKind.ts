/**
 * What kind of thing is on the overlay stack.
 *
 * Lives apart from `layersStore` so it can be tested: that module reaches for
 * `$app/environment` and `localStorage` at import time, and this predicate is
 * the part with a rule in it. The import below is type-only, so it erases and
 * nothing follows it at runtime.
 */
import type { HistoricalRef, OverlayLayer } from './layersStore';

/**
 * Narrow a stack entry to a catalogued sheet. A raster series is not one: it
 * has no `maps` row, so anything meaning "this sheet" — `?map=`, the Info rail,
 * story playback, the year scrubber — has to read past it.
 */
export function isSheetLayer(o: OverlayLayer): o is OverlayLayer & { ref: HistoricalRef } {
  return o.ref.kind === 'historical';
}
