/**
 * ocrReviewController.ts — the OCR-review half of /scan?mode=triage.
 *
 * Holds the canvas-side state (rows, selection, filter set, draw/isolation
 * toggles, last error) and every write that goes with it, so the route file is
 * left with layout. The sidebar still owns the table and its own loads; the
 * controller reaches back into it through the `reload` / `focusRow` hooks.
 *
 * Usage:
 *   const review = createOcrReview({ … });
 *   $review.extractions   // in markup
 *   on:select={review.select}
 */

import { get, writable } from 'svelte/store';
import { createManualBbox, patchExtraction, type OcrStatus } from '../shared/ocrApi';
import type { OcrExtraction } from '../shared/types';

export type OcrReviewState = {
  extractions: OcrExtraction[];
  visibleIds: Set<string>;
  selectedId: string | null;
  drawMode: boolean;
  isolationMode: boolean;
  saving: boolean;
  error: string;
};

export type OcrReviewHooks = {
  /** Current map, or null when none is selected. Every write is a no-op without it. */
  getMapId: () => string | null;
  /** Run id a new manual bbox should join (the sidebar's current run). */
  getRunId: () => string;
  /** Ask the sidebar to reload its table after a write. */
  reload: () => void;
  /** Ask the sidebar to scroll to + focus a row. */
  focusRow: (id: string) => void;
  /** Zoom the canvas to an image-space rect. */
  fitTo: (x: number, y: number, w: number, h: number) => void;
};

const EMPTY: OcrReviewState = {
  extractions: [],
  visibleIds: new Set(),
  selectedId: null,
  drawMode: false,
  isolationMode: false,
  saving: false,
  error: '',
};

export function createOcrReview(hooks: OcrReviewHooks) {
  const store = writable<OcrReviewState>({ ...EMPTY });
  const { subscribe, update } = store;

  /** Drops rows + selection but keeps the view toggles — used when the map changes. */
  function reset() {
    update((s) => ({
      ...EMPTY,
      drawMode: s.drawMode,
      isolationMode: s.isolationMode,
      visibleIds: new Set(),
    }));
  }

  function loaded(e: CustomEvent<{ extractions: OcrExtraction[] }>) {
    update((s) => ({ ...s, extractions: e.detail.extractions, selectedId: null }));
  }

  function select(e: CustomEvent<{ id: string }>) {
    update((s) => ({ ...s, selectedId: e.detail.id }));
    hooks.focusRow(e.detail.id);
  }

  function filter(e: CustomEvent<{ extractions: OcrExtraction[] }>) {
    const ids = new Set(e.detail.extractions.map((ex) => ex.id));
    update((s) => ({ ...s, visibleIds: ids }));
  }

  function zoom(
    e: CustomEvent<{ globalX: number; globalY: number; globalW: number; globalH: number }>
  ) {
    const { globalX, globalY, globalW, globalH } = e.detail;
    hooks.fitTo(globalX, globalY, globalW, globalH);
  }

  /** Optimistic: the bbox has already moved on the canvas when this fires. */
  async function move(
    e: CustomEvent<{
      id: string;
      global_x: number;
      global_y: number;
      global_w: number;
      global_h: number;
    }>
  ) {
    const mapId = hooks.getMapId();
    if (!mapId) return;
    const { id, global_x, global_y, global_w, global_h } = e.detail;
    update((s) => ({
      ...s,
      extractions: s.extractions.map((ex) =>
        ex.id === id ? { ...ex, global_x, global_y, global_w, global_h } : ex
      ),
    }));
    try {
      await patchExtraction(mapId, { id, global_x, global_y, global_w, global_h });
    } catch (err: any) {
      update((s) => ({ ...s, error: err.message }));
    }
  }

  async function draw(
    e: CustomEvent<{ global_x: number; global_y: number; global_w: number; global_h: number }>
  ) {
    const mapId = hooks.getMapId();
    if (!mapId) return;
    update((s) => ({ ...s, drawMode: false }));
    const { global_x, global_y, global_w, global_h } = e.detail;
    let id: string;
    try {
      id = await createManualBbox(mapId, {
        run_id: hooks.getRunId(),
        global_x,
        global_y,
        global_w,
        global_h,
      });
    } catch (err: any) {
      update((s) => ({ ...s, error: err.message }));
      return;
    }
    // Mirror the server defaults for a manual row (see the ocr-review POST).
    const row: OcrExtraction = {
      id,
      tile_x: Math.round(global_x),
      tile_y: Math.round(global_y),
      tile_w: 0,
      tile_h: 0,
      global_x,
      global_y,
      global_w,
      global_h,
      category: 'other',
      text: '',
      text_validated: null,
      category_validated: null,
      confidence: 1.0,
      status: 'pending',
    };
    update((s) => ({ ...s, extractions: [...s.extractions, row], selectedId: id }));
  }

  /** Writes the bbox panel's buffer back, then refreshes the sidebar. */
  async function save(e: CustomEvent<{ status: OcrStatus; text: string; category: string }>) {
    const mapId = hooks.getMapId();
    const selectedId = get(store).selectedId;
    if (!mapId || !selectedId) return;
    update((s) => ({ ...s, saving: true }));
    const { status, text, category } = e.detail;
    try {
      await patchExtraction(mapId, { id: selectedId, text, category, status });
      update((s) => ({
        ...s,
        extractions: s.extractions.map((ex) =>
          ex.id === selectedId
            ? { ...ex, text_validated: text, category_validated: category, status }
            : ex
        ),
      }));
      hooks.reload();
    } catch (err: any) {
      update((s) => ({ ...s, error: err.message }));
    } finally {
      update((s) => ({ ...s, saving: false }));
    }
  }

  function deselect() {
    update((s) => ({ ...s, selectedId: null }));
  }

  /** Turning draw mode on clears the selection so the panel gets out of the way. */
  function toggleDraw() {
    update((s) => {
      const drawMode = !s.drawMode;
      return { ...s, drawMode, selectedId: drawMode ? null : s.selectedId };
    });
  }

  function cancelDraw() {
    update((s) => (s.drawMode ? { ...s, drawMode: false } : s));
  }

  function toggleIsolation() {
    update((s) => ({ ...s, isolationMode: !s.isolationMode }));
  }

  return {
    subscribe,
    reset,
    loaded,
    select,
    filter,
    zoom,
    move,
    draw,
    save,
    deselect,
    toggleDraw,
    cancelDraw,
    toggleIsolation,
  };
}

export type OcrReviewController = ReturnType<typeof createOcrReview>;
