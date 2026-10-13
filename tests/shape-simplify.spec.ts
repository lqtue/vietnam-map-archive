import { test, expect } from '@playwright/test';
import { geometryKind } from '../src/lib/data/maps/footprintTypes';
import { get } from 'svelte/store';
import {
  simplifyRing,
  validRing,
  ringsOverlap,
  type RingPoint,
} from '../src/lib/core/geo/simplifyRing';
import { createReviewQueue } from '../src/lib/features/contribute/review/reviewQueue';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '../src/lib/data/supabase/types';

const square: RingPoint[] = [
  [0, 0],
  [100, 0],
  [100, 100],
  [0, 100],
  [0, 0],
];
const bumped: RingPoint[] = [
  [0, 0],
  [25, 1],
  [50, -1],
  [100, 0],
  [100, 100],
  [0, 100],
  [0, 0],
];

test('simplification preserves an L notch and reports its displacement', () => {
  const polygon: RingPoint[] = [
    [0, 0],
    [25, 1],
    [100, 0],
    [100, 40],
    [40, 40],
    [40, 100],
    [0, 100],
    [0, 0],
  ];
  const original = structuredClone(polygon);
  const trial = simplifyRing(polygon, 4);
  expect(trial.valid).toBe(true);
  expect(trial.polygon).toContainEqual([40, 40]);
  expect(trial.afterVertices).toBeLessThan(trial.beforeVertices);
  expect(trial.boundaryMovement).toBeLessThanOrEqual(4);
  expect(polygon).toEqual(original);
});

test('triangles and diagonal blocks keep their meaningful corners', () => {
  const triangle: RingPoint[] = [
    [10, 10],
    [80, 30],
    [30, 90],
    [10, 10],
  ];
  expect(simplifyRing(triangle, 6).polygon).toEqual(triangle);
  expect(simplifyRing(square, 6).polygon).toEqual(square);
  expect(simplifyRing(bumped, 2).afterVertices).toBe(4);
});

test('invalid or collapsed outlines cannot be accepted', () => {
  expect(
    validRing([
      [0, 0],
      [10, 10],
      [0, 10],
      [10, 0],
    ])
  ).toBe(false);
  expect(simplifyRing(square, 1000).valid).toBe(false);
  expect(simplifyRing(square, Number.NaN).valid).toBe(false);
});

test('neighbour overlap distinguishes shared edges, coincident shapes and containment', () => {
  expect(
    ringsOverlap(square, [
      [100, 0],
      [200, 0],
      [200, 100],
      [100, 100],
    ])
  ).toBe(false);
  expect(ringsOverlap(square, square)).toBe(true);
  expect(
    ringsOverlap(square, [
      [50, 50],
      [150, 50],
      [150, 150],
      [50, 150],
    ])
  ).toBe(true);
  expect(
    ringsOverlap(square, [
      [20, 20],
      [30, 20],
      [30, 30],
      [20, 30],
    ])
  ).toBe(true);
});

function client() {
  const row = {
    id: 'shape',
    map_id: 'map',
    user_id: null,
    pixel_polygon: bumped,
    name: null,
    category: null,
    feature_type: 'parcel',
    review_status: 'needs_review',
  };
  return {
    auth: { getSession: async () => ({ data: { session: null } }) },
    from: () => {
      const query: Record<string, unknown> = {};
      for (const name of ['select', 'eq', 'in', 'order']) query[name] = () => query;
      query.range = () => Promise.resolve({ data: [structuredClone(row)], error: null });
      return query;
    },
  } as unknown as SupabaseClient<Database>;
}

test('preview/cancel writes nothing; acceptance and undo preserve the working geometry', async () => {
  const queue = createReviewQueue(client());
  await queue.open('map');
  queue.previewSimplification('shape', 2);
  expect(get(queue).footprints[0].pixelPolygon).toEqual(bumped);
  expect(get(queue).simplifyPreview?.trial.afterVertices).toBe(4);
  queue.cancelSimplification();
  expect(get(queue).footprints[0].pixelPolygon).toEqual(bumped);
  queue.previewSimplification('shape', 2);
  queue.acceptSimplification();
  expect(get(queue).footprints[0].pixelPolygon).toEqual(square);
  queue.undoGeometry('shape');
  expect(get(queue).footprints[0].pixelPolygon).toEqual(bumped);
});

test('a later vertex edit cancels a stale preview', async () => {
  const queue = createReviewQueue(client());
  await queue.open('map');
  queue.previewSimplification('shape', 2);
  const changed: RingPoint[] = [
    [0, 0],
    [120, 0],
    [120, 100],
    [0, 100],
    [0, 0],
  ];
  queue.edit('shape', changed);
  queue.acceptSimplification();
  expect(get(queue).footprints[0].pixelPolygon).toEqual(changed);
  expect(get(queue).simplifyPreview).toBeNull();
});

test('the verdict sends the working outline and the original concurrency guard', async () => {
  const queue = createReviewQueue(client());
  await queue.open('map');
  queue.previewSimplification('shape', 2);
  queue.acceptSimplification();
  const savedFetch = globalThis.fetch;
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_url, options) => {
    body = JSON.parse(String(options?.body));
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  try {
    await queue.decide('map', 'shape', 'approved');
  } finally {
    globalThis.fetch = savedFetch;
  }
  expect(body.pixel_polygon).toEqual(square);
  expect(body.expected_pixel_polygon).toEqual(bumped);
  expect(body.expected_feature_type).toBe('parcel');
  expect(get(queue).footprints).toHaveLength(0);
  expect(get(queue).neighbours[0].pixelPolygon).toEqual(square);
  expect(get(queue).neighbours[0].status).toBe('approved');
});

test('road surfaces and water areas retain polygons while centrelines remain lines', () => {
  expect(geometryKind('road', square)).toBe('Polygon');
  expect(geometryKind('waterway', square)).toBe('Polygon');
  expect(
    geometryKind('road', [
      [0, 0],
      [10, 0],
      [10, 10],
    ])
  ).toBe('LineString');
});
