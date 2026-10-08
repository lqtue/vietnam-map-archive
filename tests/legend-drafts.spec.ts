/**
 * The Legend tab's drafts (`legendDrafts.ts`): what the editor's fields may
 * become, and how a draft overlays the loaded row before it is saved.
 */
import { test, expect } from '@playwright/test';
import {
  accuracyBbox,
  applyDraft,
  forgetStoredDrafts,
  readStoredDrafts,
  toDraft,
  writeStoredDrafts,
} from '../src/lib/features/shared/legendDrafts';

const fields = { name: ' Chợ Rẫy ', vn: '', grid: 'J 5', lng: undefined, lat: undefined };

test('a draft trims, blanks to null, and refuses what the notes field cannot hold', () => {
  expect(toDraft('a', { ...fields, coordinateOverride: false })).toEqual({
    id: 'a',
    name: 'Chợ Rẫy',
    vn: null,
    grid: 'J 5',
    lng: null,
    lat: null,
    coordinateOverride: false,
    find: null,
  });
  expect(toDraft('a', { ...fields, name: ' ', coordinateOverride: false })).toBe(
    'Enter the legend name.'
  );
  expect(typeof toDraft('a', { ...fields, grid: 'J;5', coordinateOverride: false })).toBe('string');
  expect(typeof toDraft('a', { ...fields, lng: 106.7, coordinateOverride: true })).toBe('string');
  // An override with no point is no override.
  expect(toDraft('a', { ...fields, coordinateOverride: true })).toMatchObject({
    coordinateOverride: false,
  });
});

test('resetting a manual point drops it rather than keeping the old one', () => {
  const point = {
    id: 'a',
    n: 5,
    name: 'x',
    vn: null,
    grid: null,
    lng: 1,
    lat: 2,
    src: 'manual' as const,
  };
  const reset = toDraft('a', { ...fields, coordinateOverride: false });
  if (typeof reset === 'string') throw new Error(reset);
  expect(applyDraft(point, reset)).toMatchObject({ lng: null, lat: null, src: null });
  const moved = toDraft('a', { ...fields, lng: 106.7, lat: 10.7, coordinateOverride: true });
  if (typeof moved === 'string') throw new Error(moved);
  expect(applyDraft(point, moved)).toMatchObject({ lng: 106.7, lat: 10.7, src: 'manual' });
});

test('a grid-derived row is framed by its accuracy, wider in longitude than the metres alone', () => {
  const [w, so, e, n] = accuracyBbox(106.7, 10.78, 500);
  expect((n - so) * 111320).toBeCloseTo(1000, 3);
  expect((e - w) * 111320 * Math.cos((10.78 * Math.PI) / 180)).toBeCloseTo(1000, 3);
  expect((w + e) / 2).toBeCloseTo(106.7, 9);
  expect((so + n) / 2).toBeCloseTo(10.78, 9);
  // Farther from the equator a degree of longitude is shorter, so the box is wider.
  const [w2, , e2] = accuracyBbox(106.7, 60, 500);
  expect(e2 - w2).toBeGreaterThan(e - w);
});

/** A Storage stand-in: the real one only exists in a browser. */
function stubStorage(throws = false) {
  const data = new Map<string, string>();
  const g = globalThis as { localStorage?: unknown };
  g.localStorage = {
    getItem: (k: string) => {
      if (throws) throw new Error('blocked');
      return data.get(k) ?? null;
    },
    setItem: (k: string, v: string) => {
      if (throws) throw new Error('blocked');
      data.set(k, v);
    },
    removeItem: (k: string) => void data.delete(k),
  };
  return data;
}
const draft = (id: string, over = {}) => ({
  id,
  name: 'x',
  vn: null,
  grid: null,
  lng: null,
  lat: null,
  coordinateOverride: false,
  ...over,
});

test('stored drafts round-trip per sheet, keep only live entries, and drop the malformed', () => {
  const data = stubStorage();
  try {
    writeStoredDrafts('m1', { a: draft('a'), b: draft('b', { lng: 106.7, lat: 10.7 }) });
    expect(Object.keys(readStoredDrafts('m1', ['a', 'b']))).toEqual(['a', 'b']);
    // An entry the sheet no longer has, and a different sheet, restore nothing.
    expect(Object.keys(readStoredDrafts('m1', ['b']))).toEqual(['b']);
    expect(readStoredDrafts('m2', ['a', 'b'])).toEqual({});
    // Malformed rows are dropped without costing the good ones.
    data.set(
      'vma-legend-drafts-v1:m3',
      JSON.stringify([draft('a'), { id: 'b' }, draft('c', { lng: 'x' }), null, draft('d')])
    );
    expect(Object.keys(readStoredDrafts('m3', ['a', 'b', 'c', 'd']))).toEqual(['a', 'd']);
    data.set('vma-legend-drafts-v1:m4', '{not json');
    expect(readStoredDrafts('m4', ['a'])).toEqual({});
    data.set('vma-legend-drafts-v1:m5', '{"a":1}');
    expect(readStoredDrafts('m5', ['a'])).toEqual({});
    // Saved entries leave; the last one out removes the key.
    forgetStoredDrafts('m1', ['a']);
    expect(Object.keys(readStoredDrafts('m1', ['a', 'b']))).toEqual(['b']);
    forgetStoredDrafts('m1', ['b']);
    expect(data.has('vma-legend-drafts-v1:m1')).toBe(false);
  } finally {
    delete (globalThis as { localStorage?: unknown }).localStorage;
  }
});

test('with storage blocked or absent the drafts helpers do nothing and throw nothing', () => {
  stubStorage(true);
  try {
    expect(() => writeStoredDrafts('m1', { a: draft('a') })).not.toThrow();
    expect(readStoredDrafts('m1', ['a'])).toEqual({});
    expect(() => forgetStoredDrafts('m1', ['a'])).not.toThrow();
  } finally {
    delete (globalThis as { localStorage?: unknown }).localStorage;
  }
  expect(readStoredDrafts('m1', ['a'])).toEqual({});
});

test('a place search rides with the point it led to, and only that point', () => {
  const find = {
    query: 'Bệnh viện Grall',
    osmType: 'way' as const,
    osmId: 123,
    osmName: 'Nhi Đồng 2',
    lng: 106.7,
    lat: 10.78,
  };
  const placed = toDraft('a', {
    ...fields,
    lng: 106.7,
    lat: 10.78,
    coordinateOverride: true,
    find,
  });
  expect(placed).toMatchObject({ find });
  // Reset to the automatic point: the search no longer explains it.
  expect(toDraft('a', { ...fields, coordinateOverride: false, find })).toMatchObject({
    find: null,
  });
});
