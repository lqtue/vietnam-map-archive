/**
 * Pure checks for which maps /explore asks Allmaps about. No browser, no
 * network — they ride the Playwright runner because it is already installed.
 *
 * These exist because until 2026-09-06 the coverage lookup probed every map
 * with no bbox, georeferenced or not. 61 of 101 maps have no annotation, so a
 * single /explore load fired 61 requests at annotations.allmaps.org that could
 * only ever 404, twice over.
 */
import { test, expect } from '@playwright/test';
import { bboxOnScreen, unresolvedBoundsSources } from '../src/lib/features/explore/spatialLookup';
import type { MapListItem } from '../src/lib/data/maps/types';

const map = (over: Partial<MapListItem>): MapListItem =>
  ({ id: 'x', name: 'x', status: 'public', ...over }) as MapListItem;

test('an un-georeferenced map is never probed', () => {
  expect(
    unresolvedBoundsSources([map({ allmaps_id: 'deadbeefdeadbeef', georef_done: false })])
  ).toEqual([]);
});

test('a georeferenced map with no bbox still is', () => {
  expect(
    unresolvedBoundsSources([map({ allmaps_id: 'deadbeefdeadbeef', georef_done: true })])
  ).toEqual(['deadbeefdeadbeef']);
});

test('a mirrored annotation outranks a stale georef_done', () => {
  expect(
    unresolvedBoundsSources([
      map({ annotation_url: 'https://x.supabase.co/a.json', georef_done: false }),
    ])
  ).toEqual(['https://x.supabase.co/a.json']);
});

test('an unset georef_done is probed, not assumed missing', () => {
  expect(unresolvedBoundsSources([map({ allmaps_id: 'deadbeefdeadbeef' })])).toEqual([
    'deadbeefdeadbeef',
  ]);
});

test('a map that already has a bbox is left alone', () => {
  expect(
    unresolvedBoundsSources([
      map({ allmaps_id: 'deadbeefdeadbeef', georef_done: true, bbox: [106.6, 10.7, 106.8, 10.9] }),
    ])
  ).toEqual([]);
});

test('drafts stay out unless asked for', () => {
  const drafts = [map({ status: 'draft', allmaps_id: 'deadbeefdeadbeef', georef_done: true })];
  expect(unresolvedBoundsSources(drafts)).toEqual([]);
  expect(unresolvedBoundsSources(drafts, true)).toEqual(['deadbeefdeadbeef']);
});

// /explore leaves the camera alone when the thing picked is already in view.
test('on screen: inside the frame, not in its edge margin, and any overlap counts', () => {
  const view: [number, number, number, number] = [106, 10, 107, 11];
  expect(bboxOnScreen(view, [106.5, 10.5, 106.5, 10.5])).toBe(true); // a point in the middle
  expect(bboxOnScreen(view, [106.02, 10.5, 106.02, 10.5])).toBe(false); // hugging the left edge
  expect(bboxOnScreen(view, [108, 10.5, 108, 10.5])).toBe(false); // off to the east
  expect(bboxOnScreen(view, [105, 9, 106.5, 10.5])).toBe(true); // a sheet reaching in
  expect(bboxOnScreen(view, [100, 0, 120, 30])).toBe(true); // a sheet covering everything
});
