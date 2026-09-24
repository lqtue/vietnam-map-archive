#!/usr/bin/env node
// Demote the 62 Indochine 1:25,000 composites to `draft`, and re-point the
// series index at the IGN half-sheets that replace them.
//
//   node --env-file=.env scripts/oneoff/demote_indochine_composites.mjs          # dry run
//   node --env-file=.env scripts/oneoff/demote_indochine_composites.mjs --apply
//
// WHY. The collection holds 205 rows in two provenances, told apart by their
// `rights` string:
//
//   62  composites — third-party scans stitched from the two printed halves.
//                    `rights` says "...this copy assembled from the two printed
//                    half-sheets". No `nakala_doi` on any of them.
//   143 half-sheets — mirrored directly from Nakala, each with its own DOI.
//
// The composites' CC BY 4.0 rests on `check_indochine_provenance.py`'s
// two-cell visual fingerprint (a shared blue pencil mark on cell 36, a shared
// library stamp on cell 72) generalised to 60 more sheets — an inference, and
// that script says so itself. The `rights` text now in those rows matches no
// string in any committed script, so the write that produced it is not
// reproducible from the tree either. The half-sheets have neither problem:
// each one's licence is confirmed per item at
// `api.nakala.fr/datas/10.34847/nkl.<id>` (`nakala.fr/terms#license`).
//
// WHAT DEMOTING COSTS, measured 2026-09-21 by matching names across the two
// provenances. Of the 62 composites:
//
//   56  have BOTH halves public and georeferenced — no ground is lost.
//    2  have only the W half (Phat Diem, Quynh Coi) — each cell's eastern half
//       stops being publicly visible.
//    4  have no half-sheet at all (An Thi, Phu Thuong Tin, Phu Xuan Truong,
//       Quang Oai) — these leave the public archive until IGN halves for them
//       are ingested.
//
// All 62 go regardless: the user's call, taken with those six named. Nothing
// is deleted — a draft row keeps its pixels, its georeference and its slug,
// and `map_slug_aliases` means the published URL still resolves.
//
// THE INDEX IS THE REAL HAZARD. 59 of the 79 `series_sheets` rows for this
// survey point their `map_id` at a composite, and NOTHING maintains
// `held_by` — no trigger, no function (ROADMAP.md, "Also open").
// Demoting without touching the index would leave the coverage page drawing 59
// cells as *held* while pointing at rows the public cannot see: the exact
// drift that item warns about, self-inflicted rather than latent. So this
// script re-points them in the same pass, per migration 083's own definition:
//
//     held_by is not null                     -> held and served
//     held_by is null and source is not null  -> obtainable, not yet fetched
//     held_by is null and source is null      -> no known scan anywhere
//
// A cell whose composite has halves gets `map_id` = its E half (W where only
// the W exists), `held_by` staying 'map'. A cell with no half gets `map_id`
// null and `held_by` null — "we do not serve it", which after the demotion is
// literally true, while `source` staying put keeps it readable as obtainable
// rather than as a sheet nobody knows a scan for.
//
// E over W is arbitrary but deterministic; `ingest_indochine_100k_nakala.mjs`
// set the precedent of pointing at one half rather than inventing a pair.
//
// MATCHING BY NAME WAS THE WRONG INSTRUMENT, and this script shipped with it.
// The first `--apply` run un-held four cells as having no replacement — 27, 35,
// 6 and 61. `check_series_index.mjs` caught three of them immediately, because
// it joins on `extra_metadata.sheet_number` rather than on names, and the
// half-sheets for those cells are named nothing like their composites:
//
//   cell 27  "Phu Thuong Tin"   -> "Thuong Tin Phu (E)"   word order
//   cell  6  "Quang Oai"        -> "Phu Quang Oai (E)"    an extra prefix
//   cell 61  "Phu Xuan Truong"  -> "Phu Xyan Truong (E)"  a typo in the scan's own name
//
// Only cell 35 "An Thi" is a real orphan. The same fold also invented the
// "only one half" pair: cell 43's other half is filed as "Quinh Coi (E)"
// against the composite's "Quynh Coi". So the true cost of the demotion is
// ONE sheet leaving the public archive, not six. `cellName()` is kept below
// because it is what ran, and the record should show what ran — but anything
// re-deriving this index must key off `extra_metadata.sheet_number`, which is
// the column the survey itself is keyed on and the only one a misspelling
// cannot move. The three cells were repointed by hand afterwards.
//
// Verify afterwards with `node --env-file=.env scripts/check_series_index.mjs`.
// It settles at **1 adrift** — cell 35, the An Thi orphan — because the drift
// check treats any `maps` row claiming a cell as evidence the index is wrong,
// and does not except a row deliberately demoted to draft. The index is right
// and the detector is reporting an honest gap as drift.

import { createClient } from '@supabase/supabase-js';
import { willApply, dryNotice } from '../lib/cli.mjs';

const SERIES_KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const COLLECTION = '%Indochine 1:25%';
// The composites are the rows whose `rights` records the stitching.
const COMPOSITE_RIGHTS = /assembled from the two printed half-sheets/;

const apply = willApply();

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

