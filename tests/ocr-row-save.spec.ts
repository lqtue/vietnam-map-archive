/**
 * One row's status write in the OCR review tables.
 *
 * This ran as two hand-copies — `OcrSidebar.save` and
 * `MapEditPipelineTab.saveReview` — and they had drifted: the admin copy always
 * decremented the `pending` count, so moving a row from validated to rejected
 * took a second bite out of a bucket the row had already left. The counts are
 * what the reviewer reads to decide whether a sheet is done, and a count that
 * drifts low reports a finished queue that is not finished.
 *
 * The other half is aliasing. `OcrSidebar` dispatches its row objects to
 * `ocrReviewController`, which keeps them; the old code then mutated those same
 * objects in place and self-assigned the array to repaint. These cases pin both:
 * the counts move by exactly one each way, and the input array is never touched.
 */
import { test, expect } from '@playwright/test';
import {
  saveRowStatus,
  markRowSaving,
  isRowDirty,
  reviewedCategory,
  type RowSaveState,
} from '../src/lib/features/contribute/shared/ocrApi';
import type { EditableOcrExtraction } from '../src/lib/features/contribute/shared/types';

const row = (
  id: string,
  status: EditableOcrExtraction['status'],
  text = 'Rue Catinat'
): EditableOcrExtraction => ({
  id,
  tile_x: 0,
  tile_y: 0,
  tile_w: 0,
  tile_h: 0,
  global_x: 10,
  global_y: 20,
  global_w: 30,
  global_h: 40,
  category: 'street',
  text,
  text_validated: null,
  category_validated: null,
  confidence: 0.9,
  status,
  _editText: text,
  _editCategory: 'street',
  _saving: false,
});

/** Every PATCH the helper makes, so the body can be asserted without a server. */
let sent: unknown[] = [];

test.beforeEach(() => {
  sent = [];
  globalThis.fetch = (async (_url: string, init?: RequestInit) => {
    sent.push(JSON.parse(String(init?.body)));
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
});

const state = (...rows: EditableOcrExtraction[]): RowSaveState => ({
  rows,
  statusCounts: { pending: 2, validated: 1, rejected: 1 },
});

test('validating a pending row moves one count each way', async () => {
  const next = await saveRowStatus('m1', state(row('a', 'pending')), 'a', 'validated', '');
  expect(next.statusCounts).toEqual({ pending: 1, validated: 2, rejected: 1 });
  expect(next.rows[0].status).toBe('validated');
  expect(next.rows[0].validated_at).toBeTruthy();
});

test('the bucket the row leaves is the one that goes down, not always pending', async () => {
  // The bug: this used to read { pending: 1, validated: 1, rejected: 2 }.
  const next = await saveRowStatus('m1', state(row('a', 'validated')), 'a', 'rejected', '');
  expect(next.statusCounts).toEqual({ pending: 2, validated: 0, rejected: 2 });
});

test('a count never goes negative', async () => {
  const empty: RowSaveState = { rows: [row('a', 'pending')], statusCounts: {} };
  const next = await saveRowStatus('m1', empty, 'a', 'validated', '');
  expect(next.statusCounts.pending).toBe(0);
});

test('rejecting clears validated_at rather than leaving the old stamp', async () => {
  const stamped = { ...row('a', 'validated'), validated_at: '2026-01-01T00:00:00.000Z' };
  const next = await saveRowStatus('m1', state(stamped), 'a', 'rejected', '');
  expect(next.rows[0].validated_at).toBeNull();
});

test('a status filter is a live query — a row that leaves it drops out', async () => {
  const before = state(row('a', 'pending'), row('b', 'pending'));
  const next = await saveRowStatus('m1', before, 'a', 'validated', 'pending');
  expect(next.rows.map((r) => r.id)).toEqual(['b']);
});

test('with no filter the row stays and keeps its place', async () => {
  const before = state(row('a', 'pending'), row('b', 'pending'));
  const next = await saveRowStatus('m1', before, 'a', 'validated', '');
  expect(next.rows.map((r) => r.id)).toEqual(['a', 'b']);
});

test('the row the reviewer edited is what gets sent', async () => {
  const edited = {
    ...row('a', 'pending'),
    _editText: 'Rue Catinat (corrigé)',
    _editCategory: 'other',
  };
  await saveRowStatus('m1', state(edited), 'a', 'validated', '');
  expect(sent).toEqual([
    { id: 'a', text: 'Rue Catinat (corrigé)', category: 'other', status: 'validated' },
  ]);
});

test('an id that is not in the table is a no-op, not a throw', async () => {
  const before = state(row('a', 'pending'));
  const next = await saveRowStatus('m1', before, 'ghost', 'validated', '');
  expect(next).toBe(before);
  expect(sent).toEqual([]);
});

test('nothing in the caller’s array is mutated — the canvas holds these objects', async () => {
  const original = row('a', 'pending');
  const before = state(original);
  const snapshot = { ...original };
  const next = await saveRowStatus('m1', before, 'a', 'validated', '');

  expect(original).toEqual(snapshot);
  expect(before.statusCounts).toEqual({ pending: 2, validated: 1, rejected: 1 });
  expect(next.rows[0]).not.toBe(original);
});

test('markRowSaving flags one row and leaves the array it was given alone', () => {
  const rows = [row('a', 'pending'), row('b', 'pending')];
  const next = markRowSaving(rows, 'a', true);

  expect(next.map((r) => r._saving)).toEqual([true, false]);
  expect(rows.map((r) => r._saving)).toEqual([false, false]);
  expect(next[1]).toBe(rows[1]);
});

test('a row is dirty against its validated columns, not its raw OCR text', () => {
  const clean = row('a', 'pending');
  expect(isRowDirty(clean)).toBe(false);

  // Already corrected once and saved: the buffer matches `text_validated`.
  expect(isRowDirty({ ...clean, text_validated: 'Rue Catinat', _editText: 'Rue Catinat' })).toBe(
    false
  );
  // The reviewer has typed something new since that save.
  expect(isRowDirty({ ...clean, text_validated: 'Rue Catinat', _editText: 'Rue Taberd' })).toBe(
    true
  );
});

test('a saved category correction is the category every review surface uses', () => {
  const corrected = { ...row('a', 'pending'), category_validated: 'place' };
  expect(reviewedCategory(corrected)).toBe('place');
  expect(reviewedCategory(row('b', 'pending'))).toBe('street');
});
