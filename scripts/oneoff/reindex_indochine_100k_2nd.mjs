#!/usr/bin/env node
// Re-index the Indochine 1:100,000 2nd édition (CartoMundi skey 561) from the
// WHOLE catalogue, not just the part that has a scan.
//
// `import_indochine_100k_series_sheets.mjs` read `serie-561.json`, which is
// reduced from CartoMundi's `exemplaire/all` endpoint and so holds only the 492
// records that carry a digitised copy. The index it built was therefore the
// archive's own holdings: 197 cells, every one held, and the coverage page said
// "197 of 197 — 100%" of a survey that is not complete.
//
// CartoMundi declares 843 records for the series, and
// `work/cartomundi-rights/feuilles/561.json` (scripts/fetch_cartomundi_sheets.mjs,
// the light `serie/561/feuilles` endpoint) holds all 843 with their extents.
// Grouped into cells the way the importer keyed them, that is 220 cells, of
// which 197 have a digitised record; the other records are further printings
// and halves of cells already held. This script writes all 220: a cell with no
// digitised record and no published map is `no_scan` (no `source`), a cell with
// a digitised record the archive has not published is `obtainable`.
//
// A cell is two half-sheets, west and east (their boxes tile it: the east half's
// west edge is 0.36° past the west half's). Seventeen cells have only ONE half in
// the catalogue, and drawn as the cell they leave a half-width hole in the row —
// the holes on the coverage map. Each gets a row of its own for the half that is
// not catalogued, keyed `<cell> W` / `<cell> E`, `no_scan`, its box inferred from
// the half that is: same height and width, on the side its label says. Where that
// side lands on top of another cell (the label is wrong: cells 33 and 154) the
// other side is used. Cell 154 clashes on both sides and gets no
// row, so 16 are written.
//
// Still the CATALOGUE's census, not the survey's: a sheet number CartoMundi never
// listed (155 is the one inside a row's run) is not in it, and nothing here can say
// whether it exists or where.
//
//   node --env-file=.env scripts/oneoff/reindex_indochine_100k_2nd.mjs [--apply]
//
// Only the columns named below are written, so `year` and `edition` (mig 086)
// on existing rows are left alone. Dry-run by default; it prints the diff
// against what is in the table.

