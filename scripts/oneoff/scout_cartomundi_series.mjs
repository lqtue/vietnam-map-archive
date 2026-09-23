#!/usr/bin/env node
// Put CartoMundi's Indochina series into the scout queue.
//
//   node --env-file=.env scripts/oneoff/scout_cartomundi_series.mjs            # dry run
//   node --env-file=.env scripts/oneoff/scout_cartomundi_series.mjs --apply
//
// This used to write unless you passed --dry. Nothing in scripts/ writes
// without --apply now.
//
// CartoMundi (MMSH, Aix-Marseille) publishes its union catalogue as open JSON
// at `/ctmd-services/serie/all`, no key. 25 of its 461 series cover Indochina,
// 3,522 sheets between them — against roughly 115 maps in this archive today.
// The Cochinchine 1:25,000 sheets alone (826 across three series) are Saigon
// and the Mekong delta, which is the archive's own subject.
//
// ONE ROW PER SERIES, not per sheet. A reviewer's decision here is "do we want
// this survey", and 3,522 sheet rows would bury a queue that currently holds
// 1,041. Sheet-level detail is one call away when a series is approved:
// `/ctmd-services/serie/<skey>/feuilles` returns every sheet with its number,
// title, date and catalogue extent — that is how serie 175 (the Tonkin series
// already in the archive) got its index.
//
// TWO THINGS A REVIEWER MUST KNOW, both in `review_note`:
//
//   - `s28NombreFeuilles` is what the series CONTAINS, not what CartoMundi has
//     digitised. They are a union catalogue recording holdings across
//     institutions, so a 330-sheet series may have far fewer scans online. The
//     digitised count could not be established from the API: the per-sheet
//     "available copies" endpoint was not found and IGN's Nakala collection
//     returns 401.
//   - THEY DO NOT GEOREFERENCE. What they publish per sheet is a catalogue
//     extent — four UNIMARC corner coordinates, good to about a minute of arc.
//     That places a rough box on a map; it cannot warp a sheet. Every sheet
//     taken from here still needs its georeference done by us.
//
// Images sit in Nakala and are served over IIIF; the item sampled was
// CC-BY-4.0, so mirroring is permitted with credit — but the licence is
// per-item, not per-series, and has to be read per sheet.

import { createClient } from '@supabase/supabase-js';
import { willApply } from '../lib/cli.mjs';

const dry = !willApply();
const ALL = 'https://www.cartomundi.fr/ctmd-services/serie/all';
const ZONES = [
  'Indochine',
  'Tonkin',
  'Annam',
  'Cochinchine',
  'Viet',
  'Laos',
  'Cambodge',
  'Hanoi',
  'Saigon',
];
// Vietnam proper is the archive's subject; Laos and Cambodia are adjacent
// interest, kept but ranked below.
const VIETNAM = ['Tonkin', 'Annam', 'Cochinchine', 'Viet', 'Hanoi', 'Saigon'];

const res = await fetch(ALL, { headers: { Accept: 'application/json' } });
const all = await res.json();
const hits = all.filter((s) => ZONES.some((z) => String(s.s2ZoneGeographique || '').includes(z)));
console.log(`${hits.length} Indochina series of ${all.length}`);

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Which series are already represented in the archive, so the queue does not
// offer work that is done. serie 175 is the Tonkin survey we hold.
const HELD = new Set([175]);

