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

/**
 * Every (editorial) page server-renders now, so the nav and the hero field are
 * painted — and clickable-looking — before their handlers exist. A click in
 * that window is dropped. The root layout sets `data-hydrated` in `onMount`;
 * waiting on it is the difference between a test that fails under parallel
 * load and one that tests the app.
 */
async function hydrated(page: import('@playwright/test').Page) {
  await page.locator('html[data-hydrated]').waitFor({ timeout: 15000 });
}

test('home renders and links into the catalog', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/./);
  await expect(page.locator('nav.top-nav a[href="/about"]')).toBeVisible();
  // The bar carries the reading pages directly; the tools sit behind Tools ▾,
  // whose contents are gated behind {#if open} — click to render them.
  await expect(page.locator('nav.top-nav a[href="/catalog"]')).toBeVisible();
  await hydrated(page);
  await page.locator('nav.top-nav button', { hasText: 'Tools' }).click();
  await expect(page.locator('nav a[href="/explore"]').first()).toBeVisible();
  await expect(page.locator('nav a[href="/directory"]').first()).toBeVisible();
});

// The hero field is a handoff, not a search: the reader's first keystroke has
// to survive the jump into the palette. Getting this wrong loses one character
// silently, which reads as a flaky keyboard rather than a bug.
test('the hero field hands its first keystrokes to the palette', async ({ page }) => {
  await page.goto('/');
  // The masthead is painted with the page now — it used to be the hero
  // sequence's last beat — but it is server-rendered, so it is on screen
  // before it is wired. Wait for both.
  const hero = page.locator('.hero-search-input').first();
  await expect(hero).toBeVisible({ timeout: 20000 });
  await hydrated(page);
  await hero.pressSequentially('Catin', { delay: 40 });

  const palette = page.locator('.cp input[role="combobox"]');
  await expect(palette).toHaveValue('Catin');
  // And the field it came from is empty, so coming back shows no ghost.
  await expect(hero).toHaveValue('');

  // A suggestion chip is the same handoff with the word already chosen.
  await page.keyboard.press('Escape');
  await page.locator('.hero-try', { hasText: '1882' }).click();
  await expect(palette).toHaveValue('1882');
});

/**
 * Loading the demo and playing it are two different triggers, and they used to
 * be one: the bytes load 400px early, which meant the four beats also started
 * 400px early — off screen, to nobody, and the reader scrolled down into a
 * composed frame having missed the sheet coming over the city.
 *
 * So this parks the page inside the preload lead but outside the viewport: the
 * clip proves the section loaded, and it must not have started.
 *
 * The third assertion is the one that keeps the front page cheap. What plays by
 * default is a recording, not OpenLayers; the live map is fetched only when the
 * reader asks for it. A canvas before that click means the section has gone
 * back to shipping ~179 kB of JavaScript and ~390 kB of basemap to everyone who
 * scrolls past.
 */
test('the how-it-works demo loads early, plays when scrolled to, and mounts no map until asked', async ({
  page,
}) => {
  await page.goto('/');
  await hydrated(page);

  const stage = page.locator('.hero-demo-stage');
  const clip = page.locator('.hero-demo-clip');

  // The catalog above the section renders after its fetch, which moves the
  // stage down the page — scroll before that and the offset means nothing.
  await expect(page.locator('.maps-loading')).toHaveCount(0, { timeout: 20000 });

  // 200px below the fold: inside the 400px lead, outside the viewport.
  await page.evaluate(() => {
    const el = document.querySelector('.hero-demo-stage');
    if (!el) throw new Error('no hero demo stage');
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo(0, top - window.innerHeight - 200);
  });

  await expect(clip).toBeAttached({ timeout: 12000 });
  // Past the point where a clip that was going to start off screen would have.
  await page.waitForTimeout(2000);
  expect(await clip.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);

  await stage.scrollIntoViewIfNeeded();
  await expect
    .poll(async () => clip.evaluate((v: HTMLVideoElement) => v.currentTime > 0), {
      timeout: 12000,
    })
    .toBe(true);

  // Nothing has fetched OpenLayers yet.
  await expect(stage.locator('canvas')).toHaveCount(0);

  await stage.getByRole('button').click();
  // `.first()`: MapShell paints more than one canvas, and a bare locator on
  // three of them is a strict-mode violation, not a wait.
  await expect(stage.locator('canvas').first()).toBeAttached({ timeout: 20000 });
  await expect(page.locator('.hero-caption p')).toBeVisible({ timeout: 20000 });
});

