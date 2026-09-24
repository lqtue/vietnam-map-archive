#!/usr/bin/env node
// Scout Humazur (Université Côte d'Azur, Omeka S) directly via its REST API.
// Targets:
//   item_set_id=59  (Cartothèque ASEMI — ~417 maps, pure collection)
//   item_set_id=519 (Indochine française — 1500 items, mixed; filter to maps)
// Filter: resource_class_id=33 (Still Image — excludes person/place entities)
//
// Output: scripts/scout_humazur_<ts>.json (same schema as scout_all_sources.mjs)
// READ-ONLY.
//
// Usage:
//   NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/scout_humazur.mjs
//   NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/scout_humazur.mjs --sets 59
//   NODE_TLS_REJECT_UNAUTHORIZED=0 node scripts/scout_humazur.mjs --merge scripts/scout_all_*.json

import { readFileSync, writeFileSync, readdirSync } from 'fs';
import { resolve } from 'path';

const env = Object.fromEntries(
  readFileSync(resolve(process.cwd(), '.env'), 'utf8')
    .split('\n')
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => l.split('=').map((s) => s.trim()))
    .filter(([k]) => k)
);
const SUPABASE_URL = env.PUBLIC_SUPABASE_URL;
const KEY = env.SUPABASE_SERVICE_KEY;
const UA = 'Mozilla/5.0 VMA-Scout/1.0';

const setsIdx = process.argv.indexOf('--sets');
const SETS = setsIdx > -1 ? process.argv[setsIdx + 1].split(',').map(Number) : [59, 519];
const mergeIdx = process.argv.indexOf('--merge');
const MERGE_PATH = mergeIdx > -1 ? process.argv[mergeIdx + 1] : null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, retries = 3) {
  for (let i = 0; i <= retries; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/json' } });
      if (r.status === 429 || r.status === 503) {
        if (i === retries) return { __error: r.status };
        await sleep(1500 * Math.pow(2, i));
        continue;
      }
      if (!r.ok) return { __error: r.status };
      return await r.json();
    } catch (e) {
      if (i === retries) return { __error: e.message };
      await sleep(1500 * Math.pow(2, i));
    }
  }
}

// ---- pick first dcterms value (handles array-of-objects) ----
function dc(item, key) {
  const arr = item[`dcterms:${key}`];
  if (!Array.isArray(arr) || !arr.length) return '';
  for (const v of arr) {
    const val = v?.['@value'] ?? v?.['display_title'] ?? v?.['o:label'] ?? '';
    if (val) return String(val);
  }
  return '';
}
function dcAll(item, key) {
  const arr = item[`dcterms:${key}`];
  if (!Array.isArray(arr)) return [];
  return arr.map((v) => v?.['@value'] ?? v?.['display_title'] ?? '').filter(Boolean);
}

function isLikelyVietnamMap(item) {
  const title = (item['o:title'] || '').toLowerCase();
  const subjects = dcAll(item, 'subject').join(' ').toLowerCase();
  const coverage = dcAll(item, 'spatial').concat(dcAll(item, 'coverage')).join(' ').toLowerCase();
  const desc = dc(item, 'description').toLowerCase();
  const combined = `${title} ${subjects} ${coverage} ${desc}`;
  return /vietnam|viet-nam|viêt|saigon|saïgon|sài gòn|hanoi|hanoï|hà nội|hue|hué|huế|tonkin|annam|cochinchin|indochin|gia định|gia-dinh|cholon|chợ lớn|tonkin|đà nẵng|tourane|haiphong|hải phòng|nam bo|bac bo|trung bo|thanh hoa|phu yen|nha trang|dalat|đà lạt|cambodge|laos/.test(
    combined
  );
}

async function scoutSet(setId, requireResourceClass = 33) {
  console.log(`\n--- Set ${setId} (resource_class=${requireResourceClass}) ---`);
  const items = [];
  let page = 1;
  while (page <= 25) {
    const url = `https://humazur.univ-cotedazur.fr/api/items?item_set_id=${setId}&resource_class_id=${requireResourceClass}&per_page=100&page=${page}`;
    const data = await fetchJson(url);
    if (data.__error || !Array.isArray(data)) {
      console.log(`  page ${page} ERR ${data.__error}`);
      break;
    }
    items.push(...data);
    process.stdout.write(`  page ${page}: ${data.length} (cum ${items.length})\r`);
    if (data.length < 100) break;
    page++;
    await sleep(300);
  }
  console.log(`  fetched ${items.length} items`);
  return items;
}

function findManifestUrl(item) {
  // Omeka S items often embed IIIF manifest in extra fields, but it's typically
  // derivable from page URL pattern. Humazur uses /iiif/<media_id>/manifest
  const media = item['o:media'];
  if (Array.isArray(media) && media[0]?.['@id']) {
    const m = String(media[0]['@id']).match(/\/media\/(\d+)/);
    if (m) return `https://humazur.univ-cotedazur.fr/iiif/${m[1]}/manifest`;
  }
  // Fallback: site has /iiif/<item_id>/manifest pattern
  return `https://humazur.univ-cotedazur.fr/iiif/${item['o:id']}/manifest`;
}

