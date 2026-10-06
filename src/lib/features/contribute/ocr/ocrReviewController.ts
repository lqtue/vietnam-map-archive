/**
 * ocrReviewController.ts — the OCR-review half of /scan?mode=text.
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
import { foldAngle, obbFromRow, obbToRow, type ObbRow } from '$lib/core/geo/rectUtils';
import { type OcrStatus } from '../shared/ocrApi';
import { OcrDraftSession } from './ocrDraftSession';
import type { OcrExtraction } from '../shared/types';

export type OcrReviewState = {
  extractions: OcrExtraction[];
  visibleIds: Set<string>;
  filterReady: boolean;
  selectedId: string | null;
  selectedIds: string[];
  groupingAvailable: boolean;
  drawMode: boolean;
  isolationMode: boolean;
  saving: boolean;
  error: string;
  dirtyCount: number;
  notice: string;
};

export type OcrReviewHooks = {
  /** Current map, or null when none is selected. Every write is a no-op without it. */
  getMapId: () => string | null;
  getUserId?: () => string | null;
  /** Run id a new manual bbox should join (the sidebar's current run). */
  getRunId: () => string;
  /** Ask the sidebar to reload its table after a write. */
  reload: () => void | Promise<void>;
  /** Ask the sidebar to scroll to a row; `focusInput` false leaves the keyboard alone. */
  focusRow: (id: string, focusInput?: boolean) => void;
  /** Zoom the canvas to an image-space rect. */
  fitTo: (x: number, y: number, w: number, h: number) => void;
  /** Bring an image-space rect into view without changing the zoom. */
  panTo: (x: number, y: number, w: number, h: number) => void;
  /** Write one row's status through the sidebar, so its table stays the one copy. */
  setRowStatus: (id: string, status: OcrStatus) => void | Promise<void>;
};

const EMPTY: OcrReviewState = {
  extractions: [],
  visibleIds: new Set(),
  filterReady: false,
  selectedId: null,
  selectedIds: [],
  groupingAvailable: false,
  drawMode: false,
  isolationMode: false,
  saving: false,
  error: '',
  dirtyCount: 0,
  notice: '',
};