/** Fold a sheet name to its cell identity: accents, case and the half suffix off. */
function cellName(name) {
  return String(name ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\(.*?\)|\b(est|ouest|[ew])\b|[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** 'E', 'W', or null when the name does not say. */
function half(name) {
  if (/\(\s*(E|Est)\s*\)/i.test(name)) return 'E';
  if (/\(\s*(W|Ouest)\s*\)/i.test(name)) return 'W';
  return null;
}

function selfCheck() {
  const eq = (a, b, what) => {
    if (a !== b)
      throw new Error(`${what}: expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
  };
  // A composite and both its halves must fold to the same cell.
  eq(cellName('Hoai Duc Phu (W)'), 'hoai duc phu', 'cellName strips the half suffix');
  eq(cellName('Hoài Đức Phủ'), 'hoai uc phu', 'cellName folds accents');
  // ^ Đ folds to a bare d only under NFD for the combining forms; Đ is its own
  // letter and drops out. That is fine — it is applied to BOTH sides of every
  // comparison, so the fold only has to be consistent, not linguistically right.
  eq(cellName('Quang Yen (Sud)'), 'quang yen', 'a non-E/W parenthetical also drops');
  eq(half('Viet Tri (E)'), 'E', 'half reads E');
  eq(half('Kien Xuong (W)'), 'W', 'half reads W');
  eq(half('An Thi'), null, 'a composite has no half');
  console.log('self-check ok');
}

if (process.argv.includes('--self-check')) {
  selfCheck();
  process.exit(0);
}
selfCheck();

const { data: rows, error } = await db
  .from('maps')
  .select('id,slug,name,status,georef_done,rights')
  .ilike('collection', COLLECTION);
if (error) throw new Error(`reading maps: ${error.message}`);

const composites = rows.filter((r) => COMPOSITE_RIGHTS.test(r.rights ?? ''));
const halves = rows.filter((r) => !COMPOSITE_RIGHTS.test(r.rights ?? ''));

// cell -> { E, W }
const byCell = new Map();
for (const r of halves) {
  const c = cellName(r.name);
  if (!byCell.has(c)) byCell.set(c, {});
  const side = half(r.name);
  if (side) byCell.get(c)[side] = r;
}

/** The half-sheet that should carry this composite's cell, or null. */
function replacementFor(composite) {
  const pair = byCell.get(cellName(composite.name));
  return pair ? (pair.E ?? pair.W ?? null) : null;
}

console.log(
  `collection: ${rows.length} rows — ${composites.length} composites, ${halves.length} half-sheets`
);
const stillPublic = composites.filter((r) => r.status !== 'draft');
console.log(
  `composites to demote: ${stillPublic.length} (${composites.length - stillPublic.length} already draft)`
);

const orphans = composites.filter((r) => !replacementFor(r));
const partial = composites.filter((r) => {
  const pair = byCell.get(cellName(r.name));
  return pair && !(pair.E && pair.W);
});
console.log(`  no half-sheet at all: ${orphans.length} — ${orphans.map((r) => r.name).join(', ')}`);
console.log(`  only one half:        ${partial.length} — ${partial.map((r) => r.name).join(', ')}`);

const { data: index, error: ixError } = await db
  .from('series_sheets')
  .select('sheet_number,name,held_by,map_id,source')
  .eq('series_key', SERIES_KEY);
if (ixError) throw new Error(`reading series_sheets: ${ixError.message}`);

const compositeById = new Map(composites.map((r) => [r.id, r]));
const affected = index.filter((r) => r.map_id && compositeById.has(r.map_id));
console.log(`\nindex rows pointing at a composite: ${affected.length} of ${index.length}`);

const repoint = [];
const unhold = [];
for (const cell of affected) {
  const composite = compositeById.get(cell.map_id);
  const replacement = replacementFor(composite);
  if (replacement) repoint.push({ cell, composite, replacement });
  else unhold.push({ cell, composite });
}
console.log(`  re-point at a half-sheet: ${repoint.length}`);
for (const { cell, composite, replacement } of repoint.slice(0, 5)) {
  console.log(`    ${cell.sheet_number} "${composite.name}" -> "${replacement.name}"`);
}
if (repoint.length > 5) console.log(`    … and ${repoint.length - 5} more`);
console.log(`  drop to not-served (held_by null): ${unhold.length}`);
for (const { cell, composite } of unhold) {
  console.log(`    ${cell.sheet_number} "${composite.name}" — source ${cell.source ?? '(none)'}`);
}

if (!apply) {
  dryNotice(
    `Would set ${stillPublic.length} maps to draft, re-point ${repoint.length} index rows and un-hold ${unhold.length}.`
  );
  process.exit(0);
}

let demoted = 0;
for (const r of stillPublic) {
  const { error: e } = await db.from('maps').update({ status: 'draft' }).eq('id', r.id);
  if (e) throw new Error(`demoting ${r.slug}: ${e.message}`);
  demoted += 1;
}
console.log(`\ndemoted: ${demoted}`);

let moved = 0;
for (const { cell, replacement } of repoint) {
  const { error: e } = await db
    .from('series_sheets')
    .update({ map_id: replacement.id, held_by: 'map' })
    .eq('series_key', SERIES_KEY)
    .eq('sheet_number', cell.sheet_number);
  if (e) throw new Error(`re-pointing ${cell.sheet_number}: ${e.message}`);
  moved += 1;
}
console.log(`re-pointed: ${moved}`);

let cleared = 0;
for (const { cell } of unhold) {
  const { error: e } = await db
    .from('series_sheets')
    .update({ map_id: null, held_by: null })
    .eq('series_key', SERIES_KEY)
    .eq('sheet_number', cell.sheet_number);
  if (e) throw new Error(`un-holding ${cell.sheet_number}: ${e.message}`);
  cleared += 1;
}
console.log(`un-held: ${cleared}`);
console.log('\nNow run: node --env-file=.env scripts/check_series_index.mjs');
