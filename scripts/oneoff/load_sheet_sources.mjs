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
 *    it. `cellOf` lives in `scripts/lib/cells.mjs` with every other parser that
 *    decides what a sheet is called; this file no longer keeps its own copy.
 *
 * 2. The Roman numeral is the QUADRANT of the 1:100,000 sheet, not an edition.
 *    ANU's "6531 II" is this archive's "6531-2". At least one secondary source
 *    reads it as an edition and produces a plausible, wrong answer.
 *
 * 3. Indochine cell numbers carry the catalogue's own typography rather than
 *    distinct cells: `[42]` is cell 42 with the bracketed half of the title
 *    restituted, and `0bis`, `0 bis`, `[0bis]`, `5 bis`, `73 bis` are three
 *    cells spelled five ways. `cellNumber` is shared with the index importer
 *    through `scripts/lib/cells.mjs`, so this loader and the index that already
 *    exists cannot disagree about what a cell is called — a mismatch there does
 *    not error, it just finds nothing.
 *
 * 4. A four-digit number on a TTU collar is not necessarily a printing year.
 *    "Indian Datum 1960", "renseignements cartographiques 1960" and
 *    "information as of 1965" are a datum and two currency-of-information
 *    dates. A greedy `\d{4}` would file three of the 25 sheets under a decade
 *    they were not printed in, and the result would look entirely reasonable.
 *    `printedYear` anchors on the two Vietnamese phrases that do mean printing.
 *
 * Every parser named above is pinned by `tests/ingest-cells.spec.ts`, on bytes
 * copied out of these same four catalogues.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { clean, yearOf, cellNumber, cellOf, sheetPart, printedYear } from '../lib/cells.mjs';
import { serviceClient, upsertChunked, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const apply = willApply();

const L7014 = 'series-l7014-vietnam-1-50-000'; // series_key(), mig 082
const INDOCHINE = 'indochine-1-25-000-tonkin-thanh-hoa';

const PCL = 'work/l7014/sheets.json';
const TTU = 'work/l7014/ttu/EDITIONS.md';
const TTU_DIR = 'work/l7014/ttu';
const ANU = 'work/l7014/anu-sources.json';
const IGN = ['work/tonkin/sources/ign-serie-243.json', 'work/tonkin/sources/ign-serie-175.json'];

const read = (p) => JSON.parse(readFileSync(p, 'utf8'));

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

/**
 * Every TTU sheet actually mirrored, from the directory rather than the notes.
 *
 * `EDITIONS.md` documents 25 sheets whose collars were read by hand. The fetch
 * on 2026-09-14 pulled 108 more and put them in R2, and those have no notes at
 * all — nobody has read their collars. Loading only the markdown recorded 25 of
 * 133 and made the other 108 look like sheets Texas Tech does not hold, which
 * is the opposite of true and the kind of gap that sends someone to re-fetch
 * what is already mirrored.
 *
 * So the directory is the source for *existence* and the markdown for
 * *description*. These rows are deliberately thin: year and edition are null
 * because they are unknown, not because the sheet has none. Emitted BEFORE
 * `ttuRows()` so the 25 hand-read records overwrite their stubs on the shared
 * `(institution, source_ref)` key.
 */
function ttuMirroredRows() {
  return readdirSync(TTU_DIR)
    .filter((f) => f.endsWith('.pdf'))
    .map((f) => f.replace(/\.pdf$/, ''))
    .filter((sheet) => /^\d{4}-\d$/.test(sheet))
    .map((sheet) => ({
      series_key: L7014,
      sheet_number: sheet,
      institution: 'TTU',
      source_ref: `${sheet}.pdf`,
      title: null,
      year: null,
      edition: null,
      part: 'whole',
      url: `https://vva.vietnam.ttu.edu/images.php?img=/maps/PDF/${sheet}.pdf`,
      rights: null,
      note: 'Mirrored 2026-09-14; collar not yet read.',
    }));
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
/** This table's spelling of `sheetPart()`. A demi-format sheet is a half-format
 *  piece of paper carrying the WHOLE of the cell the series covers, which this
 *  column calls 'whole'; `plan_indochine_halfsheet_migration.mjs` needs the two
 *  told apart and keeps the module's own word for it. */
const partOf = (note) => {
  const p = sheetPart(note);
  return p === 'demi-format' ? 'whole' : p;
};

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
  // Merged on the table's own unique key, markdown last so a hand-read collar
  // replaces its stub rather than arriving beside it as a second printing.
  TTU: [...new Map([...ttuMirroredRows(), ...ttuRows()].map((r) => [r.source_ref, r])).values()],
  ANU: anuRows(),
  IGN: ignRows(),
};
const rows = Object.values(sources).flat();

// A duplicate item key would make the upsert lose rows rather than fail, and
// the loss would be invisible in the totals. Caught here instead. NUL separates
// the two halves of the key because either may contain anything printable; it
// is written as an escape now, having been a literal byte in this file, which
// made grep(1) and file(1) treat the whole script as binary data.
const dups = duplicateKeys(rows, (r) => `${r.institution}\0${r.source_ref}`);

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
  for (const d of dups.slice(0, 10)) console.log('  ' + d.replace('\0', ' / '));
}
if (bad.length) {
  console.log(`\nrows with no cell or no item key: ${bad.length}`);
  for (const b of bad.slice(0, 10)) console.log('  ' + JSON.stringify(b));
}

if (!apply) {
  dryNotice();
  process.exit(dups.length || bad.length ? 1 : 0);
}
if (dups.length || bad.length) throw new Error('refusing to write: see the report above');

await upsertChunked(serviceClient(), 'sheet_sources', rows, {
  onConflict: 'institution,source_ref', // 087's item key
});
console.log(`\napplied: ${rows.length} rows`);
