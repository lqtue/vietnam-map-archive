#!/usr/bin/env node
// Load scout JSON file into the scout_candidates table.
// Also derives thumbnails where the source URL pattern is deterministic:
//   - Gallica/BnF: https://gallica.bnf.fr/{ark}/f1.thumbnail
//   - David Rumsey: urlSize2 (already in scout payload)
//   - LoC: image_url (already in scout payload)
//   - Humazur: deferred — needs per-item media fetch (see oneoff/backfill_humazur_thumbs.mjs)
//
// Fixes Humazur manifest URL bug (was using media_id, should be item_id).
//
// Usage:
//   node scripts/load_scout_to_db.mjs                              # auto-pick latest scout file
//   node scripts/load_scout_to_db.mjs --file path/to/scout.json
//   node scripts/load_scout_to_db.mjs --reset                      # delete existing pending rows first

import { readFileSync, readdirSync } from 'fs';
import { resolve } from 'path';
import { deriveManifestUrl, deriveImageUrl, fixSourceUrl } from './scoutDerive.mjs';

const env = Object.fromEntries(
  readFileSync(resolve(process.cwd(), '.env'), 'utf8')
    .split('\n')
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => l.split('=').map((s) => s.trim()))
    .filter(([k]) => k)
);
const SUPABASE_URL = env.PUBLIC_SUPABASE_URL;
const KEY = env.SUPABASE_SERVICE_KEY;

const fidx = process.argv.indexOf('--file');
const RESET = process.argv.includes('--reset');
const filePath =
  fidx > -1
    ? process.argv[fidx + 1]
    : (() => {
        const candidates = readdirSync('scripts')
          .filter((f) => f.startsWith('scout_all_') && f.endsWith('.json'))
          .sort();
        if (!candidates.length) {
          console.error('No scout_all_*.json found in scripts/');
          process.exit(1);
        }
        // Prefer the _with_humazur variant if present
        const withHum = candidates.filter((f) => f.includes('humazur'));
        return (
          'scripts/' +
          (withHum.length ? withHum[withHum.length - 1] : candidates[candidates.length - 1])
        );
      })();

console.log(`Loading: ${filePath}\n`);
const scout = JSON.parse(readFileSync(filePath, 'utf8'));
const candidates = scout.newCandidates || [];

// ---- Derive thumbnails + fix manifest URLs ----
function deriveThumbnail(rec) {
  if (rec.thumbnail) return rec.thumbnail;
  if (rec.source === 'gallica') {
    const ark = rec.externalId?.match(/ark:\/[0-9]+\/[a-z0-9]+/i)?.[0];
    if (ark) return `https://gallica.bnf.fr/${ark}/f1.thumbnail`;
  }
  return null;
}
function fixManifestUrl(rec) {
  if (rec.source === 'humazur') {
    // BUG FIX: scout_humazur.mjs used media @id (wrong); manifest is at iiif/{item_id}/manifest
    return `https://humazur.univ-cotedazur.fr/iiif/${rec.externalId}/manifest`;
  }
  return deriveManifestUrl(rec);
}

// ---- Parse year ----
function parseYear(rec) {
  const dateStr = String(rec.date || '');
  const m = dateStr.match(/\b(1[5-9]\d\d|20\d\d)\b/);
  return m ? parseInt(m[1]) : null;
}

