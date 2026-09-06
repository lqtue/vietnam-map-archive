import { expect, test, type Page } from '@playwright/test';

// Opening a map tallies a row in the production map_opens table (migration 049),
// which would pollute the real per-map counts with test traffic. Any test that
// opens a map must call this first. Returns a live counter of blocked inserts.
async function blockMapOpenTally(page: Page): Promise<() => number> {
  let n = 0;
  await page.route('**/rest/v1/map_opens*', (route) => {
    if (route.request().method() === 'POST') n++;
    return route.abort();
  });
  return () => n;
}

// ponytail: read-only smokes against the dev server and the real Supabase
// project. Nothing here writes a row. The two write paths worth covering —
// saving an OCR bbox and submitting a footprint — need a logged-in user and
// would insert into production tables; they want a seeded test project first.

test('home renders and links into the archive', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/./);
  // The Sept 2026 route merge left six destinations, so the nav is flat: no
  // dropdown to open before the link exists.
  await expect(page.locator('nav.nav a[href="/about"]')).toBeVisible();
  await expect(page.locator('nav.nav a[href="/archive"]')).toBeVisible();
  // The page is one Sheet: chrome in the margin, content inside the neatline.
  await expect(page.locator('.sheet .sheet__field')).toBeVisible();
});

test('catalog search returns maps', async ({ page }) => {
  await page.goto('/archive');
  await page.getByPlaceholder(/Search by title/i).fill('saigon');

  // Results come from /api/search over the tsvector column.
  const search = page.waitForResponse((r) => r.url().includes('/api/search') && r.status() === 200);
  const body = await (await search).json();
  expect(Array.isArray(body.maps)).toBe(true);
  expect(body.maps.length).toBeGreaterThan(0);
});

test('explore mounts an OpenLayers map', async ({ page }) => {
  await page.goto('/explore');
  // MapShell owns the single OL map; OL always builds a .ol-viewport canvas.
  await expect(page.locator('.shell-map canvas').first()).toBeVisible({ timeout: 20_000 });
});

test('an overlay renders on the map', async ({ page }) => {
  // Deeplinking counts as an open, so keep this one out of the tally too.
  await blockMapOpenTally(page);

  // Pick a georeferenced map from the API rather than hardcoding a UUID.
  // georef takes 'yes' | 'no', not a boolean.
  const res = await page.request.get('/api/search?georef=yes&limit=1');
  expect(res.ok()).toBe(true);
  const { maps } = await res.json();
  test.skip(!maps?.length, 'no georeferenced map in the catalogue');

  // The overlay comes from the ?map= query param; the #hash only mirrors view state.
  await page.goto(`/explore?map=${maps[0].id}`);
  await expect(page.locator('.shell-map canvas').first()).toBeVisible({ timeout: 20_000 });
  // layersStore is the single source of truth; LayerStackPanel renders it.
  await expect(page.locator('.lsp-text').first()).toBeVisible({ timeout: 20_000 });
});

test('picking a map writes ?map= and tallies the open', async ({ page }) => {
  // /explore used to be one opaque URL, so analytics could not attribute which
  // map anyone opened. syncMapParam() + recordMapOpen() fix that — assert both.

  // Aborting the insert still proves the call was made; that the server accepts
  // it is enforced by the RLS policies in migration 049.
  const tallied = await blockMapOpenTally(page);

  // The first-run tour's driver.js overlay swallows clicks on the browse rows,
  // so ack it up front the way a returning visitor would have.
  await page.addInitScript(() => localStorage.setItem('vma-explore-tour-ack-v1', 'true'));
  await page.goto('/explore');
  // Welcome chooser gates the browse panel; take the "show everything" branch.
  await page.locator('button.choice:not(.primary)').click();

  const row = page.locator('.ebp ul.rows button.row').first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.click();

  await expect(page).toHaveURL(/[?&]map=[0-9a-f-]{36}/);
  await expect.poll(tallied, { timeout: 10_000 }).toBe(1);

  // Tapping the same row again removes the overlay, which must drop the param
  // rather than leave a stale id behind. Removal is not an open — no new tally.
  await row.click();
  await expect(page).not.toHaveURL(/[?&]map=/);
  expect(tallied()).toBe(1);
});

test('the IIIF tool pages mount their ImageShell', async ({ page }) => {
  for (const route of ['/scan', '/scan?mode=trace', '/scan?mode=triage']) {
    await page.goto(route);
    await expect(page.locator('.tool-page')).toBeVisible();

    // tool-page.css is a global chunk now, not seven scoped copies. These two
    // declarations exist nowhere else, so they fail if the sheet stops loading.
    const styles = await page.evaluate(() => ({
      toolPage: getComputedStyle(document.querySelector('.tool-page')!).position,
      panel: getComputedStyle(document.querySelector('.panel')!).display,
    }));
    expect(styles, `${route} lost tool-page.css`).toEqual({
      toolPage: 'fixed',
      panel: 'flex',
    });
  }
});

test('auth-gated and legacy routes redirect', async ({ page }) => {
  await page.goto('/profile');
  await expect(page).toHaveURL(/\/login$/);

  for (const [from, to] of [
    ['/view', '/explore'],
    ['/annotate', '/explore?mode=annotate'],
    ['/contribute/label', '/scan?mode=triage'],
  ]) {
    await page.goto(from);
    // `to` carries a query string, so match the literal rather than a pattern:
    // an unescaped `?` is a regex quantifier.
    await expect(page).toHaveURL(new URL(to, page.url()).href);
  }
});
