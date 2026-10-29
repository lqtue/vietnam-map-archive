#!/usr/bin/env node
// Archive the Indochine 1:25,000 whole-cell composites that IGN's own two
// half-sheets now replace, and delete their tiles.
//
//   node --env-file=.env scripts/oneoff/archive_25k_composites.mjs           # dry run
//   node --env-file=.env scripts/oneoff/archive_25k_composites.mjs --apply
//
// A composite is a third party's join of the two halves into one image, not a
// printed sheet. Once both originals of the same printing are public it adds
// nothing, so it is archived (not deleted: its georeference versions and
// history stay) with a reason and no duplicate target. /catalog/[id] then 301s
// its slug and every retired alias to the survey cell page, which lists both
// halves. Found 2026-10-29: 60 of 63 composites qualify; Phát Diệm 1927 (W
// only), Cửa Trà Lý 1926 and An Thi 1904 (no halves) stay.
//
// Tiles go only when the image prefix is the row's own uuid and no other row
// points at it.
import { execFileSync } from 'node:child_process';
import { serviceClient } from '../lib/db.mjs';

const APPLY = process.argv.includes('--apply');
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const REASON =
  "Third party's join of IGN's two half-sheets for this cell; both originals are held. " +
  'The address opens the survey cell, which lists them.';

const db = serviceClient();
const { data: rows, error } = await db
  .from('maps')
  .select('id,slug,status,series_key,sheet_number,sheet_half,year,iiif_image')
  .eq('collection', COLLECTION);
if (error) throw error;

const halves = new Set(
  rows
    .filter((r) => r.sheet_half && ['public', 'featured'].includes(r.status))
    .map((r) => `${r.sheet_number}|${r.year}|${r.sheet_half}`)
);
const composites = rows.filter((r) => !r.sheet_half && r.status !== 'archived');
const go = composites.filter(
  (r) =>
    r.series_key &&
    r.sheet_number &&
    halves.has(`${r.sheet_number}|${r.year}|W`) &&
    halves.has(`${r.sheet_number}|${r.year}|E`)
);
const stay = composites.filter((r) => !go.includes(r));

console.log(`${composites.length} composites: ${go.length} to archive, ${stay.length} stay`);
for (const r of stay) console.log(`  stays: ${r.slug} (${r.sheet_number}, ${r.year})`);
for (const r of go) console.log(`  ${r.slug} → /catalog/series/${r.series_key}/${r.sheet_number}`);

const prefixOf = (r) => r.iiif_image?.match(/\/iiif\/([0-9a-f-]{36})(?:\/|$)/)?.[1];
const shared = new Set(
  rows
    .filter((r) => !go.includes(r))
    .map(prefixOf)
    .filter(Boolean)
);
const purge = go.filter((r) => prefixOf(r) === r.id && !shared.has(r.id));
console.log(`tiles to delete: ${purge.length} prefixes (skipped ${go.length - purge.length})`);

if (!APPLY) {
  console.log('\ndry run — nothing written. Re-run with --apply.');
  process.exit(0);
}

const { data: done, error: upErr } = await db
  .from('maps')
  .update({ status: 'archived', archive_reason: REASON })
  .in(
    'id',
    go.map((r) => r.id)
  )
  .select('id');
if (upErr) throw upErr;
console.log(`archived ${done.length} rows`);

const archived = new Set(done.map((r) => r.id));
for (const r of purge.filter((r) => archived.has(r.id))) {
  execFileSync('rclone', ['purge', `r2:vma-tiles/tiles/${r.id}`], { stdio: 'inherit' });
  console.log(`  tiles deleted: ${r.slug}`);
}
