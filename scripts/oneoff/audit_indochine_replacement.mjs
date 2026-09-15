#!/usr/bin/env node
/**
 * audit_indochine_replacement.mjs — is the data right, before anything is swapped?
 *
 *   node --env-file=.env scripts/oneoff/audit_indochine_replacement.mjs
 *   node --env-file=.env scripts/oneoff/audit_indochine_replacement.mjs --refetch
 *
 * READ-ONLY, and must stay that way. `plan_indochine_halfsheet_migration.mjs`
 * answers "what would it cost"; this answers the question that comes first,
 * "is what we believe about these sheets true". It selects from `maps` and
 * `series_sheets`, reads the two catalogue dumps, reads measured pixel sizes,
 * and writes one report. No `--apply`, ever.
 *
 * WHY IT EXISTS: THE PLAN USED AN AVERAGE WHERE IT NEEDED A MEASUREMENT. The
 * migration plan priced every replacement half-sheet at the median of the 16
 * halves we hold — 2710x3879, 10.51 Mpx — and concluded that swapping cells 25
 * and 38 would LOSE pixels. Measured against IGN's own info.json, 212 of 212
 * resolve and they are nowhere near uniform: the median is 10.43 Mpx, but cell
 * 66's halves are 43 Mpx each and cell 38's are 18-19. A flat median understates
 * the big scans by a factor of four, which is exactly the set of cells the
 * "loses pixels" verdict was drawn from. Every figure here is per sheet.
 *
 * WHICH CATALOGUE IS WHICH. CartoMundi holds the Tonkin 1:25,000 three times:
 * serie 243 the original colour half-sheets (1901-1944, dates clustering
 * 1903-1926), serie 175 IGN's later assembled printing (its dates cluster
 * 1936-1944), serie 248 the 1945-53 black edition. Ours are 243 — established
 * by `backfill_indochine_descriptions.mjs`, 60 of 62 matching on cell and year.
 * 175 is the more complete CELL list and supplies names; 243 is the edition we
 * hold and supplies provenance. Confirmed live 2026-09-15: both dumps are
 * byte-current, and serie 175 has 88 catalogue records and ZERO digitised
 * copies — no Nakala id, no IIIF, `f116Telechargement: false` on all 88. There
 * is no file anywhere for an assembled sheet. Only the halves can be fetched.
 *
 * Cell numbering is not a number and the part is not in the title: both come
 * from ../lib/cells.mjs, which is the only copy. See its header for the 79
 * records the drifted copies disagreed on.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { cellNumber, cellOrder, sheetPart, partFromTitle } from '../lib/cells.mjs';
import { serviceClient } from '../lib/db.mjs';

if (process.argv.includes('--apply')) {
  console.error('This audits. It does not change anything. See the header.');
  process.exit(2);
}

const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const SERIES_KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const SOURCES = {
  243: 'work/tonkin/sources/ign-serie-243.json',
  175: 'work/tonkin/sources/ign-serie-175.json',
};
const MEASURED = 'work/tonkin/iiif-measured.json';
const OUT = 'work/tonkin/replacement-audit.json';
const UA = { 'User-Agent': 'vma-audit', Accept: 'application/json' };

const PART_LABEL = {
  W: 'west half',
  E: 'east half',
  'demi-format': 'demi-format sheet (whole cell)',
  assemblage: 'assemblage of the two halves',
  unknown: 'unclassified',
};

const problems = [];
const flag = (kind, msg, extra = {}) => problems.push({ kind, msg, ...extra });

// ── the catalogue ──────────────────────────────────────────────────────────
/** @type {Map<string, any[]>} */
const catalogue = new Map();
for (const [serie, file] of Object.entries(SOURCES)) {
  for (const r of JSON.parse(readFileSync(file, 'utf8'))) {
    const cell = cellNumber(r.f100NumeroOuCode);
    for (const d of r.feuilleEtablissementDocuments ?? []) {
      const part = sheetPart(r.f101Note) ?? 'unknown';
      const fromTitle = partFromTitle(r.f105Titre);
      const rec = {
        serie: Number(serie),
        cell,
        cell_as_catalogued: r.f100NumeroOuCode,
        year: r.f103DateAaaa ?? null,
        part,
        part_from_title: fromTitle,
        part_disputed: Boolean(fromTitle && ['W', 'E'].includes(part) && fromTitle !== part),
        note: r.f101Note ?? null,
        title: r.f105Titre ?? null,
        fkey: r.fkey ?? null,
        dpKey: d.dpKey ?? null,
        doi: d.f110IdNakala ?? null,
        sha1: d.f111Sha1Nakala ?? null,
        file: d.f112Fichier || null,
        iiif: d.f125FluxIiifEtablissement || null,
        digitised: Boolean(d.f110IdNakala && d.f125FluxIiifEtablissement),
      };
      if (rec.part === 'unknown')
        flag(
          'catalogue',
          `cell ${cell} ${rec.year} s${serie}: note classifies as nothing — "${rec.note}"`
        );
      if (rec.part_disputed)
        flag(
          'catalogue',
          `cell ${cell} ${rec.year} s${serie} fkey ${rec.fkey}: note says ${rec.part}, title "${rec.title}" says ${fromTitle}`
        );
      if (!catalogue.has(cell)) catalogue.set(cell, []);
      catalogue.get(cell).push(rec);
    }
  }
}
for (const list of catalogue.values())
  list.sort((a, b) => (a.year ?? 0) - (b.year ?? 0) || a.serie - b.serie);