// ---- Score + category (mirror of categorize_scout_results.mjs logic) ----
function scoreAndCategorize(rec) {
  const title = String(rec.title || '').toLowerCase();
  const subj = (rec.raw?.subject || []).join(' ');
  const cov = rec.raw?.coverage || rec.raw?.region || rec.raw?.country || rec.raw?.city || [];
  const covStr = Array.isArray(cov) ? cov.join(' ') : String(cov || '');
  const allText = `${title} ${subj} ${covStr}`.toLowerCase();
  let score = 0;
  let category = 'unknown';
  const reasons = [];

  const VN_PLACES = [
    'saigon',
    'saïgon',
    'sài gòn',
    'hanoi',
    'hanoï',
    'hà nội',
    'hue',
    'hué',
    'huế',
    'đà nẵng',
    'tourane',
    'haiphong',
    'hải phòng',
    'cholon',
    'chợ lớn',
    'gia định',
    'cochinchine',
    'tonkin',
    'annam',
    'indochine',
    'indo-chine',
    'mekong',
    'mékong',
    'vietnam',
    'viêt-nam',
    'viêtnam',
    'cambodge',
    'laos',
    'thanh hoa',
    'phu yen',
    'dalat',
    'đà lạt',
    'nha trang',
    'bac bo',
    'trung bo',
    'nam bo',
  ];
  if (VN_PLACES.some((p) => allText.includes(p))) {
    score += 20;
    reasons.push('+place');
  } else {
    score -= 10;
    reasons.push('-no_vn_place');
  }

  const year = parseYear(rec);
  if (year && year >= 1850 && year <= 1955) {
    score += 20;
    reasons.push(`+colonial:${year}`);
  } else if (year && year >= 1700 && year < 1850) {
    score += 10;
    reasons.push(`+precolonial:${year}`);
  } else if (year && year > 1955) {
    score += 5;
    reasons.push(`+modern:${year}`);
  } else if (!year) {
    score -= 10;
    reasons.push('-no_year');
  }

  const MAP_HINTS =
    /\b(plan|carte|atlas|map|levé|levée|croquis topograph|topograph|cadastr|chart|itinéraire|carte routi)/i;
  const HAS_MAP_KW = MAP_HINTS.test(title);
  if (HAS_MAP_KW) {
    score += 15;
    reasons.push('+map_kw');
  }
  if (rec.manifestUrl) {
    score += 5;
    reasons.push('+iiif');
  }

  if (/cadastr/.test(title)) {
    category = 'cadastral';
    score += 5;
  } else if (/plan de la (ville|cité)|plan de saigon|plan de hanoi|plan de hué/.test(title)) {
    category = 'urban_plan';
    score += 10;
  } else if (/topograph/.test(title)) {
    category = 'topographic';
    score += 5;
  } else if (/atlas/.test(title)) {
    category = 'atlas_plate';
    score -= 5;
  } else if (/carte routière|routier|itinéraire/.test(title)) {
    category = 'route_road';
  } else if (/chemin de fer|voies? ferrée|tramway/.test(title)) {
    score -= 30;
    category = 'route_railway';
    reasons.push('-railway');
  } else if (/monde|hémisphère|projection mondiale/.test(title)) {
    score -= 50;
    category = 'world';
    reasons.push('-world');
  } else if (/carte/.test(title)) category = 'regional';
  else if (/plan/.test(title)) category = 'urban_plan';

  const PHOTO_HINTS =
    /\b(vue|intérieur|extérieur|façade|rue|avenue|boulevard|pagode|temple|village|hameau|maison|pont|gare|monument|famille|femme|homme|enfant|boutique|marché|fête|f[êe]te|portrait|jardin|tombeau|cimet|chapelle|église|cathédrale|h[oô]tel|caserne|école|usine|port|navire|bateau|pirogue|jonque|costume|annamite|tonkinois|cochinchinois|paysage|panorama photographique|cérémonie|cortège|défilé)\b/i;
  if (!HAS_MAP_KW && PHOTO_HINTS.test(title)) {
    score -= 60;
    category = 'photo';
    reasons.push('-photo_subject');
  } else if (
    !HAS_MAP_KW &&
    rec.source === 'humazur' &&
    (rec.raw?.collection || '') === 'Indochine française'
  ) {
    score -= 30;
    if (category === 'unknown') category = 'non_cartographic';
    reasons.push('-no_map_kw');
  }

  return { score, category, reasons: reasons.join(' '), year };
}

// ---- Build rows ----
const rows = candidates
  .map((rec) => {
    const sc = scoreAndCategorize(rec);
    return {
      source: rec.source,
      external_id: rec.externalId || rec.dedupKey || '',
      source_url: fixSourceUrl(rec),
      manifest_url: fixManifestUrl(rec),
      title: (rec.title || '(untitled)').slice(0, 1000),
      creator: rec.creator || null,
      publisher: rec.publisher || null,
      date: rec.date || null,
      year: sc.year,
      rights: rec.rights || null,
      language: rec.language || null,
      holding_institution: rec.holding_institution || null,
      collection: rec.raw?.collection || null,
      thumbnail: deriveThumbnail(rec),
      score: sc.score,
      category: sc.category,
      reasons: sc.reasons,
      found_via: (rec.foundVia || []).join(';'),
      review_status: 'pending',
      // A source with no reachable Presentation manifest can still have an
      // Image API endpoint (LoC). Ingest reads it from here — see /api/admin/scout.
      raw: (() => {
        const img = deriveImageUrl(rec);
        return img ? { ...(rec.raw || {}), iiif_image: img } : rec.raw || null;
      })(),
    };
  })
  .filter((r) => r.external_id);

console.log(`Prepared ${rows.length} rows for insertion`);

// ---- Insert into Supabase ----
async function sb(path, opts = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1${path}`, {
    // opts first: spreading it last would replace the merged headers wholesale,
    // which dropped the apikey on any call that passed its own headers.
    ...opts,
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates',
      ...(opts.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 200)}`);
  return r;
}

if (RESET) {
  console.log('Resetting: deleting existing pending rows...');
  await sb(`/scout_candidates?review_status=eq.pending`, {
    method: 'DELETE',
    headers: { Prefer: 'return=minimal' },
  });
}

console.log('Inserting in batches of 200...');
const batchSize = 200;
let ok = 0,
  fail = 0;
for (let i = 0; i < rows.length; i += batchSize) {
  const batch = rows.slice(i, i + batchSize);
  try {
    // on_conflict is required for merge-duplicates to target a unique constraint
    // rather than the primary key — without it a re-run 409s on the whole batch.
    await sb('/scout_candidates?on_conflict=source,external_id', {
      method: 'POST',
      body: JSON.stringify(batch),
    });
    ok += batch.length;
    process.stdout.write(`  ${ok}/${rows.length}\r`);
  } catch (e) {
    fail += batch.length;
    console.log(`\n  batch ${i / batchSize} FAILED: ${e.message}`);
  }
}
console.log(`\nDone: ${ok} inserted/upserted, ${fail} failed.`);

// Summary
const { count: pending } = await fetch(
  `${SUPABASE_URL}/rest/v1/scout_candidates?review_status=eq.pending&select=id`,
  {
    headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, Prefer: 'count=exact' },
  }
).then(async (r) => ({ count: parseInt(r.headers.get('content-range')?.split('/')?.[1] || '0') }));
console.log(`Pending in DB: ${pending}`);
