#!/usr/bin/env node
/**
 * gen-how-it-works-shots.mjs — the four pictures in the front page's
 * "How this works" section.
 *
 * Each one is a real screenshot of the app, not a mock-up: the 1882 survey
 * pinned over the city, the traced plots, a name searched in the palette, and
 * the Legend tab of the 1923 Saigon–Cholon plan. They are 3:2 crops so the
 * section reserves its height before the images arrive and nothing shifts.
 *
 * Written twice — `how-<n>-<name>.webp` at 1200 and `…-600.webp` — and the page
 * offers both as a `srcset`. Re-run it when the app's look changes or when a
 * sheet's data does (the legend counts, the traced plots): the pictures are
 * only true on the day they were taken.
 *
 *   npm run dev                          # or point HOW_BASE_URL at a preview
 *   node scripts/gen-how-it-works-shots.mjs
 *
 * Needs `cwebp` on PATH.
 */

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const BASE = process.env.HOW_BASE_URL ?? 'http://localhost:5173';
const OUT = join(ROOT, 'static/images/how');

const CADASTRE = 'plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise';
/** Cameras over the 1882 sheet, in `exploreUrl`'s hash form: the dense core, and the river edge. */
const HASH_CORE = '#@10.7745,106.6995,16.2z,0r';
const HASH_RIVER = '#@10.7712,106.7052,16z,0r';

/** 3:2, inside the map pane of a 1440×900 window — 15px in from the rails, whose drag handles sit on the edge. */
const MAP_CLIP = { x: 336, y: 300, width: 714, height: 476 };
/** 3:2 across the map and the right rail, so the list and its pin share a frame. */
const LEGEND_CLIP = { x: 320, y: 125, width: 1100, height: 733 };

const tmp = mkdtempSync(join(tmpdir(), 'how-'));

async function save(page, name, clip) {
  const png = join(tmp, `${name}.png`);
  await page.screenshot({ path: png, clip });
  for (const [suffix, width] of [
    ['', 1200],
    ['-600', 600],
  ]) {
    execFileSync('cwebp', [
      '-q',
      '82',
      '-resize',
      String(width),
      '0',
      png,
      '-o',
      join(OUT, `${name}${suffix}.webp`),
      '-quiet',
    ]);
  }
  console.log('wrote', name);
}

async function explore(browser, ref, hash = '') {
  // Fresh context each time: layer opacity is persisted in localStorage and
  // one shot's 75% must not leak into the next one's 100%.
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/explore?map=${ref}${hash}`, {
    waitUntil: 'networkidle',
  });
  await page.waitForTimeout(4000);
  return page;
}

const browser = await chromium.launch();
try {
  await import('node:fs').then((fs) => fs.mkdirSync(OUT, { recursive: true }));

  // 1 — the scan, a little transparent, so the modern streets show through its own.
  let page = await explore(browser, CADASTRE, HASH_RIVER);
  await page
    .locator('.lsp-range')
    .first()
    .evaluate((el) => {
      el.value = '0.75';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  await page.waitForTimeout(2500);
  await save(page, 'how-1-pin', MAP_CLIP);

  // 2 — the same sheet at full strength with the traced plots drawn on it.
  page = await explore(browser, CADASTRE, HASH_CORE);
  await page.getByText('Traced', { exact: false }).first().click();
  await page.waitForTimeout(4000);
  await save(page, 'how-2-trace', MAP_CLIP);

  // 3 — a name read off the sheets, found through the palette.
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  page = await ctx.newPage();
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.locator('.hero-try', { hasText: 'Khánh Hội' }).click();
  await page.locator('.cp-row').first().waitFor();
  await page.waitForTimeout(1500);
  // The scrim dims the masthead; paper instead, so the card sits on a clean ground.
  await page.addStyleTag({
    content: '.cp-scrim{background:var(--color-bg)!important;backdrop-filter:none!important}',
  });
  const box = await page.locator('.cp').boundingBox();
  // 3:2 around the dialog, centred on it: the palette is nearly square.
  const height = Math.ceil(box.height + 32);
  const width = Math.ceil(height * 1.5);
  await save(page, 'how-3-names', {
    x: box.x + box.width / 2 - width / 2,
    y: box.y - 16,
    width,
    height,
  });

  // 4 — the Legend tab: the numbered list, and the pin one entry lands on.
  page = await explore(browser, 'saigon-cholon');
  await page.getByText('Legend', { exact: true }).first().click();
  await page.getByRole('button', { name: 'Show legend points' }).click();
  await page.getByText('Institut Pasteur').first().click();
  await page.waitForTimeout(4500);
  await save(page, 'how-4-legend', LEGEND_CLIP);
} finally {
  await browser.close();
  rmSync(tmp, { recursive: true, force: true });
}