const allRecords = [...catalogue.values()].flat();

// ── measured pixels: ours and IGN's, both off a live info.json ─────────────
async function measure(url) {
  for (let a = 0; a < 3; a++) {
    try {
      const res = await fetch(url, { headers: UA, signal: AbortSignal.timeout(60000) });
      if (!res.ok) {
        if (res.status >= 500 && a < 2) continue;
        return { ok: false, http: res.status };
      }
      const j = await res.json();
      return { ok: true, w: j.width, h: j.height, mpx: +((j.width * j.height) / 1e6).toFixed(2) };
    } catch (e) {
      if (a === 2) return { ok: false, http: null, error: String(e).slice(0, 120) };
    }
  }
}
async function pool(items, fn, conc = 8) {
  const q = items.slice();
  const out = [];
  await Promise.all(
    Array.from({ length: conc }, async () => {
      for (let it = q.shift(); it !== undefined; it = q.shift()) out.push(await fn(it));
    })
  );
  return out;
}

// ── what the archive holds ─────────────────────────────────────────────────
const db = serviceClient();
const { data: maps, error } = await db
  .from('maps')
  .select(
    'id,name,slug,year,status,source_url,extra_metadata,georef_done,allmaps_id,annotation_url,bbox,rights,holding_institution'
  )
  .eq('collection', COLLECTION);
if (error) throw new Error(error.message);

const isNakala = (m) => /doi\.org\/10\.34847\//.test(m.source_url ?? '');
const mirrored = maps.filter(isNakala);
const composites = maps.filter((m) => !isNakala(m));

let measured;
if (process.argv.includes('--refetch')) {
  console.error(
    `measuring ${allRecords.filter((r) => r.digitised).length} IGN scans and ${maps.length} of ours…`
  );
  const ign = await pool(
    allRecords.filter((r) => r.digitised),
    async (r) => ({ dpKey: r.dpKey, ...(await measure(r.iiif)) })
  );
  const ours = await pool(maps, async (m) => ({
    id: m.id,
    ...(await measure(`https://iiif.maparchive.vn/iiif/${m.id}/info.json`)),
  }));
  measured = { measured_at: new Date().toISOString(), ign, ours };
  writeFileSync(MEASURED, JSON.stringify(measured, null, 1));
} else {
  measured = JSON.parse(readFileSync(MEASURED, 'utf8'));
}
// A measurement counts as good when it carries pixels, not when it carries a
// flag: the cache is written by two paths and only one of them sets `ok`.
const measuredOk = (x) =>
  Boolean(x) && x.ok !== false && Number.isFinite(x.w) && Number.isFinite(x.h);
