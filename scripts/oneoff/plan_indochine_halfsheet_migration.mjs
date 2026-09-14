#!/usr/bin/env node
/**
 * plan_indochine_halfsheet_migration.mjs — what it would cost, and what it
 * would buy, to replace the stitched Indochine composites with IGN's halves.
 *
 *   node --env-file=.env scripts/oneoff/plan_indochine_halfsheet_migration.mjs
 *
 * READ-ONLY. It selects from `maps`, `ocr_extractions` and `series_sheets`,
 * reads three files off disk, and writes one report. It has no `--apply` and
 * must never grow one: the decision it informs — halves or assemblage — has
 * not been taken, and a script that can execute a decision nobody has made is
 * worse than no script. It also fetches no scan; every pixel figure below is
 * re-derived from `work/tonkin/shape-audit.json`, which is the measurement.
 *
 * WHAT THE COLLECTION ACTUALLY HOLDS. 84 rows, and they came from two places.
 * 22 were fetched from Nakala this week by `ingest_indochine_nakala.mjs` and
 * carry a `doi.org/10.34847/...` source_url: those are IGN's own half-sheets,
 * portrait, ~0.70 aspect. The other 62 pre-date that ingest, carry only the
 * series-level CartoMundi URL, and are landscape at ~1.33 — one printed cell
 * wide, which the paper never was. They are composites somebody assembled from
 * the two halves and downscaled in the joining.
 *
 * HOW A COMPOSITE IS TOLD FROM AN ASSEMBLAGE. IGN itself issued assemblages:
 * CartoMundi serie 175 is that edition, 88 records against serie 243's 216
 * half-sheets, and `f101Note` says which a record is. So a landscape row is not
 * by itself evidence of a home-made join — the question per cell is whether
 * IGN's assemblage of OUR year exists. Where it does not, but halves of our
 * year do, the composite was made from those halves.
 *
 * CELL NUMBERING IS NOT A NUMBER. `0 bis`, `5 bis`, `10 bis`, `73 bis` are real
 * cells. Worse, `f100NumeroOuCode` uses the same bracket convention as the
 * titles: a half-sheet that does not print the cell number is catalogued as
 * `[59]`, and serie 175 spaces `0 bis` where serie 243 writes `0bis`. Match on
 * `cellKey()` below, never on `parseFloat`.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync, writeFileSync } from 'node:fs';

const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const SERIES_KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const IGN_SOURCES = [
  'work/tonkin/sources/ign-serie-243.json',
  'work/tonkin/sources/ign-serie-175.json',
];
const SHAPES = 'work/tonkin/shape-audit.json';
const OUT = 'work/tonkin/halfsheet-migration-plan.json';

if (process.argv.includes('--apply')) {
  console.error('This script plans. It does not apply. See the header.');
  process.exit(2);
}

/** One spelling for a cell, across both series and both bracket conventions. */
function cellKey(raw) {
  return String(raw ?? '')
    .replace(/[[\]]/g, '')
    .toLowerCase()
    .replace(/(\d)\s*bis/g, '$1 bis')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Sort cells the way a sheet index does: numerically, `bis` after its number. */
function cellOrder(key) {
  const m = /^(\d+)(\s*bis)?$/.exec(key);
  if (!m) return [Number.POSITIVE_INFINITY, key];
  return [Number(m[1]) + (m[2] ? 0.5 : 0), key];
}

/**
 * Which part of the cell an IGN record is, off its note.
 *
 * `assemblage` first, because an assemblage note never mentions demi-feuille
 * but a demi-feuille note sometimes discusses the other half — 73 bis 1927
 * reads "Demi-feuille Est. La partie … demi-feuille Ouest", and an unanchored
 * search calls the east half west. Hence the `^` on the demi-feuille test,
 * matching `ingest_indochine_nakala.mjs`.
 */
function part(note) {
  const n = String(note ?? '').replace(/^"+/, '');
  if (/assemblage/i.test(n)) return 'assemblage';
  if (/demi-format/i.test(n)) return 'demi-format';
  const m = /^\s*demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return 'unknown';
}

/**
 * The same fact read off the title's brackets, as `ingest_indochine_nakala.mjs`
 * reads it: brackets mark the half of the title this sheet does not print, so
 * `[Quang] -Yên` is the east half and `Quang [-Yên]` the west. It is an
 * independent check on the note, and the notes are not all right — see the
 * `part_disputed` warning. Not a correction: a disagreement is reported, never
 * resolved, because which of the two is wrong is a judgement about the paper.
 */
function partFromTitle(title) {
  const t = String(title ?? '');
  const i = t.indexOf('[');
  if (i < 0) return null;
  return t.slice(0, i).replace(/[\s-]/g, '') ? 'W' : 'E';
}

const PART_LABEL = {
  W: 'west half',
  E: 'east half',
  'demi-format': 'demi-format sheet (whole cell)',
  assemblage: 'assemblage of the two halves',
  unknown: 'unclassified',
};

const warnings = [];

// ── IGN's catalogue: every copy record, keyed by cell ──────────────────────
const ign = new Map();
for (const file of IGN_SOURCES) {
  for (const r of JSON.parse(readFileSync(file, 'utf8'))) {
    const key = cellKey(r.f100NumeroOuCode);
    const docs = r.feuilleEtablissementDocuments ?? [];
    // One sheet record, one or more held copies. The DOI hangs off the copy.
    const doc = docs.find((d) => d.f110IdNakala) ?? docs[0] ?? {};
    const rec = {
      cell: key,
      cell_as_catalogued: r.f100NumeroOuCode,
      serie: r.serieId,
      year: r.f103DateAaaa ?? null,
      part: part(r.f101Note),
      note: r.f101Note ?? null,
      title: r.f105Titre ?? null,
      fkey: r.fkey ?? null,
      copies: docs.length,
      nakala_doi: doc.f110IdNakala ?? null,
      nakala_sha1: doc.f111Sha1Nakala ?? null,
      iiif: doc.f125FluxIiifEtablissement || null,
    };
    const fromTitle = partFromTitle(rec.title);
    rec.part_from_title = fromTitle;
    rec.part_disputed = Boolean(
      fromTitle && ['W', 'E'].includes(rec.part) && fromTitle !== rec.part
    );
    if (rec.part === 'unknown') warnings.push(`unclassified IGN note, cell ${key}: ${rec.note}`);
    if (rec.part_disputed)
      warnings.push(
        `cell ${key} ${rec.year} (s${rec.serie} fkey ${rec.fkey}): note says ${rec.part}, ` +
          `title "${rec.title}" says ${fromTitle} — ingest_indochine_nakala.mjs throws on this`
      );
    if (!ign.has(key)) ign.set(key, []);
    ign.get(key).push(rec);
  }
}
for (const list of ign.values()) list.sort((a, b) => (a.year ?? 0) - (b.year ?? 0));

// ── what we measured off the pixels ────────────────────────────────────────
const shapes = new Map(JSON.parse(readFileSync(SHAPES, 'utf8')).map((s) => [s.id, s]));

// ── what the archive holds ─────────────────────────────────────────────────
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data: maps, error } = await db
  .from('maps')
  .select(
    'id,name,year,status,source_url,extra_metadata,georef_done,allmaps_id,annotation_url,triage,bbox'
  )
  .eq('collection', COLLECTION);
if (error) throw new Error(error.message);

const mapIds = maps.map((m) => m.id);
const { data: ocr, error: ocrErr } = await db
  .from('ocr_extractions')
  .select('map_id')
  .in('map_id', mapIds);
if (ocrErr) throw new Error(ocrErr.message);
const ocrCount = new Map();
for (const r of ocr) ocrCount.set(r.map_id, (ocrCount.get(r.map_id) ?? 0) + 1);

const { data: sheets, error: shErr } = await db
  .from('series_sheets')
  .select('sheet_number,held_by,map_id')
  .eq('series_key', SERIES_KEY);
if (shErr) throw new Error(shErr.message);
const sheetPointer = new Map(sheets.filter((s) => s.map_id).map((s) => [s.map_id, s.sheet_number]));

// A row is a mirrored IGN half if the ingest gave it a Nakala DOI. Everything
// else in this collection predates that ingest.
const isNakala = (m) => /doi\.org\/10\.34847\//.test(m.source_url ?? '');
const mirrored = maps.filter(isNakala);
const stitched = maps.filter((m) => !isNakala(m));

// Re-derive the half-sheet page size from the halves we actually hold, rather
// than trusting a remembered "~2720x3870". Demi-format sheets cover a whole
// cell and are excluded from the per-half figure.
const heldHalves = mirrored.filter((m) => ['W', 'E'].includes(m.extra_metadata?.sheet_half));
const median = (xs) => xs.slice().sort((a, b) => a - b)[Math.floor(xs.length / 2)];
const halfShapes = heldHalves.map((m) => shapes.get(m.id)).filter(Boolean);
if (halfShapes.length !== heldHalves.length)
  warnings.push(`${heldHalves.length - halfShapes.length} mirrored halves missing from ${SHAPES}`);
const HALF = {
  n: halfShapes.length,
  w: median(halfShapes.map((s) => s.w)),
  h: median(halfShapes.map((s) => s.h)),
};
HALF.mpx = +((HALF.w * HALF.h) / 1e6).toFixed(2);

// Halves already mirrored, so a migration would not fetch them twice.
const heldByCellPart = new Set(
  mirrored.map((m) => `${cellKey(m.extra_metadata?.sheet_number)}|${m.extra_metadata?.sheet_half}`)
);

// Cells carrying more than one composite — different printings of one cell, so
// the replacement sets differ by year and must not be planned as one.
const stitchedPerCell = new Map();
for (const m of stitched) {
  const k = cellKey(m.extra_metadata?.sheet_number);
  stitchedPerCell.set(k, (stitchedPerCell.get(k) ?? 0) + 1);
}

// ── the verdict, per composite ─────────────────────────────────────────────
const rows = [];
for (const m of stitched) {
  const cell = cellKey(m.extra_metadata?.sheet_number);
  const records = ign.get(cell) ?? [];
  if (!records.length) warnings.push(`no IGN record for cell "${cell}" (${m.name})`);
  const shape = shapes.get(m.id);
  if (!shape) warnings.push(`no measured shape for ${m.id} (${m.name})`);

  const assemblages = records.filter((r) => r.part === 'assemblage');
  const halves = records.filter((r) => ['W', 'E', 'demi-format'].includes(r.part));
  const sameYearAssemblage = assemblages.filter((r) => r.year === m.year);
  const sameYearHalves = halves.filter((r) => r.year === m.year);

  let verdict, evidence;
  if (sameYearAssemblage.length) {
    verdict = 'possibly-ign-assemblage';
    evidence =
      `IGN catalogues an assemblage of cell ${cell} dated ${m.year}, the same year this row ` +
      `claims (serie ${sameYearAssemblage[0].serie}, fkey ${sameYearAssemblage[0].fkey}). ` +
      `A human must decide whether this scan is that sheet.`;
  } else if (sameYearHalves.length) {
    verdict = 'home-made';
    evidence =
      `No IGN assemblage of cell ${cell} is dated ${m.year}` +
      (assemblages.length
        ? ` (IGN's assemblages of this cell: ${assemblages.map((r) => r.year).join(', ')})`
        : ' (IGN catalogues no assemblage of this cell at all)') +
      `, but ${sameYearHalves.length} half-sheet(s) of ${m.year} do exist ` +
      `(${sameYearHalves.map((r) => PART_LABEL[r.part]).join(', ')}). The composite was made from those.`;
  } else {
    verdict = 'unclear';
    evidence =
      `Nothing IGN holds for cell ${cell} is dated ${m.year}. ` +
      `Assemblage years: ${assemblages.map((r) => r.year).join(', ') || 'none'}. ` +
      `Half-sheet years: ${halves.map((r) => r.year).join(', ') || 'none'}.`;
  }

  // What a replacement would fetch: the halves of our year, one per part, the
  // most recent printing where a part is catalogued twice in the same year.
  const byPart = new Map();
  for (const r of sameYearHalves) {
    const cur = byPart.get(r.part);
    if (!cur || (r.year ?? 0) > (cur.year ?? 0)) byPart.set(r.part, r);
  }
  const replacement = [...byPart.values()].map((r) => ({
    part: r.part,
    part_label: PART_LABEL[r.part],
    year: r.year,
    title: r.title,
    fkey: r.fkey,
    nakala_doi: r.nakala_doi,
    iiif: r.iiif,
    digitised: Boolean(r.nakala_doi),
    part_disputed: r.part_disputed,
    already_mirrored: heldByCellPart.has(`${cell}|${r.part === 'demi-format' ? 'whole' : r.part}`),
  }));

  const compositeMpx = shape ? +((shape.w * shape.h) / 1e6).toFixed(2) : null;
  const replacementMpx = +(replacement.length * HALF.mpx).toFixed(2);
  const toIngest = replacement.filter((r) => r.digitised && !r.already_mirrored);

  // A landscape composite covers a whole cell, so anything short of a
  // demi-format sheet or both halves replaces it with less ground. Two
  // catalogue records of the same year and the same part are one part, not two
  // — cell 25 has exactly that, and the titles say one of the notes is wrong.
  const wantsPair = !byPart.has('demi-format');
  const incomplete = wantsPair ? replacement.length < 2 : replacement.length < 1;
  const disputed = sameYearHalves.filter((r) => r.part_disputed).length;
  const problems = [
    incomplete
      ? `replacement is incomplete: ${replacement.length} sheet(s) of ${m.year} for a cell that needs ${wantsPair ? 2 : 1}` +
        (disputed
          ? ` — ${disputed} IGN record(s) of this year contradict themselves on which half they are`
          : '')
      : null,
    // "The composite was downscaled in the joining" is true of most of them and
    // not of all: a composite already larger than two IGN halves would LOSE
    // pixels in the swap, which inverts the whole argument for that row.
    compositeMpx && replacementMpx && replacementMpx < compositeMpx
      ? `replacing loses pixels: ${compositeMpx} Mpx now against ${replacementMpx} Mpx after — this composite was not downscaled`
      : null,
    replacement.some((r) => !r.digitised)
      ? `${replacement.filter((r) => !r.digitised).length} of the replacement sheets is catalogued but not digitised`
      : null,
  ].filter(Boolean);

  rows.push({
    map_id: m.id,
    cell,
    sheet_number_as_stored: m.extra_metadata?.sheet_number ?? null,
    name: m.name,
    our_year: m.year,
    status: m.status,
    pixels: shape ? { w: shape.w, h: shape.h, ratio: shape.r, mpx: compositeMpx } : null,
    verdict,
    evidence,
    problems,
    needs_decision: verdict !== 'home-made' || problems.length > 0,
    cell_has_multiple_composites: (stitchedPerCell.get(cell) ?? 0) > 1,
    ign_records: records.map((r) => ({
      serie: r.serie,
      year: r.year,
      part: r.part,
      part_label: PART_LABEL[r.part],
      title: r.title,
      note: r.note,
      fkey: r.fkey,
      nakala_doi: r.nakala_doi,
      digitised: Boolean(r.nakala_doi),
      part_from_title: r.part_from_title,
      part_disputed: r.part_disputed,
    })),
    replacement: {
      sheets: replacement,
      sheets_to_ingest: toIngest.length,
      sheets_not_digitised: replacement.filter((r) => !r.digitised).length,
      sheets_already_mirrored: replacement.filter((r) => r.already_mirrored).length,
      mpx_now: compositeMpx,
      mpx_after: replacementMpx || null,
      mpx_gain: compositeMpx && replacementMpx ? +(replacementMpx - compositeMpx).toFixed(2) : null,
      gain_pct:
        compositeMpx && replacementMpx
          ? +(((replacementMpx - compositeMpx) / compositeMpx) * 100).toFixed(0)
          : null,
    },
    downstream: {
      georeferenced: Boolean(m.georef_done),
      allmaps_id: m.allmaps_id,
      annotation_url: m.annotation_url,
      bbox: Boolean(m.bbox),
      triage_regions: Array.isArray(m.triage?.regions) ? m.triage.regions.length : 0,
      ocr_labels: ocrCount.get(m.id) ?? 0,
      series_sheet_pointer: sheetPointer.get(m.id) ?? null,
      // The georeference is per-image: two halves are two new images, so the
      // GCPs, the Allmaps annotation and the triage boxes are all pixel
      // coordinates that do not survive. Only OCR costs a model run to redo.
      lost_on_replacement: [
        m.allmaps_id ? 'georeference (GCPs + Allmaps annotation)' : null,
        m.annotation_url ? 'mirrored annotation JSON' : null,
        Array.isArray(m.triage?.regions) && m.triage.regions.length ? 'triage regions' : null,
        ocrCount.get(m.id) ? `${ocrCount.get(m.id)} OCR labels — RE-EXTRACTION COST` : null,
        sheetPointer.get(m.id) ? `series_sheets.map_id for cell ${sheetPointer.get(m.id)}` : null,
      ].filter(Boolean),
    },
  });
}

// Rows a human must decide about individually come first, the way
// fix_l7014_editions.mjs puts the most-different names at the top of its CSV.
const RANK = { 'possibly-ign-assemblage': 0, unclear: 1, 'home-made': 2 };
const rank = (r) => RANK[r.verdict] + (r.verdict === 'home-made' && r.problems.length ? -0.5 : 0);
rows.sort((a, b) => {
  if (rank(a) !== rank(b)) return rank(a) - rank(b);
  const g = (b.replacement.mpx_gain ?? -1e9) - (a.replacement.mpx_gain ?? -1e9);
  if (g) return g;
  const [an, as] = cellOrder(a.cell);
  const [bn, bs] = cellOrder(b.cell);
  return an - bn || as.localeCompare(bs);
});

const byVerdict = rows.reduce((a, r) => ((a[r.verdict] = (a[r.verdict] ?? 0) + 1), a), {});
const totals = {
  maps_rows: maps.length,
  mirrored_half_sheets: mirrored.length,
  composites: stitched.length,
  distinct_composite_cells: new Set(rows.map((r) => r.cell)).size,
  sheets_to_ingest: rows.reduce((n, r) => n + r.replacement.sheets_to_ingest, 0),
  sheets_not_digitised: rows.reduce((n, r) => n + r.replacement.sheets_not_digitised, 0),
  sheets_already_mirrored: rows.reduce((n, r) => n + r.replacement.sheets_already_mirrored, 0),
  mpx_now: +rows.reduce((n, r) => n + (r.replacement.mpx_now ?? 0), 0).toFixed(1),
  mpx_after: +rows.reduce((n, r) => n + (r.replacement.mpx_after ?? 0), 0).toFixed(1),
  georeferences_lost: rows.filter((r) => r.downstream.allmaps_id).length,
  annotations_lost: rows.filter((r) => r.downstream.annotation_url).length,
  triage_lost: rows.filter((r) => r.downstream.triage_regions).length,
  ocr_rows_affected: rows.filter((r) => r.downstream.ocr_labels).length,
  ocr_labels_lost: rows.reduce((n, r) => n + r.downstream.ocr_labels, 0),
  series_sheet_pointers_to_repoint: rows.filter((r) => r.downstream.series_sheet_pointer).length,
  needing_a_decision: rows.filter((r) => r.needs_decision).length,
  replacement_incomplete: rows.filter((r) => r.problems.some((p) => p.startsWith('replacement is')))
    .length,
  replacement_loses_pixels: rows.filter((r) => r.problems.some((p) => p.startsWith('replacing')))
    .length,
};
totals.mpx_gain_pct = +(((totals.mpx_after - totals.mpx_now) / totals.mpx_now) * 100).toFixed(0);

// ── console ───────────────────────────────────────────────────────────────
const p = (n, w) => String(n).padStart(w);
const q = (s, w) => String(s ?? '').padEnd(w);

console.log(
  `\nIndochine 1:25,000 — replacing composites with IGN half-sheets: a plan, not a change`
);
console.log(`${'─'.repeat(78)}`);
console.log(`  ${totals.maps_rows} rows in the collection`);
console.log(`  ${totals.mirrored_half_sheets} mirrored from Nakala (carry a doi.org source_url)`);
console.log(
  `  ${totals.composites} composites over ${totals.distinct_composite_cells} cells (no item-level source)`
);
console.log(
  `  half-sheet page size, median of the ${HALF.n} halves we hold: ${HALF.w}×${HALF.h} = ${HALF.mpx} Mpx`
);

console.log(`\nverdicts`);
for (const [v, n] of Object.entries(byVerdict).sort((a, b) => RANK[a[0]] - RANK[b[0]])) {
  console.log(`  ${p(n, 3)}  ${v}`);
}

const decide = rows.filter((r) => r.needs_decision);
if (decide.length) {
  console.log(`\nrows a human must decide about individually (${decide.length})`);
  for (const r of decide) {
    console.log(
      `\n  cell ${q(r.cell, 7)} ${q(r.name, 22)} ${r.our_year}  ${r.pixels?.w}×${r.pixels?.h}  [${r.verdict}]`
    );
    console.log(`    ${r.evidence}`);
    for (const x of r.problems) console.log(`    ! ${x}`);
    for (const g of r.ign_records) {
      console.log(
        `      s${g.serie} ${p(g.year, 4)}  ${q(g.part_label, 30)} ${
          g.digitised ? g.nakala_doi : 'not digitised'
        }${g.part_disputed ? `  << title "${g.title}" says ${g.part_from_title}` : ''}`
      );
    }
  }
}

const clean = rows.filter((r) => !r.needs_decision);
console.log(`\nstraightforward home-made composites (${clean.length}), by resolution gained`);
console.log(`  ${q('cell', 7)} ${q('name', 22)} year  now      after    gain   fetch  downstream`);
for (const r of clean) {
  console.log(
    `  ${q(r.cell, 7)} ${q(r.name, 22)} ${r.our_year}  ${p(r.pixels?.mpx ?? '?', 5)} Mpx ${p(
      r.replacement.mpx_after ?? '?',
      5
    )} Mpx ${p((r.replacement.gain_pct ?? 0) + '%', 5)}  ${p(r.replacement.sheets_to_ingest, 5)}  ${
      r.downstream.lost_on_replacement.length
    } thing(s)${r.downstream.ocr_labels ? '  ← OCR' : ''}`
  );
}

console.log(`\ncost and yield of a full migration`);
console.log(`  rows needing an individual decision  ${totals.needing_a_decision}`);
console.log(`  IGN sheets to fetch and mirror       ${totals.sheets_to_ingest}`);
console.log(`  of those, already mirrored           ${totals.sheets_already_mirrored}`);
console.log(`  catalogued but not digitised         ${totals.sheets_not_digitised}`);
console.log(
  `  pixels                               ${totals.mpx_now} Mpx → ${totals.mpx_after} Mpx (+${totals.mpx_gain_pct}%)`
);
console.log(`\nwhat replacing them would discard`);
console.log(`  georeferences (GCPs + Allmaps)       ${totals.georeferences_lost}`);
console.log(`  mirrored annotations                 ${totals.annotations_lost}`);
console.log(`  triage region sets                   ${totals.triage_lost}`);
console.log(`  series_sheets pointers to repoint    ${totals.series_sheet_pointers_to_repoint}`);
console.log(
  `  OCR                                  ${totals.ocr_labels_lost} labels on ${totals.ocr_rows_affected} row(s)` +
    (totals.ocr_rows_affected
      ? ` — ${rows
          .filter((r) => r.downstream.ocr_labels)
          .map((r) => `cell ${r.cell} ${r.name}`)
          .join(', ')}`
      : '')
);

if (warnings.length) {
  console.log(`\nwarnings (${warnings.length})`);
  for (const w of [...new Set(warnings)]) console.log(`  ${w}`);
}

writeFileSync(
  OUT,
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      collection: COLLECTION,
      series_key: SERIES_KEY,
      note: 'Read-only plan. No migration has been decided; nothing here has been applied.',
      sources: { ign: IGN_SOURCES, shapes: SHAPES },
      measured_half_sheet: HALF,
      totals,
      by_verdict: byVerdict,
      warnings: [...new Set(warnings)],
      rows,
    },
    null,
    2
  ) + '\n'
);
console.log(`\nwritten to ${OUT} (${rows.length} rows, decisions first)`);
console.log('Nothing was written to the database.');
