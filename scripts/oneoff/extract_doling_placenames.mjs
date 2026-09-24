#!/usr/bin/env node
// Colonial -> modern place-name pairs out of Tim Doling's Historic Vietnam.
//
//   node scripts/oneoff/extract_doling_placenames.mjs --check      # self-check, no I/O
//   node scripts/oneoff/extract_doling_placenames.mjs --xml <path>
//   node scripts/oneoff/extract_doling_placenames.mjs --press       # + the two feeds
//
// SOURCE, AND THE ONLY TERMS IT CARRIES. Tim Doling, *Historic Vietnam*
// (https://www.historicvietnam.com), WordPress export 2026-01-23, 269 posts
// dated 2013-11-03 to 2026-01-23. Given to the archive by the author, who
// agreed on 2026-09-22 to be cited. Every row this writes carries the post
// title, date and URL it came from; nothing is emitted without them. If a row
// ever reaches the database, it goes in with that provenance and a source tag,
// never merged indistinguishably with a name read off a sheet -- Doling is a
// careful secondary source, not a cartographic one, and the gazetteer has to be
// able to say which is which.
//
// THIS SCRIPT DOES NOT TOUCH THE DATABASE. It reads one XML file and writes one
// CSV for a human -- ideally Doling himself -- to mark up. That is why it has
// no --apply: there is nothing here to apply. `street-name-pairs` in
// docs/ROADMAP.md said this work "needs the source data, not code"; this is the
// source data arriving, and the review is still a person's job.
//
// WHAT IT DOES NOT DO. It finds the three sentence shapes Doling actually
// writes in -- "rue Catinat (now Dong Khoi street)" and its two variants. It
// will not find a rename stated across two sentences, or in a photo caption, or
// implied by a date range. Expect this to under-report, and expect roughly one
// row in five to be wrong in `kind` rather than in the pair itself.
//
// WHAT `--press` IS FOR. `docs/ROADMAP.md`'s `press-from-gazetteer` says the
// press lookup should be fed attested names "instead of its three guessed
// spelling forms", and records it as "waiting only on a corpus with more than
// one map OCR'd". These pairs route around that wait: they are attested
// spellings from a dated, citable source, available before the OCR drain runs.
// `src/lib/server/gallica.ts:60` already names the exact gap -- "historical
// renamings ('rue de Canton' -> 'Trieu Quang Phuc') are still not derivable
// from spelling ... those come from the gazetteer too, once someone links
// them." This run produced `rue de Canton -> Ham Nghi boulevard`. That is the
// link, from the source the comment was waiting for.
//
// THE TWO ARCHIVES TAKE DIFFERENT FEEDS, because they are different things.
// Gallica has OCR'd full text and takes `extra` spellings per place name
// (`spellingVariants`), so it gets JSON keyed by the modern name. The NLV
// archive has NO TEXT -- `docs/pipelines.md` is explicit: "There is no text,
// only the scan". It can only be queried with a phrase, so it gets a quoted
// query list in the form `scripts/nlv-queries.txt` already uses. Neither file
// is applied by this script; both are inputs a person reviews first.
//
// ONE TRAP WORTH NAMING, because it is the reason `kind` exists. "rue
// Chasseloup-Laubat, now the Labour Culture Palace" is not a street rename --
// it is a building that stands where the street was. Same for "boulevard
// Galliani (now 606 Tran Hung Dao)", which is an address. Mixing those into a
// street-name table would put a building's name on a street centreline. So
// every row is classified street | address | building | unclear, and only
// `street` is a candidate for `street-name-pairs`.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import assert from 'node:assert/strict';
import { flag, opt } from '../lib/cli.mjs';

const DEFAULT_XML = '/Users/airm1/Work/Personal/Backups/historicvietnam.WordPress.2026-01-23.xml';
const OUT = 'work/doling/street-name-pairs.csv';

// The French generics Doling uses. The colonial side must start with one of
// these -- it is the single filter that does the most work, because without it
// "a piece of wood (now part of a bed)" scores as a place-name pair.
const GENERIC = 'rue|boulevard|bd|avenue|quai|place|canal|pont|impasse|chemin|route';
const VN = '[A-Z\\u00C0-\\u1EF9][\\w\\u00C0-\\u1EF9]*';

