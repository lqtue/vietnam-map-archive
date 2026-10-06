/**
 * Pure checks for the OCR review keyboard loop (`ocrReviewController`).
 * Browser-less; they ride the Playwright runner.
 *
 * The two things worth a test: `step` walks the rows the sidebar *shows*, in
 * its order, and wraps — an off-by-one here silently skips a label in a
 * hundred-label sheet — and `setStatus` toggles rather than re-writing, so
 * pressing `v` twice does not leave a row validated.
 */
import { expect, test } from '@playwright/test';
import { get } from 'svelte/store';
import { createOcrReview } from '../src/lib/features/contribute/ocr/ocrReviewController';
import type { OcrExtraction } from '../src/lib/features/contribute/shared/types';
import type { OcrStatus } from '../src/lib/features/contribute/shared/ocrApi';

const row = (id: string, status: OcrStatus = 'pending') =>
  ({
    id,
    global_x: 0,
    global_y: 0,
    global_w: 10,
    global_h: 10,
    category: 'other',
    text: id,
    text_validated: null,
    category_validated: null,
    confidence: 0.9,
    status,
  }) as OcrExtraction;

function harness(rows: OcrExtraction[], visible = rows) {
  const writes: [string, OcrStatus][] = [];
  const focused: [string, boolean | undefined][] = [];
  const review = createOcrReview({
    getMapId: () => 'map-1',
    getRunId: () => 'run-1',
    reload: () => {},
    focusRow: (id, focusInput) => focused.push([id, focusInput]),
    fitTo: () => {},
    panTo: () => {},
    setRowStatus: (id, status) => {
      writes.push([id, status]);
    },
  });
  review.loaded({ detail: { extractions: rows } } as CustomEvent<{
    extractions: OcrExtraction[];
  }>);
  review.filter({ detail: { extractions: visible } } as CustomEvent<{
    extractions: OcrExtraction[];
  }>);
  return { review, writes, focused, at: () => get(review).selectedId };
}

test('stepping walks the shown rows and wraps at both ends', () => {
  const { review, at } = harness([row('a'), row('b'), row('c')]);
  review.step(1);
  expect(at()).toBe('a');
  review.step(1);
  expect(at()).toBe('b');
  review.step(-1);
  expect(at()).toBe('a');
  review.step(-1);
  expect(at()).toBe('c'); // wrapped backwards off the top
  review.step(1);
  expect(at()).toBe('a');
});

test('stepping ignores rows the filters hide', () => {
  const rows = [row('a'), row('b'), row('c')];
  const { review, at } = harness(rows, [rows[0], rows[2]]);
  review.step(1);
  review.step(1);
  expect(at()).toBe('c');
});

test('stepping never focuses the sidebar input — the keys must keep working', () => {
  const { review, focused } = harness([row('a'), row('b')]);
  review.step(1);
  expect(focused).toEqual([['a', false]]);
});

test('a click selects without focusing the input — shortcuts must keep firing', () => {
  // Focusing the row's text field on select made every shortcut type a
  // character instead: `r` wrote "r" into the label. `e` is how you get there.
  const { review, focused, at } = harness([row('a'), row('b')]);
  review.select({ detail: { id: 'b' } } as CustomEvent<{ id: string }>);
  expect(at()).toBe('b');
  expect(focused).toEqual([['b', false]]);
});

test('validate writes through the sidebar and advances to the next row', () => {
  const { review, writes, at } = harness([row('a'), row('b')]);
  review.step(1);
  review.setStatus('validated', true);
  expect(writes).toEqual([['a', 'validated']]);
  expect(at()).toBe('b');
});

test('the same status twice puts the row back to pending', () => {
  const { review, writes } = harness([row('a', 'validated'), row('b')]);
  review.step(1);
  review.setStatus('validated');
  expect(writes).toEqual([['a', 'pending']]);
  expect(get(review).extractions[0]._editStatus).toBe('pending');
  expect(get(review).extractions[0].status).toBe('validated');
});

test('a reload keeps the selection when the row survived it', () => {
  const rows = [row('a'), row('b')];
  const { review, at } = harness(rows);
  review.step(1);
  review.loaded({ detail: { extractions: rows } } as CustomEvent<{
    extractions: OcrExtraction[];
  }>);
  expect(at()).toBe('a');
  review.loaded({ detail: { extractions: [rows[1]] } } as CustomEvent<{
    extractions: OcrExtraction[];
  }>);
  expect(at()).toBeNull();
});

test('Shift-click preserves reading order and toggles a box out of the selection', () => {
  const { review } = harness([row('a'), row('b'), row('c')]);
  review.select({ detail: { id: 'c' } } as CustomEvent<{ id: string }>);
  review.select({ detail: { id: 'a', additive: true } } as CustomEvent<{
    id: string;
    additive: boolean;
  }>);
  review.select({ detail: { id: 'b', additive: true } } as CustomEvent<{
    id: string;
    additive: boolean;
  }>);
  expect(get(review).selectedIds).toEqual(['c', 'a', 'b']);
  review.select({ detail: { id: 'a', additive: true } } as CustomEvent<{
    id: string;
    additive: boolean;
  }>);
  expect(get(review).selectedIds).toEqual(['c', 'b']);
  review.select({ detail: { id: 'a' } } as CustomEvent<{ id: string }>);
  expect(get(review).selectedIds).toEqual(['a']);
});

