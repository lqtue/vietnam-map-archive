/**
 * load_sheet_sources.mjs — four institutional catalogues into `sheet_sources`.
 *
 *   node --env-file=.env scripts/oneoff/load_sheet_sources.mjs            # dry run
 *   node --env-file=.env scripts/oneoff/load_sheet_sources.mjs --apply
 *
 * Migration 087 added one row per KNOWN PRINTING of a cell at an institution,
 * because `series_sheets` is one row per cell and cannot hold two. This is the
 * first load. It reads only files already sitting in `work/` — nothing here
 * fetches, so it is reproducible offline and cannot be confounded by a
 * catalogue that changed underneath it:
 *
 *   work/l7014/sheets.json              535 Perry-Castañeda items (L7014)
 *   work/l7014/ttu/EDITIONS.md           25 Texas Tech sheets, read off the
 *                                        collars by hand, three markdown tables
 *   work/l7014/anu-sources.json         160 ANU items (159 cells + 1 index)
 *   work/tonkin/sources/ign-serie-243.json   216 IGN copies (half-sheets)
 *   work/tonkin/sources/ign-serie-175.json    88 IGN copies (assemblies)
 *
 * Dry by default: it prints the counts and the first rows of each source and
 * writes nothing. `--apply` upserts on `(institution, source_ref)`, which is
 * 087's item key, so a re-run after a cell-number correction MOVES a row rather
 * than leaving a duplicate under the old number.
 *
 * FOUR TRAPS, ALL LIVE IN THE DATA, ALL OF WHICH FAIL SILENTLY
 *
 * 1. ANU spells the quadrant's Roman numeral with a lowercase L — "Sheet 6738
 *    lll", "6631 lV", "6539 Il" — on 21 of 160 titles. That is a typist
 *    reaching for the nearest key, not a different numbering. Unfolded, an
 *    eighth of the collection parses to no cell and reads as ANU not holding
 *    it. `cellOf` is lifted verbatim from `scout_anu_l7014.mjs`, which already
 *    solved this; it is not re-derived here.
 *
 * 2. The Roman numeral is the QUADRANT of the 1:100,000 sheet, not an edition.
 *    ANU's "6531 II" is this archive's "6531-2". At least one secondary source
 *    reads it as an edition and produces a plausible, wrong answer.
 *
 * 3. Indochine cell numbers carry the catalogue's own typography rather than
 *    distinct cells: `[42]` is cell 42 with the bracketed half of the title
 *    restituted, and `0bis`, `0 bis`, `[0bis]`, `5 bis`, `73 bis` are three
 *    cells spelled five ways. `cellNumber` is lifted verbatim from
 *    `import_indochine_series_sheets.mjs` so this loader and the index that
 *    already exists cannot disagree about what a cell is called — a mismatch
 *    there does not error, it just finds nothing.
 *
 * 4. A four-digit number on a TTU collar is not necessarily a printing year.
 *    "Indian Datum 1960", "renseignements cartographiques 1960" and
 *    "information as of 1965" are a datum and two currency-of-information
 *    dates. A greedy `\d{4}` would file three of the 25 sheets under a decade
 *    they were not printed in, and the result would look entirely reasonable.
 *    `printedYear` anchors on the two Vietnamese phrases that do mean printing.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';

const apply = process.argv.includes('--apply');

const L7014 = 'series-l7014-vietnam-1-50-000'; // series_key(), mig 082
const INDOCHINE = 'indochine-1-25-000-tonkin-thanh-hoa';

const PCL = 'work/l7014/sheets.json';
const TTU = 'work/l7014/ttu/EDITIONS.md';
const ANU = 'work/l7014/anu-sources.json';
const IGN = ['work/tonkin/sources/ign-serie-243.json', 'work/tonkin/sources/ign-serie-175.json'];

const read = (p) => JSON.parse(readFileSync(p, 'utf8'));
const clean = (s) => {
  // CartoMundi's CSV export doubled every quote and then wrapped the field, so
  // a handful of IGN notes arrive as `"""Assemblage … """`. Left alone the
  // leading quotes defeat every anchored match below.
  const t = String(s ?? '')
    .replace(/"{2,}/g, '"')
    .replace(/^"+|"+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return t || null;
};
const yearOf = (v) => {
  const n = Number(v);
  return Number.isInteger(n) && n > 1800 && n < 2100 ? n : null;
};

// ── Perry-Castañeda ────────────────────────────────────────────────────────
// One item per scanned file, which is not quite one per cell: 6542-3 is there
// twice, as a georeferenced GeoPDF and as a plain JPEG with no year and no
// edition in its name. Two items, two rows — the JPEG may be the same printing
// or another one, and this table's job is to record that both exist rather than
// to guess.
function pclRows() {
  return read(PCL).map((r) => ({
    series_key: L7014,
    sheet_number: String(r.sheet),
    institution: 'PCL',
    source_ref: String(r.file),
    title: r.name ?? null,
    year: yearOf(r.year),
    // Text on purpose (086): this file holds both "003" and "3" for the same
    // survey. Normalising them here would hide a fault rather than fix it —
    // `fix_l7014_editions.mjs` is where that repair belongs.
    edition: r.edition != null ? String(r.edition) : null,
    part: 'whole',
    url: r.url ?? null,
    rights: null, // PCL states none item-level
    note: r.kind === 'jpg' ? 'JPEG scan; no georeference, no edition recorded' : null,
  }));
}

// ── Texas Tech ─────────────────────────────────────────────────────────────
// Read off the collars by hand into three markdown tables with three different
// column sets, so the parse is generic over `| a | b |` rows and the mapping is
// per-table by column name.
function mdTables(md) {
  const out = [];
  let head = null;
  for (const line of md.split('\n')) {
    if (!line.trim().startsWith('|')) {
      head = null;
      continue;
    }
    const cells = line
      .split('|')
      .slice(1, -1)
      .map((s) => s.replace(/\*\*/g, '').trim());
    if (cells.every((c) => /^:?-+:?$/.test(c))) continue;
    if (!head) {
      head = cells;
      continue;
    }
    out.push(Object.fromEntries(head.map((h, i) => [h, cells[i] ?? ''])));
  }
  return out;
}

