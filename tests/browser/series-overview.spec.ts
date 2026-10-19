import { expect, test } from '@playwright/test';

const total = 5000;
const seriesKey = 'fixture-large-series';
const bounds = (i: number): [number, number, number, number] => {
  const west = 105 + (i % 100) * 0.02;
  const south = 9.5 + Math.floor(i / 100) * 0.02;
  return [west, south, west + 0.02, south + 0.02];
};
const rows = Array.from({ length: total }, (_, i) => ({
  id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`,
  name: `Survey sheet ${i}`,
  year: 1960,
  status: 'public',
  is_georeferenced: true,
  series_key: seriesKey,
  collection: 'Large fixture survey',
  sheet_number: String(i),
  allmaps_id: null,
  annotation_url: `https://series-fixture.test/annotations/${i}.json`,
  bbox: bounds(i),
  extra_metadata: {},
  sheet_half: null,
}));

function annotation(i: number) {
  const [w, s, e, n] = bounds(i);
  const corners = [
    [0, 0, w, n],
    [256, 0, e, n],
    [256, 256, e, s],
    [0, 256, w, s],
  ];
  return {
    type: 'AnnotationPage',
    '@context': 'http://www.w3.org/ns/anno.jsonld',
    items: [
      {
        id: `https://series-fixture.test/maps/${i}`,
        type: 'Annotation',
        '@context': [
          'http://www.w3.org/ns/anno.jsonld',
          'http://geojson.org/geojson-ld/geojson-context.jsonld',
          'http://iiif.io/api/presentation/3/context.json',
        ],
        motivation: 'georeferencing',
        target: {
          type: 'SpecificResource',
          source: {
            id: `https://series-fixture.test/iiif/${i}`,
            type: 'ImageService3',
            width: 256,
            height: 256,
          },
          selector: {
            type: 'SvgSelector',
            value:
              '<svg width="256" height="256"><polygon points="0,0 256,0 256,256 0,256" /></svg>',
          },
        },
        body: {
          type: 'FeatureCollection',
          transformation: { type: 'polynomial', options: { order: 1 } },
          features: corners.map(([x, y, lng, lat]) => ({
            type: 'Feature',
            properties: { resourceCoords: [x, y] },
            geometry: { type: 'Point', coordinates: [lng, lat] },
          })),
        },
      },
    ],
  };
}

/** Real Allmaps/WebGL renderer with local annotations: no live catalog or IIIF dependency. */
for (const [seriesCount, mobile] of [
  [1, false],
  [4, false],
  [4, true],
] as const) {
  test(`${seriesCount} large series share a bounded detail budget and release overview canvases${mobile ? ' on mobile' : ''}`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const budget = mobile ? 24 : 64;
    const annotationRequests: string[] = [];
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.addInitScript(
      ({ key, count }) => {
        localStorage.clear();
        localStorage.setItem('vma-explore-tour-ack-v1', 'true');
        localStorage.setItem('vma-explore-welcome-ack-v1', 'all');
        localStorage.setItem(
          'vma-layers-v1',
          JSON.stringify({
            base: { kind: 'basemap', key: 'none' },
            overlays: Array.from({ length: count }, (_, index) => ({
              id: `fixture-series-layer-${index}`,
              visible: true,
              opacity: 0.8,
              ref: {
                kind: 'series',
                key: `${key}-${index}`,
                mapId: `series:${key}-${index}`,
                name: `Large fixture survey ${index}`,
                parts: [
                  {
                    kind: 'sheets',
                    seriesKey: `${key}-${index}`,
                    collection: `Large fixture survey ${index}`,
                  },
                ],
                bounds: [105, 9.5, 107, 10.5],
              },
            })),
          })
        );
      },
      { key: seriesKey, count: seriesCount }
    );
    await page.route('**/rest/v1/**', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/map_series')) {
        await route.fulfill({
          json: [
            {
              key: seriesKey,
              collection: 'Large fixture survey',
              name: 'Large fixture survey',
              sheets: total,
              published_sheets: total,
              survey_sheets: total,
              first_year: 1960,
              last_year: 1960,
              bounds: [105, 9.5, 107, 10.5],
            },
          ],
        });
      } else if (url.pathname.endsWith('/maps')) {
        const offset = Number(url.searchParams.get('offset') ?? 0);
        const limit = Number(url.searchParams.get('limit') ?? 1000);
        await route.fulfill({
          json: rows.slice(offset, offset + limit).map((row) => ({
            ...row,
            annotation_url: `${row.annotation_url}?series=${url.searchParams.get('series_key')}`,
          })),
        });
      } else await route.fulfill({ json: [] });
    });
    await page.route('**/api/explore/maps?**', (route) =>
      route.fulfill({
        json: {
          maps: [],
          total: { maps: total, drafts: 0, scout: 0 },
          facets: {},
          choices: { area: [], region: [], type: [], institution: [], series: [] },
          yearBins: [],
          seriesCounts: { [seriesKey]: total },
          nextCursor: null,
        },
      })
    );
    await page.route('https://series-fixture.test/**', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/annotations/')) {
        annotationRequests.push(url.href);
        const i = Number(url.pathname.split('/').at(-1)!.replace('.json', ''));
        await route.fulfill({ json: annotation(i) });
      } else if (url.pathname.endsWith('/info.json')) {
        const id = url.origin + url.pathname.replace('/info.json', '');
        await route.fulfill({
          json: {
            '@context': 'http://iiif.io/api/image/3/context.json',
            id,
            type: 'ImageService3',
            protocol: 'http://iiif.io/api/image',
            profile: 'level0',
            width: 256,
            height: 256,
            tiles: [{ width: 256, scaleFactors: [1] }],
          },
        });
      } else {
        await route.fulfill({
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
            'base64'
          ),
        });
      }
    });
    await page.goto('/explore#@10,106,4z,0r&base=none');
    async function camera(zoom: number) {
      await page.evaluate((zoom) => {
        history.replaceState(history.state, '', `#@10,106,${zoom}z,0r&base=none`);
        window.dispatchEvent(new PopStateEvent('popstate', { state: history.state }));
      }, zoom);
    }
    await expect(page.locator('.ol-viewport').first()).toBeVisible();
    await page.waitForTimeout(500);
    await camera(4);
    const notice = page.locator('[data-series-overview-notice]');
    await expect(notice).toContainText('Zoom in to view series scans');
    expect(annotationRequests).toHaveLength(0);
    await expect(page.locator('.allmaps-warped-map-layer canvas')).toHaveCount(0);

    for (let cycle = 0; cycle < 3; cycle++) {
      const before = annotationRequests.length;
      await camera(15);
      await expect.poll(() => annotationRequests.length).toBeGreaterThan(before);
      await expect(page.locator('.allmaps-warped-map-layer canvas')).toHaveCount(seriesCount);
      expect(annotationRequests.length - before).toBeLessThanOrEqual(budget);
      await camera(4);
      await expect(notice).toContainText('Zoom in to view series scans');
      await expect(page.locator('.allmaps-warped-map-layer canvas')).toHaveCount(0);
      const stoppedAt = annotationRequests.length;
      // The idle period detects jobs that erroneously resume after overview disposal.
      await page.waitForTimeout(1000);
      expect(annotationRequests).toHaveLength(stoppedAt);
      expect(annotationRequests.length - before).toBeLessThanOrEqual(budget);
    }
    expect(errors).toEqual([]);
  });
}