test('catalog search returns maps', async ({ page }) => {
  await page.goto('/catalog');
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

  // The left rail is two tabs since Sept 2026 and the layer stack lives on the
  // Picked one, so which tab is up decides whether `.lsp-text` exists at all.
  // Arriving with a stack selects Picked — except while the first-run tour is
  // running, which owns the tab so it can point at the pane each step
  // describes, and whose first step is Browse. Ack it the way a returning
  // visitor would have, as the sibling test below does: the subject here is
  // that `?map=` renders an overlay and reaches the stack, not the tour.
  await page.addInitScript(() => localStorage.setItem('vma-explore-tour-ack-v1', 'true'));

  // The overlay comes from the ?map= query param; the #hash only mirrors view state.
  await page.goto(`/explore?map=${maps[0].id}`);
  await expect(page.locator('.shell-map canvas').first()).toBeVisible({ timeout: 20_000 });
  // layersStore is the single source of truth; LayerStackPanel renders it.
  // `.lsp-name` is the sheet's name in a row — it was `.lsp-text` until the
  // panel's rows were restructured (Sept 2026) into a name-and-controls line
  // over an opacity line. `.lsp-row` would pass on an empty `<li>`; the name
  // is what proves the overlay actually reached the store.
  await expect(page.locator('.lsp-name').first()).toBeVisible({ timeout: 20_000 });
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

  // The browse rows are `ArchiveMapRows` — the catalog table with four columns
  // dropped (Sept 2026), so a row is a `<tr>`, not the `<button>` it was.
  const row = page.locator('.ebp .amr tbody tr').first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.click();

  // A slug, not a uuid (mig 088). Asserted as *not* 36 hex-and-hyphen characters
  // rather than merely "something is there", because the way this regresses is
  // silent and specific: a list query that forgets the `slug` column makes
  // `mapRef` fall back to the uuid, and the link still works — /explore opens
  // the right sheet, nothing errors, and the address bar quietly goes back to
  // being the opaque string this whole route exists to replace.
  await expect(page).toHaveURL(/[?&]map=[a-z0-9]+(?:-[a-z0-9]+)*(?:[&#]|$)/);
  await expect(page).not.toHaveURL(/[?&]map=[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/);
  await expect.poll(tallied, { timeout: 10_000 }).toBe(1);

  // Tapping the same row again removes the overlay, which must drop the param
  // rather than leave a stale id behind. Removal is not an open — no new tally.
  await row.click();
  await expect(page).not.toHaveURL(/[?&]map=/);
  expect(tallied()).toBe(1);
});

test('the IIIF tool pages mount their ImageShell', async ({ page }) => {
  // `/scan` bare is not in this list any more: it has no default mode since the
  // viewer merged into /catalog/[id], and a request without one is redirected.
  for (const route of [
    '/scan?mode=inspect',
    '/scan?mode=shapes',
    '/scan?mode=prepare',
    '/scan?mode=text',
  ]) {
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

test('the old /scan mode names still open the mode they became', async ({ page }) => {
  // The aliases in `$lib/core/scanModes.ts`, not redirects: these spellings are
  // in bookmarks and in the links /admin?tab=status prints. A mode that resolves
  // to nothing now leaves /scan for /catalog, so a broken alias would take a
  // contributor to the catalogue instead of the tool they asked for.
  for (const [alias, title] of [
    ['triage', 'Prepare'],
    ['prepare', 'Prepare'],
    ['text', 'Text'],
    ['trace', 'Shapes'],
    ['shapes', 'Shapes'],
    ['review', 'Shapes'],
  ]) {
    await page.goto(`/scan?mode=${alias}`);
    await expect(page).toHaveTitle(new RegExp(`^${title} — Vietnam Map Archive$`));
  }
});

test('auth-gated and legacy routes redirect', async ({ page }) => {
  await page.goto('/profile');
  await expect(page).toHaveURL(/\/login$/);

  // Compared as strings, not regexes: half these targets carry a `?`, which a
  // RegExp reads as "the previous character is optional" — `/explore?mode=…`
  // would quietly match nothing and the assertion would never fail honestly.
  for (const [from, to] of [
    ['/view', '/explore'],
    ['/annotate', '/explore?mode=studio'],
    ['/studio', '/explore?mode=studio'],
    ['/create', '/explore?mode=story'],
    ['/contribute/label', '/scan?mode=prepare'],
    ['/contribute/digitalize', '/scan?mode=prepare'],
    ['/contribute/trace', '/scan?mode=shapes'],
    ['/contribute/review', '/scan?mode=shapes&tab=validate'],
    ['/image', '/catalog'],
    // /scan stopped being a public address in Sept 2026: the read-only viewer
    // it offered is /catalog/[id], which has the same tiles plus the record.
    ['/scan', '/catalog'],
    ['/scan?mode=nonsense', '/catalog'],
    ['/admin/bulk', '/admin?tab=bulk'],
    ['/admin/status', '/admin?tab=status'],
    ['/place/rue-catinat', '/catalog/place/rue-catinat'],
  ]) {
    await page.goto(from);
    const landed = new URL(page.url());
    expect(landed.pathname + landed.search).toBe(to);
  }
});

/**
 * The sheet a retired link named has to survive the retirement.
 *
 * `/scan?map=<id>` was how /explore, the /catalog drawer and every bookmark
 * reached a scan. It redirects to that sheet's own page, which carries the
 * scan now — dropping the id and landing everyone on /catalog would turn one
 * broken habit into a hundred wrong pages. A `map` that is not a uuid is not
 * pasted into a path.
 */
test('a retired /scan link keeps the sheet it named', async ({ page }) => {
  // Synthetic references on purpose: the redirect is a URL rewrite in
  // `hooks.server.ts` and knows nothing about the row, so pinning it to a real
  // sheet would make this fail the day that sheet is unpublished — a data
  // change masquerading as a routing bug. Only the landing path is asserted.
  for (const ref of ['00000000-0000-4000-8000-000000000000', 'plan-de-saigon-1799']) {
    await page.goto(`/scan?map=${ref}`);
    expect(new URL(page.url()).pathname).toBe(`/catalog/${ref}`);
  }

  // `?map=` is a stranger's query string and whatever passes is pasted into a
  // path, so anything that is neither a uuid nor a slug is dropped instead.
  for (const junk of ['..%2Fadmin', 'Not A Slug', '']) {
    await page.goto(`/scan?map=${junk}`);
    expect(new URL(page.url()).pathname, junk).toBe('/catalog');
  }
});

// `?mode=annotate` is the name the tool shipped under and is still live in
// share links and bookmarks. The dispatcher aliases it to `studio` rather than
// redirecting, so the failure it guards against is silent: an unknown mode
// falls through to browse, and an old link would open the archive instead of
// the tool with no error anywhere.
test('an old ?mode=annotate link still opens the studio', async ({ page }) => {
  for (const mode of ['studio', 'annotate']) {
    await page.goto(`/explore?mode=${mode}`);
    await expect(page).toHaveTitle(/^Studio —/);
  }
});
