/**
 * What kind of thing is on the overlay stack, and how a stored one is read
 * back.
 *
 * Lives apart from `layersStore` so it can be tested: that module reaches for
 * `$app/environment` and `localStorage` at import time, and these are the parts
 * with a rule in them. Everything imported here is either a type or pure data,
 * for the same reason.
 */
import type { HistoricalRef, OverlayLayer, OverlayRef, SeriesPart, SeriesRef } from './layersStore';

/**
 * Narrow a stack entry to a catalogued sheet. A series is not one: it has no
 * `maps` row, so anything meaning "this sheet" — `?map=`, the Info rail, story
 * playback, the year scrubber — has to read past it.
 */
export function isSheetLayer(o: OverlayLayer): o is OverlayLayer & { ref: HistoricalRef } {
  return o.ref.kind === 'historical';
}

function bbox(v: unknown): [number, number, number, number] | null {
  return Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === 'number')
    ? (v as [number, number, number, number])
    : null;
}

/**
 * Read one ref out of localStorage, or return null for anything unreadable —
 * which `load()` drops rather than handing a half-formed layer to OpenLayers.
 *
 * It is half of the migration. Until Sept 2026 a survey was one stack row per
 * route — `{ kind: 'sheets' }` for live-warped `maps` rows, and `{ kind: 'raster' }` for a
 * pre-tiled archive — and the raster route was retired on 2026-10-03 (L7014's PMTiles mosaic). So a
 * saved `raster` row, or a `raster` part inside a `series` row, is dropped here rather than handed to
 * a renderer that no longer has one. `foldLegacyOverlays` puts the remaining `sheets` rows of one
 * survey back together.
 */
export function readOverlayRef(raw: unknown): OverlayRef | null {
  const ref = raw as Record<string, any> | null;
  if (!ref || typeof ref !== 'object') return null;

  if (ref.kind === 'historical')
    return ref.mapId && ref.allmapsId ? (ref as unknown as HistoricalRef) : null;

  const bounds = bbox(ref.bounds);
  if (!ref.mapId || !ref.key || !ref.name || !bounds) return null;
  const head = { kind: 'series' as const, mapId: ref.mapId, key: ref.key, name: ref.name, bounds };

  if (ref.kind === 'series') {
    const parts = Array.isArray(ref.parts)
      ? ref.parts.filter((p: any) => p?.kind === 'sheets' && p.collection)
      : [];
    return parts.length ? ({ ...head, parts } as SeriesRef) : null;
  }
  if (ref.kind === 'sheets')
    return ref.collection
      ? { ...head, parts: [{ kind: 'sheets', seriesKey: ref.key, collection: ref.collection }] }
      : null;
  return null;
}

/** The box that holds every half of a survey. */
function union(
  a: [number, number, number, number],
  b: [number, number, number, number]
): [number, number, number, number] {
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

/**
 * Merge a stored row into the row already standing for its survey — or build
 * that row, when this is the first half seen. One part of each kind, the earlier one kept.
 */
function merge(key: string, into: SeriesRef | null, ref: SeriesRef): SeriesRef {
  const parts: SeriesPart[] = [];
  for (const p of [...(into?.parts ?? []), ...ref.parts])
    if (!parts.some((q) => q.kind === p.kind)) parts.push(p);
  return {
    kind: 'series',
    mapId: `series:${key}`,
    key,
    name: into?.name ?? ref.name,
    parts,
    bounds: into ? union(into.bounds, ref.bounds) : ref.bounds,
  };
}

/** Series keys a saved row may still carry from before the L7014 mosaic was retired (2026-10-03). */
const RETIRED_KEYS: Record<string, string> = { l7014: 'series-l7014-vietnam-1-50-000' };

/**
 * Put a restored stack back together as one row per survey.
 *
 * A stack saved before Sept 2026 holds one survey as several rows, each with its own opacity
 * slider, eye and ×. This makes them the single row they are added as today, in the higher of the
 * positions and keeping that row's opacity and visibility. It also canonicalises the id of a
 * survey stored under a retired key (L7014's mosaic archive), so a restored row is the *same* row
 * the /explore list offers rather than a second one that draws the same pixels.
 *
 * Runs on every load, for every page that renders the stack, because the stack
 * outlives any one panel: a reader who never opens Browse must not be left with
 * the two half-rows forever. It is a no-op once every row is canonical.
 */
export function foldLegacyOverlays(overlays: OverlayLayer[]): OverlayLayer[] {
  const out: OverlayLayer[] = [];
  const seen = new Map<string, number>();
  for (const o of overlays) {
    if (o.ref.kind !== 'series') {
      out.push(o);
      continue;
    }
    const key = RETIRED_KEYS[o.ref.key] ?? o.ref.key;
    const at = seen.get(key);
    if (at === undefined) {
      seen.set(key, out.length);
      out.push({ ...o, ref: merge(key, null, o.ref) });
    } else {
      // The row already standing is the higher of the two, so it keeps its
      // place, its opacity and its eye; this half only adds what it carries.
      out[at] = { ...out[at], ref: merge(key, out[at].ref as SeriesRef, o.ref) };
    }
  }
  return out;
}
