// Before building a sheet-to-sheet alignment check: is there anything to check
// with? Sheet-to-sheet needs a correspondence source per pair (shared place
// names, shared block geometry, or GCPs that happen to land on the same
// ground point) — none of which is guaranteed to exist for a given pair.
// This prints what each candidate sheet actually has, live, so the driver
// gets built for however many pairs are real, not assumed.
//
// Usage:
//   node --env-file=.env scripts/sheet_to_sheet_census.mjs
//   node --env-file=.env scripts/sheet_to_sheet_census.mjs --maps <id1,id2,...>

import { createClient } from '@supabase/supabase-js';
import { parseAnnotation } from '@allmaps/annotation';
import { readFileSync } from 'node:fs';

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
};

// Default set: the District 4 six, plus 1898 — the seven sheets
// docs/journals/260921-sheet-overlap.md already has hand-measured figures
// for, so a driver built against these can self-check against real numbers.
const D4_IDS = readFileSync(
  new URL('../work/analysis/district4/maps.txt', import.meta.url),
  'utf8'
)
  .trim()
  .split(',')
  .filter(Boolean);
const DEFAULT_IDS = [...D4_IDS, '20ec4f9a-16bd-4895-a593-40c6ed9c9555']; // + 1898 Saigon Plan

const mapIds = (arg('--maps') ?? DEFAULT_IDS.join(',')).split(',').filter(Boolean);

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Live annotation first, mirror only as fallback — memory on this project
// found 4 of 6 District 4 mirrors stale by up to 13 months (up to 3 GCPs
// stored vs 10 live). A measurement tool built on the mirror would report
// fake georeference error. `/images/{allmaps_id}` is the per-map-image
// endpoint; `/maps/{id}` is a per-annotation id and not what `allmaps_id`
// is.
async function liveAnnotation(row) {
  if (row.allmaps_id) {
    try {
      const res = await fetch(`https://annotations.allmaps.org/images/${row.allmaps_id}`);
      if (res.ok) return { ann: await res.json(), source: 'live' };
    } catch {
      /* fall through to mirror */
    }
  }
  if (row.annotation_url) {
    try {
      const res = await fetch(row.annotation_url);
      if (res.ok) return { ann: await res.json(), source: 'mirror (stale risk)' };
    } catch {
      /* no source at all */
    }
  }
  return { ann: null, source: 'unreachable' };
}

function bboxFromGcps(ann) {
  const maps = parseAnnotation(ann);
  if (!maps.length) return null;
  const gcps = maps[0].gcps ?? [];
  if (!gcps.length) return null;
  const lons = gcps.map((g) => g.geo[0]);
  const lats = gcps.map((g) => g.geo[1]);
  return {
    n: gcps.length,
    transformation: maps[0].transformation?.type ?? null,
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

function overlaps(a, b) {
  return a.maxLon >= b.minLon && b.maxLon >= a.minLon && a.maxLat >= b.minLat && b.maxLat >= a.minLat;
}

async function countRows(table, mapId, extra = {}) {
  let q = db.from(table).select('id', { count: 'exact', head: true }).eq('map_id', mapId);
  for (const [k, v] of Object.entries(extra)) q = q.eq(k, v);
  const { count, error } = await q;
  return error ? `err: ${error.message}` : count;
}

const sheets = [];
for (const id of mapIds) {
  const { data: rows, error } = await db
    .from('maps')
    .select('id,year,name,slug,allmaps_id,annotation_url')
    .eq('id', id);
  if (error || !rows?.length) {
    console.log(`${id}: could not read maps row (${error?.message ?? 'no row'})`);
    continue;
  }
  const row = rows[0];
  const { ann, source } = await liveAnnotation(row);
  const box = ann ? bboxFromGcps(ann) : null;
  const ocr = await countRows('ocr_extractions', id);
  const footprints = await countRows('footprint_submissions', id, { status: 'approved' });
  sheets.push({ ...row, box, source, ocr, footprints });
}

console.log('| year | sheet | GCPs (live) | transform | annotation source | ocr_extractions | approved footprints |');
console.log('|---|---|---:|---|---|---:|---:|');
for (const s of sheets) {
  console.log(
    `| ${s.year ?? '?'} | ${(s.name ?? s.slug ?? s.id).slice(0, 30)} | ${s.box?.n ?? '—'} | ${s.box?.transformation ?? '—'} | ${s.source} | ${s.ocr} | ${s.footprints} |`
  );
}

console.log('\n### Pairwise footprint overlap (bbox of each sheet\'s own GCPs)\n');
for (let i = 0; i < sheets.length; i++) {
  for (let j = i + 1; j < sheets.length; j++) {
    const [a, b] = [sheets[i], sheets[j]];
    if (!a.box || !b.box || !overlaps(a.box, b.box)) continue;
    const nameCheckable = a.ocr > 0 && b.ocr > 0;
    const blockCheckable = a.footprints > 0 && b.footprints > 0;
    console.log(
      `- ${a.year} <-> ${b.year}: overlap yes` +
        ` | names: ${nameCheckable ? 'both have OCR' : 'no (one side has 0 extractions)'}` +
        ` | blocks: ${blockCheckable ? 'both have approved footprints' : 'no (one side has 0 approved footprints)'}`
    );
  }
}