function normalizeHumazurItem(item, setId) {
  return {
    source: 'humazur',
    externalId: String(item['o:id']),
    title: item['o:title'] || dc(item, 'title') || '',
    creator: dc(item, 'creator'),
    publisher: dc(item, 'publisher'),
    date: dc(item, 'date') || dc(item, 'temporal'),
    rights: dc(item, 'rights') || 'Domaine public',
    language: dc(item, 'language') || 'français',
    holding_institution: "Humazur, Université Côte d'Azur",
    manifestUrl: findManifestUrl(item),
    sourceUrl: item['@id'] || `https://humazur.univ-cotedazur.fr/s/humazur/item/${item['o:id']}`,
    thumbnail: item['o:thumbnail_urls']?.['medium'] || '',
    foundVia: [`humazur:set${setId}`],
    dedupKey: `humazur:${item['o:id']}`,
    raw: {
      collection:
        setId === 59 ? 'Cartothèque ASEMI' : setId === 519 ? 'Indochine française' : `set ${setId}`,
      subject: dcAll(item, 'subject'),
      coverage: dcAll(item, 'spatial').concat(dcAll(item, 'coverage')),
      shelfmark: dc(item, 'identifier'),
    },
  };
}

// ---- main ----
const allItems = new Map();
let totalSeen = 0,
  totalKept = 0;

for (const setId of SETS) {
  const items = await scoutSet(setId);
  totalSeen += items.length;
  for (const item of items) {
    // require media (otherwise no IIIF/image)
    if (!Array.isArray(item['o:media']) || !item['o:media'].length) continue;
    // for set 519, additional Vietnam filter (Indochine but includes Laos/Cambodge photos)
    if (setId === 519 && !isLikelyVietnamMap(item)) continue;
    const key = `humazur:${item['o:id']}`;
    if (!allItems.has(key)) {
      allItems.set(key, normalizeHumazurItem(item, setId));
      totalKept++;
    } else {
      allItems.get(key).foundVia.push(`humazur:set${setId}`);
    }
  }
  await sleep(500);
}

const recs = [...allItems.values()];
console.log(`\nFetched ${totalSeen} raw items → ${totalKept} kept (media + Vietnam filter)\n`);

// VMA dedup
const r = await fetch(
  `${SUPABASE_URL}/rest/v1/maps?select=iiif_image,source_url,map_images(iiif_manifest)`,
  { headers: { apikey: KEY, Authorization: `Bearer ${KEY}` } }
);
const existing = await r.json();
const existingArks = new Set();
const existingHumazurIds = new Set();
for (const m of existing) {
  const manifests = (m.map_images ?? []).map((s) => s.iiif_manifest);
  for (const v of [...manifests, m.iiif_image, m.source_url]) {
    if (!v) continue;
    const a = v.match(/ark:\/17103\/[a-z0-9]+/i);
    if (a) existingArks.add(a[0]);
    const h = v.match(/humazur[^\/]*\/[^\/]*\/item\/(\d+)/);
    if (h) existingHumazurIds.add(h[1]);
  }
}
const newCandidates = recs.filter((r) => !existingHumazurIds.has(r.externalId));
const already = recs.length - newCandidates.length;

console.log(`Already in VMA: ${already}`);
console.log(`New candidates: ${newCandidates.length}\n`);

// By collection
const byColl = {};
for (const r of newCandidates) byColl[r.raw.collection] = (byColl[r.raw.collection] || 0) + 1;
console.log('By collection:');
for (const [c, n] of Object.entries(byColl).sort((a, b) => b[1] - a[1]))
  console.log(`  ${String(n).padStart(4)}  ${c}`);

// Decade
const dec = {};
for (const r of newCandidates) {
  const y = (r.date || '').match(/\b(1[5-9]\d\d|20\d\d)\b/);
  const k = y ? `${Math.floor(parseInt(y[1]) / 10) * 10}s` : '(no year)';
  dec[k] = (dec[k] || 0) + 1;
}
console.log('\nBy decade:');
for (const [d, n] of Object.entries(dec).sort())
  console.log(`  ${d.padEnd(10)} ${'█'.repeat(Math.min(n, 60))} ${n}`);

// Sample
console.log('\nSample (first 10):');
for (const r of newCandidates.slice(0, 10)) {
  console.log(`  [${(r.date || '?').slice(0, 10)}] ${r.title.slice(0, 80)}`);
}

// Save (merge if requested)
let merged;
if (MERGE_PATH) {
  const existing = JSON.parse(readFileSync(MERGE_PATH, 'utf8'));
  const before = existing.newCandidates.length;
  // dedup by dedupKey
  const haveKeys = new Set(existing.newCandidates.map((x) => x.dedupKey));
  const additions = newCandidates.filter((x) => !haveKeys.has(x.dedupKey));
  existing.newCandidates.push(...additions);
  existing.counts = existing.counts || {};
  existing.counts.humazur = recs.length;
  existing.sources = [...new Set([...(existing.sources || []), 'humazur'])];
  merged = existing;
  console.log(
    `\nMerged into ${MERGE_PATH}: +${additions.length} (was ${before}, now ${existing.newCandidates.length})`
  );
}

const out = MERGE_PATH
  ? MERGE_PATH.replace(/\.json$/, '_with_humazur.json')
  : `scripts/scout_humazur_${Date.now()}.json`;
writeFileSync(
  out,
  JSON.stringify(
    merged || {
      sources: ['humazur'],
      sets: SETS,
      totalUnique: recs.length,
      alreadyInVma: already,
      newCandidates,
    },
    null,
    2
  )
);
console.log(`\nSaved: ${out}`);
if (!MERGE_PATH) {
  console.log(`Next: node scripts/categorize_scout_results.mjs --report ${out}`);
}
