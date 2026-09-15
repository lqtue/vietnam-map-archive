#!/usr/bin/env node
// Fetch the Indochine 1:25,000 cells the archive does not hold, from IGN's own
// scans, and mirror them the way every other sheet in the series is mirrored.
//
//   node --env-file=.env scripts/oneoff/ingest_indochine_nakala.mjs            # dry run
//   node --env-file=.env scripts/oneoff/ingest_indochine_nakala.mjs --apply
//
// This used to insert rows and tile scans unless you passed --dry. Nothing in
// scripts/ writes without --apply now.
//
// WHERE THE SCANS ARE, AND WHY IT TOOK A WRONG TURN TO FIND THEM. CartoMundi is
// a union catalogue: `serie/<id>/feuilles` lists what the survey contains and
// says nothing about what is digitised. The digitised copy hangs off a
// *holding* record, and the endpoint that returns those is keyed on the copy's
// `dpKey` -- NOT on the sheet's `fkey`, which is the trap: pass an fkey to
// `serie/etabfeuille/<k>` and it answers 200 with a real record belonging to
// some other sheet entirely. Probed that way, four Tonkin cells came back
// carrying IIIF services that render 1:50,000 sheets of ALGERIA. Nothing in the
// response says so; the only thing that catches it is looking at the pixels.
//
// The endpoint that is actually keyed on the survey is
//
//     public/etablissement/<etKey>/serie/<serieId>/feuille/exemplaire/all
//
// -- every sheet of one series held by one institution, each with its copies
// nested under `feuilleEtablissementDocuments`. For IGN (etKey 3) over series
// 243 and 175 that is 304 copy records, of which 212 carry a Nakala DOI: the
// survey is very nearly all digitised, CC-BY-4.0, over IIIF level 2 with CORS.
// `work/tonkin/sources/nakala.json` is that read, reduced to the cells we lack.
//
// WHY MIRROR RATHER THAN POINT AT NAKALA. Nakala's IIIF is better than ours --
// level 2 against our level 0 key lookup. But `iiif.maparchive.vn/iiif/<mapId>`
// is what the whole pipeline assumes: `tonkin_georef.py` composes it from the
// row id, `ocr.py` reads through it, `atWidth` rewrites its size segment. One
// externally-hosted row would be the first in 131 and would half-work in ways
// that look like data. The scan is 20-25 MB; the tiling is a minute.
//
// HALF-SHEETS. Serie 243 issued most cells as a west and an east half, each
// with its own frame and its own printed corner figures, so each is a separate
// `maps` row sharing one `sheet_number` -- which is what `map_series` already
// counts as one cell (mig 084). Twelve cells were issued as a single
// half-format sheet covering the whole cell; those get one row.
//
// --source, AND THE TWO THINGS A YEAR-PINNED SOURCE CHANGES. The default source
// fills cells the archive does not hold at all, so "one printing per half, the
// most recent" is the right rule and a cell already held is a cell to skip.
// `nakala-originals.json` is the other job: the originals behind cells we hold
// as third-party composites, each pinned at ITS composite's year. A file
// declaring `_year_pinned: true` switches both rules to include the year, because
// cells 2, 13 and 14 are each held as two printings and need the halves of both
// -- keyed on the half alone, the second printing reads as already held and is
// silently dropped. Such a source may also carry `part` on a record, which is a
// human's decision about a half the catalogue describes two ways; the guard below
// stays armed for every record that does not carry one.

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { sheetPart, partFromTitle } from '../lib/cells.mjs';
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const apply = willApply();
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const SERIES_KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const srcArg = process.argv.indexOf('--source');
const SRC = srcArg > -1 ? process.argv[srcArg + 1] : 'work/tonkin/sources/nakala.json';

