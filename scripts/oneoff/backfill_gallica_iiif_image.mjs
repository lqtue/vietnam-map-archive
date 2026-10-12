#!/usr/bin/env node
// Give Gallica scout candidates the Image API endpoint ingest needs.
//
// A Gallica row carries a manifest and a thumbnail but no raw.iiif_image, so ingest
// (POST /api/admin/scout) would make a map with no maps.iiif_image — and the layout/OCR
// worker refuses such a map ("Map has no iiif_image"). deriveGallicaImage() in
// scripts/scoutDerive.mjs names Gallica's own IIIF Image server from the ark; this
// writes that into raw.iiif_image, the way fix_scout_iiif.mjs does for LoC. New
// candidate loads get it from load_scout_to_db.mjs without this script.
//
// By default only the candidates that matter now: approved and not yet ingested.
// --all widens it to every Gallica row still missing the field.
//
//   node scripts/oneoff/backfill_gallica_iiif_image.mjs                # dry run, writes nothing
//   node scripts/oneoff/backfill_gallica_iiif_image.mjs --probe        # + one GET of each info.json, 3 s apart
//   node scripts/oneoff/backfill_gallica_iiif_image.mjs --apply        # PATCH scout_candidates.raw

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { willApply, flag, dryNotice } from '../lib/cli.mjs';
import { deriveGallicaImage } from '../scoutDerive.mjs';

const env = Object.fromEntries(
  readFileSync(resolve(process.cwd(), '.env'), 'utf8')
    .split('\n')
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()])
    .filter(([k]) => k)
);
const KEY = env.SUPABASE_SERVICE_KEY;
const apply = willApply();
const probe = flag('--probe');
const all = flag('--all');

async function sb(path, opts = {}) {
  const r = await fetch(`${env.PUBLIC_SUPABASE_URL}/rest/v1${path}`, {
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

// PostgREST caps a response at 1000 rows whatever `limit` says: page with Range.
const filter = all ? '' : '&review_status=eq.approved&map_id=is.null';
const rows = [];
for (let from = 0; ; from += 1000) {
  const page = await (
    await sb(
      `/scout_candidates?select=id,source,source_url,manifest_url,thumbnail,raw,title&source=eq.gallica${filter}&order=id`,
      { headers: { Range: `${from}-${from + 999}` } }
    )
  ).json();
  rows.push(...page);
  if (page.length < 1000) break;
}

const todo = [];
for (const r of rows) {
  const image = deriveGallicaImage(r);
  const have = (r.raw || {}).iiif_image;
  if (!image)
    console.log(`  skip ${r.id.slice(0, 8)}  no gallica.bnf.fr ark on the row  ${r.title}`);
  else if (have === image) console.log(`  ok   ${r.id.slice(0, 8)}  already ${have}`);
  else todo.push({ row: r, image, replaces: have || null });
}

console.log(`\n${rows.length} gallica candidates in scope, ${todo.length} to fill:\n`);
for (const t of todo) {
  console.log(`  ${t.row.id.slice(0, 8)}  ${t.row.title.slice(0, 70)}`);
  console.log(`      raw.iiif_image: ${t.replaces ?? '(empty)'}  ->  ${t.image}`);
}

// A read, one request at a time. Anything but a 200 with a size is reported as a
// failure, never as "nothing there".
if (probe) {
  console.log('\nProbe (GET <image>/info.json):');
  for (const t of todo) {
    const url = `${t.image}/info.json`;
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': 'VietnamMapArchive/1.0 (maparchive.vn)' },
      });
      const body = res.ok ? await res.json() : null;
      console.log(
        `  ${t.row.id.slice(0, 8)}  HTTP ${res.status}  ${body ? `${body.width} x ${body.height}` : 'FAILED'}  ${url}`
      );
    } catch (e) {
      console.log(`  ${t.row.id.slice(0, 8)}  FAILED  ${e.message}  ${url}`);
    }
    await new Promise((ok) => setTimeout(ok, 3000));
  }
}

if (!apply) {
  dryNotice('This would set raw.iiif_image (other raw keys kept) on the rows above.');
  process.exit(0);
}

for (const t of todo) {
  await sb(`/scout_candidates?id=eq.${t.row.id}`, {
    method: 'PATCH',
    headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({ raw: { ...(t.row.raw || {}), iiif_image: t.image } }),
  });
}
console.log(`\nDone: ${todo.length} rows updated.`);
