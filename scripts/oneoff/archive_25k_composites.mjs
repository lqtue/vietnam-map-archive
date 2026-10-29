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
// points at it. The same run archives `my-tho-e` (see below).
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
for (const r of go) r.reason = REASON;

console.log(`${composites.length} composites: ${go.length} to archive, ${stay.length} stay`);
for (const r of stay) console.log(`  stays: ${r.slug} (${r.sheet_number}, ${r.year})`);

// Also: Indochine 1:100,000 sheet 229 E. IGN's Nakala deposit for it
// (nkl.710d1rim, "409_56366") holds 229W_27.jpg, byte-identical to the west
// half's deposit, so `my-tho-e` shows the west half. No east-half scan is on
// Nakala; its address opens cell 229, which honestly lists the west half alone.
const { data: myThoE, error: mtErr } = await db
  .from('maps')
  .select('id,slug,status,series_key,sheet_number,sheet_half,year,iiif_image')
  .eq('slug', 'my-tho-e')
  .neq('status', 'archived');
if (mtErr) throw mtErr;
for (const r of myThoE) {
  r.reason =
    "IGN's Nakala deposit for sheet 229 East (nkl.710d1rim) holds the West half's file " +
    '(229W_27.jpg, same SHA-1), so this record showed the wrong half. No East scan is known.';
  go.push(r);
}

for (const r of go) console.log(`  ${r.slug} → /catalog/series/${r.series_key}/${r.sheet_number}`);

// Tiles go only when no other row's image lives under the same prefix.
const prefixOf = (r) => r.iiif_image?.match(/\/iiif\/([0-9a-f-]{36})(?:\/|$)/)?.[1];
const others = [];
for (let from = 0; ; from += 1000) {
  const { data, error: e } = await db
    .from('maps')
    .select('id,iiif_image')
    .range(from, from + 999);
  if (e) throw e;
  others.push(...data);
  if (data.length < 1000) break;
}
const goIds = new Set(go.map((r) => r.id));
const shared = new Set(
  others
    .filter((r) => !goIds.has(r.id))
    .map(prefixOf)
    .filter(Boolean)
);
const purge = go.filter((r) => prefixOf(r) === r.id && !shared.has(r.id));
console.log(`tiles to delete: ${purge.length} prefixes (skipped ${go.length - purge.length})`);

if (!APPLY) {
  console.log('\ndry run — nothing written. Re-run with --apply.');
  process.exit(0);
}

const archived = new Set();
for (const reason of new Set(go.map((r) => r.reason))) {
  const { data: done, error: upErr } = await db
    .from('maps')
    .update({ status: 'archived', archive_reason: reason })
    .in(
      'id',
      go.filter((r) => r.reason === reason).map((r) => r.id)
    )
    .select('id');
  if (upErr) throw upErr;
  for (const r of done) archived.add(r.id);
}
console.log(`archived ${archived.size} rows`);

for (const r of purge.filter((r) => archived.has(r.id))) {
  execFileSync('rclone', ['purge', `r2:vma-tiles/tiles/${r.id}`], { stdio: 'inherit' });
  console.log(`  tiles deleted: ${r.slug}`);
}