/** The only two phrases on these collars that mean "printed in": `in lần thứ
 *  nhất 1980` (first printing) and `vẽ và in lại 1978` (redrawn and reprinted).
 *  Everything else four-digit on the sheet is a datum or a survey currency
 *  date — see trap 4 in the header. */
function printedYear(s) {
  const t = String(s ?? '');
  const m = /in\s+l[ạa]i\s+(\d{4})/i.exec(t) || /in\s+l[ầa]n\s+th[ứu][^\d]{0,20}(\d{4})/i.exec(t);
  return m ? yearOf(m[1]) : null;
}

function ttuRows() {
  return mdTables(readFileSync(TTU, 'utf8'))
    .filter((r) => /^\d{4}-\d$/.test(r.sheet ?? ''))
    .map((r) => ({
      series_key: L7014,
      sheet_number: r.sheet,
      institution: 'TTU',
      source_ref: `${r.sheet}.pdf`,
      title: r.title || null,
      year: printedYear(r.printing) ?? printedYear(r.notes),
      // Table 1 gives an edition token off the collar ("2-AMS (29 ETB)"); table
      // 2 gives the SRV printing statement, which IS the edition as printed.
      // Table 3's `notes` are a revision history, not an edition, and go to
      // `note` — calling "chỉnh lý 1982, 1986, 1987" an edition would put three
      // revision dates where a reader expects one printing.
      edition: r.edition || r.printing || null,
      part: 'whole',
      url: `https://vva.vietnam.ttu.edu/images.php?img=/maps/PDF/${r.sheet}.pdf`,
      rights: null,
      note: [r.content, r.notes].filter(Boolean).join('; ') || null,
    }));
}

// ── ANU ────────────────────────────────────────────────────────────────────
const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };

/** Verbatim from `scout_anu_l7014.mjs` — see traps 1 and 2. The collection's
 *  index sheet ("Vietnam INDEX, 1:50 000, Series: L7014") has no cell and
 *  correctly returns null. */
function cellOf(title) {
  const m = /Sheet\s+(\d{4})\s*([IVl]{1,3})(?=[,\s]|$)/i.exec(title || '');
  if (!m) return null;
  const q = ROMAN[m[2].replace(/l/g, 'I').toUpperCase()];
  return q ? `${m[1]}-${q}` : null;
}

function anuRows() {
  const items = read(ANU).items;
  const rows = [];
  for (const i of items) {
    const cell = cellOf(i.title);
    if (!cell) continue; // the printed series index; it is not a cell
    // ANU has no edition field. What it has is a printing note in
    // `local.description.notes` — "2nd printing 9-67" — which is the edition
    // statement off the collar in the cataloguer's words. Taken verbatim; the
    // rest of the note stays in `note` rather than being folded in.
    const ed = /(\d+(?:st|nd|rd|th)\s+printing(?:\s+\d{1,2}-\d{2})?)/i.exec(i.notes ?? '');
    rows.push({
      series_key: L7014,
      sheet_number: cell,
      institution: 'ANU',
      source_ref: i.uuid,
      title: i.title ?? null,
      year: yearOf(i.issued),
      edition: ed ? ed[1] : null,
      part: 'whole',
      url: i.url ?? null,
      rights: i.rights ?? null,
      note: clean(i.notes),
    });
  }
  return rows;
}

// ── IGN ────────────────────────────────────────────────────────────────────
/** Verbatim from `import_indochine_series_sheets.mjs` — see trap 3. */
function cellNumber(v) {
  return String(v ?? '')
    .trim()
    .replace(/^\[|\]$/g, '')
    .trim()
    .replace(/^(\d+)bis$/i, '$1 bis')
    .toLowerCase();
}