test('member clicks select the combined label, and keyboard review skips members', () => {
  const parent = { ...row('group'), is_text_group: true };
  const part = { ...row('part'), text_group_id: 'group', text_group_order: 0 };
  const { review, at } = harness([parent, part, row('next')], [parent, row('next')]);
  review.select({ detail: { id: 'part' } } as CustomEvent<{ id: string }>);
  expect(at()).toBe('group');
  expect(get(review).selectedIds).toEqual(['group']);
  review.step(1);
  expect(at()).toBe('next');
  review.deselect();
  expect(get(review).selectedIds).toEqual([]);
});

test('a multi-selection cannot accidentally validate just its last box', () => {
  const { review, writes } = harness([row('a'), row('b')]);
  review.select({ detail: { id: 'a' } } as CustomEvent<{ id: string }>);
  review.select({ detail: { id: 'b', additive: true } } as CustomEvent<{
    id: string;
    additive: boolean;
  }>);
  review.setStatus('validated');
  expect(writes).toEqual([]);
  review.toggleDraw();
  expect(get(review).selectedIds).toEqual([]);
});

test('grouping capability follows the server schema and resets with the map', () => {
  const rows = [row('a'), row('b')];
  const { review } = harness(rows);
  expect(get(review).groupingAvailable).toBe(false);
  review.loaded({ detail: { extractions: rows, groupingAvailable: true } } as CustomEvent<{
    extractions: OcrExtraction[];
    groupingAvailable: boolean;
  }>);
  expect(get(review).groupingAvailable).toBe(true);
  review.reset();
  expect(get(review).groupingAvailable).toBe(false);
});

test('an empty filtered list does not step into hidden labels', () => {
  const { review, at } = harness([row('a'), row('b')], []);
  review.step(1);
  expect(at()).toBeNull();
});

test('draft cache is scoped to user and sheet and restores after a new controller', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const data = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => data.set(key, value),
      removeItem: (key: string) => data.delete(key),
    },
  });
  let map = 'map-a';
  let user = 'user-a';
  const make = () =>
    createOcrReview({
      getMapId: () => map,
      getUserId: () => user,
      getRunId: () => 'run',
      reload: () => {},
      focusRow: () => {},
      fitTo: () => {},
      panTo: () => {},
      setRowStatus: () => {},
    });
  const load = (review: ReturnType<typeof make>) =>
    review.loaded(
      new CustomEvent('loaded', {
        detail: { extractions: [row('a')], groupingAvailable: true },
      })
    );
  const first = make();
  const recovered = make();
  const otherUser = make();
  try {
    load(first);
    first.stage('a', { _editText: 'Local draft', global_x: 17 });
    first.persist();
    load(recovered);
    expect(get(recovered).extractions[0]._editText).toBe('Local draft');
    expect(get(recovered).extractions[0].global_x).toBe(17);
    map = 'map-b';
    first.reset();
    load(first);
    expect(get(first).dirtyCount).toBe(0);
    expect(data.has('vma-ocr-drafts-v1:user-a:map-a')).toBe(true);
    map = 'map-a';
    user = 'user-b';
    load(otherUser);
    expect(get(otherUser).dirtyCount).toBe(0);
    expect(get(otherUser).extractions[0]._editText).toBe('a');
    recovered.discard();
    recovered.persist();
    expect(data.has('vma-ocr-drafts-v1:user-a:map-a')).toBe(false);
  } finally {
    first.destroy();
    recovered.destroy();
    otherUser.destroy();
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous);
    else Reflect.deleteProperty(globalThis, 'localStorage');
  }
});

test('duplicating a reviewed rotated box selects a pending draft and keeps the original intact', () => {
  const source = {
    ...row('a', 'validated'),
    run_id: 'original-run',
    rotation_deg: 42,
    label_w: 30,
    label_h: 8,
  };
  const { review } = harness([source]);
  review.select(new CustomEvent('select', { detail: { id: 'a' } }));
  review.duplicate(
    new CustomEvent('duplicate', { detail: { text: 'Copied reading', category: 'place' } })
  );
  const state = get(review);
  const copy = state.extractions.find((r) => r.id === state.selectedId)!;
  expect(copy.id).not.toBe(source.id);
  expect(copy._editText).toBe('Copied reading');
  expect(copy._editCategory).toBe('place');
  expect(copy._editStatus).toBe('pending');
  expect(copy.rotation_deg).toBe(42);
  expect(copy.run_id).toBe('original-run');
  expect(copy.label_w).toBe(30);
  expect(copy.label_h).toBe(8);
  expect(state.extractions.find((r) => r.id === 'a')?.status).toBe('validated');
  expect(state.dirtyCount).toBe(1);
  review.destroy();
});
