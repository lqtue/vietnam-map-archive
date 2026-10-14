#!/usr/bin/env node
// Backfill thumbnails for scout_candidates rows held on an Omeka S instance.
//
// Omeka stores the thumbnail on the *media* object, not the item, so it takes
// two hops: /api/items/{id} → first o:media @id → /api/media/{id} →
// o:thumbnail_urls. Which instance a row belongs to comes from its source_url
// host (see OMEKA_HOSTS in scripts/scout/scoutDerive.mjs), not from `source` — the
// Bordeaux 3 rows arrive labelled `gallica`, via SRU federation.
//
// Supersedes backfill_humazur_thumbs.mjs, which hardcoded the one host.
//
// Usage:
//   NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/oneoff/backfill_omeka_thumbs.mjs
//   NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/oneoff/backfill_omeka_thumbs.mjs --apply
//   ... --apply --min-score 40      # only the rows worth reviewing

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { OMEKA_HOSTS, host, omekaItemId } from '../scout/scoutDerive.mjs';

const env = Object.fromEntries(
  readFileSync(resolve(process.cwd(), '.env'), 'utf8')
    .split('\n')
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => l.split('=').map((s) => s.trim()))
    .filter(([k]) => k)
);
const SUPABASE_URL = env.PUBLIC_SUPABASE_URL;
const KEY = env.SUPABASE_SERVICE_KEY;
const UA = 'Mozilla/5.0 VMA-Thumb-Backfill/1.0';
const APPLY = process.argv.includes('--apply');
const midx = process.argv.indexOf('--min-score');
const MIN_SCORE = midx > -1 ? parseInt(process.argv[midx + 1]) : 0;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

async function fetchJson(url) {
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

async function deriveThumb(base, itemId) {
  const item = await fetchJson(`${base}/api/items/${itemId}`);
  const first = item?.['o:media']?.[0]?.['@id'];
  const mediaId = String(first || '').match(/\/media\/(\d+)/)?.[1];
  if (!mediaId) return null;
  const media = await fetchJson(`${base}/api/media/${mediaId}`);
  const urls = media?.['o:thumbnail_urls'] || {};
  return urls.medium || urls.large || urls.square || null;
}

const rows = await (
  await sb(
    `/scout_candidates?select=id,source,source_url,title,score&thumbnail=is.null&score=gte.${MIN_SCORE}&limit=5000`
  )
).json();

const targets = rows
  .map((r) => ({ row: r, base: OMEKA_HOSTS[host(r.source_url)], id: omekaItemId(r.source_url) }))
  .filter((t) => t.base && t.id);

const byHost = {};
for (const t of targets) byHost[host(t.row.source_url)] = (byHost[host(t.row.source_url)] || 0) + 1;
console.log(`${rows.length} rows lack a thumbnail; ${targets.length} are on an Omeka host:`);
for (const [h, n] of Object.entries(byHost)) console.log(`  ${String(n).padStart(4)}  ${h}`);
if (!APPLY) {
  console.log('\nDry run. Re-run with --apply to write.');
  process.exit(0);
}

let ok = 0,
  miss = 0;
for (const [i, t] of targets.entries()) {
  const thumb = await deriveThumb(t.base, t.id);
  if (thumb) {
    await sb(`/scout_candidates?id=eq.${t.row.id}`, {
      method: 'PATCH',
      headers: { Prefer: 'return=minimal' },
      body: JSON.stringify({ thumbnail: thumb }),
    });
    ok++;
  } else {
    miss++;
  }
  if ((i + 1) % 10 === 0)
    process.stdout.write(`  ${i + 1}/${targets.length}  (ok=${ok} miss=${miss})\r`);
  await sleep(150);
}
console.log(`\nDone: ${ok} thumbnails backfilled, ${miss} with no media to derive from.`);
