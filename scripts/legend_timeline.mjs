#!/usr/bin/env node
// Match the numbered legends of the Saigon sheets to each other, so the same
// institution can be followed across the four dates the corpus carries:
//
//   1878 Plan de la Ville de Saigon      29 entries   French
//   1923 Saigon - Cholon                182            French
//   1942 Plan de Saigon - Cho Lon       235            French
//   1959 Đô thành Sài Gòn               156            Vietnamese
//
// That last one is why this is not a string join. The city renamed its
// institutions between 1942 and 1959, so `Marché de Binh Tây` has to meet
// `Chợ Bình Tây` and `Hôpital Grall` has to meet `Bệnh-viện Đồn Đất (Grall)`.
// Both halves of every legend entry are regular — `<type> <proper name>` — so
// the match is (canonical type, folded proper name), with the type lexicon
// below carrying the French↔Vietnamese pairs and nothing else being translated.
//
// ponytail: a lexicon of ~25 type words, not a translation model. The proper
// name is a proper name in both languages (Bình Tây, Khánh Hội, Grall, Phúc
// Kiến), which is what makes this work at all. The ceiling is an institution
// whose *name* was also changed, not just its type word — those land in the
// unmatched list on purpose rather than being guessed at.
//
// Usage:
//   node scripts/legend_timeline.mjs --selftest
//   node scripts/legend_timeline.mjs                 # read DB, write work/legend/
//   node scripts/legend_timeline.mjs --report

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';

const OUT_DIR = 'work/legend';
const ENTRIES = `${OUT_DIR}/entries.json`;
const TIMELINE = `${OUT_DIR}/timeline.json`;

/** map_id → the sheet's year. The four sheets that carry a numbered legend. */
const SHEETS = {
  'dc2eda7d-a4c7-47ff-81b0-af6ec07dd012': 1878,
  '1bce28f0-aa82-48eb-8e33-8f0b07182c2f': 1923,
  'eca788e5-6780-4dca-bf23-7651a1c48aba': 1942,
  '34d4edb2-f7df-4c47-a65a-f6b471400396': 1959,
};

/**
 * Canonical type ← the words the two languages use for it. Longest first, since
 * `bảo-sanh viện` must win over `viện` and `palais de justice` over `palais`.
 * A type present in only one language is still worth listing: it keeps the type
 * out of the proper name, which is what the match key is built from.
 */
const TYPES = [
  [
    'hospital',
    [
      'bảo-sanh viện',
      'bệnh-viện',
      'bệnh viện',
      'y-viện',
      'nhà thương',
      'hôpital',
      'hopital',
      'clinique',
      'infirmerie',
    ],
  ],
  ['court', ['tòa án', 'toà án', 'tòa-án', 'palais de justice', 'justice de paix', 'tribunal']],
  // `poste de police` before anything matching bare `poste`, or a police post
  // becomes a post office and can never meet a 1959 `Cảnh-Sát-cuộc`.
  [
    'police',
    [
      'cảnh-sát-cuộc',
      'cảnh sát cuộc',
      'cảnh-sát',
      'poste de police',
      'commissariat de police',
      'commissariat',
      'sûreté',
      'surete',
      'gendarmerie',
    ],
  ],
  [
    'school',
    ['trường', 'truong', 'école', 'ecole', 'lycée', 'lycee', 'collège', 'college', 'institut'],
  ],
  ['market', ['chợ', 'cho', 'marché', 'marche', 'halles']],
  ['cemetery', ['nghĩa-địa', 'nghĩa địa', 'nghĩa-trang', 'nghĩa trang', 'cimetière', 'cimetiere']],
  [
    'church',
    [
      'nhà-thờ',
      'nhà thờ',
      'thánh-đường',
      'cathédrale',
      'cathedrale',
      'église',
      'eglise',
      'chapelle',
      'evêché',
      'eveche',
    ],
  ],
  ['pagoda', ['chùa', 'đình', 'miếu', 'pagode', 'temple']],
  ['ministry', ['bộ', 'ministère', 'ministere', 'secrétariat d’état', 'secretariat']],
  [
    'post',
    ['bưu-điện', 'nhà dây thép', 'bureau de poste', 'poste aux lettres', 'poste', 'télégraphe'],
  ],
  ['directorate', ['nha', 'direction', 'service', 'bureaux', 'bureau', 'office']],
  ['theatre', ['hý-viện', 'hý viện', 'rạp', 'théâtre', 'theatre', 'cinéma', 'cinema']],
  ['park', ['công-viên', 'công viên', 'vườn', 'parc', 'square', 'jardin']],
  ['station', ['ga', 'gare']],
  ['prison', ['khám-đường', 'khám đường', 'prison centrale', 'prison', 'maison centrale']],
  ['abattoir', ['lò sát-sanh', 'lò sát sanh', 'abattoir']],
  ['bank', ['ngân-hàng', 'ngân hàng', 'banque', 'trésor', 'tresor']],
  ['barracks', ['trại', 'caserne', 'camp', 'quartier militaire']],
  ['port', ['thương-khẩu', 'bến', 'port de commerce', 'port', 'quai', 'douane']],
  ['museum', ['viện bảo-tàng', 'bảo-tàng', 'musée', 'musee']],
  ['library', ['thư-viện', 'bibliothèque', 'bibliotheque']],
  ['consulate', ['lãnh-sự', 'consulat', 'légation', 'legation']],
  ['palace', ['dinh', 'palais', 'résidence', 'residence']],
  ['factory', ['hãng', 'nhà máy', 'usine', 'manufacture', 'brasserie', 'imprimerie']],
  ['club', ['câu-lạc-bộ', 'cercle', 'club']],
  ['housing', ['cư-xá', 'logements', 'cité', 'cite']],
  ['orphanage', ['cô nhi viện', 'cô-nhi-viện', 'orphelinat']],
];

