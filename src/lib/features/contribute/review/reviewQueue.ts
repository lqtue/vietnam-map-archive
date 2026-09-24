/**
 * reviewQueue.ts — the validating half of /scan?mode=shapes.
 *
 * The machine's shapes waiting on a person: which sheets have any, the ones on
 * the open sheet, and the approve / reject write. Geometry and type edits are
 * held until the verdict — a reviewer nudging a corner has not decided yet —
 * and applied in the same PATCH.
 *
 * Usage:
 *   const queue = createReviewQueue({ supabase });
 *   $queue.footprints   // in markup
 */

import { get, writable } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import {
  fetchMapsWithSubmittedFootprints,
  fetchSubmittedFootprints,
  type SamFootprint,
} from '$lib/data/supabase/footprints';
import type { FeatureType } from '$lib/data/maps/footprintTypes';
import { resolveMapIiifInfoUrl } from '$lib/features/contribute/shared/iiifSource';

export type QueueRow = Awaited<ReturnType<typeof fetchMapsWithSubmittedFootprints>>[number];

/** What a reviewer can decide. `submitted` is an inbox, not a verdict — sending
    it here left the row exactly as it was and never reached `approved`, which
    is the state /api/export/footprints filters on (migration 090). */
export type Verdict = 'approved' | 'rejected';
export type ReviewFeedback = { tags: string[]; note: string };

export type ReviewQueueState = {
  /** Sheets with shapes waiting, newest count first. */
  queue: QueueRow[];
  queueError: string;
  /** The open sheet's waiting shapes. */
  footprints: SamFootprint[];
  selectedId: string | null;
  /** Every row in the current selection, `selectedId` included. Multi-select is
      the common case on a sheet whose polygons are all the same verdict. */
  selectedIds: string[];
  /** How many were waiting when the sheet opened — the denominator of the progress pill. */
  total: number;
  loading: boolean;
  error: string;
  /** Id currently being written, so its row can say so. */
  deciding: string | null;
  feedback: ReviewFeedback;
  /** The open sheet's IIIF base (no `/info.json`) and pixel dimensions, for the
   *  sidebar's ink crops. Resolved once per `open()`; null/0 until it lands, or
   *  if it can't be resolved at all — the crop just stays unmounted. */
  iiifBase: string | null;
  imageWidth: number;
  imageHeight: number;
};

const EMPTY: ReviewQueueState = {
  queue: [],
  queueError: '',
  footprints: [],
  selectedId: null,
  selectedIds: [],
  total: 0,
  loading: false,
  error: '',
  deciding: null,
  feedback: { tags: [], note: '' },
  iiifBase: null,
  imageWidth: 0,
  imageHeight: 0,
};