const PATTERNS = [
  // rue Catinat (now Dong Khoi street)
  {
    name: 'X (now Y)',
    re: new RegExp(
      `((?:${GENERIC})\\s+[^,.;()]{2,45}?)\\s*\\(\\s*(?:now|today|modern|present[- ]day)\\s+([^)]{2,50})\\)`,
      'gi'
    ),
    order: 'fwd',
  },
  // rue Mac-Mahon, now Nam Ky Khoi Nghia
  {
    name: 'X, now Y',
    re: new RegExp(
      `((?:${GENERIC})\\s+[^,.;()]{2,45}?),\\s*(?:now|today)\\s+((?:the\\s+)?${VN}(?:\\s+${VN}){0,4})`,
      'gi'
    ),
    order: 'fwd',
  },
  // Ly Tu Trong street (formerly rue de La Grandiere)
  {
    name: 'Y (formerly X)',
    re: new RegExp(
      `((?:the\\s+)?${VN}(?:\\s+${VN}){0,4})\\s*\\(\\s*(?:formerly|previously|then)\\s+((?:${GENERIC})[^)]{2,50})\\)`,
      'gi'
    ),
    order: 'rev',
  },
];

const BUILDING =
  /\b(hotel|palace|museum|building|church|cathedral|hospital|school|market|station|theatre|theater|hall|pagoda|tower|centre|center|bank|club|villa)\b/i;

/** @param {string} s */
function classify(modern) {
  if (/^\s*\d/.test(modern)) return 'address';
  if (BUILDING.test(modern)) return 'building';
  if (/\b(street|boulevard|avenue|square|road|quay|canal|bridge)\b/i.test(modern)) return 'street';
  // A bare Vietnamese proper noun after "now" is a street far more often than
  // not in this corpus, but it is the case most likely to be wrong.
  return 'unclear';
}

/** @param {string} s */
const tidy = (s) =>
  s
    // Quote characters of any flavour, straight or curly. Not U+2019, which is
    // French orthography -- `rue d\u2019Adran` -- and not a stray character.
    .replace(/["\u201c\u201d\u201e\u00ab\u00bb]/g, '')
    .replace(/\s+/g, ' ')
    .replace(/^(?:the|a)\s+/i, '')
    .replace(/[\s,;:]+$/, '')
    .trim();

/** @param {string} s */
const key = (s) =>
  tidy(s)
    .toLowerCase()
    .replace(/\s+(street|boulevard|avenue|square|road)$/i, '');

// ponytail: entity table covers what this export actually contains, not HTML5.
// Swap in a real decoder if the corpus ever widens.
const ENTITIES = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  rsquo: '’',
  lsquo: '‘',
  ldquo: '“',
  rdquo: '”',
  ndash: '–',
  mdash: '—',
  hellip: '…',
  eacute: 'é',
  egrave: 'è',
};

/** @param {string} html */
export function toText(html) {
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&([a-z]+);/gi, (m, n) => ENTITIES[n.toLowerCase()] ?? m)
    .replace(/\s+/g, ' ')
    .trim();
}

// ponytail: regex over a known 13 MB export beats adding an XML dependency for
// one file. Ceiling: a post whose body contains `]]>` is split across CDATA
// sections by WordPress and this would truncate it. None do today -- if the
// post count below ever drops, that is the reason, and the fix is a real parser.
/** @param {string} xml */
export function posts(xml) {
  const out = [];
  for (const [, item] of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const pick = (tag) => {
      const m = item.match(
        new RegExp(`<${tag}>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${tag}>`)
      );
      return m ? m[1].trim() : '';
    };
    if (pick('wp:post_type') !== 'post') continue;
    if (pick('wp:status') !== 'publish') continue;
    out.push({
      title: toText(pick('title')),
      url: pick('link'),
      date: pick('wp:post_date').slice(0, 10),
      text: toText(pick('content:encoded')),
    });
  }
  return out;
}

/** @param {{title:string,url:string,date:string,text:string}[]} docs */
export function pairs(docs) {
  /** @type {Map<string, any>} */
  const seen = new Map();
  for (const doc of docs) {
    for (const { name, re, order } of PATTERNS) {
      for (const m of doc.text.matchAll(re)) {
        const colonial = tidy(order === 'fwd' ? m[1] : m[2]);
        const modern = tidy(order === 'fwd' ? m[2] : m[1]);
        if (!colonial || !modern) continue;
        if (key(colonial) === key(modern)) continue;
        const k = `${key(colonial)}\u0000${key(modern)}`;
        const row = seen.get(k);
        if (row) {
          row.sightings += 1;
          continue;
        }
        const at = m.index ?? 0;
        seen.set(k, {
          colonial,
          modern,
          kind: classify(modern),
          pattern: name,
          sightings: 1,
          evidence: doc.text.slice(Math.max(0, at - 60), at + m[0].length + 60).trim(),
          post_title: doc.title,
          post_date: doc.date,
          post_url: doc.url,
        });
      }
    }
  }
  return [...seen.values()].sort(
    (a, b) => b.sightings - a.sightings || a.colonial.localeCompare(b.colonial)
  );
}

