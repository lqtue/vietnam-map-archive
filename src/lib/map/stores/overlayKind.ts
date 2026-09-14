/**
 * What kind of thing is on the overlay stack, and how a stored one is read
 * back.
 *
 * Lives apart from `layersStore` so it can be tested: that module reaches for
 * `$app/environment` and `localStorage` at import time, and these are the parts
 * with a rule in them. Everything imported here is either a type or pure data,
 * for the same reason.
 */
import { archiveFor, type RasterSeries } from '$lib/map/rasterSeries';
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
 * route — `{ kind: 'raster' }` for a pre-tiled archive, `{ kind: 'sheets' }`
 * for live-warped `maps` rows — so a reader with L7014 on the map has **two**
 * saved rows for one survey. Each becomes a one-part `series` row here, under
 * the id it was saved with; `foldLegacyOverlays` is what puts the pair back
 * together.
 */
export function readOverlayRef(raw: unknown): OverlayRef | null {
  const ref = raw as Record<string, any> | null;
  if (!ref || typeof ref !== 'object') return null;

  if (ref.kind === 'historical')
    return ref.mapId && ref.allmapsId ? (ref as unknown as HistoricalRef) : null;

  const bounds = bbox(ref.bounds);
  if (!ref.mapId || !ref.key || !ref.name || !bounds) return null;
  const head = { kind: 'series' as const, mapId: ref.mapId, key: ref.key, name: ref.name, bounds };

  if (ref.kind === 'series')
    return Array.isArray(ref.parts) && ref.parts.length
      ? ({ ...head, parts: ref.parts } as SeriesRef)
      : null;
  if (ref.kind === 'raster') return { ...head, parts: [{ kind: 'raster', key: ref.key }] };
  if (ref.kind === 'sheets')
    return ref.collection
      ? { ...head, parts: [{ kind: 'sheets', collection: ref.collection }] }
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
 * that row, when this is the first half seen.
 *
 * The archive contributes its own raster part whether or not the reader had it
 * saved, so someone who kept only the nine warped city sheets gets the mosaic
 * back under them: a survey goes on the map whole, which is the property every
 * other path here defends. It cannot work the other way — a raster row does not
 * carry the collection name the sheets half needs — so a reader who kept only
 * the mosaic keeps only the mosaic.
 */
function merge(
  key: string,
  archive: RasterSeries | undefined,
  into: SeriesRef | null,
  ref: SeriesRef
): SeriesRef {
  const parts: SeriesPart[] = [];
  if (archive) parts.push({ kind: 'raster', key: archive.key });
  // Raster under, warped sheets over, and one of each: the sheets are a sharper
  // survey of the ground the archive is missing and belong above its pixels.
  for (const p of [...(into?.parts ?? []), ...ref.parts])
    if (!parts.some((q) => q.kind === p.kind)) parts.push(p);
  return {
    kind: 'series',
    mapId: `series:${key}`,
    key,
    // The archive names the survey it is half of: that is what the /explore row
    // is called, and a row the reader cannot match to the list reads as a
    // different layer.
    name: archive?.name ?? into?.name ?? ref.name,
    parts,
    bounds: [into?.bounds, ref.bounds, archive?.bounds]
      .filter((b): b is [number, number, number, number] => !!b)
      .reduce(union),
  };
}

/**
 * Put a restored stack back together as one row per survey.
 *
 * A stack saved before Sept 2026 holds L7014 as two rows — the mosaic and the
 * nine warped city sheets — each with its own opacity slider, eye and ×, for
 * one survey. This is what makes them the single row they are added as today,
 * in the higher of the two positions and keeping that row's opacity and
 * visibility. It also canonicalises the id of a survey stored on its own, so a
 * restored row is the *same* row the /explore list offers rather than a second
 * one that draws the same pixels.
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
    const archive = archiveFor(o.ref.key);
    const key = archive?.key ?? o.ref.key;
    const at = seen.get(key);
    if (at === undefined) {
      seen.set(key, out.length);
      out.push({ ...o, ref: merge(key, archive, null, o.ref) });
    } else {
      // The row already standing is the higher of the two, so it keeps its
      // place, its opacity and its eye; this half only adds what it carries.
      out[at] = { ...out[at], ref: merge(key, archive, out[at].ref as SeriesRef, o.ref) };
    }
  }
  return out;
}
