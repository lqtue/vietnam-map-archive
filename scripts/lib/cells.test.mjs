/**
 * Full-corpus parity for `cells.mjs`: every parser it replaced, run verbatim
 * beside it over every real record, asserting they still agree.
 *
 *   node scripts/lib/cells.test.mjs
 *
 * The catalogue dumps this reads are gitignored (42 MB), so this cannot ride
 * CI; `tests/ingest-cells.spec.ts` pins the same behaviour on trap bytes copied
 * out of them and runs anywhere. Run this one when the dumps are on disk —
 * after a re-fetch especially, because it is a re-fetch that would introduce a
 * spelling nobody has seen.
 *
 * Where old and new are *meant* to differ, the difference is asserted rather
 * than tolerated: `ingest_indochine_nakala.mjs`'s `half()` had no assemblage
 * branch and called all 79 of them 'whole'.
 */
import { readFileSync, existsSync } from 'node:fs';
import assert from 'node:assert';
import { cellNumber, cellOf, sheetPart, printedYear, partFromTitle } from './cells.mjs';

// ── the implementations as they stood before the merge ──────────────────────
const cleanOld = (s) => {
  const t = String(s ?? '')
    .replace(/"{2,}/g, '"')
    .replace(/^"+|"+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return t || null;
};
/** load_sheet_sources.mjs */
const cellNumberOld = (v) =>
  String(v ?? '')
    .trim()
    .replace(/^\[|\]$/g, '')
    .trim()
    .replace(/^(\d+)bis$/i, '$1 bis')
    .toLowerCase();
/** plan_indochine_halfsheet_migration.mjs */
const cellKeyOld = (raw) =>
  String(raw ?? '')
    .replace(/[[\]]/g, '')
    .toLowerCase()
    .replace(/(\d)\s*bis/g, '$1 bis')
    .replace(/\s+/g, ' ')
    .trim();
/** load_sheet_sources.mjs */
const partOfOld = (note) => {
  const n = cleanOld(note) ?? '';
  if (/demi-format/i.test(n)) return 'whole';
  if (/^assemblage/i.test(n)) return 'assemblage';
  const m = /^demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return null;
};
/** plan_indochine_halfsheet_migration.mjs */
const partPlanOld = (note) => {
  const n = String(note ?? '').replace(/^"+/, '');
  if (/assemblage/i.test(n)) return 'assemblage';
  if (/demi-format/i.test(n)) return 'demi-format';
  const m = /^\s*demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return 'unknown';
};
/** ingest_indochine_nakala.mjs — the one with no assemblage branch */
const halfOld = (note) => {
  const n = String(note || '');
  if (/demi-format/i.test(n)) return 'whole';
  const m = /^\s*demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return 'whole';
};
const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };
/** scout_anu_l7014.mjs */
const cellOfOld = (title) => {
  const m = /Sheet\s+(\d{4})\s*([IVl]{1,3})(?=[,\s]|$)/i.exec(title || '');
  if (!m) return null;
  const q = ROMAN[m[2].replace(/l/g, 'I').toUpperCase()];
  return q ? `${m[1]}-${q}` : null;
};

// the caller-side mappings the merged classifier is used through
const asSheetSources = (p) => (p === 'demi-format' ? 'whole' : p);
const asPlan = (p) => p ?? 'unknown';

const IGN = ['work/tonkin/sources/ign-serie-243.json', 'work/tonkin/sources/ign-serie-175.json'];
const ANU = 'work/l7014/anu-sources.json';
const TTU = 'work/l7014/ttu/EDITIONS.md';
const missing = [...IGN, ANU, TTU].filter((p) => !existsSync(p));
if (missing.length) {
  console.log(`cells parity: SKIPPED — not on disk:\n  ${missing.join('\n  ')}`);
  process.exit(0);
}

// ── IGN: 304 copy records ───────────────────────────────────────────────────
const ign = IGN.flatMap((p) => JSON.parse(readFileSync(p, 'utf8')));
let assemblageDivergence = 0;
for (const r of ign) {
  const raw = r.f100NumeroOuCode;
  assert.equal(cellNumber(raw), cellNumberOld(raw), `cellNumber drift on ${JSON.stringify(raw)}`);
  assert.equal(cellNumber(raw), cellKeyOld(raw), `cellKey drift on ${JSON.stringify(raw)}`);

  const p = sheetPart(r.f101Note);
  assert.equal(
    asSheetSources(p),
    partOfOld(r.f101Note),
    `partOf drift on ${JSON.stringify(cleanOld(r.f101Note))}`
  );
  assert.equal(
    asPlan(p),
    partPlanOld(r.f101Note),
    `plan part drift on ${JSON.stringify(cleanOld(r.f101Note))}`
  );

  const old = halfOld(r.f101Note);
  if (p === 'assemblage') {
    assert.equal(old, 'whole', 'expected the old half() to mislabel an assemblage');
    assemblageDivergence++;
  } else {
    assert.equal(
      p === 'demi-format' || p === null ? 'whole' : p,
      old,
      `half() drift on ${JSON.stringify(cleanOld(r.f101Note))}`
    );
  }

  // the title's brackets are the independent read; it must not have moved
  assert.equal(
    partFromTitle(r.f105Titre),
    ((t) => {
      const s = String(t ?? '');
      const i = s.indexOf('[');
      return i < 0 ? null : s.slice(0, i).replace(/[\s-]/g, '') ? 'W' : 'E';
    })(r.f105Titre)
  );
}
assert.equal(ign.length, 304, `expected 304 IGN copy records, got ${ign.length}`);
assert.equal(
  assemblageDivergence,
  79,
  `expected 79 assemblages the old half() got wrong, got ${assemblageDivergence}`
);

// ── ANU: 160 items ──────────────────────────────────────────────────────────
const anu = JSON.parse(readFileSync(ANU, 'utf8')).items;
for (const i of anu)
  assert.equal(cellOf(i.title), cellOfOld(i.title), `cellOf drift on ${JSON.stringify(i.title)}`);
assert.equal(anu.length, 160);
assert.equal(anu.filter((i) => cellOf(i.title)).length, 159, 'expected 159 cells + 1 index sheet');

// ── TTU: every four-digit number in the hand-read tables ────────────────────
const md = readFileSync(TTU, 'utf8');
const yearOfOld = (v) => {
  const n = Number(v);
  return Number.isInteger(n) && n > 1800 && n < 2100 ? n : null;
};
const printedYearOld = (s) => {
  const t = String(s ?? '');
  const m = /in\s+l[ạa]i\s+(\d{4})/i.exec(t) || /in\s+l[ầa]n\s+th[ứu][^\d]{0,20}(\d{4})/i.exec(t);
  return m ? yearOfOld(m[1]) : null;
};
const cells = md
  .split('\n')
  .filter((l) => l.trim().startsWith('|'))
  .flatMap((l) => l.split('|'));
for (const c of cells)
  assert.equal(printedYear(c), printedYearOld(c), `printedYear drift on ${JSON.stringify(c)}`);
assert.ok(
  cells.some((c) => printedYear(c) === 1978),
  'expected the two 1978 SRV redraws'
);
assert.ok(
  cells.some((c) => printedYear(c) === 1980),
  'expected the 1980 first printings'
);
// the three decoys the greedy \d{4} would have taken
for (const decoy of cells.filter((c) =>
  /Indian Datum|renseignements cartographiques|information as of/i.test(c)
))
  assert.equal(
    printedYear(decoy),
    null,
    `a decoy year was read as a printing: ${JSON.stringify(decoy)}`
  );

console.log(
  `cells parity: all assertions pass — ${ign.length} IGN records, ${anu.length} ANU items, ` +
    `${cells.length} TTU table cells; ${assemblageDivergence} assemblages the old half() called 'whole'`
);
