#!/usr/bin/env node
// Fetch the Indochine 1:25,000 cells the archive does not hold, from IGN's own
// scans, and mirror them the way every other sheet in the series is mirrored.
//
//   node --env-file=.env scripts/oneoff/ingest_indochine_nakala.mjs --dry
//   node --env-file=.env scripts/oneoff/ingest_indochine_nakala.mjs
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

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
const COLLECTION = 'Indochine 1:25,000 — Tonkin & Thanh Hóa';
const SERIES_KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const SRC = 'work/tonkin/sources/nakala.json';

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

/** Which half of the cell this record is. A demi-format sheet is the whole of it.
 *
 * Anchored on the note's opening `Demi-feuille <X>`, because a few notes go on
 * to discuss the OTHER half -- 73 bis 1927 reads "Demi-feuille Est. La partie
 * de la mention de date ... demi-feuille Ouest", and a search of the whole
 * string calls the east half west. The title is the independent check: brackets
 * mark the part this sheet does not print, so `[Cua-] Day` is the east half and
 * `Cua- [Day]` the west, and `halfFromTitle` must agree.
 */
function half(note) {
  const n = String(note || '');
  if (/demi-format/i.test(n)) return 'whole';
  const m = /^\s*demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return 'whole';
}

/** The same fact read off the title's brackets. Disagreement means stop. */
function halfFromTitle(title) {
  const t = String(title || '');
  const i = t.indexOf('[');
  if (i < 0) return null;
  return t.slice(0, i).replace(/[\s-]/g, '') ? 'W' : 'E';
}

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { cells } = JSON.parse(readFileSync(SRC, 'utf8'));
const { data: held, error } = await db
  .from('maps')
  .select('id,extra_metadata')
  .eq('collection', COLLECTION);
if (error) throw error;
const have = new Set(
  held.map((m) => `${m.extra_metadata?.sheet_number}|${m.extra_metadata?.sheet_half ?? 'whole'}`)
);

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
    const h = half(r.note);
    const t = halfFromTitle(r.title);
    if (h !== 'whole' && t && t !== h) {
      throw new Error(`cell ${cell} ${r.year}: note says ${h}, title "${r.title}" says ${t}`);
    }
    // One printing per half: the most recent, which is the one whose revision
    // date the sheet itself is catalogued under.
    const cur = byHalf.get(h);
    if (!cur || (r.year || 0) > (cur.year || 0)) byHalf.set(h, r);
  }
  for (const [h, r] of byHalf) {
    if (have.has(`${cell}|${h}`)) continue;
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

  if (dry) {
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
    console.log(`  ${label.padStart(8)}  ${name.padEnd(22)} TILING FAILED — row left draft, no pixels`);
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

if (!dry) console.log(`\n${done}/${jobs.length} mirrored. Next: tonkin_georef.py all, then annotate --write.`);
