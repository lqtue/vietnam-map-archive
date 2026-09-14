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
// `/ctmd-services/`, no key. It catalogues this survey more than once, and
// **both lists are incomplete, in different directions** — so the denominator
// is the UNION of serie 175 (assembled sheets, 1901–1944, IGN) and serie 243
// (half-sheets in colour), not either alone:
//
//     175: 76 cells     only in 175: 7, 8, 9, 19
//     243: 75 cells     only in 243: 1, 34, 67
//     union: 79
//
// The first seeding took 175 alone, on the reasoning that the half-sheet
// editions would double-count every sheet. That reasoning is right about
// PRINTINGS and wrong about CELLS, which is what this table is keyed on:
// collapsing a sheet's W and E halves onto their cell number double-counts
// nothing. The cost of getting it wrong was not an abstract three: **we hold
// sheet 1, Viet Tri 1906, and 175 does not list it** — so the archive held a
// sheet its own survey index said the survey did not contain, which is the
// exact failure this table exists to prevent, one level up. It also explains an
// arithmetic mismatch nobody had chased: 58 held against 59 distinct cells in
// `maps`. The missing one was cell 1.
//
// Two normalisations, both of them the catalogue's own typography rather than
// real distinctions:
//
//   - 243 brackets a number it is inferring — `[42]` is cell 42 — and for a
//     cell held as two half-sheets it brackets the WEST half and leaves the
//     east bare, so `[1]` and `1` are one cell's two halves. Unbracketed, 243
//     has 142 "cells"; bracket-stripped it has 75.
//   - `0bis` is written without the space that `5 bis`, `10 bis` and `73 bis`
//     all have. Left alone it lands as an 80th cell. This is the same class of
//     bug as the `00b` → `0 bis` renumbering below, which is why it is called
//     out here: it has now bitten twice.
//
// The bbox is the union of every record for that cell, across both series,
// which is what makes a half-sheet pair come out as its whole cell. It is the
// catalogue's UNIMARC corner fields (right to about a minute of arc), NOT a
// georeference — it is here so an unheld sheet can be drawn as a gap, and
// nothing should warp against it. Checked against our own 59 georeferenced
// cells: every one agrees with the catalogue to better than 0.01°.
//
// The series declares 81 sheets and neither list reaches that, so 79 is still a
// floor rather than the truth.

import fs from 'node:fs';
import { cellNumber } from '../lib/cells.mjs';
import { serviceClient, upsertChunked } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

// Was: write unless --dry. Nothing in scripts/ writes without --apply now.
const apply = willApply();
const SERIES_IDS = [175, 243]; // see the header: neither list is complete
const SERIES = 'indochine-1-25-000-tonkin-thanh-hoa'; // series_key(), mig 082
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const api = (id) => `https://www.cartomundi.fr/ctmd-services/serie/${id}/feuilles`;

/** Brackets mark a part the catalogue is reconstructing; the name is the rest. */
function cellName(v) {
  return (
    String(v ?? '')
      .replace(/[[\]]/g, '')
      .replace(/\s+/g, ' ')
      .trim() || null
  );
}

/** UNIMARC corner: a hemisphere letter then DDDMMSS, e.g. "e1055008" -> 105.8356. */
function unimarc(v) {
  const m = /^([nsew])(\d{3})(\d{2})(\d{2})$/i.exec(String(v || '').trim());
  if (!m) return null;
  const deg = +m[2] + +m[3] / 60 + +m[4] / 3600;
  return /[sw]/i.test(m[1]) ? -deg : deg;
}

const sheets = [];
for (const id of SERIES_IDS) {
  const recs = await (await fetch(api(id), { headers: { Accept: 'application/json' } })).json();
  console.log(
    `CartoMundi serie ${id}: ${recs.length} records over ` +
      `${new Set(recs.map((f) => cellNumber(f.f100NumeroOuCode))).size} cells`
  );
  for (const f of recs) sheets.push({ ...f, serie: id });
}

const db = serviceClient();
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
  const sn = cellNumber(f.f100NumeroOuCode);
  if (!sn) continue;
  if (!byNumber.has(sn)) byNumber.set(sn, []);
  byNumber.get(sn).push(f);
}

const out = [];
for (const [sn, editions] of byNumber) {
  // The newest record carries the best title; the extent is the union of every
  // record, which is what turns a bracketed/bare pair back into its whole cell.
  const best = editions.slice().sort((a, b) => (b.f103DateAaaa || 0) - (a.f103DateAaaa || 0))[0];
  let bbox = null;
  for (const f of editions) {
    const g = f.geometrieEmprise || {};
    const b = [
      unimarc(g.l123dLimiteOuestUnimarc),
      unimarc(g.l123gLimiteSudUnimarc),
      unimarc(g.l123eLimiteEstUnimarc),
      unimarc(g.l123fLimiteNordUnimarc),
    ];
    if (!b.every((v) => typeof v === 'number')) continue;
    bbox = bbox
      ? [
          Math.min(bbox[0], b[0]),
          Math.min(bbox[1], b[1]),
          Math.max(bbox[2], b[2]),
          Math.max(bbox[3], b[3]),
        ]
      : b;
  }
  const m = held.get(sn);
  const years = [...new Set(editions.map((x) => x.f103DateAaaa).filter(Boolean))].sort();
  const series = [...new Set(editions.map((x) => x.serie))].sort();
  out.push({
    series_key: SERIES,
    sheet_number: sn,
    name: cellName(best.f105Titre),
    bbox,
    held_by: m ? 'map' : null,
    map_id: m ? m.id : null,
    source: 'CartoMundi',
    source_ref: best.fkey ? String(best.fkey) : null,
    note: [
      years.length > 1
        ? `${editions.length} records, ${years.length} dates: ${years.join(', ')}`
        : years[0]
          ? `edition ${years[0]}`
          : null,
      `serie ${series.join('+')}`,
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
const orphan = [...held.keys()].filter((k) => !byNumber.has(cellNumber(k)));
if (orphan.length) console.log(`\nour sheet numbers not in the catalogue: ${orphan.join(', ')}`);

if (!apply) {
  dryNotice(`It would upsert ${out.length} rows into series_sheets.`);
  process.exit(0);
}

await upsertChunked(db, 'series_sheets', out, {
  onConflict: 'series_key,sheet_number',
  quiet: true,
});
console.log(`\nupserted ${out.length} rows`);
