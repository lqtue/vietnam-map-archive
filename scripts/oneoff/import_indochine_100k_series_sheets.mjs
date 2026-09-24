#!/usr/bin/env node
// Seed `series_sheets` (mig 083) with the two Indochine 1:100,000 series —
// CartoMundi skey 325 (1st éd. SGI, 1900-1947, 252 declared sheets) and skey
// 561 (2nd éd. SGI "L 605", 1947-1959, 413 declared sheets, civil+military
// editions interleaved).
//
//   node --env-file=.env scripts/oneoff/import_indochine_100k_series_sheets.mjs [--apply]
//
// Unlike the 25,000 Tonkin pair (175+243, two catalogues of the SAME sheets,
// unioned into one series_key), these are two different TIME PERIODS of one
// map programme -- so they stay two series_key values, not a union. A cell
// held by both editions appears once in each series' coverage page, which is
// literally true: they are different scans, taken decades apart.
//
// SOURCE. `work/indochine-100k/sources/serie-{325,561}.json`, reduced from
// CartoMundi's own `/ctmd-services/public/etablissement/3/serie/<id>/feuille/
// exemplaire/all` -- read 2026-09-21 over ~45 raw minutes each; the endpoint
// generates at roughly 10 KB/s server-side (confirmed via --compressed: same
// decoded rate, so it is generation-bound, not bandwidth-bound) and every raw
// row repeats the entire parent serie object plus, on this endpoint, the
// holding institution's logo as a base64 data URI -- 252 declared sheets
// became an 86 MB raw response. Regenerate the source files from a fresh pull
// if CartoMundi revises either series; there is no lighter endpoint.
//
// COVERAGE, for the record (from the reduced sources, re-derivable):
//   325: 514 half-sheet records over 143 cells. 223 halves (43%) carry a
//        digitized asset; 135 cells (89%) have at least one half scanned.
//   561: 492 half-sheet records over 197 cells. ALL 492 (100%) are digitized.
// Licence on both: CC-BY-NC-SA-4.0, Nakala collection 10.34847/nkl.d2a82952 --
// noncommercial, unlike the CC-BY-4.0 on the 25,000 series. Checked per-copy
// `tr38Licence`: always null on both series, so this is the collection-level
// licence, not a per-sheet override.
//
// NUMBERING. This scale's `f100NumeroOuCode` is NOT the 25,000 series'
// convention (bracket = catalogue-inferred, part comes from the NOTE field).
// Here East/West is IN the code itself, four ways observed: `113 [Est]`,
// `[203 Ouest]`, `178 E`, and bare `23` (a few dozen sheets with no E/W split
// at all). `normalizeCode()` below is this scale's own parser -- do not reach
// for `cellNumber()` from `scripts/lib/cells.mjs`, which is pinned to the
// 25,000 series' different convention and will silently misparse this one.
// Verified against every distinct shape in both files (`python3` survey, not
// eyeballed): 1004 of 1006 records parse; 2 are `[s.n.]` (no number at all)
// and are dropped, both in 325. Three sheets in 325 and three in 561 carry a
// `bis`/`b` suffix (`88 bis`, `167bis`, `159b`) and one cell in each series is
// a `99-107`-style compound number covering two catalogue cells in one sheet
// -- both kept as their own literal cell key rather than guessed apart.
//
// This is catalogue-only: `bbox` is the union of each cell's UNIMARC corner
// fields (good to about a minute of arc, via the SAME `unimarc()` parser the
// 25,000 importer uses, so the two series' extents are computed the same
// way), not a georeference. Nothing should warp against it.

