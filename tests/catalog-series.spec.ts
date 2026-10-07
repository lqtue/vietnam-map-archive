import { test, expect } from '@playwright/test';
import { matchesGeographicRegion } from '../src/lib/core/catalogRegions';

test('catalog begins with compact disclosures while collection links remain in the HTML', async ({
  page,
}) => {
  const response = await page.goto('/catalog');
  const html = await response!.text();
  expect(html).toContain('/catalog/area/ho-chi-minh');
  expect(html).toContain('/catalog?region=mekong-delta');
  await expect(page.locator('.collection-browser')).not.toHaveAttribute('open');
  await expect(page.locator('.series-band')).not.toBeVisible();
  await expect(page.locator('.filters .add-filter select')).not.toBeVisible();
  await page.locator('.collection-browser > summary').click();
  await expect(page.locator('.series-band')).toBeVisible();
  await page.locator('.collection-browser > summary').click();
  await page.locator('.filters .add-filter > summary').click();
  await expect(page.getByLabel('Series or type')).toBeVisible();
  await expect(page.getByLabel('Place')).toBeVisible();
});

test('geographic region filter agrees with the API and Cochinchine includes HCMC', async ({
  request,
  page,
}) => {
  const all = await (await request.get('/api/search?include=maps&limit=5000')).json();
  const cochinchine = all.maps.find(
    (map: { slug: string }) => map.slug === 'cochinchine-francaise'
  );
  expect(cochinchine.regions).toContain('Hồ Chí Minh');
  for (const region of ['mekong-delta', 'red-river-delta']) {
    const expected = all.maps.filter((map: Record<string, unknown>) =>
      matchesGeographicRegion(map, [region])
    );
    const filtered = await (
      await request.get(`/api/search?include=maps&limit=5000&region=${region}`)
    ).json();
    expect(filtered.maps.map((map: { id: string }) => map.id).sort()).toEqual(
      expected.map((map: { id: string }) => map.id).sort()
    );
    await page.goto(`/catalog?region=${region}`);
    await expect(page.locator('.active-chips')).toContainText('Region:');
    await expect(page.locator('.v2-count')).toHaveText(`${expected.length} in archive`);
  }
});

test('area destinations are crawlable and their lists agree with public area search', async ({
  request,
  page,
}) => {
  const catalog = await request.get('/catalog');
  expect(catalog.status()).toBe(200);
  const html = await catalog.text();
  const areas = [
    ...new Set([...html.matchAll(/href="(\/catalog\/area\/[^"]+)"/g)].map((m) => m[1])),
  ];
  expect(areas.length).toBeGreaterThan(0);
  for (const href of areas) {
    const response = await request.get(href);
    expect(response.status()).toBe(200);
    const body = await response.text();
    const filter = body.match(/href="(\/catalog\?area=[^"]+)"/)?.[1];
    expect(filter).toBeTruthy();
    const name = new URL(filter!, 'https://maparchive.vn').searchParams.get('area')!;
    const search = await request.get(
      `/api/search?include=maps&area=${encodeURIComponent(name)}&limit=5000`
    );
    expect(search.status()).toBe(200);
    const result = await search.json();
    expect(result.maps.length).toBeGreaterThan(0);
    for (const map of result.maps) {
      expect(map.status === 'public' || map.status === 'featured').toBe(true);
      expect(map.regions?.includes(name) || map.region === name).toBe(true);
      expect(body).toContain(`/catalog/${map.slug}`);
    }
    const list = body.match(/<ul\b[^>]*id="area-maps"[^>]*>([\s\S]*?)<\/ul>/)?.[1];
    expect(list).toBeDefined();
    const links = new Set(
      [...list!.matchAll(/href="\/catalog\/([^/?"]+)"/g)].map((match) => match[1])
    );
    expect(links.size).toBe(result.total.maps);
    if (href === '/catalog/area/ho-chi-minh') {
      await page.goto(filter!);
      await expect(page.locator('.active-chips')).toContainText(`Place: ${name}`);
      await expect(page.locator('.v2-count')).toHaveText(`${result.total.maps} in archive`);
    }
  }
  expect((await request.get('/catalog/area/unknown-area')).status()).toBe(404);
  const sitemap = await request.get('/sitemap.xml');
  const xml = await sitemap.text();
  for (const href of areas) expect(xml).toContain(`https://maparchive.vn${href}`);
});

