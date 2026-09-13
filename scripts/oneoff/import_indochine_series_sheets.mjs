#!/usr/bin/env node
// Seed `series_sheets` (mig 083) with the Indochine 1:25,000 Tonkin index,
// read from CartoMundi's own catalogue.
//
//   node --env-file=.env scripts/oneoff/import_indochine_series_sheets.mjs [--dry]
//
// Until now this survey had no denominator at all: 62 `maps` rows with
// `source_url` null and no record of what the series contains, so "which
// sheets are we missing" could only be answered by staring at sheet numbers
// and guessing which gaps were real. That guess was wrong in both directions —
// it invented sheets 34, 41, 47, 53 and 67, which the series never issued, and
// it counted 0 bis, 5 bis and 10 bis as missing when we hold all three under
// our own `0b`/`5b`/`10b` spelling.
//
// CartoMundi (MMSH, Aix-Marseille) publishes the catalogue as open JSON at
// `/ctmd-services/`, no key. `serie/175` is the assembled-sheet edition,
// 1901–1944, held by IGN — deliberately not the two half-sheet editions in the
// same catalogue (157 sheets in colour, 160 in black 1945–53), which are a
// different product and would double-count every sheet.
//
// The series declares 81 sheets and lists 88 records over 76 distinct numbers,
// the surplus being second and third editions of the same sheet.
// `series_sheets` is keyed by sheet number, so the editions collapse to one
// row and their count goes in the note — the question this table answers is
// "does the survey contain this sheet", not "how many printings exist".
//
// The bbox is CartoMundi's catalogue extent (UNIMARC corner fields), NOT a
// georeference. It is right to about a minute of arc and is here so an unheld
// sheet can be drawn as a gap on a map; nothing should warp against it. Our
// own sheets' `maps.bbox` disagrees with it by a few hundred metres, which is
// unsurprising for a catalogue value and is also the subject of the open
// question about this series' projection.

import fs from 'node:fs';
import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
const SERIE = 175;
const SERIES = 'indochine-1-25-000-tonkin-thanh-hoa'; // series_key(), mig 082
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const API = `https://www.cartomundi.fr/ctmd-services/serie/${SERIE}/feuilles`;

/** UNIMARC corner: a hemisphere letter then DDDMMSS, e.g. "e1055008" -> 105.8356. */
function unimarc(v) {
  const m = /^([nsew])(\d{3})(\d{2})(\d{2})$/i.exec(String(v || '').trim());
  if (!m) return null;
  const deg = +m[2] + +m[3] / 60 + +m[4] / 3600;
  return /[sw]/i.test(m[1]) ? -deg : deg;
}

const sheets = await (await fetch(API, { headers: { Accept: 'application/json' } })).json();
console.log(`CartoMundi serie ${SERIE}: ${sheets.length} records`);

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data: rows, error } = await db
  .from('maps')
  .select('id,status,georef_done,extra_metadata')
  .eq('collection', COLLECTION);
if (error) throw error;

// Several sheets have more than one edition as separate `maps` rows. Prefer a
// georeferenced one, then a published one — that is the row a reader gets.
const held = new Map();
for (const m of rows) {
  const sn = String(m.extra_metadata?.sheet_number || '').trim();
  if (!sn) continue;
  const rank = (r) => (r.georef_done ? 2 : 0) + (r.status === 'public' ? 1 : 0);
  if (!held.has(sn) || rank(m) > rank(held.get(sn))) held.set(sn, m);
}

const byNumber = new Map();
for (const f of sheets) {
  const sn = String(f.f100NumeroOuCode).trim();
  if (!byNumber.has(sn)) byNumber.set(sn, []);
  byNumber.get(sn).push(f);
}

const out = [];
for (const [sn, editions] of byNumber) {
  // The newest edition carries the best title; any of them carries the extent.
  const best = editions.slice().sort((a, b) => (b.f103DateAaaa || 0) - (a.f103DateAaaa || 0))[0];
  const g = best.geometrieEmprise || {};
  const w = unimarc(g.l123dLimiteOuestUnimarc),
    e = unimarc(g.l123eLimiteEstUnimarc);
  const n = unimarc(g.l123fLimiteNordUnimarc),
    s = unimarc(g.l123gLimiteSudUnimarc);
  const m = held.get(sn);
  const years = editions
    .map((x) => x.f103DateAaaa)
    .filter(Boolean)
    .sort();
  out.push({
    series_key: SERIES,
    sheet_number: sn,
    name: best.f105Titre || null,
    bbox: [w, s, e, n].every((v) => typeof v === 'number') ? [w, s, e, n] : null,
    held_by: m ? 'map' : null,
    map_id: m ? m.id : null,
    source: 'CartoMundi',
    source_ref: best.fkey ? String(best.fkey) : null,
    note: [
      years.length > 1
        ? `${editions.length} editions: ${years.join(', ')}`
        : years[0]
          ? `edition ${years[0]}`
          : null,
      'bbox is CartoMundi catalogue extent, not a georeference',
    ]
      .filter(Boolean)
      .join(' · '),
  });
}

const heldN = out.filter((r) => r.held_by).length;
console.log(`${out.length} distinct sheets | held ${heldN} | gaps ${out.length - heldN}`);
console.log(`no bbox parsed: ${out.filter((r) => !r.bbox).length}`);
console.log('\ngaps:');
for (const r of out
  .filter((x) => !x.held_by)
  .sort((a, b) => a.sheet_number.localeCompare(b.sheet_number, undefined, { numeric: true })))
  console.log(
    `  ${r.sheet_number.padStart(6)}  ${(r.name || '?').padEnd(20)} ${r.bbox ? r.bbox.map((v) => v.toFixed(3)).join(',') : 'no bbox'}`
  );

// Our rows whose number the catalogue does not list — a spelling mismatch or a
// sheet filed under a number the series never issued. Either way, worth seeing.
const orphan = [...held.keys()].filter((k) => !byNumber.has(k));
if (orphan.length) console.log(`\nour sheet numbers not in the catalogue: ${orphan.join(', ')}`);

if (dry) {
  console.log('\n--dry: nothing written');
  process.exit(0);
}

for (let i = 0; i < out.length; i += 200) {
  const { error: upErr } = await db
    .from('series_sheets')
    .upsert(out.slice(i, i + 200), { onConflict: 'series_key,sheet_number' });
  if (upErr) throw upErr;
}
console.log(`\nupserted ${out.length} rows`);
