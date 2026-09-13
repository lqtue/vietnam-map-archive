#!/usr/bin/env node
// Seed `series_sheets` (mig 083) with the L7014 survey's own index.
//
//   node --env-file=.env scripts/oneoff/import_l7014_series_sheets.mjs [--dry]
//
// `work/l7014/coverage.json` is 627 rows, one per cell of the AMS 1:50,000
// index, and it already knows more than the database does: which cells we
// serve, which have a scan nobody has fetched, and which have no scan anywhere.
// It has been the real denominator for this survey all along while living in
// `work/`, where nothing can query it and a UI counting `maps` rows reported
// the survey at 9 sheets.
//
// The mapping, and the reason each status lands where it does:
//
//   in mosaic (452)          held, served as raster:l7014 -- no `maps` row
//                            exists or should; the pixels are in the PMTiles
//                            archive.
//   city (Allmaps) (9)       held, served as a `maps` row warped live. These
//                            are the sheets PCL publishes as plain JPGs with
//                            no embedded georeference, which is why they are
//                            rows and not mosaic cells -- and they are the
//                            ones over Saigon.
//   no georeference (62)     not held. A scan is in hand; what is missing is
//                            the pixel half of a georeference, four clicks a
//                            sheet. This is the cheapest work on the board.
//   not published by PCL     50 of the 93 carry a TTU link and an indexed
//                            scan: obtainable, never fetched. The other 43
//                            have no known scan anywhere and are a research
//                            task, not a processing one.
//   off-grid (11)            outside the regular grid but scanned and
//                            indexed at TTU; obtainable.
//
// `source` is the archive a scan can be got from, NOT where our copy came
// from -- for an unheld sheet there is no copy, and recording where to go is
// the entire point.

import fs from 'node:fs';
import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
// series_key('Series L7014 (Vietnam 1:50,000)') per migration 082. Hardcoded
// because this is a one-off seed; anything recurring should call the function.
const SERIES = 'series-l7014-vietnam-1-50-000';
const COLLECTION = 'Series L7014 (Vietnam 1:50,000)';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const cov = JSON.parse(fs.readFileSync('work/l7014/coverage.json', 'utf8'));

// The city sheets are `maps` rows; match them by sheet number. Several sheets
// have more than one row (different editions from different archives), so
// prefer a georeferenced one, then a published one — that is the row a reader
// actually gets.
const { data: rows, error: mapErr } = await db
  .from('maps')
  .select('id,status,georef_done,extra_metadata')
  .eq('collection', COLLECTION);
if (mapErr) throw mapErr;

const bySheet = new Map();
for (const m of rows) {
  const sn = String(m.extra_metadata?.sheet_number || '').replace(' IV', '-4');
  if (!sn) continue;
  const prev = bySheet.get(sn);
  const rank = (r) => (r.georef_done ? 2 : 0) + (r.status === 'public' ? 1 : 0);
  if (!prev || rank(m) > rank(prev)) bySheet.set(sn, m);
}

const out = [];
for (const c of cov) {
  const sheet = String(c.sheet);
  let held_by = null, map_id = null, source = null, source_ref = null, note = null;

  if (c.status === 'in mosaic') {
    held_by = 'raster:l7014';
    source = 'PCL';
  } else if (c.status === 'city (Allmaps)') {
    const m = bySheet.get(sheet);
    if (m) { held_by = 'map'; map_id = m.id; }
    source = 'PCL';
  } else if (c.status === 'off-grid') {
    note = 'off-grid: outside the regular 15′ lattice';
  }

  // Source of a scan for anything not already served, and for the record on
  // what is. TTU is the fallback and, for 50 cells, the only holder.
  if (!source && c.ttu) { source = 'TTU'; source_ref = c.ttu; }
  else if (source && c.ttu && !source_ref) source_ref = c.ttu;

  if (c.status === 'not published by PCL' && !c.ttu) note = 'no known scan in any indexed archive';

  out.push({
    series_key: SERIES,
    sheet_number: sheet,
    name: c.name || null,
    bbox: c.bbox || null,
    held_by, map_id, source, source_ref, note,
  });
}

const tally = out.reduce((a, r) => {
  const k = r.held_by ? `held (${r.held_by})` : r.source ? `obtainable (${r.source})` : 'no known scan';
  a[k] = (a[k] || 0) + 1;
  return a;
}, {});
console.log(`${out.length} cells:`);
for (const [k, v] of Object.entries(tally).sort((a, b) => b[1] - a[1])) console.log(`  ${String(v).padStart(4)}  ${k}`);

const unmatched = out.filter((r) => r.held_by === null && cov.find((c) => String(c.sheet) === r.sheet_number)?.status === 'city (Allmaps)');
if (unmatched.length) console.log(`\nWARNING: ${unmatched.length} city cells found no maps row: ${unmatched.map((r) => r.sheet_number).join(', ')}`);

if (dry) { console.log('\n--dry: nothing written'); process.exit(0); }

for (let i = 0; i < out.length; i += 200) {
  const { error } = await db.from('series_sheets').upsert(out.slice(i, i + 200), { onConflict: 'series_key,sheet_number' });
  if (error) throw error;
}
console.log(`\nupserted ${out.length} rows into series_sheets`);