test('city collections expose translated content, previews and language-specific canonicals in HTML', async ({
  request,
}) => {
  const cases = [
    ['ho-chi-minh', 'Historical maps of Saigon (Ho Chi Minh City)', 'Bản đồ Sài Gòn xưa'],
    ['ha-noi', 'Historical maps of Hanoi', 'Bản đồ Hà Nội xưa'],
    ['thua-thien-hue', 'Historical maps of Huế', 'Bản đồ Huế xưa'],
  ];
  const sitemap = await (await request.get('/sitemap.xml')).text();
  for (const [slug, english, vietnamese] of cases) {
    const path = `/catalog/area/${slug}`;
    for (const [prefix, title] of [
      ['', english],
      ['/vi', vietnamese],
    ]) {
      const response = await request.get(prefix + path);
      expect(response.status()).toBe(200);
      const html = await response.text();
      expect(html).toContain(`<title>${title}`);
      expect(html).toContain(`rel="canonical" href="https://maparchive.vn${prefix}${path}"`);
      expect(html).toContain(`hreflang="en" href="https://maparchive.vn${path}"`);
      expect(html).toContain(`hreflang="vi" href="https://maparchive.vn/vi${path}"`);
      expect(html).toMatch(/<img[^>]+alt="[^"]+"/);
      expect(html).toContain('id="area-maps"');
      expect(sitemap).toContain(`<loc>https://maparchive.vn${prefix}${path}</loc>`);
    }
  }
});

/**
 * The series band on /catalog, and the drawer it opens.
 *
 * Three things here have been wrong before in this repo and look right from
 * the outside, which is why each gets a check rather than a glance:
 *
 *  - the band is server-rendered, so a crawler and a reader with no JavaScript
 *    both reach the coverage pages. the coverage pages once had
 *    exactly one way in — a control inside an `ssr = false` tool.
 *  - the row keeps its `href` while opening a drawer. A button here would have
 *    silently removed the only crawlable path to the coverage pages, and
 *    nothing on screen would have looked different.
 *  - the series filter matches `maps.collection`. It is a different column
 *    from the label the reader picks, and a filter reading the wrong key is
 *    the failure this file's neighbour documents: the compact type `<select>`
 *    wrote `map_type` where the filter read `type`, and did nothing at all,
 *    visibly working.
 */

test('the band is in the HTML, with a link to every coverage page', async ({ page }) => {
  const res = await page.goto('/catalog');
  const html = await res!.text();

  // The server's HTML, before any hydration — this is what a crawler sees.
  expect(html).toContain('series-band');
  const hrefs = [...html.matchAll(/href="(\/catalog\/series\/[^"]+)"/g)].map((m) => m[1]);
  expect(hrefs.length).toBeGreaterThan(0);

  // Every row's href resolves — a 404 here is a survey with no imported index
  // that the band should have filtered out.
  for (const href of new Set(hrefs)) {
    const r = await page.request.get(href);
    expect(r.status(), `${href} should not 404`).toBe(200);
  }
});

/**
 * Wait until the page is hydrated AND the archive has answered.
 *
 * Both matter, and the count alone is not enough to tell them apart: the
 * toolbar is server-rendered too, and it renders "0 in archive" before
 * /api/search has replied. A test that waited for the text "in archive" was
 * satisfied by the server's HTML and clicked a row whose handler did not exist
 * yet — so it navigated, which is exactly what a row is supposed to do before
 * JavaScript arrives.
 *
 * ANCHORED, because a substring is not a number. This waited on the text not
 * CONTAINING "0 in archive", which every count ending in a zero also contains:
 * the archive reached 250 sheets and five tests began failing on a page that
 * was working perfectly. The zero being waited out is the whole count, so the
 * pattern says so.
 */
