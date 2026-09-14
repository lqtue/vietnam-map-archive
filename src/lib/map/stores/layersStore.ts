/**
 * layersStore — single source of truth for what the map renders.
 *
 *   base   = exactly one layer at the bottom (modern basemap OR historical map)
 *   overlays = 0..N historical maps on top, each with own opacity + visibility
 *
 * Conventions:
 *   - overlays array is TOP-OF-STACK FIRST (overlays[0] = topmost, displayed at top of UI list)
 *   - z-index when rendering: base = 0, then two per overlay row, bottom-up —
 *     overlays[N-1] = 10, overlays[N-2] = 12, … overlays[0] = 10 + 2(N-1). The
 *     gap is the second half of a two-part series row (LayerRenderer).
 */
import { writable, derived, get, type Readable } from 'svelte/store';
import { browser } from '$app/environment';
import { randomId } from '$lib/core/utils/id';
import { readJson, writeJson } from '$lib/core/utils/persistence/storage';
import { foldLegacyOverlays, isSheetLayer, readOverlayRef } from './overlayKind';

export { isSheetLayer };

export type BasemapRef = { kind: 'basemap'; key: string };
export type HistoricalRef = {
  kind: 'historical';
  mapId: string; // maps.id (uuid)
  allmapsId: string; // annotation source (allmaps id or annotation url)
  name?: string;
  thumbnail?: string;
};
/**
 * A whole survey as one stack row.
 *
 * A survey can reach the map by two routes, and they are complementary rather
 * than alternative: the AMS L7014 is 452 cells pre-tiled into a raster archive
 * on our own tile domain, **plus** 9 `maps` rows warped live by Allmaps — the
 * city sheets the source library published with no georeference attached, which
 * are exactly the ones the mosaic is missing. A reader does not want to hold
 * those two apart, so they are `parts` of one row: one name, one opacity, one
 * eye, one ×, one slot against `MAX_OVERLAYS`. `LayerRenderer` is where a part
 * becomes an OpenLayers layer, and `parts[0]` draws beneath `parts[1]`.
 *
 * It is an overlay rather than a basemap because a series is one thing among
 * the archive's others, not a backdrop: the reader wants it *over* whichever
 * basemap they chose, at an opacity they pick, and where the survey has no
 * sheet the gap should show their basemap rather than punch a hole in the page.
 *
 * `mapId` is synthetic and stable (`series:<key>`). It is not a `maps.id`, and
 * nothing will resolve it in the catalogue — it exists so that the overlay
 * stack's identity, dedupe and removal keep working on one field for every kind
 * of overlay.
 *
 * The sheet list is deliberately **not** stored here. It is resolved from the
 * collection at render time, so the row survives in localStorage as a handful
 * of short fields and a series that gains a sheet does not need the reader to
 * re-add it.
 */
export type SeriesPart =
  /** A pre-warped raster archive, by the key `buildRasterOverlayLayer` knows. */
  | { kind: 'raster'; key: string }
  /** `maps.collection` — the sheets are whatever rows carry this string. */
  | { kind: 'sheets'; collection: string };

export type SeriesRef = {
  kind: 'series';
  mapId: string;
  key: string;
  name: string;
  /** Bottom-up: `parts[0]` is drawn under `parts[1]`. */
  parts: SeriesPart[];
  /** [minLon, minLat, maxLon, maxLat] — what "zoom to this layer" means. */
  bounds: [number, number, number, number];
};

export type LayerRef = BasemapRef | HistoricalRef;
/** Anything that can sit in the overlay stack: one catalogued sheet, or a survey. */
export type OverlayRef = HistoricalRef | SeriesRef;

/** Build a HistoricalRef from a catalogue row. `annotation_url` (R2 mirror) wins over the bare Allmaps id. */
export function toHistoricalRef(map: {
  id: string;
  allmaps_id?: string | null;
  annotation_url?: string | null;
  name?: string | null;
  thumbnail?: string | null;
}): HistoricalRef {
  return {
    kind: 'historical',
    mapId: map.id,
    allmapsId: map.annotation_url ?? map.allmaps_id ?? '',
    name: map.name ?? undefined,
    thumbnail: map.thumbnail ?? undefined,
  };
}

export interface OverlayLayer {
  /** Stable local id (for keyed iteration; survives reorder). */
  id: string;
  ref: OverlayRef;
  opacity: number; // 0..1
  visible: boolean;
}

export interface LayersState {
  base: LayerRef;
  overlays: OverlayLayer[]; // index 0 = topmost
}

const STORAGE_KEY = 'vma-layers-v1';
const DEFAULT_BASE: BasemapRef = { kind: 'basemap', key: 'g-streets' };
const MAX_OVERLAYS = 10;

