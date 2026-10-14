#!/usr/bin/env node
/**
 * gen-changelog-shots.mjs — the pictures on /changelog.
 *
 * A version history that shows nothing is a list of claims. These are real
 * screenshots of running sites, which is also why there are only two of them:
 *
 *   changelog-7.0.webp  maparchive.vn as it stands
 *   changelog-2.1.webp  lqtue.github.io/VMA — the 2025 site, still published
 *
 * Versions 3.0 through 6.0 have no image and are not going to get one. There
 * is no deployed instance of any of them, and the code of, say, 4.0 against
 * today's database renders error pages rather than that version's front page —
 * a screenshot of it would be a lie about what shipped. An empty slot is
 * honest; a reconstruction is not.
 *
 * Both shots are deterministic on purpose. The front page's header slider
 * sweeps by itself until a reader touches it, so the script touches it —
 * a real pointerdown, which is the documented way the sweep stops — and then
 * pins the slider to the 1882 end. Without that, the frame lands wherever the
 * animation happened to be. The 2025 site gets its own furniture removed: the
 * notice we added in Sept 2026 pointing at maparchive.vn is 2026 chrome on a
 * 2025 page, and photographing it would date the picture wrongly.
 *
 *   node scripts/gen/gen-changelog-shots.mjs
 *   CHANGELOG_BASE_URL=http://localhost:5173 node scripts/gen/gen-changelog-shots.mjs
 *
 * Re-run it when a version ships, and add the row in
 * `src/routes/(editorial)/changelog/releases.ts`. Needs `cwebp` on PATH.
 */

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const OUT = join(ROOT, 'static/images/changelog');
const BASE = process.env.CHANGELOG_BASE_URL ?? 'https://maparchive.vn';

/** The card is never wider than the 1100px `.editorial-main`; 1200 covers it. */
const WIDTH = 1200;
const HEIGHT = 750;
/** The small end of the `srcset`, for a phone that gets the card full-bleed. */
const SMALL_WIDTH = 600;

mkdirSync(OUT, { recursive: true });
const tmp = mkdtempSync(join(tmpdir(), 'vma-changelog-'));
const browser = await chromium.launch();

/** Screenshot one page, then write both cuts as webp. */
async function shoot(name, url, prepare) {
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: HEIGHT },
    // Twice the output, so the downscale resolves hairlines rather than
    // aliasing them — the same reason gen-hero-still.mjs shoots at 2x.
    deviceScaleFactor: 2,
  });

  await page.goto(url, { waitUntil: 'load' });
  await prepare(page);

  const raw = join(tmp, `${name}.png`);
  await page.screenshot({ path: raw });
  await page.close();

  // cwebp resizes as it encodes. vips is deliberately not in this chain: it
  // read the freshly written PNG as truncated ("not enough data") and wrote a
  // doubled frame, and one tool that does both is one fewer thing to be wrong.
  for (const [suffix, width] of [
    ['', WIDTH],
    ['-600', SMALL_WIDTH],
  ]) {
    const out = join(OUT, `${name}${suffix}.webp`);
    execFileSync('cwebp', ['-q', '82', '-resize', String(width), '0', '-quiet', raw, '-o', out]);
    console.log(`${name}${suffix}.webp  ${(statSync(out).size / 1024).toFixed(0)} kB`);
  }
}

await shoot('changelog-7.0', BASE, async (page) => {
  // Stop the header's self-sweep the way a reader does, then pin the slider to
  // the 1882 end so the frame is the same every run.
  const slider = page.locator('input[type="range"]').first();
  await slider.waitFor();
  await slider.dispatchEvent('pointerdown');
  await slider.evaluate((el) => {
    el.value = el.max;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(1200);
});

await shoot('changelog-2.1', 'https://lqtue.github.io/VMA/', async (page) => {
  // Its welcome screen fades on a timer, and Leaflet has tiles to fetch.
  await page.waitForTimeout(6000);
  // Drop the Sept 2026 notice — 2026 chrome does not belong in a 2025 picture.
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('body > div[style*="position:fixed"]')) {
      if (el.textContent?.includes('maparchive.vn')) el.remove();
    }
  });
  await page.waitForTimeout(300);
});

await browser.close();
rmSync(tmp, { recursive: true, force: true });