const csv = (rows) => {
  const cols = [
    'colonial',
    'modern',
    'kind',
    'pattern',
    'sightings',
    'evidence',
    'post_title',
    'post_date',
    'post_url',
  ];
  const q = (v) => `"${String(v).replace(/"/g, '""')}"`;
  return [cols.join(','), ...rows.map((r) => cols.map((c) => q(r[c])).join(','))].join('\n') + '\n';
};

/**
 * Gallica takes attested spellings per place name via `spellingVariants(name,
 * extra)`. Key by the MODERN name, because that is what a reader searches and
 * what `/api/press` is called with; the colonial forms are the value. Gallica
 * caps at 8 variants and its own OCR is mostly unaccented, so the accented
 * form is kept -- `spellingVariants` unaccents it itself.
 */
/**
 * `rue Capitaine Faucon -> Tr\u1ea7n Quang Di\u1ec7u and Tr\u1ea7n Huy Li\u1ec7u streets` is a true
 * statement and a useless query: one colonial street became two, and neither
 * archive can be asked for the pair. Compounds stay in the review CSV, because
 * a person should see them, and stay out of both feeds.
 */
const compound = (s) => /\s(?:and|or)\s/i.test(s);

export function gallicaVariants(rows) {
  /** @type {Record<string, {variants: string[], source: string}>} */
  const out = {};
  for (const r of rows) {
    if (r.kind !== 'street' && r.kind !== 'unclear') continue;
    if (compound(r.colonial) || compound(r.modern)) continue;
    const modern = r.modern.replace(/\s+(street|boulevard|square|avenue)$/i, '').trim();
    if (!modern) continue;
    const bare = r.colonial.replace(
      /^(?:rue|boulevard|bd|avenue|quai|place|canal|pont|impasse|chemin|route)\s+(?:de\s+la\s+|de\s+|du\s+|des\s+|d\u2019|d')?/i,
      ''
    );
    const forms = [r.colonial, bare].map((s) => s.trim()).filter(Boolean);
    const e = (out[modern] ??= { variants: [], source: r.post_url });
    for (const f of forms) if (!e.variants.includes(f)) e.variants.push(f);
  }
  return out;
}

/**
 * The NLV archive has no full text, so a name is only ever a phrase to search
 * for. Quoted, because `txq` ANDs an unquoted query's words and returns
 * thousands of pages carrying each word anywhere -- the mistake
 * `scripts/nlv-queries.txt` documents at length. Both sides go in: the French
 * form for the colonial press, the Vietnamese one for post-1975 titles.
 */
export function nlvQueries(rows) {
  const lines = [
    '# Street names attested in Tim Doling, Historic Vietnam (historicvietnam.com),',
    '# cited with permission. Generated by scripts/oneoff/extract_doling_placenames.mjs.',
    '#',
    '# QUOTED, for the reason scripts/nlv-queries.txt gives: txq ANDs an unquoted',
    '# query. Unlike the map vocabulary in that file, a street name IS a good query',
    '# term -- the press prints addresses. Counts are not measured yet; run the',
    '# harvest with --report to fill them in.',
    '',
  ];
  const seen = new Set();
  for (const r of rows) {
    if (r.kind === 'building') continue;
    if (compound(r.colonial) || compound(r.modern)) continue;
    for (const [side, era] of [
      [r.colonial, 'colonial'],
      [r.modern, 'modern'],
    ]) {
      const q = side
        .replace(/^\d+[-\d]*\s+/, '')
        .replace(/\s+(street|boulevard|square|avenue)$/i, '')
        .trim();
      if (q.length < 4 || seen.has(q.toLowerCase())) continue;
      seen.add(q.toLowerCase());
      lines.push(`"${q}"${' '.repeat(Math.max(1, 34 - q.length))}# ${era}`);
    }
  }
  return lines.join('\n') + '\n';
}

function check() {
  const doc = [
    {
      title: 'T',
      url: 'u',
      date: '2020-01-01',
      text:
        'The old rue Catinat (now Đồng Khởi street) ran north. ' +
        'He lived on rue Mac-Mahon, now Nam Kỳ Khởi Nghĩa. ' +
        'Lý Tự Trọng street (formerly rue de La Grandière) is short. ' +
        'rue Chasseloup-Laubat, now the Labour Culture Palace, closed. ' +
        'boulevard Galliéni (now 606 Trần Hưng Đạo) stands. ' +
        'He found a piece of wood (now part of a bed) there. ' +
        'The old \u201crue Catinat\u201d (now \u0110\u1ed3ng Kh\u1edfi street) again. ' +
        'rue Capitaine Faucon (now Tr\u1ea7n Quang Di\u1ec7u and Tr\u1ea7n Huy Li\u1ec7u streets) split.',
    },
  ];
  const got = pairs(doc);
  const find = (c) => got.find((r) => r.colonial.toLowerCase().startsWith(c));
  assert.equal(toText('a &amp; b &#8217;s'), 'a & b ’s');
  assert.ok(find('rue catinat'), 'X (now Y) must match');
  assert.equal(find('rue catinat').kind, 'street');
  assert.ok(find('rue mac-mahon'), 'X, now Y must match');
  assert.ok(find('rue de la grandi'), 'Y (formerly X) must match, reversed');
  assert.equal(find('rue chasseloup').kind, 'building', 'a palace is not a street rename');
  assert.equal(find('boulevard galli').kind, 'address', 'a house number is not a street rename');
  assert.ok(
    !got.some((r) => /piece of wood/i.test(r.colonial + r.modern)),
    'no French generic, no row'
  );
  assert.ok(
    got.every((r) => r.post_url && r.post_date),
    'every row carries its citation'
  );
  const gv = gallicaVariants(got);
  assert.ok(gv['Đồng Khởi'], 'gallica feed keyed by the modern name');
  assert.ok(gv['Đồng Khởi'].variants.includes('rue Catinat'), 'full colonial form kept');
  assert.ok(gv['Đồng Khởi'].variants.includes('Catinat'), 'bare form too — OCR drops the generic');
  assert.ok(!gv['Labour Culture Palace'], 'a building is not a street variant');
  assert.ok(
    gv['\u0110\u1ed3ng Kh\u1edfi'].variants.every((v) => !/["\u201c\u201d]/.test(v)),
    'no quote character reaches the CQL'
  );
  assert.ok(!Object.keys(gv).some((k) => /\sand\s/i.test(k)), 'a compound is not one place name');

  const nq = nlvQueries(got);
  assert.ok(/^"rue Catinat"/m.test(nq), 'nlv queries are quoted');
  assert.ok(/^"Đồng Khởi"/m.test(nq), 'both sides of the pair are queryable');
  assert.ok(!/^"606 /m.test(nq), 'a house number is not a press query');

  console.log(
    `self-check ok — ${got.length} rows, ${Object.keys(gv).length} gallica keys from the fixture`
  );
}

if (flag('--check')) {
  check();
} else {
  const xml = resolve(opt('--xml') ?? DEFAULT_XML);
  const docs = posts(readFileSync(xml, 'utf8'));
  const rows = pairs(docs);
  const out = opt('--out') ?? OUT;
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, csv(rows));

  const by = (k) => rows.filter((r) => r.kind === k).length;
  console.log(
    `${docs.length} published posts, ${docs.reduce((n, d) => n + d.text.length, 0).toLocaleString()} chars`
  );
  console.log(
    `${rows.length} candidate pairs — street ${by('street')}, unclear ${by('unclear')}, building ${by('building')}, address ${by('address')}`
  );
  console.log(`→ ${out}`);

  if (flag('--press')) {
    const gv = gallicaVariants(rows);
    writeFileSync('work/doling/gallica-variants.json', JSON.stringify(gv, null, 2) + '\n');
    writeFileSync('work/doling/nlv-queries.txt', nlvQueries(rows));
    console.log(`→ work/doling/gallica-variants.json (${Object.keys(gv).length} place names)`);
    console.log('→ work/doling/nlv-queries.txt');
  }

  console.log('Source: Tim Doling, Historic Vietnam (historicvietnam.com), cited with permission.');
  console.log('Nothing was written to the database; this is a review sheet.');
}