function load(): LayersState {
  if (!browser) return { base: DEFAULT_BASE, overlays: [] };
  const parsed = readJson<Partial<LayersState> | null>(STORAGE_KEY, null);
  if (!parsed) return { base: DEFAULT_BASE, overlays: [] };
  const base: LayerRef =
    parsed.base?.kind === 'historical' || parsed.base?.kind === 'basemap'
      ? parsed.base
      : DEFAULT_BASE;
  // `readOverlayRef` is both the validator and half the migration: it drops a
  // row it cannot read, and reads the two pre-`series` shapes (`raster`,
  // `sheets`) as one-part series rows. `foldLegacyOverlays` is the other half —
  // it puts the halves of one survey back together as the single row a survey
  // is added as today.
  const overlays: OverlayLayer[] = Array.isArray(parsed.overlays)
    ? parsed.overlays
        .slice(0, MAX_OVERLAYS)
        .map((o: any) => ({
          id: String(o?.id ?? makeId()),
          ref: readOverlayRef(o?.ref),
          opacity: clamp01(typeof o?.opacity === 'number' ? o.opacity : 1),
          visible: o?.visible !== false,
        }))
        .filter((o): o is OverlayLayer => o.ref !== null)
    : [];
  return { base, overlays: foldLegacyOverlays(overlays) };
}

function persist(s: LayersState) {
  if (browser) writeJson(STORAGE_KEY, s);
}

export function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}
const makeId = () => randomId('layer');

function create() {
  const inner = writable<LayersState>(load());
  const { subscribe, update } = inner;

  return {
    subscribe,

    setBase(ref: LayerRef) {
      update((s) => {
        const next = { ...s, base: ref };
        persist(next);
        return next;
      });
    },

    /** Add as topmost overlay. Returns the new layer id; no-op if already present. */
    addOverlay(ref: OverlayRef, opts: { opacity?: number } = {}): string {
      let id = '';
      update((s) => {
        if (s.overlays.some((o) => o.ref.mapId === ref.mapId)) return s;
        if (s.overlays.length >= MAX_OVERLAYS) return s;
        id = makeId();
        const layer: OverlayLayer = {
          id,
          ref,
          opacity: clamp01(opts.opacity ?? 1),
          visible: true,
        };
        const next = { ...s, overlays: [layer, ...s.overlays] };
        persist(next);
        return next;
      });
      return id;
    },

    removeOverlay(id: string) {
      update((s) => {
        const next = { ...s, overlays: s.overlays.filter((o) => o.id !== id) };
        persist(next);
        return next;
      });
    },

    removeOverlayByMapId(mapId: string) {
      update((s) => {
        const next = { ...s, overlays: s.overlays.filter((o) => o.ref.mapId !== mapId) };
        persist(next);
        return next;
      });
    },

    setOpacity(id: string, opacity: number) {
      update((s) => {
        const next = {
          ...s,
          overlays: s.overlays.map((o) => (o.id === id ? { ...o, opacity: clamp01(opacity) } : o)),
        };
        persist(next);
        return next;
      });
    },

    setVisible(id: string, visible: boolean) {
      update((s) => {
        const next = {
          ...s,
          overlays: s.overlays.map((o) => (o.id === id ? { ...o, visible } : o)),
        };
        persist(next);
        return next;
      });
    },

    /** Move overlay at index `from` to index `to`. */
    reorderOverlay(from: number, to: number) {
      update((s) => {
        if (from < 0 || from >= s.overlays.length) return s;
        const arr = s.overlays.slice();
        const [item] = arr.splice(from, 1);
        arr.splice(Math.max(0, Math.min(arr.length, to)), 0, item);
        const next = { ...s, overlays: arr };
        persist(next);
        return next;
      });
    },

    clearOverlays() {
      update((s) => {
        const next = { ...s, overlays: [] };
        persist(next);
        return next;
      });
    },

    isOverlay(mapId: string): boolean {
      return get(inner).overlays.some((o) => o.ref.mapId === mapId);
    },
  };
}

export const layersStore = create();

export const MAX_OVERLAY_LAYERS = MAX_OVERLAYS;

// ── Derived: top overlay ──
// `createGeoMapStores()` mirrors this into the per-instance mapStore's
// activeMapId/activeAllmapsId, which the URL hash + story playback read.
/**
 * Add the map to the overlay stack, or remove it if it's already on.
 * No-op for maps without an annotation source, or when the stack is full.
 * Returns the resulting membership (true = now an overlay).
 */
export function toggleOverlayFor(map: Parameters<typeof toHistoricalRef>[0]): boolean {
  const ref = toHistoricalRef(map);
  if (!ref.allmapsId) return layersStore.isOverlay(ref.mapId);
  if (layersStore.isOverlay(ref.mapId)) {
    layersStore.removeOverlayByMapId(ref.mapId);
    return false;
  }
  if (get(layersStore).overlays.length >= MAX_OVERLAYS) return false;
  layersStore.addOverlay(ref);
  return true;
}

/**
 * The topmost *sheet* on the stack — what `?map=`, the Info rail and story
 * playback all mean by "this sheet". A series row is skipped: it is a whole
 * survey, has no catalogue row, and putting it here would write a `?map=` that
 * resolves to nothing.
 */
export const topOverlay: Readable<HistoricalRef | null> = derived(
  layersStore,
  ($l) => $l.overlays.find(isSheetLayer)?.ref ?? null
);
