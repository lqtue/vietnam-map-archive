#!/usr/bin/env node
// Mirror digitised cells of the Indochine 1:100,000 series (skey 325, 561)
// from Nakala into iiif.maparchive.vn, tile them, and mint real `maps` rows —
// the phase `scripts/oneoff/import_indochine_100k_series_sheets.mjs` (mig 083,
// `series_sheets`) left undone. See `.claude/handoff.md` for the full trail.
//
//   node --env-file=.env scripts/oneoff/ingest_indochine_100k_nakala.mjs                     # dry run, both series
//   node --env-file=.env scripts/oneoff/ingest_indochine_100k_nakala.mjs --series 561 --limit 3 --apply
//   node --env-file=.env scripts/oneoff/ingest_indochine_100k_nakala.mjs --apply              # all 327
//
// Same shape as `ingest_indochine_nakala.mjs` did for the 25,000 Tonkin pair:
// one `maps` row per digitised half (or whole, where the cell was never
// split), tiled via `tile_map.sh`, `series_sheets.held_by` pointed at the
// first half in. Start with `--series` + `--limit` — a small batch proves the
// path before all 327; nothing here is transactional.
//
// TWO NAKALA FIELDS, ONE SERIES EACH. The reduced sources
// (`work/indochine-100k/sources/serie-{325,561}.json`) carry a digitised
// asset under whichever of two CartoMundi fields was populated:
//   - `f125FluxIiifEtablissement` — a ready IIIF `info.json` URL. All 492
//     digitised records in 561 are this shape.
//   - `f110IdNakala` — a bare Nakala DOI, with `sha1` alongside it. All 221
//     digitised records in 325 are this shape; 325 has *zero* f125 records.
// Both resolve to the same IIIF base, `https://api.nakala.fr/iiif/<doi>/
// <sha1>`, confirmed live (200 on a constructed f110 URL, 2026-09-21) — so
// `iiifBase()` below builds it either way rather than requiring the ready
// form. A `nakala_field: null` asset (325 has 291 of these) is a holding
// record with no digitised copy at all — not this scale's version of a
// thumbnail-only asset, there isn't one in either file — and is skipped.
//
// TITLES DO NOT RELIABLY SAY WHICH HALF. In 561, title text spells out
// "Est"/"Ouest" on all but 4 of 470 half-records. In 325 it's the opposite:
// 457 of 473 do NOT — the convention there is bracketing the part the sheet
// DOESN'T cover (`[Maha]xay` vs `Maha[xay]`), which `cellName()` strips along
// with everything else. So the "(E)"/"(W)" suffix below is appended
// unconditionally rather than inferred from title text, exactly like the
// Tonkin script's `half` suffix — the two series can't be treated as a single
// convention.
//
// LICENCE. CC BY 4.0 — same as the 25,000 series. An earlier pass here believed it was
// CC BY-NC-SA 4.0, reasoning from CartoMundi's per-copy `tr38Licence` (always null on both
// series) as if that implied a stricter *Nakala collection*-level licence. That was never
// checked against Nakala itself and was wrong: probed directly against 5 items' own metadata
// (`http://nakala.fr/terms#license` on `GET api.nakala.fr/datas/<doi>`), spanning both series —
// 325's `10.34847/nkl.2decsq4u` and 561's `10.34847/nkl.c2e6722w`, `nkl.eb1256k9`,
// `nkl.35fcy2mk`, `nkl.92dad5xi` — every one says `CC-BY-4.0`. Confirmed 2026-09-22, after 21
// rows had already gone out with the wrong `rights` string; those were corrected by hand
// (`UPDATE maps SET rights = ...` — see `.claude/handoff.md`). The Nakala collection API itself
// 401s without a key, so it was never actually checked either time; the per-item metadata above
// is the ground truth, because it's literally the licence attached to the object being mirrored.
//
// This does not georeference anything. `series_sheets.bbox` (already loaded)
// is a catalogue extent, not a warp; every row lands `georef_done: false`.

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice, opt } from '../lib/cli.mjs';

const apply = willApply();
const onlySkey = opt('--series') ? Number(opt('--series')) : null;
const limit = opt('--limit') ? Number(opt('--limit')) : null;

const SERIES = [
  {
    skey: 325,
    key: 'indochine-1-100-000-1900-1947',
    collection: 'Indochine 1:100,000 — 1st édition SGI (1900–1947)',
    source: 'work/indochine-100k/sources/serie-325.json',
    description:
      "Sheet from the Service Géographique de l'Indochine survey of Indochine at 1:100,000, " +
      '1st édition, published 1900–1947. Digitised by IGN, held in the CartoMundi union ' +
      'catalogue and deposited in Nakala (collection 10.34847/nkl.d2a82952).',
  },
  {
    skey: 561,
    key: 'indochine-1-100-000-1947-1959',
    collection: 'Indochine 1:100,000 — 2nd édition SGI (1947–1959)',
    source: 'work/indochine-100k/sources/serie-561.json',
    description:
      "Sheet from the Service Géographique de l'Indochine survey of Indochine at 1:100,000, " +
      '2nd édition ("L 605"), published 1947–1959. Digitised by IGN, held in the CartoMundi ' +
      'union catalogue and deposited in Nakala (collection 10.34847/nkl.d2a82952).',
  },
].filter((s) => !onlySkey || s.skey === onlySkey);

/** Brackets mark a part the catalogue is reconstructing (either its own — see
 * the header — or a genuine editorial bracket); the name is the rest. */
