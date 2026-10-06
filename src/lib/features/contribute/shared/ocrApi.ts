/**
 * ocrApi.ts — the single client for `/api/admin/maps/[id]/ocr-review`.
 *
 * Every call throws `Error(<server message>)` on a non-2xx response; callers
 * decide how to surface it. No caller should hand-roll these fetches.
 */

import type { EditableOcrExtraction, OcrExtraction } from './types';

export type OcrStatus = 'pending' | 'validated' | 'rejected';

/** The category a reviewer has accepted takes precedence over the model's guess.
 * Keep this at the data seam so every review surface agrees after a correction. */
export function reviewedCategory(
  row: Pick<OcrExtraction, 'category' | 'category_validated'>
): string {
  return row.category_validated ?? row.category;
}

export type OcrReviewPage = {
  extractions: OcrExtraction[];
  parts?: OcrExtraction[];
  groupingAvailable?: boolean;
  total: number;
  statusCounts: Record<string, number>;
  runIds: string[];
};

/** Fields the PATCH handler accepts alongside the required `id`. */
export type OcrExtractionPatch = {
  id: string;
  text?: string;
  category?: string;
  notes?: string;
  status?: OcrStatus;
  global_x?: number;
  global_y?: number;
  global_w?: number;
  global_h?: number;
  rotation_deg?: number | null;
  label_w?: number | null;
  label_h?: number | null;
};

export type ManualBboxInput = {
  run_id: string;
  global_x: number;
  global_y: number;
  global_w: number;
  global_h: number;
  rotation_deg?: number | null;
  label_w?: number | null;
  label_h?: number | null;
  category?: string;
  text?: string;
};

const JSON_HEADERS = { 'Content-Type': 'application/json' };

/** Reads the server's error text, preferring SvelteKit's `{ message }` body. */
async function errorMessage(res: Response): Promise<string> {
  const body = await res.text().catch(() => '');
  try {
    const parsed = JSON.parse(body);
    if (parsed?.message) return String(parsed.message);
  } catch {
    /* not JSON — fall through to the raw text */
  }
  return body || res.statusText;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(await errorMessage(res));
  return (await res.json()) as T;
}

const base = (mapId: string) => `/api/admin/maps/${mapId}/ocr-review`;

export async function fetchExtractions(
  mapId: string,
  params: {
    status?: string | string[];
    runId?: string;
    limit?: number;
    offset?: number;
    all?: boolean;
  } = {}
): Promise<OcrReviewPage> {
  const qs = new URLSearchParams({ limit: String(params.limit ?? 200) });
  const status = [params.status ?? []].flat().join(',');
  if (status) qs.set('status', status);
  if (params.runId?.trim()) qs.set('run_id', params.runId.trim());
  if (params.offset) qs.set('offset', String(params.offset));
  if (params.all) qs.set('all', 'true');
  const page = await request<OcrReviewPage>(`${base(mapId)}?${qs}`);
  return {
    extractions: page.extractions ?? [],
    parts: page.parts ?? [],
    groupingAvailable: page.groupingAvailable ?? false,
    total: page.total ?? 0,
    statusCounts: page.statusCounts ?? {},
    runIds: page.runIds ?? [],
  };
}

export async function patchExtraction(mapId: string, body: OcrExtractionPatch): Promise<void> {
  await request(base(mapId), {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

/** Bulk status update. Returns the number of rows the server reports changed. */
export async function batchSetStatus(
  mapId: string,
  ids: string[],
  status: OcrStatus
): Promise<number> {
  const data = await request<{ count?: number }>(base(mapId), {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify({ ids, status }),
  });
  return data.count ?? ids.length;
}

/** Reverts rows this user validated in the last `minutes`. Returns the count. */
export async function revertRecent(mapId: string, minutes: number): Promise<number> {
  const data = await request<{ count?: number }>(`${base(mapId)}/revert-recent`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ windowMins: minutes }),
  });
  return data.count ?? 0;
}