/** Words that carry no identity — dropped before the proper name is keyed. */
const STOP = new Set([
  'de',
  'du',
  'des',
  'la',
  'le',
  'les',
  'd',
  'l',
  'et',
  'aux',
  'au',
  'a',
  'và',
  'cua',
  'của',
  'the',
]);

/** Lowercase, strip Vietnamese and French diacritics, collapse punctuation. Pure. */
export function fold(s) {
  return (s ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/gi, 'd')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/**
 * `"3. Bệnh-viện Đồn Đất (Grall)"` → number, canonical type, proper name, and
 * any parenthetical — which on the 1959 sheet is the French name the entry
 * replaced, and therefore a free cross-language anchor. Pure.
 */
export function parseEntry(raw) {
  const m = /^\s*(\d+)\s*[.．:)\-–]?\s*(.*)$/.exec(raw ?? '');
  const n = m ? Number(m[1]) : null;
  let rest = (m ? m[2] : (raw ?? '')).trim();

  const aliases = [...rest.matchAll(/\(([^)]+)\)/g)].map((x) => x[1].trim());
  rest = rest
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const folded = fold(rest);
  let type = '';
  let name = rest;
  for (const [canon, words] of TYPES) {
    const hit = words.find((w) => {
      const f = fold(w);
      return folded === f || folded.startsWith(f + ' ');
    });
    if (hit) {
      type = canon;
      name = rest
        .slice(0, rest.length)
        .replace(new RegExp(`^\\s*${escapeRe(hit)}`, 'i'), '')
        .trim();
      // The lexicon word may itself be spelled with different diacritics than
      // the entry; fall back to trimming by folded length when the slice missed.
      if (name === rest) name = rest.split(/\s+/).slice(fold(hit).split(' ').length).join(' ');
      break;
    }
  }
  // Drop the connector the type word leaves behind ("Marché de Binh Tây" →
  // "Binh Tây"). It has to come off `name` too, not just the key: `name` is
  // what gets sent to Gallica, and `adj "de Binh Tay"` is a different phrase.
  name = name.replace(/^(?:de\s+la|de\s+l['’]|des|du|de|d['’]|la|le|les|và|of|the)\s+/i, '').trim();
  const key = fold(name)
    .split(' ')
    .filter((w) => w && !STOP.has(w))
    .join(' ');
  return { n, raw: (raw ?? '').trim(), type, name, key, aliases };
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Entries → threads: one per institution, carrying what each year called it.
 * Matched on (type, key).
 *
 * Threads **partition** the entries — every entry belongs to exactly one — which
 * is what makes the counts in the report mean anything. A parenthetical that
 * names another thread is therefore recorded as a *link*, never merged in:
 * `Bệnh-viện Đồn Đất (Grall)` links to `Hôpital Grall` one-to-one and that is a
 * rename, but the four 1942 cemeteries carrying `(Phú Thọ)` link to the single
 * 1959 `Nghĩa-địa Phú Thọ` and that is a consolidation. Merging flattened the
 * second case into the first and claimed the same 1959 entry four times; the
 * link keeps the arity visible, which is the more interesting fact anyway.
 */