function cellName(v) {
  return (
    String(v ?? '')
      .replace(/[[\]]/g, '')
      .replace(/\s+/g, ' ')
      .trim() || null
  );
}

/** @returns {{doi: string, sha1: string, upstream: string} | null} */
function iiifBase(asset) {
  if (!asset?.nakala_value) return null;
  if (asset.nakala_field === 'f125FluxIiifEtablissement') {
    const m = /^(https:\/\/api\.nakala\.fr\/iiif\/.+)\/([0-9a-f]{40})\/info\.json$/.exec(
      asset.nakala_value
    );
    if (!m) throw new Error(`unrecognised f125 IIIF URL: ${asset.nakala_value}`);
    const doi = m[1].replace(/^https:\/\/api\.nakala\.fr\/iiif\//, '');
    return { doi, sha1: m[2], upstream: `${m[1]}/${m[2]}` };
  }
  if (asset.nakala_field === 'f110IdNakala') {
    if (!asset.sha1) throw new Error(`f110IdNakala without sha1: ${asset.nakala_value}`);
    return {
      doi: asset.nakala_value,
      sha1: asset.sha1,
      upstream: `https://api.nakala.fr/iiif/${asset.nakala_value}/${asset.sha1}`,
    };
  }
  return null; // e.g. null nakala_field — a holding record with nothing digitised
}

const db = apply ? serviceClient() : null;
const jobs = [];

for (const { skey, key: SERIES_KEY, collection, source, description } of SERIES) {
  const { cells } = JSON.parse(readFileSync(source, 'utf8'));

  let have = new Set();
  if (apply) {
    const { data: rows, error } = await db
      .from('maps')
      .select('extra_metadata')
      .eq('collection', collection);
    if (error) throw error;
    have = new Set(
      rows
        .filter((m) => m.extra_metadata?.sheet_number)
        .map((m) => `${m.extra_metadata.sheet_number}|${m.extra_metadata.sheet_half}`)
    );
  }

  for (const cell of Object.keys(cells).sort()) {
    const byPart = new Map(); // part ('E'|'W'|'null') -> best digitised record
    for (const r of cells[cell]) {
      const asset = (r.assets || []).find((a) => iiifBase(a));
      if (!asset) continue; // catalogued only, nothing digitised for this record
      const partKey = r.part ?? 'null';
      const cur = byPart.get(partKey);
      if (!cur || (r.year || 0) > (cur.r.year || 0)) byPart.set(partKey, { r, asset });
    }
    for (const [partKey, { r, asset }] of byPart) {
      const half = partKey === 'null' ? 'whole' : partKey;
      if (have.has(`${cell}|${half}`)) continue;
      jobs.push({ skey, SERIES_KEY, collection, description, cell, half, r, asset });
    }
  }
}

if (limit) jobs.length = Math.min(jobs.length, limit);

console.log(`${jobs.length} scans to ingest\n`);
let done = 0;
for (const { skey, SERIES_KEY, collection, description, cell, half, r, asset } of jobs) {
  const base = cellName(r.title);
  const name = half === 'whole' ? base : `${base} (${half})`;
  const { doi, sha1, upstream } = iiifBase(asset);
  const label = `${cell}${half === 'whole' ? '' : ' ' + half}`;

  if (!apply) {
    console.log(`  serie ${skey}  ${label.padStart(10)}  ${name.padEnd(28)} ${r.year}  ${doi}`);
    continue;
  }

  const id = randomUUID();
  const row = {
    id,
    name,
    location: 'Indochine',
    year: r.year,
    date_label: String(r.year),
    language: 'fr',
    map_type: 'topographic',
    source_type: 'self',
    status: 'draft',
    collection,
    creator: "Service Géographique de l'Indochine",
    publisher: "Service Géographique de l'Indochine",
    description,
    holding_institution: 'Cartomundi (Aix-Marseille Université / CNRS)',
    rights: 'CC BY 4.0 — IGN, deposited in Nakala',
    source_url: `https://doi.org/${doi}`,
    iiif_image: `https://iiif.maparchive.vn/iiif/${id}`,
    thumbnail: `https://iiif.maparchive.vn/iiif/${id}/full/400,/0/default.jpg`,
    is_georeferenced: false,
    extra_metadata: {
      sheet_number: cell,
      sheet_half: half,
      sheet_note: r.note,
      cartomundi_serie: skey,
      cartomundi_fkeys: [r.fkey],
      nakala_doi: doi,
      nakala_sha1: sha1,
      nakala_iiif: upstream,
    },
  };
  const ins = await db.from('maps').insert(row);
  if (ins.error) {
    console.log(`  ${label.padStart(10)}  ${name.padEnd(28)} INSERT FAILED ${ins.error.message}`);
    continue;
  }

  try {
    execFileSync('bash', ['scripts/tile_map.sh', id, `${upstream}/full/max/0/default.jpg`], {
      stdio: ['ignore', 'ignore', 'pipe'],
    });
  } catch (e) {
    console.log(
      `  ${label.padStart(10)}  ${name.padEnd(28)} TILING FAILED — row left draft, no pixels`
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
  console.log(`  serie ${skey}  ${label.padStart(10)}  ${name.padEnd(28)} ${r.year}  ${id}`);
}

if (apply) console.log(`\n${done}/${jobs.length} mirrored.`);
else dryNotice(`It would insert ${jobs.length} maps rows and tile each scan.`);