export function createOcrReview(hooks: OcrReviewHooks) {
  const store = writable<OcrReviewState>({ ...EMPTY });
  const { subscribe, update } = store;

  let session = new OcrDraftSession();
  let activeMap = '';
  let activeUser = 'local';
  let cacheTimer: ReturnType<typeof setTimeout> | undefined;
  const cacheKey = () => `vma-ocr-drafts-v1:${activeUser}:${activeMap}`;
  function persist() {
    if (cacheTimer) clearTimeout(cacheTimer);
    cacheTimer = undefined;
    if (!activeMap || typeof localStorage === 'undefined') return;
    try {
      if (session.dirtyIds().size)
        localStorage.setItem(cacheKey(), JSON.stringify(session.snapshot()));
      else localStorage.removeItem(cacheKey());
    } catch {
      update((s) => ({
        ...s,
        error:
          'Draft cache could not be saved on this device. Keep this page open until Save succeeds.',
      }));
    }
  }
  function publish(cache = true) {
    const dirty = session.dirtyIds();
    session.rows = session.rows.map((r) =>
      r._draft === dirty.has(r.id) ? r : { ...r, _draft: dirty.has(r.id) }
    );
    update((s) => ({
      ...s,
      extractions: session.rows,
      dirtyCount: dirty.size,
      selectedId: s.selectedId ? session.resolveId(s.selectedId) : null,
      selectedIds: s.selectedIds.map((id) => session.resolveId(id)),
    }));
    if (cache) {
      if (cacheTimer) clearTimeout(cacheTimer);
      cacheTimer = setTimeout(persist, 200);
    }
  }
  function reset() {
    persist();
    session = new OcrDraftSession();
    activeMap = '';
    update((s) => ({
      ...EMPTY,
      drawMode: s.drawMode,
      isolationMode: s.isolationMode,
      visibleIds: new Set(),
      filterReady: false,
    }));
  }
  function loaded(e: CustomEvent<{ extractions: OcrExtraction[]; groupingAvailable?: boolean }>) {
    const mapId = hooks.getMapId();
    if (!mapId) return;
    const userId = hooks.getUserId?.() ?? 'local';
    if (activeMap !== mapId || activeUser !== userId) {
      persist();
      session = new OcrDraftSession();
      activeMap = mapId;
      activeUser = userId;
      if (typeof localStorage !== 'undefined') {
        try {
          const cached = localStorage.getItem(cacheKey());
          if (cached) session.restore(JSON.parse(cached));
        } catch {
          update((s) => ({ ...s, error: 'Could not restore the local OCR draft cache.' }));
        }
      }
    }
    session.load(e.detail.extractions);
    publish();
    update((s) => ({
      ...s,
      groupingAvailable: e.detail.groupingAvailable ?? false,
      selectedId: session.rows.some((r) => r.id === s.selectedId) ? s.selectedId : null,
      selectedIds: s.selectedIds.filter((id) => session.rows.some((r) => r.id === id)),
      error: session.conflicts.length
        ? `${session.conflicts.length} drafted labels changed on the server. Drafts were kept; resolve before saving.`
        : s.error,
    }));
  }
  function stage(id: string, patch: Partial<import('../shared/types').EditableOcrExtraction>) {
    if (get(store).saving) return;
    session.stage(id, patch);
    publish();
  }
  async function saveAll() {
    const mapId = hooks.getMapId();
    if (!mapId || get(store).saving || !session.dirtyIds().size) return;
    update((s) => ({ ...s, saving: true, error: '', notice: '' }));
    try {
      const count = await session.flush(mapId, () => {
        publish(false);
        persist();
      });
      update((s) => ({
        ...s,
        notice: `Saved ${count} change${count === 1 ? '' : 's'}.`,
        selectedId: session.rows.some((r) => r.id === s.selectedId) ? s.selectedId : null,
        selectedIds: s.selectedIds.filter((id) => session.rows.some((r) => r.id === id)),
      }));
    } catch (err: any) {
      update((s) => ({ ...s, error: `${err.message} Unsaved work remains in the draft cache.` }));
    } finally {
      publish(false);
      persist();
      update((s) => ({ ...s, saving: false }));
    }
  }
  function discard() {
    if (get(store).saving) return;
    session.discard();
    publish(false);
    persist();
    update((s) => ({ ...s, error: '', notice: '', selectedId: null, selectedIds: [] }));
  }
  function destroy() {
    persist();
  }

  /**
   * Canvas or row click. It deliberately does NOT focus the row's text input:
   * that put the keyboard in a text field, so every shortcut (r, v, x, j, k)
   * typed a character instead of firing. `e` is how you get to the text.
   */
  function select(e: CustomEvent<{ id: string; additive?: boolean }>) {
    const s = get(store);
    const row = s.extractions.find((r) => r.id === e.detail.id);
    const id = row?.text_group_id ?? e.detail.id;
    const ids = e.detail.additive
      ? s.selectedIds.includes(id)
        ? s.selectedIds.filter((v) => v !== id)
        : [...s.selectedIds, id]
      : [id];
    const selectedId = ids.at(-1) ?? null;
    update((st) => ({ ...st, selectedId, selectedIds: ids }));
    if (selectedId) {
      reveal(selectedId);
      hooks.focusRow(selectedId, false);
    }
  }

  /** Pans the canvas only when the bbox is off screen, so a click never jumps. */
  function reveal(id: string) {
    const ext = get(store).extractions.find((ex) => ex.id === id);
    if (ext) hooks.panTo(ext.global_x, ext.global_y, ext.global_w, ext.global_h);
  }

  /**
   * Moves the selection through the rows the sidebar shows, in its sort order —
   * `visibleIds` is built from that list and a Set keeps insertion order. Wraps
   * at both ends; with nothing selected, forward starts at the top and back at
   * the bottom. Leaves the keyboard on the canvas.
   */
  function step(delta: number) {
    const s = get(store);
    const ids = s.filterReady
      ? [...s.visibleIds]
      : s.extractions.filter((ex) => !ex.text_group_id).map((ex) => ex.id);
    if (!ids.length) return;
    const at = s.selectedId ? ids.indexOf(s.selectedId) : -1;
    const to = at < 0 ? (delta > 0 ? 0 : ids.length - 1) : (at + delta + ids.length) % ids.length;
    const id = ids[to];
    update((st) => ({ ...st, selectedId: id, selectedIds: [id] }));
    reveal(id);
    hooks.focusRow(id, false);
  }

  /**
   * Keyboard validate / reject. Pressing the same one twice returns the row to
   * pending, like the panel's buttons. It stages the shared working copy; Save
   * is the only write boundary.
   */
  function setStatus(status: OcrStatus, advance = false) {
    const s = get(store);
    if (s.saving || s.selectedIds.length > 1) return;
    const id = s.selectedId;
    const ext = id ? s.extractions.find((ex) => ex.id === id) : null;
    if (!id || !ext) return;
    const next: OcrStatus = (ext._editStatus ?? ext.status) === status ? 'pending' : status;
    stage(id, { _editStatus: next });
    void hooks.setRowStatus(id, next);
    if (advance) step(1);
  }

  function filter(e: CustomEvent<{ extractions: OcrExtraction[] }>) {
    const ids = new Set(e.detail.extractions.map((ex) => ex.id));
    const s = get(store);
    if (s.filterReady && [...ids].join('|') === [...s.visibleIds].join('|')) return;
    update((s) => ({ ...s, visibleIds: ids, filterReady: true }));
  }

  function zoom(
    e: CustomEvent<{ globalX: number; globalY: number; globalW: number; globalH: number }>
  ) {
    const { globalX, globalY, globalW, globalH } = e.detail;
    hooks.fitTo(globalX, globalY, globalW, globalH);
  }

  /**
   * Every geometry edit — move, resize, turn — arrives here as the label's own
   * rectangle plus the axis-aligned box around it (see `obbToRow`). Optimistic:
   * the canvas has already drawn it by the time this fires.
   */
  function edit(e: CustomEvent<{ id: string } & Required<ObbRow>>) {
    const { id, ...cols } = e.detail;
    stage(id, cols);
  }

  /**
   * Angle-only edit for the keyboard and the panel's reset. Nothing but `deg`
   * changes, so the label keeps its size and the box is rebuilt around it.
   */
  function turnSelected(deg: number) {
    const ext = selected();
    if (!ext || ext.is_text_group) return;
    const obb = obbFromRow(ext);
    void edit(
      new CustomEvent('edit', {
        detail: { id: ext.id, ...obbToRow({ ...obb, deg: foldAngle(deg) }) },
      })
    );
  }

  /** Keyboard fine-tune of the selected label's angle, in degrees. */
  function nudgeRotation(delta: number) {
    const ext = selected();
    if (ext) turnSelected(obbFromRow(ext).deg + delta);
  }

  function selected(): OcrExtraction | null {
    const s = get(store);
    return (s.selectedId && s.extractions.find((ex) => ex.id === s.selectedId)) || null;
  }

  function draw(e: CustomEvent<Required<ObbRow>>) {
    if (!hooks.getMapId() || get(store).saving) return;
    const cols = e.detail;
    const id = crypto.randomUUID();
    session.add({
      id,
      run_id: hooks.getRunId(),
      tile_x: Math.round(cols.global_x),
      tile_y: Math.round(cols.global_y),
      tile_w: 0,
      tile_h: 0,
      ...cols,
      category: 'other',
      text: '',
      text_validated: null,
      category_validated: null,
      confidence: 1,
      status: 'pending',
    });
    publish();
    update((s) => ({ ...s, drawMode: false, selectedId: id, selectedIds: [id] }));
  }
  function duplicate(e: CustomEvent<{ text: string; category: string }>) {
    const source = selected();
    if (!source || source.is_text_group || get(store).saving) return;
    const obb = obbFromRow(source);
    const offset = Math.max(4, Math.min(obb.w, obb.h) / 4);
    draw(
      new CustomEvent('draw', {
        detail: obbToRow({ ...obb, cx: obb.cx + offset, cy: obb.cy + offset }),
      })
    );
    const id = get(store).selectedId;
    if (id)
      stage(id, {
        run_id: source.run_id || hooks.getRunId(),
        _editText: e.detail.text,
        _editCategory: e.detail.category,
      });
  }
  /** The floating editor stages the same fields as the table. */
  function save(e: CustomEvent<{ status: OcrStatus; text: string; category: string }>) {
    const id = get(store).selectedId;
    if (id)
      stage(id, {
        _editText: e.detail.text,
        _editCategory: e.detail.category,
        _editStatus: e.detail.status,
      });
  }

  function deselect() {
    update((s) => ({ ...s, selectedId: null, selectedIds: [] }));
  }

  /** Turning draw mode on clears the selection so the panel gets out of the way. */
  function toggleDraw() {
    update((s) => {
      const drawMode = !s.drawMode;
      return {
        ...s,
        drawMode,
        selectedId: drawMode ? null : s.selectedId,
        selectedIds: drawMode ? [] : s.selectedIds,
      };
    });
  }

  function cancelDraw() {
    update((s) => (s.drawMode ? { ...s, drawMode: false } : s));
  }

  function toggleIsolation() {
    update((s) => ({ ...s, isolationMode: !s.isolationMode }));
  }

  function group(e: CustomEvent<{ text: string; category: string }>) {
    const s = get(store);
    if (!hooks.getMapId() || !s.groupingAvailable || s.saving) return;
    try {
      const id = session.group(s.selectedIds, e.detail.text, e.detail.category);
      publish();
      update((st) => ({ ...st, selectedId: id, selectedIds: [id] }));
    } catch (err: any) {
      update((st) => ({ ...st, error: err.message }));
    }
  }
  function ungroup() {
    const s = get(store);
    if (!s.selectedId || s.saving) return;
    const part = session.rows.find((r) => r.text_group_id === s.selectedId);
    session.ungroup(s.selectedId);
    publish();
    update((st) => ({ ...st, selectedId: part?.id ?? null, selectedIds: part ? [part.id] : [] }));
  }

  return {
    subscribe,
    stage,
    saveAll,
    discard,
    persist,
    destroy,
    group,
    ungroup,
    reset,
    loaded,
    select,
    step,
    setStatus,
    filter,
    zoom,
    edit,
    nudgeRotation,
    turnSelected,
    draw,
    duplicate,
    save,
    deselect,
    toggleDraw,
    cancelDraw,
    toggleIsolation,
  };
}

export type OcrReviewController = ReturnType<typeof createOcrReview>;