/** Brackets mark the half of the title this half-sheet does not print. */
function cleanName(t) {
  return String(t || '')
    .replace(/[[\]']/g, '')
    .replace(/-/g, ' ')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Which half of the cell this record is, in the two values `sheet_half` holds.
 *
 * The classifier is `sheetPart()` in ../lib/cells.mjs; this is the mapping into
 * this table's vocabulary, and the ASSEMBLAGE branch is the reason it is a
 * mapping rather than a call. This script's row model has no way to say "one
 * sheet of paper covering both halves of the cell": it mints one `maps` row per
 * half. The copy of this function that used to live here had no assemblage test
 * at all and answered 'whole' — which on the 304 IGN copy records is 79 of them
 * (measured 2026-09-14), every one of which would have been minted as a
 * whole-cell sheet with nothing in the output saying so.
 *
 * It has never happened, because `nakala.json` is a pre-filtered read holding
 * 11 demi-format and 21 demi-feuille records and no assemblage. Regenerate that
 * file over serie 175, which is ALL assemblages, and it would. So it stops.
 */
function half(note, decided) {
  // A record whose half a human decided, because the catalogue said two things.
  // `partFromTitle` disagreeing with the note is what the throw below catches;
  // this is the only way past it, and it is per record rather than a mode.
  if (decided === 'W' || decided === 'E') return decided;
  const p = sheetPart(note);
  if (p === 'assemblage') {
    throw new Error(
      `assemblage in ${SRC}: this script mints one row per half and cannot ingest one. ` +
        'Filter it out of the source read, or teach it the third case. Note: ' +
        JSON.stringify(String(note ?? '').slice(0, 120))
    );
  }
  return p === 'W' || p === 'E' ? p : 'whole';
}

const db = serviceClient();

const source = JSON.parse(readFileSync(SRC, 'utf8'));
const { cells } = source;
const yearPinned = source._year_pinned === true;
const { data: held, error } = await db
  .from('maps')
  .select('id,year,extra_metadata')
  .eq('collection', COLLECTION);
if (error) throw error;
const heldKey = (m) =>
  `${m.extra_metadata?.sheet_number}|${m.extra_metadata?.sheet_half ?? 'whole'}` +
  (yearPinned ? `|${m.year}` : '');
const have = new Set(held.map(heldKey));

// The series blurb every row in this collection carries.
const { data: sib } = await db
  .from('maps')
  .select('dc_description')
  .eq('collection', COLLECTION)
  .not('dc_description', 'is', null)
  .limit(1);
const BLURB = sib?.[0]?.dc_description ?? null;

const jobs = [];
for (const cell of Object.keys(cells).sort((a, b) => parseFloat(a) - parseFloat(b))) {
  const byHalf = new Map();
  for (const r of cells[cell]) {
    const h = half(r.note, r.part);
    const t = partFromTitle(r.title);
    if (h !== 'whole' && t && t !== h && !r.part) {
      throw new Error(`cell ${cell} ${r.year}: note says ${h}, title "${r.title}" says ${t}`);
    }
    // One printing per half: the most recent, which is the one whose revision
    // date the sheet itself is catalogued under. A year-pinned source has
    // already chosen, and its cells may legitimately hold two printings of the
    // same half, so there the year is part of the key rather than a tie-break.
    const k = yearPinned ? `${h}|${r.year}` : h;
    const cur = byHalf.get(k);
    if (!cur || (r.year || 0) > (cur.year || 0)) byHalf.set(k, { h, r });
  }
  for (const { h, r } of byHalf.values()) {
    if (have.has(`${cell}|${h}` + (yearPinned ? `|${r.year}` : ''))) continue;
    jobs.push({ cell, h, r });
  }
}

console.log(`${jobs.length} scans to ingest\n`);
let done = 0;
for (const { cell, h, r } of jobs) {
  const base = cleanName(r.title);
  const name = h === 'whole' ? base : `${base} (${h})`;
  const id = randomUUID();
  const upstream = r.iiif.replace(/\/info\.json$/, '');
  const label = `${cell}${h === 'whole' ? '' : ' ' + h}`;

  if (!apply) {
    console.log(`  ${label.padStart(8)}  ${name.padEnd(22)} ${r.year}  ${r.nakala}`);
    continue;
  }

  const row = {
    id,
    name,
    location: 'Tonkin',
    year: r.year,
    year_label: String(r.year),
    language: 'fr',
    map_type: 'topographic',
    source_type: 'self',
    status: 'draft',
    collection: COLLECTION,
    creator: "Service Géographique de l'Indochine",
    dc_publisher: "Service Géographique de l'Indochine",
    dc_description: BLURB,
    holding_institution: 'Cartomundi (Aix-Marseille Université / CNRS)',
    rights: 'CC BY 4.0 — IGN, deposited in Nakala',
    source_url: `https://doi.org/${r.nakala}`,
    iiif_image: `https://iiif.maparchive.vn/iiif/${id}`,
    thumbnail: `https://iiif.maparchive.vn/iiif/${id}/full/400,/0/default.jpg`,
    georef_done: false,
    extra_metadata: {
      sheet_number: cell,
      sheet_half: h,
      sheet_note: r.note,
      cartomundi_serie: r.serie,
      cartomundi_fkeys: [r.fkey],
      nakala_doi: r.nakala,
      nakala_sha1: r.sha1,
      nakala_iiif: upstream,
      ...(r.part ? { sheet_half_decided_because: r.part_decided_because ?? null } : {}),
      ...(r.replaces_map_id
        ? {
            mirrors_original_for: r.replaces_map_id,
            mirrors_original_note:
              'Mirrored as the IGN original behind a third-party composite this archive already publishes. Nothing about that row is changed by this one.',
          }
        : {}),
    },
  };
  const ins = await db.from('maps').insert(row);
  if (ins.error) {
    console.log(`  ${label.padStart(8)}  ${name.padEnd(22)} INSERT FAILED ${ins.error.message}`);
    continue;
  }

  try {
    execFileSync('bash', ['scripts/tile_map.sh', id, `${upstream}/full/max/0/default.jpg`], {
      stdio: ['ignore', 'ignore', 'pipe'],
    });
  } catch (e) {
    console.log(
      `  ${label.padStart(8)}  ${name.padEnd(22)} TILING FAILED — row left draft, no pixels`
    );
    console.log(String(e.stderr || e).slice(-400));
    continue;
  }

  // The cell counts as held once one of its halves is in. Point at the first.
  const { data: ss } = await db
    .from('series_sheets')
    .select('held_by')
    .eq('series_key', SERIES_KEY)
    .eq('sheet_number', cell)
    .maybeSingle();
  if (ss && !ss.held_by) {
    await db
      .from('series_sheets')
      .update({ held_by: 'map', map_id: id })
      .eq('series_key', SERIES_KEY)
      .eq('sheet_number', cell);
  }

  done++;
  console.log(`  ${label.padStart(8)}  ${name.padEnd(22)} ${r.year}  ${id}`);
}

if (apply)
  console.log(
    `\n${done}/${jobs.length} mirrored. Next: tonkin_georef.py all, then annotate --write.`
  );
else dryNotice(`It would insert ${jobs.length} maps rows and tile each scan.`);
