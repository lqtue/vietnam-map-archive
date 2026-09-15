#!/usr/bin/env node
/**
 * gen-hero-video.mjs — the front page's demo clip.
 *
 *   npm run dev                      # or point HERO_BASE_URL at a preview
 *   node scripts/gen-hero-video.mjs
 *
 * Writes, into `static/video/`:
 *
 *   hero-demo.mp4        1200px wide, H.264
 *   hero-demo-800.mp4    the phone cut
 *   hero-demo-poster.webp + -800   frame 0, which is the clip's own first frame
 *
 * Why a clip at all. The section's whole claim is a sheet arriving over the
 * city, and until now a reader who never got OpenLayers — a metered connection,
 * a refused WebGL context, anyone who left before ~600 kB of map arrived — saw
 * one frozen frame of the end state and none of the movement. The clip is
 * cheaper than the map it stands in for: measured on this sequence, 832 kB at
 * 1200px and 367 kB at 800px, against ~179 kB of JavaScript plus ~390 kB of
 * basemap before OL draws a single tile.
 *
 * **Not a GIF.** The same nine seconds at 800px and 10 fps is 12.1 MB as a GIF
 * — 33x the H.264 of the same width. 256 colours and no interframe compression
 * is the worst possible match for a hand-coloured survey cross-fading into
 * satellite imagery, and this content is nearly static, which is exactly what
 * interframe compression is for.
 *
 * The poster is **frame 0 of the clip**, not `hero-1882.webp`. The header's
 * stills are a pinned close-up kept on purpose while this section frames the
 * whole sheet (see `HERO_1882` on the home page), so borrowing one put an
 * enlarged sheet behind the live map. Taking the poster off the clip makes the
 * two agree by construction, and leaves the header alone.
 *
 * Shares `HIDE_CHROME` with `gen-hero-still.mjs` for the same reasons, with one
 * difference: the **captions stay**. They are furniture in a photograph and
 * narration in a clip — they are the four claims the section makes.
 *
 * The whole of `.hero-controls` goes, which is the slider *and* the
 * ⌘/Ctrl-scroll hint. Both are promises about a surface that accepts gestures,
 * and a clip does not; the first cut left the hint in and it sat there over the
 * last two seconds inviting the reader to try. Dragging and zooming are what
 * the live map is for, and the section offers it as an upgrade.
 *
 * Re-run it whenever `HERO_SHEET` changes, the fabric is regenerated, or the
 * beats in `HeroSequence` move. Needs `ffmpeg`, `vips` and `cwebp` on PATH.
 */

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, statSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const BASE = process.env.HERO_BASE_URL ?? 'http://localhost:5173';

/**
 * Tall enough that the stage is a true 16:9. `.hero-demo-stage` is
 * `aspect-ratio: 16/9` capped at `max-height: 70vh`, and at a 900px viewport
 * the cap wins — the stage comes out 1192x630, which is 1.89:1. Then the clip
 * does not match the box it plays in. 1100px of viewport puts the cap above
 * the ratio's own height, so the ratio decides.
 */
const VIEWPORT = { width: 1600, height: 1100 };

/** Output widths. The 800 is the phone cut, as with the stills. */
const WIDTHS = [1200, 800];

/**
 * Constant rate factor. 30 was chosen by sweeping this exact sequence:
 * crf 26 = 1487 kB, crf 30 = 832 kB, crf 34 = 451 kB. At 30 the sheet's
 * printed label text is still crisp at 1200px, which is the thing worth
 * spending bytes on.
 */
const CRF = 30;

/** Beats run to 6400 ms, then the last fade. This is the ceiling, not the wait. */
const SETTLE_TIMEOUT_MS = 90_000;
/** Held past the final beat so the clip ends on the composed frame, not mid-fade. */
const TAIL_MS = 2500;

/** As `gen-hero-still.mjs`, minus the captions — see the header. */
const HIDE_CHROME = `
  .hero-controls,
  .hero-demo-stage .ol-scale-line,
  .hero-demo-stage .ol-attribution,
  .hero-demo-stage .ol-control { display: none !important }
  .top-nav { display: none !important }
  .hero-demo-stage { border: 0 !important; border-radius: 0 !important }
`;

const tmp = mkdtempSync(join(tmpdir(), 'vma-hero-vid-'));
const outDir = join(ROOT, 'static/video');
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();

const kB = (p) => `${(statSync(p).size / 1024).toFixed(0)} kB`;