async function ready(page: import('@playwright/test').Page) {
  await expect(page.locator('.v2-count')).not.toHaveText(/^\s*0\s+in archive/);
  await page.locator('.collection-browser > summary').click();
  await expect(page.locator('.series-band a.drow').first()).toBeVisible();
}

test('a row opens the drawer and still carries its link', async ({ page }) => {
  await page.goto('/catalog');
  await ready(page);
  const row = page.locator('.series-band a.drow').first();
  const href = await row.getAttribute('href');
  expect(href).toMatch(/^\/catalog\/series\//);

  await row.click();
  const drawer = page.getByRole('dialog', { name: /series details/i });
  await expect(drawer).toBeVisible();

  // The coverage bar, not a thumbnail: held + obtainable + no_scan.
  await expect(drawer.locator('.bar .seg')).toHaveCount(3);
  // "All sheets" goes to the same page the row links to.
  await expect(drawer.getByRole('link', { name: 'All sheets' })).toHaveAttribute('href', href!);

  /* "Open in map" is /explore's own `?series=` deeplink, and it must carry a
     camera. Without the `#@lat,lng,zoomz` half the survey lands on whatever
     the reader last looked at, which for a layer the size of a country is one
     corner of it and looks like a layer that failed to draw — a failure with
     no error and nothing on screen to read. The key is the same one the
     coverage page is addressed by. */
  const mapHref = await drawer.getByRole('link', { name: 'Open in map' }).getAttribute('href');
  const key = href!.split('/').pop()!;
  expect(mapHref).toMatch(
    new RegExp(`^/explore\\?series=${key}#@-?\\d+\\.\\d+,-?\\d+\\.\\d+,\\d+(\\.\\d+)?z,0r$`)
  );

  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
});

test('the drawer is over the nav, not under it', async ({ page }) => {
  /**
   * The nav is sticky at `z-index: 100`; the drawer and its scrim are fixed
   * above it. This is asserted because it was false, and because the reason it
   * was false is invisible from the styles: `.page` carried
   * `animation: page-fade-in .5s ease both`, and a `forwards` fill keeps an
   * opacity animation applied forever, which keeps the stacking context it
   * creates forever. Every fixed descendant of `.page` — both catalog drawers,
   * their scrim, MapEditModal — was sealed under the nav, and no z-index on
   * the drawer could reach past it. `getComputedStyle` reports `opacity: 1`
   * the whole time, so the styles all read as correct.
   *
   * Hit-testing rather than a screenshot: what matters is that the nav is not
   * reachable under an open modal. It was clickable, so the page behind could
   * be navigated away from while the drawer stayed open over it.
   */
  await page.goto('/catalog');
  await ready(page);
  await page.locator('.series-band a.drow').first().click();
  await expect(page.getByRole('dialog', { name: /series details/i })).toBeVisible();
  await expect(page.locator('.drawer-head')).toBeVisible();

  const nav = (await page.locator('.top-nav').boundingBox())!;
  const drawer = (await page.locator('.drawer').boundingBox())!;
  // A point inside both the nav's strip and the drawer's column.
  const x = drawer.x + drawer.width / 2;
  const y = nav.y + nav.height / 2;
  const topmost = await page.evaluate(
    ([px, py]) => {
      const el = document.elementFromPoint(px as number, py as number);
      return el
        ? el.closest('.top-nav')
          ? 'nav'
          : el.closest('.drawer')
            ? 'drawer'
            : 'other'
        : 'none';
    },
    [x, y]
  );
  expect(topmost).toBe('drawer');
});

test('"Filter the catalog" narrows the list to that survey, and the band steps aside', async ({
  page,
}) => {
  await page.goto('/catalog');
  await ready(page);
  const count = page.locator('.v2-count');
  const all = Number((await count.textContent())!.match(/(\d+)/)![1]);

  await page.locator('.series-band a.drow').first().click();
  await page.getByRole('button', { name: 'Filter the catalog' }).click();

  // The drawer closes, the band goes away, and the list is smaller than the
  // whole archive but not empty — a filter matching the wrong column gives
  // either "unchanged" or "zero", and both are visibly plausible.
  await expect(page.getByRole('dialog', { name: /series details/i })).toHaveCount(0);
  await expect(page.locator('.series-band')).toHaveCount(0);
  const narrowed = Number((await count.textContent())!.match(/(\d+)/)![1]);
  expect(narrowed).toBeGreaterThan(0);
  expect(narrowed).toBeLessThan(all);

  // Reset puts all three back.
  await page.getByRole('button', { name: 'Clear all' }).click();
  await expect(page.locator('.collection-browser')).toBeVisible();
  await expect(count).toContainText(`${all} in archive`);
});

test('"Open in map" actually puts the survey on the map', async ({ page }) => {
  await page.goto('/catalog');
  await ready(page);
  await page.locator('.series-band a.drow').first().click();
  const name = (await page.getByRole('dialog').getByRole('heading').textContent())!.trim();
  await page.getByRole('link', { name: 'Open in map' }).click();

  /* The param is consumed on arrival — /explore deletes it so a reload cannot
     put back a survey the reader has since taken off — so the URL proves
     nothing and the layer stack is the evidence. A survey named in the stack
     is a layer the renderer has been handed.

     Also asserted by getting this far without a click: arriving on `?series=`
     must not raise the welcome chooser. It is a modal, so if it came back this
     line would fail on it rather than on the layer. */
  await expect(page).toHaveURL(/\/explore/);
  await expect(page.getByRole('button', { name })).toBeVisible({ timeout: 20000 });
});

test('a series page opens its survey alone, clearing a previously selected survey', async ({
  page,
}) => {
  await page.goto('/catalog');
  const hrefs = await page
    .locator('a[href^="/catalog/series/"]')
    .evaluateAll((links) => [
      ...new Set(links.map((link) => link.getAttribute('href')).filter(Boolean)),
    ]);
  expect(hrefs.length).toBeGreaterThan(1);

  const previousKey = hrefs[1]!.split('/').pop()!;
  await page.goto(`/explore?series=${previousKey}`);
  await expect
    .poll(() =>
      page.evaluate(
        () => JSON.parse(localStorage.getItem('vma-layers-v1') || '{}').overlays?.length
      )
    )
    .toBe(1);
  const previousRefKey = await page.evaluate(
    () => JSON.parse(localStorage.getItem('vma-layers-v1') || '{}').overlays[0].ref.key
  );

  await page.goto(hrefs[0]!);
  const link = page.getByRole('link', { name: 'Open in map' });
  await expect(link).toHaveAttribute('href', /\/explore\?series=.+&solo=1#@/);
  await link.click();
  await expect
    .poll(() =>
      page.evaluate((oldKey) => {
        const layers = JSON.parse(localStorage.getItem('vma-layers-v1') || '{}');
        return {
          count: layers.overlays?.length,
          kind: layers.overlays?.[0]?.ref.kind,
          oldPresent: layers.overlays?.some(
            (overlay: { ref: { key: string } }) => overlay.ref.key === oldKey
          ),
        };
      }, previousRefKey)
    )
    .toEqual({ count: 1, kind: 'series', oldPresent: false });
});

test('a query puts the band away too', async ({ page }) => {
  await page.goto('/catalog');
  await ready(page);
  await page.locator('.sb-search-input').fill('saigon');
  await expect(page.locator('.series-band')).toHaveCount(0);
});