export function buildThreads(entries) {
  const threads = new Map();
  for (const e of entries) {
    if (!e.key) continue;
    const k = `${e.type}|${e.key}`;
    if (!threads.has(k))
      threads.set(k, { key: k, type: e.type, name: e.key, years: {}, links: [] });
    (threads.get(k).years[e.year] ??= []).push(e);
  }
  // An alias is a pointer to another thread of the same type, in another year.
  for (const t of threads.values()) {
    for (const [year, list] of Object.entries(t.years)) {
      for (const e of list) {
        for (const a of e.aliases) {
          const target = threads.get(`${e.type}|${fold(a)}`);
          if (!target || target === t) continue;
          const otherYears = Object.keys(target.years).filter((y) => y !== year);
          if (!otherYears.length) continue;
          t.links.push({
            to: target.key,
            via: a,
            from_year: Number(year),
            to_years: otherYears.map(Number),
          });
        }
      }
    }
  }
  return [...threads.values()];
}

async function loadFromDb() {
  const env = Object.fromEntries(
    readFileSync('.env', 'utf8')
      .split('\n')
      .filter((l) => l && !l.startsWith('#'))
      .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()])
  );
  const url = `${env.PUBLIC_SUPABASE_URL}/rest/v1/ocr_extractions?select=map_id,text,text_validated,status&category=eq.legend_entry&limit=2000`;
  const res = await fetch(url, {
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    },
  });
  if (!res.ok) throw new Error(`supabase http ${res.status}`);
  return (await res.json())
    .filter((r) => r.status !== 'rejected' && SHEETS[r.map_id])
    .map((r) => ({ year: SHEETS[r.map_id], raw: (r.text_validated ?? r.text ?? '').trim() }));
}

function selftest() {
  let bad = 0;
  const ok = (c, m) => {
    if (!c) {
      bad++;
      console.error(`  FAIL ${m}`);
    }
  };
  ok(
    fold('Bệnh-viện Đồn Đất') === 'benh vien don dat',
    `fold vietnamese: ${fold('Bệnh-viện Đồn Đất')}`
  );
  ok(fold("Cimetière d'Akas") === 'cimetiere d akas', `fold french: ${fold("Cimetière d'Akas")}`);

  const vi = parseEntry('3. Bệnh-viện Đồn Đất (Grall)');
  ok(vi.n === 3, 'number');
  ok(vi.type === 'hospital', `vi type, got ${vi.type}`);
  ok(vi.key === 'don dat', `vi key, got "${vi.key}"`);
  ok(vi.aliases[0] === 'Grall', 'parenthetical kept as alias');

  ok(
    parseEntry('141. Poste de Police de Phú Lâm').type === 'police',
    'a police post is police, not post'
  );
  ok(parseEntry('141. Poste de Police de Phú Lâm').key === 'phu lam', 'and keys on the place');
  ok(
    parseEntry('158. Bureau de Poste de Chợ Quán').type === 'post',
    'a post office is post, not a directorate'
  );
  ok(
    parseEntry('83. Bureaux des Chemins de fer').type === 'directorate',
    'a bare bureau is still a directorate'
  );

  const conn = parseEntry('211. Marché de Binh-Đông');
  ok(conn.name === 'Binh-Đông', `the connector comes off the name too, got "${conn.name}"`);
  ok(conn.key === 'binh dong', `and the key, got "${conn.key}"`);

  const fr = parseEntry('45. Hôpital Grall');
  ok(fr.type === 'hospital', `fr type, got ${fr.type}`);
  ok(fr.key === 'grall', `fr key, got "${fr.key}"`);

  const mkt = [parseEntry('90. Marché de Binh Tây'), parseEntry('15. Chợ Bình Tây')];
  ok(mkt[0].type === 'market' && mkt[1].type === 'market', 'both markets');
  ok(mkt[0].key === mkt[1].key, `market keys meet: "${mkt[0].key}" vs "${mkt[1].key}"`);

  // The pair that must NOT merge: same proper name, different institution.
  const clash = [parseEntry('8. Bệnh-viện Phúc Kiến'), parseEntry('97. Cimetière Phúc Kiên')];
  ok(clash[0].key === clash[1].key, 'same proper name folds the same');
  ok(clash[0].type !== clash[1].type, 'but the types differ, so the key differs');

  const threads = buildThreads([
    { ...parseEntry('45. Hôpital Grall'), year: 1942 },
    { ...parseEntry('3. Bệnh-viện Đồn Đất (Grall)'), year: 1959 },
    { ...parseEntry('90. Marché de Binh Tây'), year: 1942 },
    { ...parseEntry('15. Chợ Bình Tây'), year: 1959 },
    { ...parseEntry('137. Cimetière Cantonnais (Phú Thọ)'), year: 1942 },
    { ...parseEntry('171. Cimetière Musulman (Phú Thọ)'), year: 1942 },
    { ...parseEntry('80. Nghĩa-địa Phú Thọ'), year: 1959 },
  ]);
  // The invariant the merge broke: every entry lands in exactly one thread.
  const placed = threads.flatMap((t) => Object.values(t.years).flat());
  ok(placed.length === 7, `threads partition the entries, got ${placed.length} of 7`);
  ok(new Set(placed).size === placed.length, 'no entry claimed twice');

  ok(threads.filter((t) => t.type === 'market').length === 1, 'one market thread, not two');
  const donDat = threads.find((t) => t.name === 'don dat');
  ok(donDat?.links[0]?.to === 'hospital|grall', 'the rename is a link to Hôpital Grall');
  ok(donDat?.links[0]?.to_years?.[0] === 1942, 'and it points at the 1942 sheet');
  const phuTho = threads.filter((t) => t.links.some((l) => l.to === 'cemetery|phu tho'));
  ok(phuTho.length === 2, `both 1942 cemeteries link to Phú Thọ separately, got ${phuTho.length}`);
  ok(
    threads.find((t) => t.key === 'cemetery|phu tho') &&
      Object.keys(threads.find((t) => t.key === 'cemetery|phu tho').years).length === 1,
    'and Phú Thọ itself is still one 1959 entry, not four'
  );

  console.log(bad ? `selftest FAILED (${bad})` : 'selftest ok');
  process.exitCode = bad ? 1 : 0;
}