import fs from 'node:fs';
import { serviceClient, upsertChunked, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const apply = willApply();
const SERIES_KEY = 'indochine-1-100-000-2nd-edition-sgi-1947-1959';
const FEUILLES = 'work/cartomundi-rights/feuilles/561.json';
const DIGITISED = 'work/indochine-100k/sources/serie-561.json';

/** UNIMARC corner: a hemisphere letter then DDDMMSS, e.g. "e1055008" -> 105.8356. */
function unimarc(v) {
  const m = /^([nsew])(\d{3})(\d{2})(\d{2})$/i.exec(String(v || '').trim());
  if (!m) return null;
  const deg = +m[2] + +m[3] / 60 + +m[4] / 3600;
  return /[sw]/i.test(m[1]) ? -deg : deg;
}

/**
 * The cell a catalogue number belongs to, and which half it is. Validated
 * against the 492 digitised records: every one lands on the key the existing
 * rows use (`158 bis`, `99-107`, `22`).
 */
function parseNumber(number) {
  let s = String(number ?? '')
    .replace(/[[\]]/g, '')
    .trim();
  let part = null;
  const m = /\s*(Est|Ouest|E|W)$/i.exec(s);
  if (m) {
    part = /^e/i.test(m[1]) ? 'E' : 'W';
    s = s.slice(0, m.index);
  }
  s = s
    .trim()
    .replace(/\s*-\s*/g, '-')
    .replace(/(\d)\s*(bis|b)$/i, '$1 bis');
  return { cell: s, part };
}

const records = JSON.parse(fs.readFileSync(FEUILLES, 'utf8')).records;
const digitised = new Set(
  Object.values(JSON.parse(fs.readFileSync(DIGITISED, 'utf8')).cells)
    .flat()
    .map((r) => r.fkey)
);

const cells = new Map();
for (const r of records) {
  const { cell, part } = parseNumber(r.number);
  if (!cell) continue;
  if (!cells.has(cell)) cells.set(cell, []);
  const box = (r.bbox ?? []).map(unimarc);
  cells.get(cell).push({
    ...r,
    part,
    digitised: digitised.has(r.fkey),
    box: box.length === 4 && box.every((v) => typeof v === 'number') ? box : null,
  });
}

/**
 * CartoMundi's extents are wrong for two cells: 154's records carry 153's
 * extent, and 157's east half carries 156's. The sheets themselves are fine, the
 * copy is not — a cell's neighbours in its row sit one pitch (twice a half's
 * width) apart, so the record of the higher-numbered cell moves one cell east,
 * which lands it flush against its neighbours (154 west at 105.84 = 153's east
 * edge; 157 east half ending at 108.62 = 158's west edge). Found by looking for
 * one extent shared by records of different cells; these are the only two.
 */
const byExtent = new Map();
for (const [cell, recs] of cells)
  for (const r of recs) {
    if (!r.box) continue;
    const k = r.box.join(',');
    if (!byExtent.has(k)) byExtent.set(k, new Set());
    byExtent.get(k).add(cell);
  }
for (const [k, owners] of byExtent) {
  if (owners.size < 2) continue;
  const [first, ...later] = [...owners].sort((a, b) => parseFloat(a) - parseFloat(b));
  for (const cell of later)
    for (const r of cells.get(cell).filter((r) => r.box?.join(',') === k)) {
      const pitch = 2 * (r.box[2] - r.box[0]);
      r.box = [r.box[0] + pitch, r.box[1], r.box[2] + pitch, r.box[3]];
      console.log(
        `cell ${cell}: extent copied from cell ${first}; moved ${pitch.toFixed(2)}° east`
      );
    }
}

const db = serviceClient();

// Held = an archive map in this series carries the cell's number. The most
// finished record stands for the cell, as the first importer ranked them.
const { data: maps, error } = await db
  .from('maps')
  .select('id,status,is_georeferenced,sheet_number')
  .eq('series_key', SERIES_KEY)
  .not('sheet_number', 'is', null);
if (error) throw error;
const rank = (r) => (r.is_georeferenced ? 2 : 0) + (r.status === 'public' ? 1 : 0);
const held = new Map();
for (const m of maps) {
  const sn = String(m.sheet_number).trim();
  if (!held.has(sn) || rank(m) > rank(held.get(sn))) held.set(sn, m);
}

const out = [];
for (const [cell, recs] of cells) {
  const best = recs.slice().sort((a, b) => (b.year || 0) - (a.year || 0))[0];
  let bbox = null;
  for (const r of recs) {
    const b = r.box;
    if (!b) continue;
    bbox = bbox
      ? [
          Math.min(bbox[0], b[0]),
          Math.min(bbox[1], b[1]),
          Math.max(bbox[2], b[2]),
          Math.max(bbox[3], b[3]),
        ]
      : b;
  }
  const anyDigitised = recs.some((r) => r.digitised);
  const m = held.get(cell);
  const parts = [...new Set(recs.map((r) => r.part).filter(Boolean))].sort();
  const years = [...new Set(recs.map((r) => r.year).filter(Boolean))].sort();

  out.push({
    series_key: SERIES_KEY,
    sheet_number: cell,
    name: String(best.title ?? '')
      .replace(/[[\]]/g, '')
      .replace(/\s+/g, ' ')
      .trim(),
    bbox,
    held_by: m ? 'map' : null,
    map_id: m ? m.id : null,
    // A catalogue record with no digitised copy has nowhere to fetch a scan
    // from: no `source`, so the cell reads "no known scan".
    source: m || anyDigitised ? 'CartoMundi' : null,
    source_ref: best.fkey ? String(best.fkey) : null,
    note: [
      `${recs.length} record${recs.length > 1 ? 's' : ''}${parts.length ? ` (${parts.join('+')})` : ''}`,
      years.length ? `dates ${years.join(', ')}` : null,
      'serie 561',
      anyDigitised ? 'digitised copy at IGN/Nakala' : 'catalogued only, no digitised copy found',
      'bbox is CartoMundi catalogue extent, not a georeference',
    ]
      .filter(Boolean)
      .join(' · '),
  });
}

/** Overlap of two boxes as a fraction of the first one's area. */
function overlap(a, b) {
  const w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]);
  const h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
  return w > 0 && h > 0 ? (w * h) / ((a[2] - a[0]) * (a[3] - a[1])) : 0;
}
const boxOf = (recs) =>
  recs
    .map((r) => r.box)
    .filter(Boolean)
    .reduce(
      (u, b) =>
        u
          ? [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])]
          : b,
      null
    );
