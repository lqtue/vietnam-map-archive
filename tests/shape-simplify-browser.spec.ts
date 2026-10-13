import { test, expect } from '@playwright/test';

// Synthetic browser fixture: every data read and verdict is intercepted. No
// authentication or live database writes, and no real image/reference crop.
test('Validate previews, cancels, undoes and stages simplification until the verdict', async ({
  page,
}) => {
  const mapId = 'aaaaaaaa-0000-0000-0000-000000000001';
  const shapeId = 'bbbbbbbb-0000-0000-0000-000000000001';
  const original = [
    [100, 100],
    [125, 101],
    [150, 99],
    [200, 100],
    [200, 200],
    [100, 200],
    [100, 100],
  ];
  const footprint = {
    id: shapeId,
    map_id: mapId,
    pixel_polygon: original,
    feature_type: 'parcel',
    review_status: 'needs_review',
    name: null,
    category: null,
    maps: {
      id: mapId,
      name: 'Synthetic parcel fixture',
      allmaps_id: null,
      iiif_image: 'https://fixture.test/image',
    },
  };
  const writes: Record<string, unknown>[] = [];
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.route('**/rest/v1/**', (route) =>
    route.fulfill({
      json: [footprint],
      headers: {
        'access-control-allow-origin': '*',
        'access-control-allow-headers': '*',
        'access-control-allow-methods': '*',
      },
    })
  );
  await page.route('https://fixture.test/image/**', (route) => {
    if (route.request().url().endsWith('/info.json'))
      return route.fulfill({
        json: {
          '@context': 'http://iiif.io/api/image/2/context.json',
          '@id': 'https://fixture.test/image',
          protocol: 'http://iiif.io/api/image',
          width: 1000,
          height: 1000,
          profile: ['http://iiif.io/api/image/2/level2.json'],
          tiles: [{ width: 256, scaleFactors: [1, 2, 4] }],
        },
      });
    return route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="white"/></svg>',
    });
  });
  await page.route('**/api/admin/footprints', async (route) => {
    writes.push(route.request().postDataJSON());
    await route.fulfill({ json: { ok: true } });
  });
  await page.goto(`/scan?mode=shapes&tab=validate&map=${mapId}`);
  try {
    await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeVisible({
      timeout: 20000,
    });
  } catch (err) {
    throw new Error(`Browser errors: ${errors.join('; ')}; URL: ${page.url()}`, { cause: err });
  }
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await expect(page.getByText(/6 → 4 vertices/)).toBeVisible();
  expect(writes).toHaveLength(0);
  await page.getByRole('button', { name: 'Cancel preview' }).click();
  await expect(page.getByRole('button', { name: 'Use outline' })).toHaveCount(0);
  expect(writes).toHaveLength(0);
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await page.getByRole('button', { name: 'Use outline' }).click();
  await page.getByRole('button', { name: 'Undo outline edit' }).click();
  await expect(page.getByRole('button', { name: 'Undo outline edit' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await page.getByRole('button', { name: 'Use outline' }).click();
  expect(writes).toHaveLength(0);
  await page.getByRole('button', { name: '✓ Approve', exact: true }).click();
  await expect(page.getByText('All done for this map.')).toBeVisible();
  expect(writes).toHaveLength(1);
  expect(writes[0].expected_pixel_polygon).toEqual(original);
  expect(writes[0].pixel_polygon).toEqual([
    [100, 100],
    [200, 100],
    [200, 200],
    [100, 200],
    [100, 100],
  ]);
});