export function createReviewQueue(supabase: SupabaseClient<Database>) {
  const store = writable<ReviewQueueState>({ ...EMPTY });
  const { subscribe, update } = store;

  /** Held until the verdict, then sent with it. */
  let pendingEdits: Record<string, { pixelPolygon?: [number, number][]; featureType?: string }> =
    {};
  let pendingFeedback: Record<string, ReviewFeedback> = {};

  async function loadQueue() {
    try {
      const queue = await fetchMapsWithSubmittedFootprints(supabase);
      update((s) => ({ ...s, queue, queueError: '' }));
    } catch (e: any) {
      update((s) => ({ ...s, queueError: e.message }));
    }
  }

  /** Guards `loadImageInfo` against a sheet switch outrunning its own fetch —
   *  bumped by every `reset()`, so a resolve that lands after the next `open()`
   *  is a no-op instead of stamping the wrong sheet's dimensions in. */
  let imgSeq = 0;

  /** Drop the open sheet's rows; the queue itself survives a sheet change. */
  function reset() {
    pendingEdits = {};
    pendingFeedback = {};
    imgSeq++;
    update((s) => ({ ...EMPTY, queue: s.queue, queueError: s.queueError }));
  }

  async function open(mapId: string) {
    reset();
    const seq = imgSeq;
    update((s) => ({ ...s, loading: true }));
    try {
      const footprints = await fetchSubmittedFootprints(supabase, mapId);
      update((s) => ({
        ...s,
        footprints,
        total: footprints.length,
        selectedId: footprints[0]?.id ?? null,
        selectedIds: footprints[0] ? [footprints[0].id] : [],
      }));
      void loadImageInfo(mapId, seq);
    } catch (e: any) {
      update((s) => ({ ...s, error: e.message }));
    } finally {
      update((s) => ({ ...s, loading: false }));
    }
  }

  /**
   * The sidebar's ink crops need the sheet's own pixel dimensions, to size the
   * edge tiles correctly — the footprint rows don't carry them. Resolved from
   * the same `info.json` ImageShell already fetches for the canvas; a second
   * small request rather than threading the value through props from there.
   */
  async function loadImageInfo(mapId: string, seq: number) {
    const row = get(store).queue.find((m) => m.id === mapId);
    const infoUrl = await resolveMapIiifInfoUrl(row ?? null).catch(() => null);
    if (!infoUrl || seq !== imgSeq) return;
    try {
      const res = await fetch(infoUrl);
      if (!res.ok || seq !== imgSeq) return;
      const info = await res.json();
      if (seq !== imgSeq) return;
      update((s) => ({
        ...s,
        iiifBase: infoUrl.replace(/\/info\.json$/, ''),
        imageWidth: info.width ?? 0,
        imageHeight: info.height ?? 0,
      }));
    } catch {
      // Leave iiifBase null — the crop just stays unmounted, never wrong.
    }
  }

  /**
   * Plain click replaces the selection, ctrl/cmd toggles one row, shift extends
   * from the last anchor — the list convention everywhere else, so nobody has
   * to be told. The anchor is `selectedId`, which stays the row whose editor is
   * open.
   */
  function select(id: string | null, mode: 'replace' | 'toggle' | 'range' = 'replace') {
    update((s) => {
      if (id === null)
        return { ...s, selectedId: null, selectedIds: [], feedback: { tags: [], note: '' } };

      if (mode === 'toggle') {
        const has = s.selectedIds.includes(id);
        const selectedIds = has ? s.selectedIds.filter((x) => x !== id) : [...s.selectedIds, id];
        // Deselecting the anchor hands the anchor to whatever is still selected.
        const selectedId = has && s.selectedId === id ? (selectedIds[0] ?? null) : id;
        return {
          ...s,
          selectedId,
          selectedIds,
          feedback: pendingFeedback[selectedId ?? ''] ?? { tags: [], note: '' },
        };
      }

      if (mode === 'range' && s.selectedId) {
        const from = s.footprints.findIndex((f) => f.id === s.selectedId);
        const to = s.footprints.findIndex((f) => f.id === id);
        if (from !== -1 && to !== -1) {
          const [lo, hi] = from < to ? [from, to] : [to, from];
          // The anchor does not move on a shift-click, so the next one extends
          // from the same place rather than walking down the list.
          return {
            ...s,
            selectedIds: s.footprints.slice(lo, hi + 1).map((f) => f.id),
            feedback: pendingFeedback[s.selectedId] ?? { tags: [], note: '' },
          };
        }
      }

      return {
        ...s,
        selectedId: id,
        selectedIds: [id],
        feedback: pendingFeedback[id] ?? { tags: [], note: '' },
      };
    });
  }

  function setFeedback(id: string, feedback: ReviewFeedback) {
    pendingFeedback[id] = feedback;
    update((s) => (s.selectedId === id ? { ...s, feedback } : s));
  }

  function selectAll() {
    update((s) => ({
      ...s,
      selectedIds: s.footprints.map((f) => f.id),
      selectedId: s.selectedId ?? s.footprints[0]?.id ?? null,
    }));
  }

  function clearSelection() {
    update((s) => ({ ...s, selectedIds: s.selectedId ? [s.selectedId] : [] }));
  }

  function edit(id: string, pixelPolygon: [number, number][]) {
    pendingEdits[id] = { ...pendingEdits[id], pixelPolygon };
  }

  function retype(id: string, featureType: string) {
    pendingEdits[id] = { ...pendingEdits[id], featureType };
    // Local too, so the sidebar swatch follows the choice before the verdict.
    update((s) => ({
      ...s,
      footprints: s.footprints.map((f) =>
        f.id === id ? { ...f, featureType: featureType as FeatureType } : f
      ),
    }));
  }

  /** One PATCH. Returns the server's message on failure, null on success. */
  async function writeVerdict(id: string, status: Verdict): Promise<string | null> {
    const edits = pendingEdits[id];
    const body: Record<string, any> = { id, status };
    if (edits?.pixelPolygon) body.pixel_polygon = edits.pixelPolygon;
    if (edits?.featureType) body.feature_type = edits.featureType;
    const feedback = pendingFeedback[id];
    if (feedback?.tags.length) body.review_tags = feedback.tags;
    if (feedback?.note.trim()) body.review_note = feedback.note.trim();

    const res = await fetch('/api/admin/footprints', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const { message } = await res.json().catch(() => ({ message: res.statusText }));
      return message as string;
    }
    delete pendingEdits[id];
    delete pendingFeedback[id];
    return null;
  }

  /** Drop decided rows from the list, the selection and the rail's count. */
  function forget(mapId: string, ids: string[]) {
    const gone = new Set(ids);
    update((s) => {
      const idx = s.footprints.findIndex((f) => gone.has(f.id));
      const footprints = s.footprints.filter((f) => !gone.has(f.id));
      const selectedId =
        s.footprints[idx] && gone.has(s.footprints[idx].id)
          ? (footprints[idx]?.id ?? footprints[idx - 1]?.id ?? null)
          : s.selectedId;
      return {
        ...s,
        footprints,
        selectedId,
        selectedIds: selectedId ? [selectedId] : [],
        feedback: pendingFeedback[selectedId ?? ''] ?? { tags: [], note: '' },
        // Keep the rail's count honest without re-querying the whole queue.
        queue: s.queue.map((m) =>
          m.id === mapId ? { ...m, pendingCount: Math.max(0, m.pendingCount - ids.length) } : m
        ),
      };
    });
  }

  async function decide(mapId: string, id: string, status: Verdict) {
    update((s) => ({ ...s, deciding: id, error: '' }));
    try {
      const message = await writeVerdict(id, status);
      if (message) {
        update((s) => ({
          ...s,
          error: `Could not ${status === 'rejected' ? 'reject' : 'approve'}: ${message}`,
        }));
        return;
      }
      forget(mapId, [id]);
    } finally {
      update((s) => ({ ...s, deciding: null }));
    }
  }

  /**
   * The same verdict over the whole selection. Sequential on purpose: each row
   * is one PATCH and one RPC, the counts stay legible while it runs, and a
   * sheet's queue is tens of rows rather than thousands.
   *
   * ponytail: serial writes, batch the ids into one endpoint if a sheet ever
   * arrives with thousands of polygons.
   */
  async function decideMany(mapId: string, ids: string[], status: Verdict) {
    if (!ids.length) return;
    const done: string[] = [];
    const failures: string[] = [];
    update((s) => ({ ...s, error: '' }));
    for (const id of ids) {
      update((s) => ({ ...s, deciding: id }));
      const message = await writeVerdict(id, status);
      if (message) failures.push(message);
      else done.push(id);
    }
    // Whatever succeeded leaves the queue even when a later row failed, so a
    // retry is over the remainder rather than over everything again.
    if (done.length) forget(mapId, done);
    update((s) => ({
      ...s,
      deciding: null,
      error: failures.length
        ? `${done.length} of ${ids.length} saved; ${failures.length} failed: ${failures[0]}`
        : '',
    }));
  }

  return {
    subscribe,
    loadQueue,
    reset,
    open,
    select,
    selectAll,
    clearSelection,
    edit,
    retype,
    setFeedback,
    decide,
    decideMany,
  };
}