function report(threads, entries) {
  const years = [1878, 1923, 1942, 1959];
  const multi = threads.filter((t) => Object.keys(t.years).length > 1);
  const linked = threads.filter((t) => t.links.length);
  console.log(`${entries.length} entries → ${threads.length} threads`);
  console.log(`  ${multi.length} appear on more than one sheet`);
  console.log(
    `  ${multi.filter((t) => t.years[1959]).length} of those survive into the 1959 Vietnamese legend`
  );
  console.log(
    `  ${linked.length} carry a parenthetical naming another entry (renames and consolidations)\n`
  );

  console.log('— across the 1959 rename —');
  for (const t of multi.filter((t) => t.years[1959]).sort((a, b) => a.key.localeCompare(b.key))) {
    console.log(`${t.type.padEnd(11)} ${t.name}`);
    for (const y of years)
      if (t.years[y]) console.log(`   ${y}  ${t.years[y].map((e) => e.raw).join(' / ')}`);
  }

  console.log('\n— renames and consolidations named in the legend itself —');
  const byTarget = new Map();
  for (const t of linked)
    for (const l of t.links)
      (byTarget.get(l.to) ?? byTarget.set(l.to, []).get(l.to)).push({ t, l });
  for (const [to, list] of byTarget) {
    const target = threads.find((x) => x.key === to);
    const verb = list.length > 1 ? `${list.length} →` : '→';
    console.log(`${verb} ${target ? Object.values(target.years).flat()[0].raw : to}`);
    for (const { t, l } of list)
      console.log(`     ${Object.values(t.years).flat()[0].raw}   (via "${l.via}")`);
  }

  console.log('\n— on every French sheet but gone by 1959 —');
  for (const t of multi.filter((t) => !t.years[1959]).sort((a, b) => a.key.localeCompare(b.key)))
    console.log(`${t.type.padEnd(11)} ${t.name}   ${years.filter((y) => t.years[y]).join(' ')}`);
}

mkdirSync(OUT_DIR, { recursive: true });

if (process.argv.includes('--selftest')) {
  selftest();
} else {
  const raw =
    existsSync(ENTRIES) && process.argv.includes('--report')
      ? JSON.parse(readFileSync(ENTRIES, 'utf8'))
      : await loadFromDb();
  writeFileSync(ENTRIES, JSON.stringify(raw, null, 1));
  const entries = raw.map((r) => ({ ...parseEntry(r.raw), year: r.year }));
  const threads = buildThreads(entries);
  writeFileSync(TIMELINE, JSON.stringify(threads, null, 1));
  report(threads, entries);
  console.log(`\n→ ${TIMELINE}`);
}