const ignPx = new Map(measured.ign.map((r) => [r.dpKey, r]));
const ourPx = new Map(measured.ours.map((r) => [r.id, r]));
for (const r of allRecords) {
  if (!r.digitised) continue;
  const px = ignPx.get(r.dpKey);
  if (!px)
    flag(
      'measurement',
      `cell ${r.cell} ${r.year} s${r.serie} dpKey ${r.dpKey}: digitised but never measured — re-run with --refetch`
    );
  else if (!measuredOk(px))
    flag(
      'measurement',
      `cell ${r.cell} ${r.year} s${r.serie} dpKey ${r.dpKey}: IIIF did not resolve (http ${px.http})`
    );
  else Object.assign(r, { w: px.w, h: px.h, mpx: px.mpx });
}

// ── every row we hold: does the catalogue know it? ─────────────────────────
const doiOf = (m) => (m.source_url?.match(/10\.34847\/[^\s/?#]+/) ?? [])[0] ?? null;
const byDoi = new Map(allRecords.filter((r) => r.doi).map((r) => [r.doi, r]));
const heldRows = [];
for (const m of maps) {
  const cell = cellNumber(m.extra_metadata?.sheet_number);
  const px = ourPx.get(m.id);
  const row = {
    map_id: m.id,
    slug: m.slug ?? null,
    name: m.name,
    cell,
    sheet_number_as_stored: m.extra_metadata?.sheet_number ?? null,
    sheet_half: m.extra_metadata?.sheet_half ?? null,
    year: m.year,
    status: m.status,
    kind: isNakala(m) ? 'ign-half-sheet' : 'third-party-composite',
    pixels: measuredOk(px) ? { w: px.w, h: px.h, mpx: px.mpx } : null,
    matched: null,
  };
  if (!cell) flag('our-rows', `${m.name} (${m.id}) has no sheet_number in extra_metadata`);
  if (!measuredOk(px)) flag('our-rows', `${m.name} (${m.id}): our own IIIF did not resolve`);
  if (row.kind === 'ign-half-sheet') {
    const rec = byDoi.get(doiOf(m));
    if (!rec) flag('our-rows', `${m.name}: source_url DOI ${doiOf(m)} is in no catalogue record`);
    else {
      row.matched = { by: 'doi', serie: rec.serie, fkey: rec.fkey, year: rec.year, part: rec.part };
      if (rec.year !== m.year)
        flag('our-rows', `${m.name}: our year ${m.year}, catalogue says ${rec.year}`);
      if (cellNumber(rec.cell) !== cell)
        flag('our-rows', `${m.name}: our cell ${cell}, catalogue says ${rec.cell}`);
      if (measuredOk(px) && rec.mpx && (px.w !== rec.w || px.h !== rec.h))
        flag('our-rows', `${m.name}: we mirrored ${px.w}x${px.h}, IGN serves ${rec.w}x${rec.h}`);
    }
  } else {
    const same = (catalogue.get(cell) ?? []).filter((r) => r.serie === 243 && r.year === m.year);
    row.matched = same.length ? { by: 'cell+year', serie: 243, records: same.length } : null;
    if (!same.length) {
      const anyCell = catalogue.get(cell) ?? [];
      flag(
        'our-rows',
        anyCell.length
          ? `${m.name} (cell ${cell}, ours ${m.year}): serie 243 has no record of that year — it holds ${[...new Set(anyCell.filter((r) => r.serie === 243).map((r) => r.year))].join(', ') || 'nothing for this cell'}`
          : `${m.name} (cell ${cell}): no catalogue record at all, in either serie`
      );
    }
  }
  heldRows.push(row);
}

// ── the replacement, priced per sheet rather than off a median ─────────────
const rows = [];
for (const m of composites) {
  const cell = cellNumber(m.extra_metadata?.sheet_number);
  const records = catalogue.get(cell) ?? [];
  const px = ourPx.get(m.id);
  const ourMpx = measuredOk(px) ? px.mpx : null;

  const s243 = records.filter((r) => r.serie === 243);
  const sameYear = s243.filter(
    (r) => r.year === m.year && ['W', 'E', 'demi-format'].includes(r.part)
  );
  const assemblages = records.filter((r) => r.part === 'assemblage');

  // WHICH HALF A RECORD IS, when the catalogue says two things. `f101Note` and
  // the title's brackets are independent, and on cells 25 and 74 the note is
  // wrong: both 1904 records of each are noted "Demi-feuille Ouest" while the
  // titles read `Quang [-Yên]` (west) and `[Quang] -Yên` (east). The brackets
  // are the typography of the printed sheet — they mark the half of the title
  // this piece of paper does NOT carry — so where the two disagree the title
  // wins here. cells.mjs deliberately refuses to resolve this and reports it
  // instead; this is the call site that decides, and it says so in the row.
  const resolvedPart = (r) => (r.part_disputed && r.part_from_title ? r.part_from_title : r.part);

  // One sheet per part. Where a part is catalogued twice in the same year, take
  // the larger scan — they are two copies of one piece of paper, not two parts.
  // Keyed on the note alone this silently dropped a half whenever the note was
  // the wrong one of the pair, and reported the cell as a clean swap.
  const byPart = new Map();
  for (const r of sameYear) {
    const k = resolvedPart(r);
    const cur = byPart.get(k);
    if (!cur || (r.mpx ?? 0) > (cur.mpx ?? 0)) byPart.set(k, r);
  }
  const picked = [...byPart.values()];
  // A collapse is the shape of the bug above: more records of this year than
  // distinct parts means two of them claim the same half, and one is wrong.
  const collapsed = sameYear.length - picked.length;
  const wantsPair = !byPart.has('demi-format');
  const complete = wantsPair ? byPart.has('W') && byPart.has('E') : true;
  const newMpx = picked.reduce((n, r) => n + (r.mpx ?? 0), 0);

  const issues = [];
  const notesOut = [];
  if (!picked.length) issues.push(`serie 243 has nothing of ${m.year} for cell ${cell}`);
  else if (!complete)
    issues.push(
      `incomplete: ${picked.map((r) => PART_LABEL[r.part]).join(' + ')} only — a whole cell needs west + east`
    );
  if (picked.some((r) => !r.digitised))
    issues.push(
      `${picked.filter((r) => !r.digitised).length} of the replacement sheets is catalogued but not digitised`
    );
  // A disputed record that still lands in a coherent west+east pair is not an
  // open question: two notes saying "Ouest" and two titles saying one of each
  // resolve one way only, and the pair being complete is the corroboration.
  // It stays on the row as a note, because a catalogue we corrected is worth
  // saying out loud. A dispute that leaves the cell ambiguous is an issue.
  const disputed = picked.filter((r) => r.part_disputed);
  if (disputed.length && complete)
    notesOut.push(
      `the catalogue calls ${disputed.length + collapsed} of the ${sameYear.length} sheets of ${m.year} the wrong half — its notes read ${sameYear.map((r) => PART_LABEL[r.part]).join(' + ')}, while the title brackets read ${picked.map((r) => PART_LABEL[resolvedPart(r)]).join(' + ')}. Read off the titles they make a complete pair, which is what this row assumes.`
    );
  else if (disputed.length)
    issues.push(
      `the catalogue contradicts itself on which half ${disputed.length} of these is, and the result is not a complete pair`
    );
  if (collapsed > 0 && !picked.some((r) => r.part_disputed))
    issues.push(
      `${sameYear.length} sheets catalogued for ${m.year} collapse to ${picked.length} part(s) — two records claim the same half and nothing distinguishes them`
    );
  if (ourMpx && newMpx && newMpx < ourMpx)
    issues.push(`fewer pixels after: ${ourMpx} Mpx now against ${newMpx.toFixed(2)} Mpx`);
  // IGN catalogues its own assemblages (serie 175) and the migration plan
  // treated a same-year one as "this row may be that sheet, a human must
  // decide". It is decidable, and the answer is no: serie 175 has 88 catalogue
  // records and zero digitised copies, so an assembled sheet exists on paper in
  // Saint-Mandé and nowhere a file could have been downloaded from. A same-year
  // assemblage is worth recording — it is the sheet ours imitates — but it is
  // not a reason to hold the swap. Only a DIGITISED one would be.
  const sameYearAssemblage = assemblages.filter((r) => r.year === m.year);
  const fetchableAssemblage = sameYearAssemblage.filter((r) => r.digitised);
  if (fetchableAssemblage.length)
    issues.push(
      `IGN's own assemblage of this cell dated ${m.year} IS digitised (${fetchableAssemblage[0].doi}) — this row may be that sheet, and that sheet is fetchable`
    );

  rows.push({
    map_id: m.id,
    slug: m.slug ?? null,
    cell,
    name: m.name,
    our_year: m.year,
    status: m.status,
    ours: measuredOk(px) ? { w: px.w, h: px.h, mpx: ourMpx } : null,
    replacement: {
      complete,
      sheets: picked
        .sort((a, b) => String(a.part).localeCompare(String(b.part)))
        .map((r) => ({
          part: resolvedPart(r),
          part_label: PART_LABEL[resolvedPart(r)],
          part_per_note: r.part,
          note: r.note,
          year: r.year,
          title: r.title,
          fkey: r.fkey,
          dpKey: r.dpKey,
          doi: r.doi,
          iiif: r.iiif,
          w: r.w ?? null,
          h: r.h ?? null,
          mpx: r.mpx ?? null,
          digitised: r.digitised,
          part_disputed: r.part_disputed,
        })),
      mpx_now: ourMpx,
      mpx_after: picked.length ? +newMpx.toFixed(2) : null,
      gain_pct: ourMpx && newMpx ? +(((newMpx - ourMpx) / ourMpx) * 100).toFixed(0) : null,
    },
    notes: [
      ...notesOut,
      ...(sameYearAssemblage.length
        ? [
            `IGN catalogues its own assemblage of cell ${cell} dated ${m.year} (serie ${sameYearAssemblage[0].serie}, fkey ${sameYearAssemblage[0].fkey}) — the sheet this composite imitates. Not digitised, so it cannot be the source of our file and cannot be fetched.`,
          ]
        : []),
    ],
    issues,
    clean: issues.length === 0,
  });
}
rows.sort((a, b) => {
  if (a.clean !== b.clean) return a.clean ? 1 : -1;
  const [an, as] = cellOrder(a.cell);
  const [bn, bs] = cellOrder(b.cell);
  return an - bn || as.localeCompare(bs);
});

// ── cells the catalogue has and we do not ──────────────────────────────────
const heldCells = new Set(
  maps.map((m) => cellNumber(m.extra_metadata?.sheet_number)).filter(Boolean)
);
const catalogueCells = [...catalogue.keys()];
const missingCells = catalogueCells
  .filter((c) => !heldCells.has(c))
  .sort((a, b) => cellOrder(a)[0] - cellOrder(b)[0]);

const digitised243 = allRecords.filter((r) => r.serie === 243 && r.digitised);
const totals = {
  rows_in_collection: maps.length,
  ign_half_sheets_held: mirrored.length,
  third_party_composites: composites.length,
  catalogue_cells: catalogueCells.length,
  cells_we_hold: heldCells.size,
  cells_not_held: missingCells.length,
  serie_243_records: allRecords.filter((r) => r.serie === 243).length,
  serie_243_digitised: digitised243.length,
  serie_175_records: allRecords.filter((r) => r.serie === 175).length,
  serie_175_digitised: allRecords.filter((r) => r.serie === 175 && r.digitised).length,
  composites_clean_swap: rows.filter((r) => r.clean).length,
  composites_with_issues: rows.filter((r) => !r.clean).length,
  composites_imitating_a_real_ign_assemblage: rows.filter((r) => r.notes?.length).length,
  replacement_sheets: rows.reduce((n, r) => n + r.replacement.sheets.length, 0),
  mpx_now: +rows.reduce((n, r) => n + (r.replacement.mpx_now ?? 0), 0).toFixed(1),
  mpx_after: +rows.reduce((n, r) => n + (r.replacement.mpx_after ?? 0), 0).toFixed(1),
  data_problems: problems.length,
};
totals.mpx_gain_pct = +(((totals.mpx_after - totals.mpx_now) / totals.mpx_now) * 100).toFixed(0);

writeFileSync(
  OUT,
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      collection: COLLECTION,
      series_key: SERIES_KEY,
      measured_at: measured.measured_at,
      note: "Read-only audit. Every pixel figure is that sheet's own info.json, not a median.",
      totals,
      problems,
      composites: rows,
      held_rows: heldRows,
      cells_not_held: missingCells,
    },
    null,
    1
  )
);

// ── console ────────────────────────────────────────────────────────────────
const p = (n, w) => String(n).padStart(w);
const q = (s, w) => String(s ?? '').padEnd(w);
console.log(`\nIndochine 1:25,000 — is the data right? (audit, changes nothing)`);
console.log('─'.repeat(78));
console.log(
  `  ${totals.rows_in_collection} rows: ${totals.ign_half_sheets_held} IGN half-sheets, ${totals.third_party_composites} third-party composites`
);
console.log(
  `  serie 243 (the 1903x original halves): ${totals.serie_243_records} copies, ${totals.serie_243_digitised} digitised`
);
console.log(
  `  serie 175 (IGN's assembled printing):  ${totals.serie_175_records} copies, ${totals.serie_175_digitised} digitised`
);
console.log(
  `  catalogue covers ${totals.catalogue_cells} cells; we hold ${totals.cells_we_hold}; ${totals.cells_not_held} not held`
);

console.log(`\nswapping the ${totals.third_party_composites} composites for serie 243 originals`);
console.log(`  ${p(totals.composites_clean_swap, 3)} swap cleanly`);
console.log(`  ${p(totals.composites_with_issues, 3)} need a decision`);
console.log(`  ${p(totals.replacement_sheets, 3)} original sheets to fetch`);
console.log(
  `  ${totals.mpx_now} Mpx now → ${totals.mpx_after} Mpx after  (${totals.mpx_gain_pct > 0 ? '+' : ''}${totals.mpx_gain_pct}%)`
);

const bad = rows.filter((r) => !r.clean);
if (bad.length) {
  console.log(`\ncomposites needing a decision (${bad.length})`);
  for (const r of bad) {
    console.log(
      `\n  cell ${q(r.cell, 7)} ${q(r.name, 20)} ${r.our_year}  ${r.ours ? `${r.ours.w}x${r.ours.h} ${r.ours.mpx}Mpx` : 'unmeasured'}`
    );
    for (const i of r.issues) console.log(`    ! ${i}`);
    for (const n of r.notes ?? []) console.log(`    · ${n}`);
    for (const s of r.replacement.sheets)
      console.log(
        `      ${q(s.part_label, 32)} ${s.year}  ${q(s.w && `${s.w}x${s.h} ${s.mpx}Mpx`, 22)} ${s.digitised ? s.doi : 'NOT DIGITISED'}`
      );
  }
}

if (problems.length) {
  console.log(`\ndata problems (${problems.length})`);
  const byKind = {};
  for (const x of problems) (byKind[x.kind] ??= []).push(x);
  for (const [k, list] of Object.entries(byKind)) {
    console.log(`\n  ${k} (${list.length})`);
    for (const x of list) console.log(`    - ${x.msg}`);
  }
} else {
  console.log(`\nno data problems found`);
}
console.log(`\nwrote ${OUT}\n`);