/** Which part of the cell this sheet of paper is.
 *
 *  Anchored on the note's OPENING clause, because several notes go on to
 *  discuss the other half — 73 bis 1927 reads "Demi-feuille Est. La partie de
 *  la mention de date … demi-feuille Ouest", and a search of the whole string
 *  calls the east half west. Same rule as `half()` in
 *  `ingest_indochine_nakala.mjs`, widened for serie 175's assemblies.
 *
 *  "Feuille de demi-format titrée comme une feuille complète" is a half-format
 *  sheet that carries the whole of the cell the series covers, so it is
 *  'whole', not a half. */
function partOf(note) {
  const n = clean(note) ?? '';
  if (/demi-format/i.test(n)) return 'whole';
  if (/^assemblage/i.test(n)) return 'assemblage';
  const m = /^demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return null;
}

function ignRows() {
  const rows = [];
  for (const path of IGN) {
    for (const r of read(path)) {
      const doc = (r.feuilleEtablissementDocuments ?? [])[0] ?? {};
      const doi = doc.f110IdNakala || null;
      rows.push({
        series_key: INDOCHINE,
        sheet_number: cellNumber(r.f100NumeroOuCode),
        institution: 'IGN',
        source_ref: String(doc.dpKey ?? r.fkey),
        // Brackets are kept: they mark the half of the title this sheet does
        // NOT print, which is the independent check on `part`.
        title: clean(r.f105Titre),
        year: yearOf(r.f103DateAaaa),
        // `f106MentionEdition` is the field named for this and is null on 252
        // of the 304 copies; `f104NoteDatation` carries the edition sentence on
        // 251 of those 252. Reading only the named field loses five sixths of
        // the editions this survey actually states.
        edition: clean(r.f106MentionEdition) ?? clean(r.f104NoteDatation),
        part: partOf(r.f101Note),
        // Nakala serves the scan; the DOI is the item. `f109UrlPageDeVisualisation`
        // is an empty string throughout this dump, so there is no second chance.
        url: doi ? `https://doi.org/${doi}` : null,
        // `tr38Licence` exists on every copy record and is null on every one of
        // the 304. Null means not stated.
        rights: clean(doc.tr38Licence),
        note: clean(r.f101Note),
      });
    }
  }
  return rows;
}

// ── collect, check, report ─────────────────────────────────────────────────
const sources = {
  PCL: pclRows(),
  TTU: ttuRows(),
  ANU: anuRows(),
  IGN: ignRows(),
};
const rows = Object.values(sources).flat();

// A duplicate item key would make the upsert lose rows rather than fail, and
// the loss would be invisible in the totals. Caught here instead.
const seen = new Map();
const dups = [];
for (const r of rows) {
  const k = `${r.institution} ${r.source_ref}`;
  if (seen.has(k)) dups.push(k);
  else seen.set(k, r);
}

const bad = rows.filter((r) => !r.sheet_number || !r.source_ref);

console.log('rows by institution');
for (const [k, v] of Object.entries(sources)) {
  const cells = new Set(v.map((r) => r.sheet_number)).size;
  const multi = v.length - cells;
  console.log(
    `  ${k.padEnd(4)} ${String(v.length).padStart(4)} printings over ${String(cells).padStart(3)}` +
      ` cells (+${multi} beyond one each)` +
      `  year ${v.filter((r) => r.year).length}` +
      `  edition ${v.filter((r) => r.edition).length}` +
      `  url ${v.filter((r) => r.url).length}` +
      `  rights ${v.filter((r) => r.rights).length}`
  );
}
console.log(`  ---- ${String(rows.length).padStart(4)} total`);

const byPart = {};
for (const r of rows) byPart[r.part ?? '(null)'] = (byPart[r.part ?? '(null)'] ?? 0) + 1;
console.log('\npart:', JSON.stringify(byPart));

for (const key of [L7014, INDOCHINE]) {
  const of = rows.filter((r) => r.series_key === key);
  const per = new Map();
  for (const r of of) per.set(r.sheet_number, (per.get(r.sheet_number) ?? 0) + 1);
  const many = [...per.values()].filter((n) => n > 1).length;
  console.log(
    `\n${key}\n  ${of.length} printings over ${per.size} cells; ` +
      `${many} cells have more than one, most is ${Math.max(0, ...per.values())}`
  );
}

if (dups.length) {
  console.log(`\nDUPLICATE item keys: ${dups.length}`);
  for (const d of dups.slice(0, 10)) console.log('  ' + d.replace(' ', ' / '));
}
if (bad.length) {
  console.log(`\nrows with no cell or no item key: ${bad.length}`);
  for (const b of bad.slice(0, 10)) console.log('  ' + JSON.stringify(b));
}

if (!apply) {
  console.log('\nDry run. Nothing was written. Re-run with --apply.');
  process.exit(dups.length || bad.length ? 1 : 0);
}
if (dups.length || bad.length) throw new Error('refusing to write: see the report above');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
for (let i = 0; i < rows.length; i += 200) {
  const { error } = await db
    .from('sheet_sources')
    .upsert(rows.slice(i, i + 200), { onConflict: 'institution,source_ref' });
  if (error) throw new Error(error.message);
  console.log(`  upserted ${Math.min(i + 200, rows.length)}/${rows.length}`);
}
console.log(`\napplied: ${rows.length} rows`);
