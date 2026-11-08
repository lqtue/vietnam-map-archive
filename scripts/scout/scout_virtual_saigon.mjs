#!/usr/bin/env node
// Scout Virtual Saigon (IAO / Virtual Cities Project) from saved Wayback pages. The site is down.
// OFFLINE and READ-ONLY: it reads HTML files you saved with curl, never the network, never the DB.
// Output: scripts/scout_virtual_saigon_<ts>.json, same row shape as scout_humazur.mjs.
//
//   node scripts/scout/scout_virtual_saigon.mjs --ids <dir>      # IDs on saved list pages (Maps_Source_*.html)
//   node scripts/scout/scout_virtual_saigon.mjs --records <dir>  # saved record pages + list pages -> JSON (full records, plus title-and-year rows for the rest)
//   node scripts/scout/scout_virtual_saigon.mjs --selftest <dir>
//
// Terms (virtual-saigon.net/Project/Rules_and_Conditions): free, non-commercial, cite the original
// author, no high-res files of items that are not theirs. So rows carry metadata and the HOLDER's
// link, never a scan. The date is the site's, not ours; `raw.dateNote` says so.

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const unwrap = (u) => u.replace(/^https?:\/\/web\.archive\.org\/web\/\d+[a-z_]*\//, '');
const text = (h) =>
  h
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

// The record page is a label/value table; read it by structure, not by text order.
export function parseRecord(html) {
  const f = {};
  for (const m of html.matchAll(
    /<td class="defaultDocTableLabel">([^<]*)<\/td><td class="defaultDocTableContent[^"]*">([\s\S]*?)<\/td><\/tr>/g
  )) {
    const k = text(m[1]);
    if (!(k in f)) f[k] = text(m[2]);
    if (k === 'URL') {
      const a = m[2].match(/href="([^"]+)"/);
      if (a) f.URL = unwrap(a[1]);
    }
  }
  return f;
}

// List pages: page 1 is a thumbnail grid, pages 2-9 a table. Both give ID, title and year.
export function parseList(html) {
  const out = new Map();
  for (const m of html.matchAll(
    /<td>(\d+)<\/td><td><a href="\?ID=\1">([^<]*)<\/a><\/td><td>([^<]*)<\/td><td>([^<]*)<\/td>/g
  ))
    out.set(m[1], { title: text(m[2]), year: text(m[3]), yearRange: text(m[4]) });
  for (const m of html.matchAll(
    /Document ID : (\d+)<br><a href="\?ID=\1">([^<]*)<\/a><br>((?:[A-Za-z ]+ : [^<]*<br>)*)/g
  )) {
    const g = (k) => m[3].match(new RegExp(`${k} : ([^<]*)<br>`))?.[1] || '';
    out.set(m[1], { title: text(m[2]), year: text(g('Year')), yearRange: text(g('Year range')) });
  }
  return out;
}

const HOLDERS = [
  [
    /Vietnam Archive Map Collection|Vietnam Center and Archive/i,
    'Vietnam Center and Archive, Texas Tech',
  ],
  [/IAO Map Collection|Fonds Philippe Langlet/i, 'IAO (Lyons Institute of East Asian Studies)'],
];

export function toScoutRow(f) {
  const id = f['Document ID'];
  const blob = `${f.Comments || ''} ${f.Keywords || ''}`;
  const holder = HOLDERS.find(([re]) => re.test(blob))?.[1] || '';
  return {
    source: 'virtual-saigon',
    externalId: id,
    title: f['Original title'] || '',
    creator: f['Author(s)'] || f['Cartographer(s)'] || '',
    publisher: f.Publisher || '',
    date: f.Year || f['Year range'] || '',
    rights: 'unknown (site: free, non-commercial, cite author)',
    language: f.Language || '',
    holding_institution: holder,
    manifestUrl: '',
    sourceUrl: `https://virtual-saigon.net/maps/source?ID=${id}`,
    thumbnail: '',
    foundVia: ['virtual-saigon:wayback'],
    dedupKey: `virtual-saigon:${id}`,
    raw: {
      collection: f.Collection || '',
      scale: f.Scale || '',
      size: f.Size || '',
      edition: f.Edition || '',
      support: f['Map support'] || '',
      comments: f.Comments || '',
      keywords: f.Keywords || '',
      holderUrl: f.URL || '',
      digitized: f['Digitized file'] || '',
      dateNote: 'date as given by Virtual Saigon; not checked against the sheet',
    },
  };
}

