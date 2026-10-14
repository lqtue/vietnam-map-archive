#!/usr/bin/env node
/**
 * gen-hero-still.mjs — the front page's header images.
 *
 * The header used to be the live OpenLayers hero, which cost every visitor
 * 179 kB of JavaScript and ~390 kB of basemap before the masthead painted. It
 * is two images now, cross-faded by the Today/1882 slider, and this is where
 * they come from: it drives the real `HeroDemo` section and photographs it
 * twice, so the header and the live demo below it are the same picture at the
 * same scale and rotation.
 *
 *   hero-now.webp   the modern city alone — the sequence's first beat
 *   hero-1882.webp  the composed frame: sheet, traced plots, placed labels
 *
 * Each is written twice, at 1600 and at 800 (`hero-now-800.webp`), which is the
 * `srcset` the header offers. Both cuts are regenerated together — a stale 800
 * beside a fresh 1600 is a phone showing last week's frame.
 *
 * The two passes are separate page loads rather than two moments in one, and
 * the first one **aborts the annotation request** on purpose. That is not a
 * trick to save a download — it is what makes the shot deterministic:
 * `HeroSequence.start()` catches a failed overlay by parking at stage 0 and
 * returning, so the sheet, the footprints and the labels never arrive and
 * there is no 1.5-second window to race. Shooting the live beat 0 instead
 * meant catching the frame between "the basemap painted" and "the sheet
 * starts fading in".
 *
 * Re-run it whenever `HERO_SHEET` on the home page changes, or when the fabric
 * is regenerated (`scripts/gen/gen-hero-fabric.mjs`) and the drawing moves.
 *
 * **The committed stills are older than the current demo camera.** The live
 * section was refitted to frame the whole sheet; the header was deliberately
 * left on the earlier pinned close-up. Running this replaces the header with
 * the wide view — which is a decision to make, not a fix to apply.
 *
 *   npm run dev                     # or point HERO_BASE_URL at a preview
 *   node scripts/gen/gen-hero-still.mjs
 *
 * Needs `vips` and `cwebp` on PATH (both come with the tile pipeline).
 */

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const BASE = process.env.HERO_BASE_URL ?? 'http://localhost:5173';

/** What the `<img>`s on the home page declare. Keep these in step. */
const WIDTH = 1600;
const HEIGHT = 900;

/**
 * The second cut, written beside each full-size still as `<name>-800.webp` and
 * offered as the small end of the header's `srcset`. The header image is
 * full-bleed, so a 390px phone was being handed 1600px of picture — the two
 * stills alone were a third of the front page's weight at rest, most of it
 * pixels the screen cannot draw. Same frame, half the edge, a quarter the area.
 */
const SMALL_WIDTH = 800;

/** The sequence is four beats plus fades; this is the ceiling, not the wait. */
const SETTLE_TIMEOUT_MS = 90_000;

/**
 * Everything in the stage that is chrome rather than picture. The header draws
 * its own furniture, and the live demo below still carries the real OL
 * attribution — the sheet covers the basemap at this opacity anyway. The
 * sticky top bar paints *over* the stage, so Playwright photographs it along
 * with the map unless it is hidden; the stage's own border would otherwise be
 * photographed and then drawn again over the photograph.
 */
const HIDE_CHROME = `
  .hero-demo-stage label,
  .hero-demo-stage [aria-live],
  .hero-demo-stage .ol-scale-line,
  .hero-demo-stage .ol-attribution,
  .hero-demo-stage .ol-control { display: none !important }
  .top-nav { display: none !important }
  .hero-demo-stage { border: 0 !important; border-radius: 0 !important }
`;

const tmp = mkdtempSync(join(tmpdir(), 'vma-hero-'));
const browser = await chromium.launch();

/** One pass: load the page, get the stage to `ready`, photograph it. */
async function shoot(name, ready, { blockAnnotation = false } = {}) {
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: HEIGHT },
    // Twice the output size, so the downscale to 1600×900 resolves the sheet's
    // hairlines instead of aliasing them.
    deviceScaleFactor: 2,
  });

  if (blockAnnotation) {
    await page.route('**/storage/v1/object/public/annotations/*', (r) => r.abort());
  }

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.locator('#how-it-works').scrollIntoViewIfNeeded();
  await ready(page);
  await page.addStyleTag({ content: HIDE_CHROME });

  const raw = join(tmp, `${name}.png`);
  await page.locator('.hero-demo-stage').screenshot({ path: raw });
  await page.close();

  // `thumbnail` crops to the exact frame rather than letterboxing it — the
  // stage is already 16:9, so this is a resize with a rounding tolerance. Both
  // cuts come off the same 2x screenshot rather than one off the other, so the
  // small one is a downscale of the capture and not of a lossy WebP.
  for (const width of [WIDTH, SMALL_WIDTH]) {
    const height = Math.round((width * HEIGHT) / WIDTH);
    const stem = width === WIDTH ? name : `${name}-${width}`;
    const resized = join(tmp, `${stem}-resized.png`);
    const out = join(ROOT, `static/images/${stem}.webp`);
    const size = [String(width), '--height', String(height), '--crop', 'centre'];
    execFileSync('vips', ['thumbnail', raw, resized, ...size]);
    execFileSync('cwebp', ['-q', '78', '-m', '6', resized, '-o', out]);
    console.log(`${out} — ${(statSync(out).size / 1024).toFixed(0)} kB`);
  }
}

try {
  // Today. With the annotation aborted the sequence parks at beat 0 forever,
  // so the only thing left to wait for is the basemap finishing its tiles.
  await shoot(
    'hero-now',
    async (page) => {
      await page.locator('.hero-demo-stage canvas').first().waitFor({ timeout: SETTLE_TIMEOUT_MS });
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
    },
    { blockAnnotation: true }
  );

  // 1882. The slider only appears once every beat has played, which is exactly
  // the frame worth photographing.
  await shoot('hero-1882', async (page) => {
    await page.locator('.hero-demo-stage label').waitFor({ timeout: SETTLE_TIMEOUT_MS });
    // Let the last tiles at the final opacity actually paint.
    await page.waitForTimeout(3000);
  });
} finally {
  await browser.close();
  rmSync(tmp, { recursive: true, force: true });
}