try {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: { dir: tmp, size: VIEWPORT },
  });
  const page = await ctx.newPage();
  const t0 = Date.now();

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  // The catalog above the section renders after its own fetch and moves the
  // stage down the page; parking before that lands somewhere else entirely.
  await page.locator('.maps-loading').waitFor({ state: 'detached', timeout: 30_000 });
  await page.addStyleTag({ content: HIDE_CHROME });

  // Park 200px below the fold: inside HeroDemo's 400px preload lead, outside
  // the viewport. The map mounts and warms its tiles, and the beats — which
  // wait on a second observer at the real viewport edge — do not start. So the
  // clip opens on a basemap that has already painted rather than on grey.
  await page.evaluate(() => {
    const el = document.querySelector('.hero-demo-stage');
    if (!el) throw new Error('no .hero-demo-stage');
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo(0, top - window.innerHeight - 200);
  });
  await page.locator('.hero-demo-stage canvas').first().waitFor({ timeout: SETTLE_TIMEOUT_MS });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);

  // Now let it play, and remember when — the recording started at context
  // creation, so this offset is where the clip should begin.
  await page.locator('.hero-demo-stage').scrollIntoViewIfNeeded();
  const startMs = Date.now() - t0;
  const rect = await page.evaluate(() => {
    const r = document.querySelector('.hero-demo-stage').getBoundingClientRect();
    return {
      x: Math.round(r.x),
      y: Math.round(r.y),
      w: Math.round(r.width),
      h: Math.round(r.height),
    };
  });
  console.log(
    `stage ${rect.w}x${rect.h} at ${rect.x},${rect.y} — ratio ${(rect.w / rect.h).toFixed(3)}`
  );

  // The controls are hidden, not absent: `attached` is what says the beats are
  // done, since `HeroDemo` only renders them once the sequence has settled.
  await page.locator('.hero-controls').waitFor({ state: 'attached', timeout: SETTLE_TIMEOUT_MS });
  await page.waitForTimeout(TAIL_MS);
  const endMs = Date.now() - t0;

  await ctx.close();

  const raw = join(
    tmp,
    readdirSync(tmp).find((f) => f.endsWith('.webm'))
  );
  const ss = (startMs / 1000).toFixed(2);
  const dur = ((endMs - startMs) / 1000).toFixed(2);
  console.log(`clip: ${dur}s from ${ss}s of the recording`);

  // Crop first, into a visually lossless intermediate, so each output width is
  // a scale of the capture rather than of an already-compressed frame.
  const cropped = join(tmp, 'cropped.mp4');
  execFileSync('ffmpeg', [
    '-v',
    'error',
    '-y',
    '-ss',
    ss,
    '-t',
    dur,
    '-i',
    raw,
    '-vf',
    `crop=${rect.w}:${rect.h}:${rect.x}:${rect.y}`,
    '-an',
    '-c:v',
    'libx264',
    '-crf',
    '14',
    '-preset',
    'veryfast',
    cropped,
  ]);

  for (const width of WIDTHS) {
    const stem = width === WIDTHS[0] ? 'hero-demo' : `hero-demo-${width}`;
    const out = join(outDir, `${stem}.mp4`);
    execFileSync('ffmpeg', [
      '-v',
      'error',
      '-y',
      '-i',
      cropped,
      // -2: keep the height even, which H.264 requires and 16:9 does not grant.
      '-vf',
      `scale=${width}:-2`,
      '-an',
      '-c:v',
      'libx264',
      '-crf',
      String(CRF),
      '-preset',
      'slow',
      '-pix_fmt',
      'yuv420p',
      '-movflags',
      '+faststart',
      out,
    ]);
    console.log(`${out} — ${kB(out)}`);
  }

  // The poster is frame 0 of the clip itself, so the still the reader waits on
  // is the exact frame the clip opens with.
  const frame = join(tmp, 'poster.png');
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', cropped, '-frames:v', '1', frame]);
  for (const width of WIDTHS) {
    const stem = width === WIDTHS[0] ? 'hero-demo-poster' : `hero-demo-poster-${width}`;
    const resized = join(tmp, `${stem}.png`);
    const out = join(outDir, `${stem}.webp`);
    execFileSync('vips', ['thumbnail', frame, resized, String(width)]);
    execFileSync('cwebp', ['-q', '78', '-m', '6', resized, '-o', out]);
    console.log(`${out} — ${kB(out)}`);
  }
} finally {
  await browser.close();
  rmSync(tmp, { recursive: true, force: true });
}
