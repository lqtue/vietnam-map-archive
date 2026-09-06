/**
 * triagePrefs.ts — per-map localStorage for the /scan?mode=triage page.
 *
 * Two independent records, both keyed by map id:
 *   digitalize-triage-<mapId>  neatline + tile grid + per-tile overrides
 *   digitalize-seg-<mapId>     MapSAM2 command configuration
 *
 * Keys and stored shapes are deliberately unchanged from the inline version so
 * existing per-map state survives this refactor. (They predate the `vma-*-v1`
 * convention; renaming them is a separate migration.) `runId` and
 * `minConfidence` are per-run choices and stay out of storage, as before.
 *
 * localStorage is the working draft — it autosaves on every edit and never
 * leaves the browser. `maps.triage` (migration 069) is the deliberate save: a
 * person pressing the button is asserting "this sheet is triaged", and that is
 * what `scripts/enqueue_ocr_all.mjs` reads when it decides what to queue. Both
 * carry the same `StoredTriage` shape so neither has to translate.
 */

import { readJson, writeJson } from '$lib/core/utils/persistence/storage';
import type { TileOverrides } from './tileParams';
import { DEFAULT_SEG_CONFIG, type SegConfig } from './segCommand';
import type { StoredTriage } from '$lib/data/maps/types';
import type { LayoutRegion } from '$lib/data/maps/triageTypes';

/** Everything the Triage phase edits, shared between its sidebar and the canvas. */
export type TriageState = {
  neatline: [number, number, number, number] | null;
  tileSize: number;
  overlap: number;
  runId: string;
  minConfidence: number;
  tileOverrides: TileOverrides;
  /** What the sheet is made of. Empty until the layout pass runs or someone
   *  draws one by hand. */
  regions: LayoutRegion[];
};

export function defaultTriageState(): TriageState {
  return {
    neatline: null,
    tileSize: 2400,
    overlap: 300,
    runId: '',
    minConfidence: 0.5,
    tileOverrides: {},
    regions: [],
  };
}

// The on-disk shape is domain, not screen — it lives in `data/maps/types.ts`
// because `fetchLabelMaps` and the enqueue script both read it.
export type { StoredTriage };

/** The saved shape, from whichever store it came out of. */
export function toStoredTriage(state: TriageState): StoredTriage | null {
  if (!state.neatline) return null;
  return {
    neatline: state.neatline,
    tile_size: state.tileSize,
    overlap: state.overlap,
    tile_overrides: state.tileOverrides,
    ...(state.regions.length ? { regions: state.regions } : {}),
  };
}

/** `base` with a stored record applied over it. Shared by both stores. */
export function applyStoredTriage(
  data: Partial<StoredTriage> | null,
  base: TriageState
): TriageState {
  if (!data) return base;
  return {
    ...base,
    ...(Array.isArray(data.neatline) && data.neatline.length === 4
      ? { neatline: data.neatline }
      : {}),
    ...(data.tile_size ? { tileSize: data.tile_size } : {}),
    ...(data.overlap ? { overlap: data.overlap } : {}),
    ...(data.tile_overrides ? { tileOverrides: data.tile_overrides } : {}),
    ...(Array.isArray(data.regions) ? { regions: data.regions } : {}),
  };
}

const triageKey = (mapId: string) => `digitalize-triage-${mapId}`;
const segKey = (mapId: string) => `digitalize-seg-${mapId}`;

/** `base` with any well-formed stored fields applied over it. */
export function loadTriageState(mapId: string, base: TriageState): TriageState {
  return applyStoredTriage(readJson<Partial<StoredTriage> | null>(triageKey(mapId), null), base);
}

export function saveTriageState(mapId: string, state: TriageState): void {
  const stored = toStoredTriage(state);
  if (stored) writeJson(triageKey(mapId), stored);
}

/**
 * Write the triage to `maps.triage`, so the enqueue script can see it.
 * Throws with the server's message, which the sidebar shows verbatim.
 */
export async function saveTriageToServer(mapId: string, state: TriageState): Promise<void> {
  const stored = toStoredTriage(state);
  if (!stored) throw new Error('Draw a neatline before saving.');
  const res = await fetch(`/api/admin/maps/${mapId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ triage: { ...stored, saved_at: new Date().toISOString() } }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? res.statusText);
  }
}

/** `base` with any stored MapSAM2 config applied over it. */
export function loadSegConfig(mapId: string, base: SegConfig = DEFAULT_SEG_CONFIG): SegConfig {
  const data = readJson<Partial<SegConfig> | null>(segKey(mapId), null);
  if (!data) return { ...base };
  return {
    ...base,
    ...(data.checkpointPath ? { checkpointPath: data.checkpointPath } : {}),
    ...(data.mapsam2Dir ? { mapsam2Dir: data.mapsam2Dir } : {}),
    ...(data.encoder ? { encoder: data.encoder } : {}),
    ...(typeof data.useTextMask === 'boolean' ? { useTextMask: data.useTextMask } : {}),
    ...(typeof data.useWatershed === 'boolean' ? { useWatershed: data.useWatershed } : {}),
  };
}

export function saveSegConfig(mapId: string, cfg: SegConfig): void {
  writeJson(segKey(mapId), cfg);
}
