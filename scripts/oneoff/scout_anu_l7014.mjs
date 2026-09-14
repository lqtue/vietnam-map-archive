/**
 * scout_anu_l7014.mjs — what the ANU repository holds of AMS Series L7014.
 *
 *   node --env-file=.env scripts/oneoff/scout_anu_l7014.mjs
 *
 * Read-only on both ends: it pages the ANU DSpace API and reads our own index,
 * and writes one JSON report to work/l7014/anu-sources.json. It fetches no
 * scans and changes no row.
 *
 * Why a third source matters. `series_sheets.source` says where a cell we do
 * not hold could be got, and for all 123 of ours it says TTU — because TTU is
 * the only place anyone looked. ANU states its rights plainly ("Copyright
 * expired", open access), which TTU does not, so for any cell both hold, ANU
 * is the better provenance even when it is not the only one.
 *
 * NUMBERING. ANU titles the quadrant in Roman ("Sheet 6027 II"); we number it
 * in arabic ("6027-2"). They are the same cell — the numeral is the quadrant of
 * the 1:100,000 sheet, NOT an edition, which at least one secondary source gets
 * wrong. Sheet numbers in the titles carry irregular spacing ("Sheet  6027 II"
 * with two spaces), so the parse is a regex over the whole title rather than a
 * split.
 */
import { createClient } from '@supabase/supabase-js';
import { writeFileSync } from 'node:fs';

const SCOPE = 'cccec9bf-da69-449f-8946-03d79d6063f9';
const API = 'https://openresearch-repository.anu.edu.au/server/api/discover/search/objects';
const OUT = 'work/l7014/anu-sources.json';
const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };

const first = (md, key) => md?.[key]?.[0]?.value ?? null;

/** "Vietnam, Gia Rai, Series: L7014, Sheet  6027 II, 1966, 1:50 000" -> 6027-2
 *
 * 21 of the 160 titles spell the Roman numeral with lowercase L — "Sheet 6738
 * lll", "6631 lV", "6539 Il" — which is a typist reaching for the nearest key,
 * not a different numbering. Fold `l` to `I` before reading it, or an eighth of
 * the collection silently fails to match a cell and reads as ANU not holding it.
 *
 * The collection's index sheet ("Vietnam INDEX, 1:50 000, Series: L7014") has
 * no cell at all and correctly returns null. */
function cellOf(title) {
  const m = /Sheet\s+(\d{4})\s*([IVl]{1,3})(?=[,\s]|$)/i.exec(title || '');
  if (!m) return null;
  const q = ROMAN[m[2].replace(/l/g, 'I').toUpperCase()];
  return q ? `${m[1]}-${q}` : null;
}

const items = [];
for (let page = 0; ; page++) {
  const res = await fetch(`${API}?scope=${SCOPE}&size=100&page=${page}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`ANU page ${page}: HTTP ${res.status}`);
  const sr = (await res.json())._embedded?.searchResult;
  const objs = sr?._embedded?.objects ?? [];
  for (const o of objs) {
    const it = o._embedded.indexableObject;
    const md = it.metadata;
    items.push({
      cell: cellOf(it.name),
      title: it.name,
      uuid: it.uuid,
      url: first(md, 'dc.identifier.uri'),
      issued: first(md, 'dc.date.issued'),
      publisher: first(md, 'dc.publisher'),
      rights: first(md, 'dc.rights'),
      access: first(md, 'dcterms.accessRights'),
      notes: first(md, 'local.description.notes'),
      series: first(md, 'dc.relation.ispartofseries'),
    });
  }
  const p = sr?.page;
  if (!p || page + 1 >= p.totalPages) break;
}
console.log(`ANU items: ${items.length}`);

const unparsed = items.filter((i) => !i.cell);
if (unparsed.length) {
  console.log(`\ntitles whose sheet number did not parse: ${unparsed.length}`);
  unparsed.slice(0, 8).forEach((i) => console.log('  ' + i.title));
}

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data: ours, error } = await db
  .from('series_sheets')
  .select('sheet_number,name,held_by,source,year,edition')
  .eq('series_key', 'series-l7014-vietnam-1-50-000')
  .limit(2000);
if (error) throw new Error(error.message);
const by = new Map(ours.map((r) => [r.sheet_number, r]));

const held = [],
  fillsTTU = [],
  fillsNone = [],
  notInIndex = [];
for (const i of items) {
  if (!i.cell) continue;
  const r = by.get(i.cell);
  if (!r) notInIndex.push(i);
  else if (r.held_by) held.push(i);
  else if (r.source) fillsTTU.push(i);
  else fillsNone.push(i);
}
const cells = new Set(items.map((i) => i.cell).filter(Boolean));

console.log(`\ndistinct cells at ANU:            ${cells.size}`);
console.log(`  we already hold:                ${held.length}`);
console.log(`  gap, TTU was the only source:   ${fillsTTU.length}`);
console.log(`  gap, NO known scan until now:   ${fillsNone.length}`);
console.log(`  not in our index at all:        ${notInIndex.length}`);
for (const i of notInIndex.slice(0, 10)) console.log(`    ${i.cell}  ${i.title}`);

const years = items
  .map((i) => i.issued)
  .filter(Boolean)
  .sort();
console.log(`\nissued range: ${years[0]} … ${years.at(-1)}`);
const tally = (f) => {
  const t = {};
  for (const i of items) {
    const v = i[f] ?? '(none)';
    t[v] = (t[v] ?? 0) + 1;
  }
  return Object.entries(t).sort((a, b) => b[1] - a[1]);
};
for (const f of ['rights', 'access', 'publisher']) {
  console.log(`\n${f}:`);
  for (const [k, v] of tally(f).slice(0, 6)) console.log(`  ${String(v).padStart(4)}  ${k}`);
}

writeFileSync(
  OUT,
  JSON.stringify({ fetched: new Date().toISOString(), scope: SCOPE, items }, null, 2)
);
console.log(`\nwritten to ${OUT}`);
