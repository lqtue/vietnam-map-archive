import { expect, test } from '@playwright/test';

// Mocked catalog scale checks: no database writes, no dependence on production counts.
for (const [total, mobile] of [
  [10000, false],
  [100000, false],
  [100000, true],
] as const) {
  test(`Explore renders bounded pages for ${total} maps${mobile ? ' on mobile' : ''}`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const requests: URL[] = [];
    const fullReads: string[] = [];
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.addInitScript(() => {
      localStorage.clear();
      localStorage.setItem('vma-explore-tour-ack-v1', 'true');
      localStorage.setItem('vma-explore-welcome-ack-v2', 'all');
    });
    await page.route('**/rest/v1/**', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/maps')) fullReads.push(url.href);
      await route.fulfill({ json: [] });
    });
    await page.route('**/api/explore/maps?**', async (route) => {
      const url = new URL(route.request().url());
      requests.push(url);
      const second = url.searchParams.has('cursor');
      const query = url.searchParams.get('q');
      const maps = Array.from({ length: query ? 1 : 60 }, (_, i) => ({
        id: `00000000-0000-4000-8000-${String((second ? 60 : 0) + i).padStart(12, '0')}`,
        slug: `fixture-${(second ? 60 : 0) + i}`,
        name: query ? 'Huế rare sheet' : `Fixture sheet ${(second ? 60 : 0) + i}`,
        year: 1960,
        status: 'public',
        georef_done: true,
        region: 'Thừa Thiên Huế',
        series_key: 'fixture-series',
        collection: 'Fixture survey',
      }));
      await route.fulfill({
        json: {
          maps,
          total: { maps: query ? 1 : total, drafts: 0, scout: 0 },
          facets: { series_key: { 'fixture-series': total } },
          choices: { area: [], region: [], type: [], institution: [], series: [] },
          yearBins: [
            { decade: 1960, count: 10 },
            { decade: 2000, count: 20 },
          ],
          seriesCounts: { 'fixture-series': query ? 1 : total },
          nextCursor:
            second || query
              ? null
              : JSON.stringify({ year: 1960, name: 'Fixture sheet 59', id: maps[59].id }),
        },
      });
    });
    await page.goto('/explore');
    if (mobile) await page.getByRole('button', { name: 'Browse', exact: true }).click();
    const browse = page.locator(mobile ? '[data-tour="browse-mobile"]' : 'aside.sb-rail');
    await expect(browse.getByText(`${total} maps`, { exact: true })).toBeVisible();
    await expect(browse.locator('.amr tbody tr')).toHaveCount(60);
    await expect(browse.locator('.bars .bar').nth(1)).toHaveCSS('left', /.+/);
    expect(
      await browse
        .locator('.bars .bar')
        .nth(1)
        .evaluate((bar) => (bar as HTMLElement).style.left)
    ).toBe('80%');
    expect(requests).toHaveLength(1); // Desktop and mobile share their page-scoped controller.
    await browse
      .getByRole('navigation', { name: 'Map result pages' })
      .getByRole('button', { name: 'Next' })
      .click();
    await expect(browse.getByText('Fixture sheet 60', { exact: true })).toBeVisible();
    await expect(browse.locator('.amr tbody tr')).toHaveCount(60);
    await browse
      .getByRole('navigation', { name: 'Map result pages' })
      .getByRole('button', { name: 'Previous' })
      .click();
    await expect(browse.getByText('Fixture sheet 0', { exact: true })).toBeVisible();
    await browse.getByPlaceholder('Search maps…').fill('hue');
    await expect(browse.getByText('Huế rare sheet', { exact: true })).toBeVisible();
    await expect(browse.locator('.amr tbody tr')).toHaveCount(1);
    expect(requests.every((url) => Number(url.searchParams.get('limit')) <= 100)).toBe(true);
    expect(fullReads).toEqual([]);
    expect(errors).toEqual([]);
  });
}