const rows = hits.map((s) => {
  const sheets = s.s28NombreFeuilles || 0;
  const scale = typeof s.s7Echelle === 'number' ? s.s7Echelle : null;
  const zone = String(s.s2ZoneGeographique || '');
  const vn = VIETNAM.some((z) => zone.includes(z));
  const title = (s.serieTitres || [{}])[0]?.s50TitreSerie || zone;
  const holders = (s.etablissementDetenteurs || []).map((e) => e.et70Etablissement).filter(Boolean);

  // Rank by what makes a series worth doing next: our own subject first, then
  // detail (a 1:25,000 sheet carries street names; 1:1,000,000 carries none),
  // then how much of it there is. Deliberately coarse — it orders a queue, it
  // does not decide anything.
  let score = 10;
  const reasons = [];
  if (vn) {
    score += 25;
    reasons.push('+vietnam');
  } else {
    reasons.push('+indochina');
  }
  if (scale && scale <= 25000) {
    score += 20;
    reasons.push('+large-scale');
  } else if (scale && scale <= 100000) {
    score += 8;
    reasons.push('+medium-scale');
  }
  if (sheets >= 100) {
    score += 10;
    reasons.push('+bulk');
  }
  if (zone.includes('Cochinchine') || zone.includes('Saigon')) {
    score += 10;
    reasons.push('+saigon-region');
  }
  if (HELD.has(s.skey)) {
    score -= 40;
    reasons.push('-already-held');
  }
  reasons.push(`+${sheets}sheets`);

  const category = scale && scale <= 50000 ? 'topographic' : 'regional';

  return {
    source: 'cartomundi',
    external_id: `serie/${s.skey}`,
    source_url: `https://www.cartomundi.fr/searchMap?type=serie&id=${s.skey}`,
    manifest_url: null,
    title,
    creator: s.s10ResponsabiliteIndividuelle || null,
    publisher: s.s9ResponsabiliteCollective || null,
    date: `${s.s5DateDebutAaaa ?? '?'}-${s.s6DatefinAaaa ?? '?'}`,
    year: s.s5DateDebutAaaa || null,
    rights: null, // per-item on Nakala, not per-series; must be read per sheet
    language: 'fre',
    holding_institution: holders.join(', ') || null,
    collection: 'CartoMundi',
    thumbnail: null,
    score,
    category,
    reasons: reasons.join(' '),
    found_via: 'cartomundi serie/all',
    status: 'pending',
    review_note:
      `${sheets} sheets CATALOGUED (not necessarily digitised — CartoMundi is a union catalogue). ` +
      `Scale ${scale ? '1:' + scale.toLocaleString() : '?'}, ${zone}. ` +
      `Sheet list: /ctmd-services/serie/${s.skey}/feuilles — number, title, date and catalogue extent per sheet. ` +
      `NO GEOREFERENCE is provided, only a ~1 arcminute catalogue extent; warping is still ours to do. ` +
      `Images are Nakala IIIF, licence is per-item (sample was CC-BY-4.0).` +
      (HELD.has(s.skey)
        ? ' ALREADY IN THE ARCHIVE as "Indochine 1:25,000 — Tonkin & Thanh Hóa".'
        : ''),
    raw: {
      skey: s.skey,
      zone,
      scale,
      sheets,
      subtitle: s.s8SousTitre || null,
      complement: s.s51ComplementTitre || null,
      projection: s.s11ProjectionEllipsoideDatum || null,
      sheet_size: s.s17DimensionFeuille || null,
      cell_size: s.s22FormatUniteDecoupage || null,
      note: s.s8NoteGenerale || null,
      titles: (s.serieTitres || []).map((t) => t.s50TitreSerie),
      holders: (s.etablissementDetenteurs || []).map((e) => ({
        name: e.et70Etablissement,
        city: e.et71Ville,
        nakala_series: e.et75IdCollecNakalaSeries || null,
      })),
      feuilles_api: `https://www.cartomundi.fr/ctmd-services/serie/${s.skey}/feuilles`,
    },
  };
});

rows.sort((a, b) => b.score - a.score);
console.log(`\n${'score'.padStart(5)} ${'sheets'.padStart(6)}  title`);
for (const r of rows)
  console.log(
    `${String(r.score).padStart(5)} ${String(r.raw.sheets).padStart(6)}  ${r.title.slice(0, 52)}`
  );

if (dry) {
  console.log('\ndry run — nothing written. Re-run with --apply.');
  process.exit(0);
}

const { error } = await db
  .from('scout_candidates')
  .upsert(rows, { onConflict: 'source,external_id' });
if (error) throw error;
console.log(`\nupserted ${rows.length} rows into scout_candidates (source=cartomundi)`);