/** Creates a hand-drawn bbox (model: 'manual'). Returns the new row's id. */
export async function createManualBbox(mapId: string, body: ManualBboxInput): Promise<string> {
  const data = await request<{ id: string }>(base(mapId), {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
  return data.id;
}

/** Seeds the client-side edit buffer used by the review tables. */
export function withEditState(rows: OcrExtraction[]): EditableOcrExtraction[] {
  return rows.map((e) => ({
    ...e,
    _editText: e.text_validated ?? e.text,
    _editCategory: e.category_validated ?? e.category,
    _editStatus: e.status,
    _saving: false,
  }));
}

/** A review table's two pieces of row state, moved together by the writes below. */
export type RowSaveState = {
  rows: EditableOcrExtraction[];
  statusCounts: Record<string, number>;
};

/**
 * Flags one row as writing, or done writing.
 *
 * The reason this returns a new array instead of setting `row._saving` is the
 * same reason every helper here does: `OcrSidebar` dispatches its row objects
 * to `ocrReviewController`, which keeps them. A row mutated in place changes
 * under the controller without its store ever firing, and once the controller
 * replaces that row immutably the two tables are holding different objects for
 * the same label.
 */
export function markRowSaving(
  rows: EditableOcrExtraction[],
  id: string,
  saving: boolean
): EditableOcrExtraction[] {
  return rows.map((r) => (r.id === id ? { ...r, _saving: saving } : r));
}

/**
 * Writes one row's status and returns the next rows and counts. Throws what
 * `patchExtraction` throws; the caller owns the error line.
 *
 * `filterStatus` is the table's status filter (`''` for all). A status filter
 * is a live query, so a row whose new status leaves it drops out of the list.
 */
export async function saveRowStatus(
  mapId: string,
  state: RowSaveState,
  id: string,
  status: OcrStatus,
  filterStatus: string
): Promise<RowSaveState> {
  const row = state.rows.find((r) => r.id === id);
  if (!row) return state;

  await patchExtraction(mapId, {
    id,
    text: row._editText,
    category: row._editCategory,
    status,
  });

  // Decrement the status the row is leaving, whatever it was. The admin tab's
  // copy of this always decremented `pending`, so validated → rejected drove
  // the pending count down a second time.
  const statusCounts = { ...state.statusCounts };
  statusCounts[status] = (statusCounts[status] ?? 0) + 1;
  statusCounts[row.status] = Math.max(0, (statusCounts[row.status] ?? 1) - 1);

  const validated_at = status === 'validated' ? new Date().toISOString() : null;
  const rows =
    filterStatus && filterStatus !== status
      ? state.rows.filter((r) => r.id !== id)
      : state.rows.map((r) => (r.id === id ? { ...r, status, validated_at } : r));

  return { rows, statusCounts };
}

/**
 * Writes one row's edited text and category, leaving its status alone. Returns
 * the next rows, with the edit buffer promoted to the validated columns.
 */
export async function saveRowText(
  mapId: string,
  rows: EditableOcrExtraction[],
  id: string
): Promise<EditableOcrExtraction[]> {
  const row = rows.find((r) => r.id === id);
  if (!row) return rows;

  await patchExtraction(mapId, {
    id,
    text: row._editText,
    category: row._editCategory,
    status: row.status,
  });

  return rows.map((r) =>
    r.id === id ? { ...r, text_validated: r._editText, category_validated: r._editCategory } : r
  );
}

/** True when a row's text or category has diverged from what is stored. */
export function isTextDirty(row: EditableOcrExtraction): boolean {
  return (
    row._editText !== (row.text_validated ?? row.text) ||
    row._editCategory !== (row.category_validated ?? row.category)
  );
}

/** True when a row holds a draft — an edit or a verdict — that is not saved yet. */
export function isRowDirty(row: EditableOcrExtraction): boolean {
  return isTextDirty(row) || row._editStatus !== row.status;
}

/**
 * Writes every draft at once, the way the legend tool saves its staged entries.
 *
 * A row with a text or category edit goes as one PATCH carrying its verdict too;
 * rows that only changed verdict go as one PUT per status, so fifty ✓ presses
 * are three requests, not fifty. Stops at the first failure and says which rows
 * made it, so the caller keeps the rest as drafts and Save can simply be pressed
 * again. Never throws.
 */
export async function saveDrafts(
  mapId: string,
  rows: EditableOcrExtraction[]
): Promise<{ saved: Set<string>; error: string }> {
  const dirty = rows.filter(isRowDirty);
  const saved = new Set<string>();
  try {
    for (const r of dirty.filter(isTextDirty)) {
      await patchExtraction(mapId, {
        id: r.id,
        text: r._editText,
        category: r._editCategory,
        status: r._editStatus,
      });
      saved.add(r.id);
    }
    const verdictOnly = dirty.filter((r) => !isTextDirty(r));
    for (const status of ['pending', 'validated', 'rejected'] as OcrStatus[]) {
      const ids = verdictOnly.filter((r) => r._editStatus === status).map((r) => r.id);
      if (!ids.length) continue;
      await batchSetStatus(mapId, ids, status);
      for (const id of ids) saved.add(id);
    }
    return { saved, error: '' };
  } catch (e: any) {
    return { saved, error: e.message };
  }
}

/** Rows and counts after `saved` reached the server: those drafts are now what is stored. */
export function promoteSaved(state: RowSaveState, saved: Set<string>): RowSaveState {
  const statusCounts = { ...state.statusCounts };
  const stamp = new Date().toISOString();
  const rows = state.rows.map((r) => {
    if (!saved.has(r.id)) return r;
    if (r._editStatus !== r.status) {
      statusCounts[r._editStatus] = (statusCounts[r._editStatus] ?? 0) + 1;
      statusCounts[r.status] = Math.max(0, (statusCounts[r.status] ?? 1) - 1);
    }
    return {
      ...r,
      status: r._editStatus,
      validated_at: r._editStatus === 'validated' ? stamp : null,
      text_validated: r._editText,
      category_validated: r._editCategory,
    };
  });
  return { rows, statusCounts };
}

/** Ordered original boxes remain attached to a separate combined label. */
export async function groupTextBoxes(
  mapId: string,
  ids: string[],
  text: string,
  category: string
): Promise<string> {
  const data = await request<{ id: string }>(`${base(mapId)}/groups`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ ids, text, category }),
  });
  return data.id;
}
export async function ungroupTextBoxes(mapId: string, id: string): Promise<void> {
  await request(`${base(mapId)}/groups`, {
    method: 'DELETE',
    headers: JSON_HEADERS,
    body: JSON.stringify({ id }),
  });
}
