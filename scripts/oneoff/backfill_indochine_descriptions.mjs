#!/usr/bin/env node
// Give the Indochine 1:25,000 sheets a description and their printed diacritics.
//
//   node --env-file=.env scripts/oneoff/backfill_indochine_descriptions.mjs --dry
//   node --env-file=.env scripts/oneoff/backfill_indochine_descriptions.mjs
//
// Measured 2026-09-13: 0 of 62 rows carried `dc_description` and 0 carried
// `source_url`. This fills both — the second only after establishing which of
// CartoMundi's three Tonkin 1:25,000 series these sheets actually are.
//
// **Which series these are — checked, because the first answer was wrong.**
// CartoMundi catalogues the Tonkin 1:25,000 survey THREE times: serie 175
// (sheets assembled from two halves, 1901-1944), serie 243 (the original
// half-sheets in colour, same span) and serie 248 (half-sheets in black,
// 1945-53). Compared against 175 our rows looked unrelated — 8 of 62 matching
// on sheet number and year, ours clustering 1903-1926 against its 1936-1944 —
// which reads exactly like a wrong provenance. It was a wrong *series*.
// Against **243** the match is 60 of 62. Sheet 20 Hà Nội is ours 1903, 243 has
// 1903, 175 has 1943; the same shape holds all the way down. 175 catalogues
// IGN's later printings of the same cells.
//
// So the `holding_institution` already on these rows is right, and `source_url`
// can be filled. Two rows still do not match and are left without one:
//   35 "An Thi" — ours 1904, 243 holds 1905 and 1924. Off by one year.
//   0 bis "Nha nam" — absent from 243 altogether; 175 has it, so the gap is in
//                     CartoMundi's half-sheet catalogue, not in ours.
//
// `series_sheets` stays seeded from 175: both catalogue the same survey and 175
// is the more complete cell list (76 against 243's 75, the difference being
// 0 bis). The denominator is unaffected by any of this.
//
// The URL is the series page, not a per-sheet one. CartoMundi's site is an
// Angular SPA that serves the same 1969-byte shell for every path, so a deep
// link cannot be verified to resolve and a link that 404s is worse than one
// that lands a level up. The per-sheet record id goes in `extra_metadata`
// instead, where it is exact and machine-readable.
//
// ponytail: writes `dc_description`, `source_url` and (opt-in) `name`. `rights` stays "Public
// domain" — a 1900s French colonial survey probably is, but CartoMundi's Nakala
// items for the neighbouring 1:100,000 series are CC-BY-NC-SA-4.0, and guessing
// a licence is the same error as guessing a source. Flagged, not changed.

import { createClient } from '@supabase/supabase-js';

// The description is a plain gap-fill. The renaming is an editorial decision
// and is opt-in, because the catalogue's spellings are French colonial
// transcriptions: authentic to the printed sheet, hyphenated, and only
// partially accented. "Kim Thanh" → "Kim-Thành" restores a real diacritic;
// "Bac Ninh" → "Bac-Ninh" only adds a hyphen; "Yen Dinh" → "Yên-Dinh" is
// half-accented for Yên Định and may read as an error rather than as period
// spelling. 58 of these are public titles, so it is a call for a person.
const dry = process.argv.includes('--dry');
const withNames = process.argv.includes('--names');
// 175 supplies the names (it is the complete cell list); 243 supplies the
// provenance (it is the edition we actually hold). See the header.
const NAME_SERIE = 175;
const HELD_SERIE = 243;
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const feuillesApi = (k) => `https://www.cartomundi.fr/ctmd-services/serie/${k}/feuilles`;
const SERIES_URL = `https://www.cartomundi.fr/searchMap?type=serie&id=${HELD_SERIE}`;

// Catalogue spellings we do not adopt.
//  6: catalogue prints "Phu-Quang-0ai" — a zero for an O, a transcription slip.
// 27: catalogue reorders to "Thuong-Tin-Phu"; ours "Phu Thuong Tin" matches the
//     sheet as printed and the order every other Phu- sheet here uses.
const SKIP_NAME = new Set(['6', '27']);

const DESCRIPTION = [
  "Sheet from the Service Géographique de l'Indochine survey of Tonkin and Thanh Hóa at 1:25,000,",
  'published at Hanoï between 1901 and 1944.',
  'Each sheet covers 12.5 × 18.75 km on paper 62 × 86 cm, assembled from two original half-sheets,',
  'and represents one sixteenth of a 1:100,000 sheet.',
  'Clarke ellipsoid, Bonne projection, origin 115 grades east of Paris.',
].join(' ');

