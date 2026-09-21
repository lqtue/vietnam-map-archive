import { test, expect } from '@playwright/test';
import { declaredSourceSize, sourceSizeMismatch } from '../src/lib/core/iiif/sourceSize';

// The mirror's URL rewrite is a string replace. It cannot move resourceCoords or
// the mask, so an R2 copy that is a rescan silently multiplies the georeference
// by the scale ratio. The 1942 sheet is the real case: 7479x6314 annotation,
// 14915x12602 rescan in R2.
const annotation = (width: number, height: number) => ({
  type: 'AnnotationPage',
  items: [
    {
      type: 'Annotation',
      target: {
        source: { id: 'https://iiif.maparchive.vn/iiif/m', type: 'ImageService2', width, height },
      },
    },
  ],
});

const withInfo = async (info: unknown | null, fn: () => Promise<string | null>) => {
  const real = globalThis.fetch;
  globalThis.fetch = (async () =>
    info === null
      ? { ok: false, statusText: 'Not Found', json: async () => ({}) }
      : { ok: true, json: async () => info }) as unknown as typeof fetch;
  try {
    return await fn();
  } finally {
    globalThis.fetch = real;
  }
};

test('the declared size is the one the control points are in', () => {
  expect(declaredSourceSize(annotation(7479, 6314))).toEqual({ width: 7479, height: 6314 });
  expect(declaredSourceSize({ type: 'AnnotationPage', items: [{ target: {} }] })).toBeNull();
});

test('a rescan under the same id is refused, with both sizes named', async () => {
  const msg = await withInfo({ width: 14915, height: 12602 }, () =>
    sourceSizeMismatch(annotation(7479, 6314), 'https://iiif.maparchive.vn/iiif/m')
  );
  expect(msg).toContain('7479x6314');
  expect(msg).toContain('14915x12602');
});

test('matching sizes pass, and a missing info.json is the first mirror, not a fault', async () => {
  expect(
    await withInfo({ width: 7479, height: 6314 }, () =>
      sourceSizeMismatch(annotation(7479, 6314), 'https://iiif.maparchive.vn/iiif/m')
    )
  ).toBeNull();
  expect(
    await withInfo(null, () =>
      sourceSizeMismatch(annotation(7479, 6314), 'https://iiif.maparchive.vn/iiif/m')
    )
  ).toBeNull();
});
