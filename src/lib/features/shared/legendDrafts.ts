/**
 * Legend drafts for the Legend tab (SheetLegendPanel): an editor's unsaved
 * changes to one entry, how they overlay the loaded row, and the one PATCH
 * that saves them all, and the copy kept in localStorage so a reload doesn't
 * lose them. No Svelte here, so the rules are checkable bare.
 */

import { readJson, writeText } from '$lib/core/utils/persistence/storage';

export type LegendPoint = {
  src?: 'manual' | 'grid' | 'numeral' | null;
  id?: string;
  n: number;
  name: string | null;
  vn: string | null;
  grid: string | null;
  lng: number | null;
  lat: number | null;
  accuracy_m?: number;
};

/** `[west, south, east, north]` in degrees. */
export type Bbox = [number, number, number, number];

const METRES_PER_DEGREE = 111320;

/**
 * The box a row's approximate point could be anywhere in: the point ± its
 * `accuracy_m`, so framing it shows the whole grid cell rather than the
 * cell's middle at street level.
 */
export function accuracyBbox(lng: number, lat: number, accuracyM: number): Bbox {
  const dLat = accuracyM / METRES_PER_DEGREE;
  const dLng = accuracyM / (METRES_PER_DEGREE * Math.cos((lat * Math.PI) / 180));
  return [lng - dLng, lat - dLat, lng + dLng, lat + dLat];
}

/** The place search that led to an entry's point (mig 119 `legend_finds`). */
export type LegendFind = {
  query: string;
  osmType: 'node' | 'way' | 'relation' | null;
  osmId: number | null;
  osmName: string | null;
  lng: number;
  lat: number;
};

export interface LegendDraft {
  id: string;
  name: string;
  vn: string | null;
  grid: string | null;
  lng: number | null;
  lat: number | null;
  coordinateOverride: boolean;
  /** Set when the point was clicked after a Find pick; saved as ground truth for today's place. */
  find?: LegendFind | null;
}

export type DraftFields = {
  name: string;
  vn: string;
  grid: string;
  lng: number | undefined;
  lat: number | undefined;
  coordinateOverride: boolean;
  find?: LegendFind | null;
};

/** The row as it will read once the draft is saved. */
export function applyDraft(point: LegendPoint, draft: LegendDraft): LegendPoint {
  const wasManual = point.src === 'manual';
  return {
    ...point,
    name: draft.name,
    vn: draft.vn,
    grid: draft.grid,
    lng: draft.coordinateOverride ? draft.lng : wasManual ? null : draft.lng,
    lat: draft.coordinateOverride ? draft.lat : wasManual ? null : draft.lat,
    src: draft.coordinateOverride ? 'manual' : wasManual ? null : point.src,
  };
}

/** A draft from the editor's fields, or the reason it can't be one. */
export function toDraft(id: string, f: DraftFields): LegendDraft | string {
  if ([f.name, f.vn, f.grid].some((text) => /[;\r\n]/.test(text)))
    return 'Use plain text without semicolons or line breaks.';
  if (!f.name.trim()) return 'Enter the legend name.';
  const { lng, lat } = f;
  if (
    (lng == null) !== (lat == null) ||
    (lng != null && (!Number.isFinite(lng) || Math.abs(lng) > 180)) ||
    (lat != null && (!Number.isFinite(lat) || Math.abs(lat) > 90))
  )
    return 'Enter both longitude and latitude, or reset the point.';
  return {
    id,
    name: f.name.trim(),
    vn: f.vn.trim() || null,
    grid: f.grid.trim() || null,
    lng: lng ?? null,
    lat: lat ?? null,
    coordinateOverride: f.coordinateOverride && lng != null && lat != null,
    // A search only counts as finding the point while that point is the one kept.
    find: f.coordinateOverride && lng != null && lat != null ? (f.find ?? null) : null,
  };
}

const draftsKey = (mapId: string) => `vma-legend-drafts-v1:${mapId}`;

const text = (v: unknown) => v === null || typeof v === 'string';
const coordinate = (v: unknown) => v === null || (typeof v === 'number' && Number.isFinite(v));

/** Whether something read back from storage is a draft this code could have written. */
function isDraft(v: unknown): v is LegendDraft {
  const d = v as Record<string, unknown> | null;
  return (
    !!d &&
    typeof d === 'object' &&
    typeof d.id === 'string' &&
    typeof d.name === 'string' &&
    text(d.vn) &&
    text(d.grid) &&
    coordinate(d.lng) &&
    coordinate(d.lat) &&
    typeof d.coordinateOverride === 'boolean'
  );
}

function isFind(v: unknown): v is LegendFind {
  const f = v as Record<string, unknown> | null;
  return (
    !!f &&
    typeof f === 'object' &&
    typeof f.query === 'string' &&
    !!f.query &&
    (f.osmType === null || ['node', 'way', 'relation'].includes(f.osmType as string)) &&
    (f.osmId === null || Number.isSafeInteger(f.osmId)) &&
    text(f.osmName) &&
    typeof f.lng === 'number' &&
    typeof f.lat === 'number'
  );
}

/** The drafts kept for this sheet, by entry id; anything malformed is dropped
 *  (a malformed search only loses the search, not the draft). */
function readAllStoredDrafts(mapId: string): Record<string, LegendDraft> {
  const stored = readJson<unknown>(draftsKey(mapId), null);
  const out: Record<string, LegendDraft> = {};
  if (Array.isArray(stored))
    for (const d of stored)
      if (isDraft(d)) out[d.id] = { ...d, find: isFind(d.find) ? d.find : null };
  return out;
}

/** The stored drafts whose entry is still on the sheet. */
export function readStoredDrafts(mapId: string, entryIds: string[]): Record<string, LegendDraft> {
  const live = new Set(entryIds);
  return Object.fromEntries(
    Object.entries(readAllStoredDrafts(mapId)).filter(([id]) => live.has(id))
  );
}

/** Keeps this sheet's drafts; none left removes the key. */
export function writeStoredDrafts(mapId: string, drafts: Record<string, LegendDraft>) {
  const list = Object.values(drafts);
  writeText(draftsKey(mapId), list.length ? JSON.stringify(list) : null);
}

/** Drops saved entries from a sheet's stored drafts, whichever sheet is open now. */
export function forgetStoredDrafts(mapId: string, entryIds: Iterable<string>) {
  const kept = readAllStoredDrafts(mapId);
  for (const id of entryIds) delete kept[id];
  writeStoredDrafts(mapId, kept);
}

/** Saves every draft in one PATCH; throws with the server's message on failure. */
export async function saveDrafts(
  mapId: string,
  drafts: LegendDraft[]
): Promise<{
  saved: Set<string>;
  failed: { id: string; message: string }[];
  /** The entries saved but their search not recorded. */
  warning?: string;
}> {
  const response = await fetch(`/api/admin/maps/${mapId}/legend-points`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      entries: drafts.map((d) => ({
        id: d.id,
        name: d.name,
        vn: d.vn,
        grid: d.grid,
        lng: d.coordinateOverride ? d.lng : null,
        lat: d.coordinateOverride ? d.lat : null,
        find: d.coordinateOverride ? (d.find ?? null) : null,
      })),
    }),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.message ?? result.error ?? 'Could not save the legend drafts.');
  return {
    saved: new Set<string>(result.saved ?? drafts.map((d) => d.id)),
    failed: result.failed ?? [],
    warning: typeof result.warning === 'string' ? result.warning : undefined,
  };
}
