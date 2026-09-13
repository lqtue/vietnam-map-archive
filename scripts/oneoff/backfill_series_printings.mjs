#!/usr/bin/env node
// Fill `series_sheets.year` / `.edition` (migration 086).
//
//   node --env-file=.env scripts/oneoff/backfill_series_printings.mjs [--dry]
//
// Two sources, because a survey's sheets reach a reader two ways and the
// printing is recorded in a different place for each:
//
//   1. `work/l7014/sheets.json` — what `scripts/l7014_mosaic.py` read out of
//      each GeoPDF's XMP while warping it. This is the only record of the
//      printing behind the 452 mosaic cells, which have no `maps` row. 442 of
//      the 535 scanned sheets carry it; the other 93 say nothing, and null is
//      the right answer for those rather than a guess.
//   2. `maps` rows — `year` and `extra_metadata->>'edition'` for every sheet
//      held as a catalogue record, in either series.
//
// (2) is applied after (1) and wins where they disagree: for a cell we hold as
// a `maps` row, the printing served is the one on the row, whatever PCL's index
// says about the copy it published.
//
// Editions are normalised only in the one way that is safe: a value that is
// all digits loses its leading zeros, so PCL's "003" and "3" stop being two
// editions of one sheet. Anything else is stored exactly as printed — "3-DMA"
// and "2-AMS" carry the issuing agency, and that is the half of the value that
// says whether two printings came out of the same office.
//
// Re-runnable: it writes the same values again rather than skipping, so a
// corrected `sheets.json` can simply be replayed.
//
// **If it dies partway, replay it before debugging it.** The first real run
// failed mid-loop with a Postgres error and the second, byte-identical, run
// completed — 510 sequential UPDATEs over the REST API is enough round trips
// for one to drop, and nothing here is order-dependent. The failure looks like
// a data problem and is not one.

import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';

const dry = process.argv.includes('--dry');
const L7014 = 'series-l7014-vietnam-1-50-000';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

/** "003" -> "3"; "3-DMA" -> "3-DMA"; "" -> null. */
function normEdition(e) {
  const s = String(e ?? '').trim();
  if (!s) return null;
  return /^\d+$/.test(s) ? String(Number(s)) : s;
}

function normYear(y) {
  const n = Number(y);
  return Number.isInteger(n) && n > 1800 && n < 2100 ? n : null;
}

/**
 * `${series_key}\u0000${sheet_number}` -> { year, edition }.
 *
 * NUL as the separator, not a space: the Indochine index contains sheet "0 bis",
 * and a space-joined key splits back into the wrong sheet — it wrote that
 * sheet's printing onto sheet "0" instead, silently, because both rows exist.
 */
const wanted = new Map();

// (1) the mosaic's own index
const pcl = JSON.parse(readFileSync('work/l7014/sheets.json', 'utf8'));
for (const s of pcl) {
  if (!s.sheet) continue;
  const year = normYear(s.year);
  const edition = normEdition(s.edition);
  if (year === null && edition === null) continue;
  wanted.set(`${L7014}\u0000${s.sheet}`, { year, edition });
}
console.log(`sheets.json: ${wanted.size} sheets carry a printing`);

// (2) the catalogue rows, which win for the cells they serve
const { data: held, error: heldErr } = await db
  .from('series_sheets')
  .select('series_key, sheet_number, map_id')
  .not('map_id', 'is', null);
if (heldErr) throw heldErr;

const ids = [...new Set(held.map((r) => r.map_id))];
const { data: maps, error: mapsErr } = await db
  .from('maps')
  .select('id, year, extra_metadata')
  .in('id', ids);
if (mapsErr) throw mapsErr;
const byId = new Map(maps.map((m) => [m.id, m]));

let fromMaps = 0;
for (const r of held) {
  const m = byId.get(r.map_id);
  if (!m) continue;
  const year = normYear(m.year);
  const edition = normEdition(m.extra_metadata?.edition);
  if (year === null && edition === null) continue;
  wanted.set(`${r.series_key}\u0000${r.sheet_number}`, { year, edition });
  fromMaps++;
}
console.log(`maps rows: ${fromMaps} held sheets carry a printing`);

// Only touch rows that exist — `sheets.json` lists sheets the index does not,
// and writing those would invent rows in a table whose whole point is that it
// is the survey's own list.
const { data: existing, error: exErr } = await db
  .from('series_sheets')
  .select('series_key, sheet_number');
if (exErr) throw exErr;
const present = new Set(existing.map((r) => `${r.series_key}\u0000${r.sheet_number}`));

let written = 0;
let skipped = 0;
for (const [key, v] of wanted) {
  if (!present.has(key)) {
    skipped++;
    continue;
  }
  const [series_key, sheet_number] = key.split('\u0000');
  if (dry) {
    written++;
    continue;
  }
  const { error } = await db
    .from('series_sheets')
    .update({ year: v.year, edition: v.edition })
    .eq('series_key', series_key)
    .eq('sheet_number', sheet_number);
  if (error) throw error;
  written++;
}
console.log(`${dry ? 'dry run — ' : ''}${written} rows updated, ${skipped} not in any index`);

// Read it back: this is the number the coverage page will print.
const { count: withPrinting, error: cErr } = await db
  .from('series_sheets')
  .select('sheet_number', { count: 'exact', head: true })
  .not('year', 'is', null);
if (cErr) throw cErr;
const { count: total } = await db
  .from('series_sheets')
  .select('sheet_number', { count: 'exact', head: true });
console.log(`${withPrinting} of ${total} sheets now carry a year`);