import fs from 'node:fs';
import { serviceClient, upsertChunked, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const apply = willApply();

const SERIES = [
  {
    skey: 325,
    key: 'indochine-1-100-000-1st-edition-sgi-1900-1947',
    collection: 'Indochine 1:100,000 — 1st édition SGI (1900–1947)',
    source: 'work/indochine-100k/sources/serie-325.json',
  },
  {
    skey: 561,
    key: 'indochine-1-100-000-2nd-edition-sgi-1947-1959',
    collection: 'Indochine 1:100,000 — 2nd édition SGI (1947–1959)',
    source: 'work/indochine-100k/sources/serie-561.json',
  },
];

/** UNIMARC corner: a hemisphere letter then DDDMMSS, e.g. "e1055008" -> 105.8356. */
function unimarc(v) {
  const m = /^([nsew])(\d{3})(\d{2})(\d{2})$/i.exec(String(v || '').trim());
  if (!m) return null;
  const deg = +m[2] + +m[3] / 60 + +m[4] / 3600;
  return /[sw]/i.test(m[1]) ? -deg : deg;
}

/** Brackets mark a part the catalogue is reconstructing; the name is the rest. */
function cellName(v) {
  return (
    String(v ?? '')
      .replace(/[[\]]/g, '')
      .replace(/\s+/g, ' ')
      .trim() || null
  );
}

const db = apply ? serviceClient() : null;
const out = [];

for (const { skey, key: SERIES_KEY, collection, source } of SERIES) {
  const raw = JSON.parse(fs.readFileSync(source, 'utf8'));
  const cells = raw.cells;
  const cellKeys = Object.keys(cells);

  let held = new Map();
  if (apply) {
    const { data: rows, error } = await db
      .from('maps')
      .select('id,status,is_georeferenced,extra_metadata')
      .eq('collection', collection);
    if (error) throw error;
    const rank = (r) => (r.is_georeferenced ? 2 : 0) + (r.status === 'public' ? 1 : 0);
    for (const m of rows) {
      const sn = String(m.extra_metadata?.sheet_number || '').trim();
      if (!sn) continue;
      if (!held.has(sn) || rank(m) > rank(held.get(sn))) held.set(sn, m);
    }
  }

  let digitizedCells = 0;
  for (const cell of cellKeys) {
    const records = cells[cell];
    const best = records.slice().sort((a, b) => (b.year || 0) - (a.year || 0))[0];

    let bbox = null;
    for (const r of records) {
      const u = r.unimarc || {};
      const b = [unimarc(u.w), unimarc(u.s), unimarc(u.e), unimarc(u.n)];
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

    const anyDigitized = records.some((r) => r.assets?.some((a) => a.nakala_value));
    if (anyDigitized) digitizedCells++;
    const parts = [...new Set(records.map((r) => r.part).filter(Boolean))].sort();
    const years = [...new Set(records.map((r) => r.year).filter(Boolean))].sort();
    const m = held.get(cell);

    out.push({
      series_key: SERIES_KEY,
      sheet_number: cell,
      name: cellName(best.title),
      bbox,
      held_by: m ? 'map' : null,
      map_id: m ? m.id : null,
      source: 'CartoMundi',
      source_ref: best.fkey ? String(best.fkey) : null,
      note: [
        `${records.length} record${records.length > 1 ? 's' : ''}${parts.length ? ` (${parts.join('+')})` : ''}`,
        years.length ? `dates ${years.join(', ')}` : null,
        `serie ${skey}`,
        anyDigitized ? 'digitised copy at IGN/Nakala' : 'catalogued only, no digitised copy found',
        'bbox is CartoMundi catalogue extent, not a georeference',
      ]
        .filter(Boolean)
        .join(' · '),
    });
  }

  console.log(
    `serie ${skey} (${SERIES_KEY}): ${cellKeys.length} cells, ` +
      `${digitizedCells} with a digitised copy (${Math.round((100 * digitizedCells) / cellKeys.length)}%)`
  );
}

const dups = duplicateKeys(out, (r) => `${r.series_key}\u0000${r.sheet_number}`);
if (dups.length) {
  console.error(
    `duplicate (series_key, sheet_number) keys, refusing to upsert: ${dups.join(', ')}`
  );
  process.exit(1);
}

console.log(`\n${out.length} rows total across both series`);
console.log(`no bbox parsed: ${out.filter((r) => !r.bbox).length}`);

if (!apply) {
  dryNotice(`It would upsert ${out.length} rows into series_sheets.`);
  process.exit(0);
}

await upsertChunked(db, 'series_sheets', out, {
  onConflict: 'series_key,sheet_number',
  quiet: true,
});
console.log(`\nupserted ${out.length} rows`);
