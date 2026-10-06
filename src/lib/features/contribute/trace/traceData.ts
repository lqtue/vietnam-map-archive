/**
 * traceData.ts — the drawing half of /scan?mode=shapes.
 *
 * Every footprint write a person makes by hand: create on draw, reshape on
 * modify, rename/retype from the table, delete. Holds the sheet's shapes and
 * the last error, so the page is left with layout.
 *
 * Usage:
 *   const trace = createTrace({ supabase, userId, getMapId });
 *   $trace.footprints   // in markup
 */

import { get, writable } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import {
  fetchMapFootprints,
  createFootprint,
  updateFootprint,
  updateFootprintMeta,
  deleteFootprint,
} from '$lib/data/supabase/footprints';
import type { FootprintSubmission, PixelCoord, FeatureType } from '$lib/data/maps/footprintTypes';
import { trackMeasurement } from '$lib/data/measurement';

export type TraceState = {
  footprints: FootprintSubmission[];
  /** The id just drawn, for the 150 ms highlight the table plays. */
  newId: string | null;
  error: string;
};

export type TraceHooks = {
  supabase: SupabaseClient<Database>;
  /** Author of anything drawn here; null means signed out, and every write is a no-op. */
  userId: string | null;
  getMapId: () => string | null;
};

export function createTrace({ supabase, userId, getMapId }: TraceHooks) {
  const store = writable<TraceState>({ footprints: [], newId: null, error: '' });
  const { subscribe, update, set } = store;
  let draftPending = false;

  function reset() {
    draftPending = false;
    set({ footprints: [], newId: null, error: '' });
  }

  async function load() {
    const mapId = getMapId();
    if (!mapId) return;
    try {
      const rows = await fetchMapFootprints(supabase, mapId);
      update((s) => ({ ...s, footprints: rows, error: '' }));
    } catch (err: any) {
      update((s) => ({
        ...s,
        footprints: [],
        error: `Couldn't load shapes: ${err?.message ?? err}`,
      }));
    }
  }

  /** `Shape 7` — counted over this person's own shapes, which is what the table lists. */
  function nextName(rows: FootprintSubmission[]) {
    return `Shape ${rows.filter((f) => f.userId === userId).length + 1}`;
  }

  async function draw(pixelPolygon: PixelCoord[], geometry: 'Polygon' | 'LineString') {
    const mapId = getMapId();
    if (!mapId || !userId) return;
    if (pixelPolygon.length < (geometry === 'Polygon' ? 3 : 2)) return;
    if (!draftPending) {
      draftPending = true;
      trackMeasurement('draft_started', {
        surface: 'scan',
        workflow: 'shapes',
        map_id: mapId,
        action: 'submit',
      });
    }
    const name = nextName(get(store).footprints);
    const featureType: FeatureType = geometry === 'LineString' ? 'road' : 'building';
    const id = await createFootprint(supabase, {
      mapId,
      userId,
      pixelPolygon,
      name,
      category: null,
      featureType,
    });
    if (!id) return;
    draftPending = false;
    trackMeasurement('save_success', {
      surface: 'scan',
      workflow: 'shapes',
      map_id: mapId,
      action: 'submit',
    });
    const row: FootprintSubmission = {
      id,
      mapId,
      userId,
      pixelPolygon,
      name,
      category: null,
      featureType,
      status: 'submitted',
    };
    update((s) => ({ ...s, footprints: [...s.footprints, row], newId: id }));
    setTimeout(() => update((s) => (s.newId === id ? { ...s, newId: null } : s)), 150);
  }

  async function modify(footprintId: string, pixelPolygon: PixelCoord[]) {
    if (!(await updateFootprint(supabase, footprintId, pixelPolygon))) return;
    update((s) => ({
      ...s,
      footprints: s.footprints.map((f) => (f.id === footprintId ? { ...f, pixelPolygon } : f)),
    }));
  }

  async function remove(footprintId: string) {
    if (!(await deleteFootprint(supabase, footprintId))) return;
    update((s) => ({ ...s, footprints: s.footprints.filter((f) => f.id !== footprintId) }));
  }

  async function retitle(
    footprintId: string,
    patch: { name?: string; featureType?: FeatureType; category?: string | null }
  ) {
    const ok = await updateFootprintMeta(supabase, footprintId, {
      name: patch.name ?? undefined,
      featureType: patch.featureType ?? undefined,
      category: patch.category !== undefined ? patch.category : undefined,
    });
    if (!ok) return;
    update((s) => ({
      ...s,
      footprints: s.footprints.map((f) => (f.id === footprintId ? { ...f, ...patch } : f)),
    }));
  }

  return { subscribe, reset, load, draw, modify, remove, retitle };
}