const cellBoxes = new Map(out.map((r) => [r.sheet_number, r.bbox]));
const halves = [];
for (const [cell, recs] of cells) {
  const parts = new Set(recs.map((r) => r.part));
  if (parts.has(null) || parts.size !== 1) continue;
  const [part] = parts;
  const known = boxOf(recs);
  if (!known) continue;
  const width = known[2] - known[0];
  // The missing half sits west of an east half and east of a west half.
  const westOf = [known[0] - width, known[1], known[0], known[3]];
  const eastOf = [known[2], known[1], known[2] + width, known[3]];
  const [label, other] = part === 'E' ? [westOf, eastOf] : [eastOf, westOf];
  const clash = (box) =>
    Math.max(
      0,
      ...[...cellBoxes].filter(([k]) => k !== cell).map(([, b]) => (b ? overlap(box, b) : 0))
    );
  let box = label;
  if (clash(label) > 0.5) {
    if (clash(other) > 0.5) {
      console.log(`cell ${cell}: both sides overlap another cell, no half row written`);
      continue;
    }
    console.log(
      `cell ${cell}: its label puts the missing half on another cell; using the other side`
    );
    box = other;
  }
  // Named by where it sits, not by the catalogue's label, which is wrong for two cells.
  const side = box === westOf ? 'W' : 'E';
  const best = recs.slice().sort((a, b) => (b.year || 0) - (a.year || 0))[0];
  const base = String(best.title ?? '')
    .replace(/\s+(est|ouest)\s*$/i, '')
    .replace(/[[\]]/g, '')
    .trim();
  halves.push({
    series_key: SERIES_KEY,
    sheet_number: `${cell} ${side}`,
    name: `${base} ${side === 'E' ? 'Est' : 'Ouest'}`.trim(),
    bbox: box.map((n) => Math.round(n * 1e5) / 1e5),
    held_by: null,
    map_id: null,
    source: null,
    source_ref: null,
    note: `half-sheet of cell ${cell} with no CartoMundi record · serie 561 · box inferred from the catalogued half (${part}), not from a record`,
  });
}
console.log(`half-sheets with no catalogue record: ${halves.length}`);
out.push(...halves);

/**
 * A number inside a row's run that the catalogue never lists. 155 is the only
 * one: its neighbours 154 and 156 are catalogued, and with their missing halves
 * filled the space between them is exactly one cell. Its box is that space.
 */
const edge = (cell, side) => {
  const bs = out.filter((r) => r.sheet_number === cell || r.sheet_number.startsWith(`${cell} `));
  const xs = bs.map((r) => r.bbox[side === 'east' ? 2 : 0]);
  return side === 'east' ? Math.max(...xs) : Math.min(...xs);
};
const lower = out.find((r) => r.sheet_number === '154');
if (lower && !cells.has('155')) {
  const west = edge('154', 'east');
  const east = edge('156', 'west');
  out.push({
    series_key: SERIES_KEY,
    sheet_number: '155',
    name: null,
    bbox: [west, lower.bbox[1], east, lower.bbox[3]].map((n) => Math.round(n * 1e5) / 1e5),
    held_by: null,
    map_id: null,
    source: null,
    source_ref: null,
    note: 'no CartoMundi record · serie 561 · number inside the row between 154 and 156; box is the space between them',
  });
  console.log(
    `cell 155: no record; box ${out.at(-1).bbox.join(', ')} (one cell wide: ${(east - west).toFixed(2)}°)`
  );
}

const dups = duplicateKeys(out, (r) => `${r.series_key}\u0000${r.sheet_number}`);
if (dups.length) {
  console.error(`duplicate keys, refusing: ${dups.join(', ')}`);
  process.exit(1);
}

const { data: current, error: curErr } = await db
  .from('series_cells')
  .select('sheet_number,bbox,held_by,source,note')
  .eq('series_key', SERIES_KEY);
if (curErr) throw curErr;
const before = new Map(current.map((r) => [r.sheet_number, r]));

const status = (r) => (r.held_by ? 'held' : r.source ? 'obtainable' : 'no_scan');
const tally = (rows) =>
  rows.reduce((t, r) => ({ ...t, [status(r)]: (t[status(r)] ?? 0) + 1 }), { total: rows.length });
const near = (a, b) => a && b && a.every((v, i) => Math.abs(v - b[i]) < 1e-3);

console.log(
  `records ${records.length} → ${cells.size} cells (${digitised.size} digitised records)`
);
console.log('before', tally(current));
console.log('after ', tally(out));
console.log(`new cells: ${out.filter((r) => !before.has(r.sheet_number)).length}`);
console.log(
  `existing cells dropped: ${[...before.keys()].filter((k) => !out.some((r) => r.sheet_number === k)).join(', ') || 'none'}`
);
console.log(
  `bbox changed on existing: ${out.filter((r) => before.has(r.sheet_number) && !near(before.get(r.sheet_number).bbox, r.bbox)).length}`
);
console.log(
  `status changed on existing: ${out.filter((r) => before.has(r.sheet_number) && status(before.get(r.sheet_number)) !== status(r)).length}`
);
console.log(`no bbox parsed: ${out.filter((r) => !r.bbox).length}`);
console.log(
  'unheld:',
  out
    .filter((r) => !r.held_by)
    .map((r) => `${r.sheet_number}(${status(r)})`)
    .join(' ')
);

if (!apply) {
  dryNotice(`It would upsert ${out.length} rows into series_cells.`);
  process.exit(0);
}
await upsertChunked(db, 'series_cells', out, {
  onConflict: 'series_key,sheet_number',
  quiet: true,
});
console.log(`upserted ${out.length} rows`);
