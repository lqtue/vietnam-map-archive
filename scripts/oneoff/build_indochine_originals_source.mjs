#!/usr/bin/env node
/**
 * build_indochine_originals_source.mjs — the 122 IGN originals, as an ingest source.
 *
 *   node scripts/oneoff/build_indochine_originals_source.mjs
 *
 * READ-ONLY apart from the one file it writes. Turns
 * `work/tonkin/replacement-audit.json` into the `{cells: {...}}` shape
 * `ingest_indochine_nakala.mjs` already consumes, so the mirroring runs through
 * the path that mirrored the first 22 rather than a second copy of it.
 *
 * TWO THINGS THIS FIXES THAT A NAIVE READ OF THE CATALOGUE WOULD NOT.
 *
 * THE YEAR IS PINNED, NOT LATEST. The ingest picks "the most recent printing per
 * half" when handed several, which is right when filling an empty cell and wrong
 * here: these are replacements for composites that each carry a year, and cell 35
 * alone offers 1905 and 1924. Every cell below holds exactly one record per half,
 * already chosen at our composite's own year, so that rule becomes a no-op.
 *
 * THE DISPUTED HALF IS DECIDED, AND SAYS SO. Cells 25 and 74 each carry two 1904
 * records noted "Demi-feuille Ouest" whose titles read one west and one east; the
 * ingest throws on exactly this disagreement, deliberately. Falsifying `note` to
 * silence it would destroy the evidence, so the record carries `part`, the
 * decision, alongside the untouched `note` and `title` it was drawn from. Only a
 * record where a human has decided gets one, and the ingest's guard stays armed
 * for every record that does not.
 *
 * Cell 35 (An Thi) is excluded: our row says 1904 and serie 243 has no 1904 for
 * it. Cell 69's east half is excluded because IGN never digitised it. Neither is
 * a thing to paper over by fetching a different year.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { cellOrder } from '../lib/cells.mjs';

const AUDIT = 'work/tonkin/replacement-audit.json';
const OUT = 'work/tonkin/sources/nakala-originals.json';

const audit = JSON.parse(readFileSync(AUDIT, 'utf8'));

// A CELL CAN HOLD TWO COMPOSITES, AND THEY ARE NOT THE SAME SHEET. Cells 2, 13
// and 14 each carry two printings — Vinh Yen 1906 and 1919, and so on — and each
// wants the halves of ITS year, so those cells need four originals, not two.
// Assigning per composite rather than merging silently kept whichever came last
// and halved three cells. Records are keyed on half AND year for that reason;
// the same half of two printings is two pieces of paper.
const cells = {};
const skipped = [];
for (const row of audit.composites) {
  const usable = row.replacement.sheets.filter((s) => s.digitised && s.iiif);
  if (!usable.length) {
    skipped.push(`cell ${row.cell} ${row.name} ${row.our_year}: nothing digitised for that year`);
    continue;
  }
  for (const s of row.replacement.sheets) {
    if (!s.digitised || !s.iiif)
      skipped.push(
        `cell ${row.cell} ${row.name} ${row.our_year}: ${s.part_label} catalogued but not digitised`
      );
  }
  const into = (cells[row.cell] ??= new Map());
  for (const s of usable) {
    const k = `${s.part}|${s.year}`;
    if (into.has(k)) continue;
    into.set(k, {
      title: s.title,
      note: s.note ?? null,
      // The decision, where the catalogue contradicted itself. Absent otherwise.
      ...(s.part_per_note && s.part_per_note !== s.part
        ? {
            part: s.part,
            part_decided_because: `note says ${s.part_per_note}, title ${JSON.stringify(s.title)} says ${s.part}; the brackets mark the half of the title this sheet does not print, and read that way the cell makes a complete pair`,
          }
        : {}),
      year: s.year,
      serie: 243,
      fkey: s.fkey,
      nakala: s.doi,
      sha1: (s.iiif.match(/\/iiif\/[^/]+\/([^/]+)\//) ?? [])[1] ?? null,
      iiif: s.iiif,
      replaces_map_id: row.map_id,
      replaces_name: row.name,
    });
  }
}
let sheets = 0;
for (const [c, m] of Object.entries(cells)) {
  cells[c] = [...m.values()].sort(
    (a, b) => a.year - b.year || String(a.part).localeCompare(String(b.part))
  );
  sheets += cells[c].length;
}

// The ingest needs `note` to classify the half; a record we decided carries both.
for (const list of Object.values(cells)) {
  for (const r of list) {
    if (!r.note) throw new Error(`${r.title} ${r.year}: no note, the ingest cannot classify it`);
    if (!r.nakala || !r.sha1) throw new Error(`${r.title} ${r.year}: missing Nakala id or sha1`);
  }
}

const ordered = {};
for (const c of Object.keys(cells).sort((a, b) => cellOrder(a)[0] - cellOrder(b)[0]))
  ordered[c] = cells[c];

writeFileSync(
  OUT,
  JSON.stringify(
    {
      _source:
        'work/tonkin/replacement-audit.json, itself read from CartoMundi serie 243 + live IIIF',
      // Cells 2, 13 and 14 are each held as two printings and need the halves of
      // both, so the ingest must key on the year as well as the half.
      _year_pinned: true,
      _note:
        "IGN originals for the cells currently held as third-party composites. One record per half, pinned at the composite's own year. `part` appears only where the catalogue contradicted itself and a human decided; `note` and `title` are untouched. Mirroring these changes nothing public: rows land as drafts.",
      _generated_at: new Date().toISOString(),
      cells: ordered,
    },
    null,
    1
  )
);

console.log(`${sheets} original sheets over ${Object.keys(ordered).length} cells → ${OUT}`);
const size = {};
for (const l of Object.values(ordered)) size[l.length] = (size[l.length] ?? 0) + 1;
for (const n of Object.keys(size).sort())
  console.log(`  ${size[n]} cell(s) needing ${n} original sheet(s)`);
const multi = Object.entries(ordered).filter(([, l]) => new Set(l.map((r) => r.year)).size > 1);
if (multi.length) {
  console.log(
    `\n  ${multi.length} cell(s) held as two printings, each taking its own year's halves:`
  );
  for (const [c, l] of multi)
    console.log(`    cell ${c}: ${l.map((r) => `${r.part ?? ''}${r.year}`).join(', ')}`);
}
const decided = Object.values(ordered)
  .flat()
  .filter((r) => r.part);
if (decided.length) {
  console.log(
    `\n  ${decided.length} record(s) whose half we decided against the catalogue's note:`
  );
  for (const r of decided) console.log(`    ${r.title} ${r.year} → ${r.part}`);
}
if (skipped.length) {
  console.log(`\n  not included (${skipped.length}):`);
  for (const s of skipped) console.log(`    - ${s}`);
}
