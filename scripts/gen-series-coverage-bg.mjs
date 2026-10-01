#!/usr/bin/env node
/**
 * gen-series-coverage-bg.mjs — the picture behind each survey's coverage map.
 *
 * `SeriesCoverageMap` draws a survey's cells as SVG; this makes the ground
 * under them. It does not render the PMTiles itself: it opens /explore, which
 * already draws our own basemap (`tiles.maparchive.vn`), at a camera worked
 * out from the survey's cells, and photographs the map element. One image per
 * survey, a few tens of kB, so the page makes no tile requests at all.
 *
 * What the component needs back is the image's exact extent, so it can put the
 * cells in the right place. That is worked out here from the camera, not read
 * off the map: OL's default View is 256px tiles, so a zoom `z` is
 * `156543.03392 / 2^z` metres per pixel in EPSG:3857, and the frame is the
 * centre ± half the element's size at that resolution. The zoom is rounded
 * DOWN to two decimals (the hash carries two) and the extent is computed from
 * the rounded value, so the manifest describes the picture that was taken.
 *
 *   npm run dev                       # or BASE_URL=<preview>
 *   node scripts/gen-series-coverage-bg.mjs
 *
 * Writes static/images/coverage/<key>.webp and
 * src/lib/features/catalog/coverageBackdrops.json. Re-run when a survey gains
 * cells outside its old frame, or the basemap's style changes. Needs `cwebp`.
 */

import { chromium } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const BASE = process.env.BASE_URL ?? 'http://localhost:5173';
const OUT_DIR = join(ROOT, 'static/images/coverage');
const MANIFEST = join(ROOT, 'src/lib/features/catalog/coverageBackdrops.json');

const R = 6378137;
const Z0_RES = 156543.03392;
/** Margin round the cells, as a fraction of their span. */
const MARGIN = 0.06;

const mx = (lng) => (R * lng * Math.PI) / 180;
const my = (lat) => R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const lng = (x) => ((x / R) * 180) / Math.PI;
const lat = (y) => ((2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * 180) / Math.PI;

const env = Object.fromEntries(
  readFileSync(join(ROOT, '.env'), 'utf8')
    .split('\n')
    .filter((l) => l.includes('=') && !l.startsWith('#'))
    .map((l) => [
      l.slice(0, l.indexOf('=')),
      l.slice(l.indexOf('=') + 1).replace(/^["']|["']$/g, ''),
    ])
);
const supabase = createClient(env.PUBLIC_SUPABASE_URL, env.PUBLIC_SUPABASE_ANON_KEY);

/**
 * Every survey's cells, as one union box each — the cells' own boxes and the
 * georeferenced records', which is what the series page draws (a cell's own box
 * is one half-sheet).
 */
async function surveyBoxes() {
  const [cells, maps] = await Promise.all([
    supabase.from('series_cells').select('series_key,bbox'),
    supabase
      .from('maps')
      .select('series_key,bbox')
      .not('series_key', 'is', null)
      .in('status', ['public', 'featured']),
  ]);
  if (cells.error) throw cells.error;
  if (maps.error) throw maps.error;
  const boxes = new Map();
  for (const { series_key, bbox } of [...cells.data, ...maps.data]) {
    if (bbox?.length !== 4) continue;
    const b = boxes.get(series_key) ?? [180, 90, -180, -90];
    boxes.set(series_key, [
      Math.min(b[0], bbox[0]),
      Math.min(b[1], bbox[1]),
      Math.max(b[2], bbox[2]),
      Math.max(b[3], bbox[3]),
    ]);
  }
  return boxes;
}

/**
 * The first-visit notice and the tour are dialogs over the map. They are hidden
 * rather than answered: answering "show all maps" re-centres the map and the
 * hash camera is lost.
 */
const HIDE_CHROME = `
  .ol-control, .ol-attribution, .ol-scale-line, .ol-zoom { display: none !important }
  .top-nav, [aria-modal="true"], .backdrop { display: none !important }
`;

/** The sidebars' drag handles sit on the map's left and right edges; cut them off. */
const INSET = 16;

const browser = await chromium.launch();

/** A fresh page each time: the hash is only read when the map is built. */
async function open(hash) {
  const page = await browser.newPage({
    viewport: { width: 1400, height: 1000 },
    colorScheme: 'light',
  });
  await page.goto(`${BASE}/explore#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.locator('.ol-viewport').first().waitFor({ timeout: 60_000 });
  await page.addStyleTag({ content: HIDE_CHROME });
  return page;
}

mkdirSync(OUT_DIR, { recursive: true });
const manifest = {};

try {
  const probe = await open('@0,0,2z,0r');
  const size = await probe.locator('.ol-viewport').first().boundingBox();
  await probe.close();
  const [w, h] = [Math.round(size.width) - 2 * INSET, Math.round(size.height)];

  for (const [key, b] of await surveyBoxes()) {
    const [x0, y0, x1, y1] = [mx(b[0]), my(b[1]), mx(b[2]), my(b[3])];
    const [cx, cy] = [(x0 + x1) / 2, (y0 + y1) / 2];
    const res = Math.max(((x1 - x0) * (1 + 2 * MARGIN)) / w, ((y1 - y0) * (1 + 2 * MARGIN)) / h);
    const zoom = Math.floor(Math.log2(Z0_RES / res) * 100) / 100;
    const px = Z0_RES / 2 ** zoom;

    const page = await open(`@${lat(cy).toFixed(6)},${lng(cx).toFixed(6)},${zoom}z,0r`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    const raw = join(OUT_DIR, `${key}.png`);
    const box = await page.locator('.ol-viewport').first().boundingBox();
    await page.screenshot({ path: raw, clip: { x: box.x + INSET, y: box.y, width: w, height: h } });
    await page.close();

    const out = join(OUT_DIR, `${key}.webp`);
    execFileSync('cwebp', ['-q', '70', '-m', '6', raw, '-o', out], { stdio: 'ignore' });
    execFileSync('rm', [raw]);

    manifest[key] = {
      file: `/images/coverage/${key}.webp`,
      bbox: [
        lng(cx - (w * px) / 2),
        lat(cy - (h * px) / 2),
        lng(cx + (w * px) / 2),
        lat(cy + (h * px) / 2),
      ].map((n) => Math.round(n * 1e5) / 1e5),
    };
    console.log(`${key} z${zoom} — ${(statSync(out).size / 1024).toFixed(0)} kB`);
  }
  writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2) + '\n');
} finally {
  await browser.close();
}
