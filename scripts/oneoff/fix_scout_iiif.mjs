#!/usr/bin/env node
// Backfill the IIIF fields on scout_candidates rows loaded before
// scripts/scout/scoutDerive.mjs existed.
//
// Three fixes, all derived from data already on the row — no source fetches:
//   1. Omeka S rows (Bordeaux 3) arrived with no manifest_url; derive it.
//   2. LoC rows have no reachable manifest, but their thumbnail names an
//      Image API endpoint; store it in raw.iiif_image so ingest can use it.
//   3. LoC protocol-relative source_url (`//hdl.loc.gov/…`) gets a scheme.
//
// Without 1 and 2 an approved row ingests as a maps draft with no image at all:
// /api/admin/scout writes whatever manifest_url holds, and null is allowed on a
// draft (mig 062 only constrains published maps).
//
// Usage:
//   node scripts/oneoff/fix_scout_iiif.mjs            # dry-run, prints the diff
//   node scripts/oneoff/fix_scout_iiif.mjs --apply

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { deriveManifestUrl, deriveImageUrl, fixSourceUrl } from '../scout/scoutDerive.mjs';

const env = Object.fromEntries(
  readFileSync(resolve(process.cwd(), '.env'), 'utf8')
    .split('\n')
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => l.split('=').map((s) => s.trim()))
    .filter(([k]) => k)
);
const SUPABASE_URL = env.PUBLIC_SUPABASE_URL;
const KEY = env.SUPABASE_SERVICE_KEY;
const APPLY = process.argv.includes('--apply');

async function sb(path, opts = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1${path}`, {
    // opts first: spreading it last would replace the merged headers wholesale.
    ...opts,
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
  return r;
}

// PostgREST caps a response at 1000 rows regardless of `limit`, so page with Range.
const rows = [];
for (let from = 0; ; from += 1000) {
  const page = await (
    await sb(
      '/scout_candidates?select=id,source,source_url,manifest_url,thumbnail,raw,title&order=id',
      {
        headers: { Range: `${from}-${from + 999}` },
      }
    )
  ).json();
  rows.push(...page);
  if (page.length < 1000) break;
}
console.log(`Scanned ${rows.length} candidates\n`);

const updates = [];
for (const r of rows) {
  const patch = {};

  const manifest = deriveManifestUrl(r);
  if (manifest && manifest !== r.manifest_url) patch.manifest_url = manifest;

  const image = deriveImageUrl(r);
  if (image && (r.raw || {}).iiif_image !== image)
    patch.raw = { ...(r.raw || {}), iiif_image: image };

  const src = fixSourceUrl(r);
  if (src !== r.source_url) patch.source_url = src;

  if (Object.keys(patch).length) updates.push({ row: r, patch });
}

const tally = {};
for (const u of updates)
  for (const f of Object.keys(u.patch)) {
    const k = `${u.row.source}.${f === 'raw' ? 'raw.iiif_image' : f}`;
    tally[k] = (tally[k] || 0) + 1;
  }
console.log(`${updates.length} rows need a fix:`);
for (const [k, v] of Object.entries(tally).sort()) console.log(`  ${String(v).padStart(4)}  ${k}`);

console.log('\nSample:');
for (const u of updates.slice(0, 5)) {
  console.log(`  [${u.row.source}] ${u.row.title.slice(0, 54)}`);
  for (const [f, v] of Object.entries(u.patch))
    console.log(`      ${f}: ${JSON.stringify(f === 'raw' ? v.iiif_image : v).slice(0, 100)}`);
}

if (!APPLY) {
  console.log('\nDry run. Re-run with --apply to write.');
  process.exit(0);
}

let ok = 0;
for (const u of updates) {
  await sb(`/scout_candidates?id=eq.${u.row.id}`, {
    method: 'PATCH',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify(u.patch),
  });
  ok++;
  if (ok % 10 === 0) process.stdout.write(`  ${ok}/${updates.length}\r`);
}
console.log(`\nDone: ${ok} rows updated.`);