const get = async (k) =>
  await (await fetch(feuillesApi(k), { headers: { Accept: 'application/json' } })).json();
const feuilles = await get(NAME_SERIE);
const heldFeuilles = await get(HELD_SERIE);
console.log(
  `CartoMundi serie ${NAME_SERIE}: ${feuilles.length} records | serie ${HELD_SERIE}: ${heldFeuilles.length} records`
);

// 243 numbers a half-sheet by its cell plus a W/E suffix, and brackets the part
// of the name that is not on that half. Strip both to get back to the cell.
const cellOf = (v) =>
  String(v)
    .replace(/[[\]]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\s*[WE]$/, '');
const heldByCell = new Map();
for (const f of heldFeuilles) {
  const n = cellOf(f.f100NumeroOuCode);
  if (!heldByCell.has(n)) heldByCell.set(n, []);
  heldByCell.get(n).push(f);
}

// One title per cell. Editions of a cell share a name; take the earliest, which
// is the one least likely to carry a later administrative rename.
const titleFor = new Map();
for (const f of feuilles) {
  const sn = String(f.f100NumeroOuCode).trim();
  const prev = titleFor.get(sn);
  if (!prev || (f.f103DateAaaa || 9999) < prev.year)
    titleFor.set(sn, { title: f.f105Titre, year: f.f103DateAaaa || 9999 });
}

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data: rows, error } = await db
  .from('maps')
  .select('id,name,year,status,dc_description,source_url,extra_metadata')
  .eq('collection', COLLECTION);
if (error) throw error;

const updates = [];
const unmatched = [];
let renames = 0;
for (const m of rows) {
  const sn = String(m.extra_metadata?.sheet_number ?? '').trim();
  const patch = { id: m.id };
  if (!m.dc_description) patch.dc_description = DESCRIPTION;

  const cat = titleFor.get(sn);
  // Adopt the catalogue spelling only when it is the same name more precisely
  // written: strip accents and punctuation from both and require a match, so a
  // genuinely different name is never silently swapped in.
  if (withNames && cat?.title && !SKIP_NAME.has(sn) && cat.title !== m.name) {
    const fold = (s) =>
      s
        .normalize('NFD')
        .replace(/[̀-ͯ]/g, '')
        .replace(/[^a-z0-9]/gi, '')
        .toLowerCase();
    if (fold(cat.title) === fold(m.name)) {
      patch.name = cat.title;
      renames++;
    } else {
      console.log(
        `  name differs beyond accents, left alone: "${m.name}" vs "${cat.title}" (sheet ${sn})`
      );
    }
  }
  // Provenance, and only where the year agrees. A sheet whose printing the
  // catalogue does not list gets no source_url at all — pointing it at a series
  // page that does not contain it is the same guess this script exists to avoid.
  const held = (heldByCell.get(cellOf(sn)) || []).filter((f) => f.f103DateAaaa === m.year);
  if (held.length && !m.source_url) {
    patch.source_url = SERIES_URL;
    patch.extra_metadata = {
      ...(m.extra_metadata ?? {}),
      cartomundi_serie: HELD_SERIE,
      // Both halves of the assembled sheet, when the catalogue lists both.
      cartomundi_fkeys: held.map((f) => f.fkey),
    };
  } else if (!held.length) {
    unmatched.push(`${sn} (${m.name} ${m.year})`);
  }

  if (Object.keys(patch).length > 1) updates.push(patch);
}

console.log(
  `\n${rows.length} rows | ${updates.length} to update` +
    ` | ${updates.filter((u) => u.dc_description).length} gain a description` +
    ` | ${updates.filter((u) => u.source_url).length} gain a source URL` +
    ` | ${renames} gain diacritics`
);
if (unmatched.length)
  console.log(
    `no serie ${HELD_SERIE} printing for this year, left without a source: ${unmatched.join(' · ')}`
  );
for (const u of updates.slice(0, 8)) {
  const m = rows.find((r) => r.id === u.id);
  console.log(`  ${m.name}${u.name ? ` → ${u.name}` : ''}${u.dc_description ? ' +desc' : ''}`);
}
if (updates.length > 8) console.log(`  … and ${updates.length - 8} more`);

if (dry) {
  console.log('\n--dry: nothing written');
  process.exit(0);
}

let done = 0;
for (const u of updates) {
  const { id, ...fields } = u;
  const { error: e } = await db.from('maps').update(fields).eq('id', id);
  if (e) throw e;
  done++;
}
console.log(`\nupdated ${done} rows`);