const [mode, dir] = [process.argv[2], process.argv[3]];
const files = (re) => (dir ? readdirSync(dir).filter((n) => re.test(n)) : []);

if (mode === '--ids') {
  const ids = new Set();
  for (const n of files(/^Maps_Source.*\.html$/))
    // page 1 is a thumbnail grid, pages 2-9 a table; both link each record as href="?ID=n"
    for (const m of readFileSync(join(dir, n), 'utf8').matchAll(/href="\?ID=(\d+)"/g))
      ids.add(m[1]);
  console.log([...ids].sort((a, b) => a - b).join(' '));
  console.error(
    `${ids.size} ids from ${files(/^Maps_Source.*\.html$/).length} list pages (expect 532)`
  );
} else if (mode === '--records' || mode === '--selftest') {
  // A saved record page that Wayback never archived is an error page with no table: skip it.
  const rows = files(/^maps_source_ID_\d+\.html$/)
    .map((n) => readFileSync(join(dir, n), 'utf8'))
    .filter((h) => h.includes('defaultDocTableLabel'))
    .map((h) => toScoutRow(parseRecord(h)));
  const full = rows.length;
  // Every other ID on the list pages becomes a title-and-year row, so the 532 are all counted.
  const list = new Map();
  for (const n of files(/^Maps_Source.*\.html$/))
    for (const [id, v] of parseList(readFileSync(join(dir, n), 'utf8'))) list.set(id, v);
  const have = new Set(rows.map((x) => x.externalId));
  for (const [id, v] of list)
    if (!have.has(id)) {
      const r = toScoutRow({
        'Document ID': id,
        'Original title': v.title,
        Year: v.year,
        'Year range': v.yearRange,
      });
      r.raw.titleOnly = true; // no full record in Wayback: no publisher, scale or holder
      rows.push(r);
    }
  if (mode === '--selftest') {
    console.assert(list.size === 532, `list has ${list.size}, expected 532`);
    console.assert(
      list.get('833')?.title === 'Plan de la ville de Saigon' && list.get('833').year === '1948',
      'list 833 (grid)'
    );
    console.assert(
      list.get('1092')?.title === 'Sài Gòn' && list.get('1092').year === '1968',
      'list 1092 (table)'
    );
    console.assert(list.get('1054')?.yearRange === '1950-1960', 'list 1054 year range');
    const r = Object.fromEntries(rows.map((x) => [x.externalId, x]));
    console.assert(r[1054]?.publisher === 'Tiếng Chuông', 'publisher 1054');
    console.assert(
      r[1054].date === '1950-1960' && r[1054].raw.scale === '1:20 000',
      'date/scale 1054'
    );
    console.assert(r[1054].holding_institution.includes('Texas'), 'holder 1054');
    console.assert(
      r[1054].raw.holderUrl.startsWith('http://www.flickr.com/'),
      'holder url unwrapped'
    );
    console.assert(r[836].date === '1965' && r[836].holding_institution.startsWith('IAO'), '836');
    console.assert(r[855].publisher.startsWith('Nha Địa-Dư'), '855');
    console.log(
      `selftest ran on ${rows.length} rows (${full} full records, ${list.size} on the list)`
    );
  } else {
    const out = `scripts/scout_virtual_saigon_${Date.now()}.json`;
    writeFileSync(out, JSON.stringify(rows, null, 1));
    const n = (p) => rows.filter(p).length;
    console.log(
      `${rows.length} rows (${full} full records, ${rows.length - full} title and year only) -> ${out}`
    );
    console.log(
      `  with a date ${n((x) => x.date)}, a scale ${n((x) => x.raw.scale)}, a holder ${n((x) => x.holding_institution)}, a holder link ${n((x) => x.raw.holderUrl)}`
    );
  }
} else {
  console.error('usage: --ids <dir> | --records <dir> | --selftest <dir>');
  process.exit(1);
}
