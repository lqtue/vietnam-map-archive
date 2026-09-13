#!/usr/bin/env node
// Attach period press to the legend threads built by scripts/legend_timeline.mjs:
// for each institution, how often the press named it, decade by decade, in both
// languages.
//
//   NLV  (baochi.nlv.gov.vn) — the Vietnamese press. ONE request per name gives
//        the whole curve: Veridian's results page carries a decade facet with
//        counts, so there is no need to ask per decade.
//   BnF  (gallica.bnf.fr SRU) — the French press and the Annuaire directories.
//        No facet, so one request per decade; `numberOfRecords` is the count.
//
// The legend is what makes this askable at all: a thread that crosses 1959
// carries its own bilingual pair — `Chợ Bình Tây` for the Vietnamese archive and
// `Marché de Binh Tây` for the French one — so the two curves are the same
// institution, not two guesses.
//
// Query the PROPER NAME, not the whole entry. Both archives match phrases only
// when quoted (NLV) or via `adj` (Gallica), and the type word is noise that the
// period press does not repeat: `"Chợ Bình Tây"` is 4 hits, `"Bình Tây"` is 60.
//
// Politeness: sequential, PAUSE_MS apart, one retry. Two public archives.
//
// Usage:
//   node scripts/legend_press.mjs --selftest
//   node scripts/legend_press.mjs                  # threads on more than one sheet
//   node scripts/legend_press.mjs --threads cross  # only those crossing the 1959 rename
//   node scripts/legend_press.mjs --baseline      # the corpus's own shape, once
//   node scripts/legend_press.mjs --report        # shape; --rate / --raw for numbers

import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const TIMELINE = 'work/legend/timeline.json';
const OUT = 'work/legend/press.json';
const BASELINE = 'work/legend/baseline.json';
const NLV = 'http://baochi.nlv.gov.vn/baochi/cgi-bin/baochi';
const SRU = 'https://gallica.bnf.fr/SRU';
const UA = 'VietnamMapArchive/1.0 (+https://maparchive.vn; period press lookup)';
const PAUSE_MS = 1200;
/** The decades Gallica is asked about — the French-era window plus a margin. */
const DECADES = [1860, 1870, 1880, 1890, 1900, 1910, 1920, 1930, 1940, 1950];

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => (argv.indexOf(n) > -1 ? argv[argv.indexOf(n) + 1] : d);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const unaccent = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D');

/**
 * The spellings one name takes in a French OCR corpus. Same rule as
 * `spellingVariants` in src/lib/server/gallica.ts — unaccented first, then the
 * colonial press's hyphenated house style, then the accented modern form.
 */
export function spellingVariants(name) {
  const clean = (name ?? '').replace(/["()[\]{}\\-]+/g, ' ').replace(/\s+/g, ' ').trim();
  if (!clean) return [];
  const plain = unaccent(clean);
  const out = [plain];
  if (plain.includes(' ')) out.push(plain.replace(/ /g, '-'));
  if (clean !== plain) out.push(clean);
  return [...new Set(out)].slice(0, 8);
}

/**
 * CQL for one name in one decade. Pinned in --selftest against the exact string
 * tests/press.spec.ts asserts for the TypeScript copy, because this is the same
 * query builder living in a second language and a drift between them would look
 * like an archive with nothing in it rather than like a bug.
 */
export function buildGallicaQuery(name, from, to) {
  const variants = spellingVariants(name);
  if (!variants.length) throw new Error('buildGallicaQuery: empty query');
  const phrases = variants.map((v) => `(gallica adj "${v}")`).join(' or ');
  return `(${phrases}) and (dc.date >= "${from}" and dc.date <= "${to}")`;
}

/**
 * The same query, restricted to documents that also name Saigon.
 *
 * Gallica is all of France, so an unscoped legend name is only as good as the
 * name: `Binh Tay` is a place and `Européen` is an adjective, and `Cimetière
 * Européen` scored 52,075 hits before this — the whole francophone world's
 * European cemeteries. Scoping every query to Saigon is the fix that needs no
 * lexicon. Querying the full entry instead does not work: the press writes
 * `marché de Binh-Tây` with its own accents and hyphens, so `adj` over four
 * words returns 0 where the name alone returns 145.
 */
export function buildScopedQuery(name, from, to) {
  return `${buildGallicaQuery(name, from, to)} and (gallica adj "Saigon")`;
}

/** `<srw:numberOfRecords>123<` → 123. Null when the response states none. Pure. */
export function parseSruCount(xml) {
  const m = /<(?:srw:)?numberOfRecords>\s*(\d+)/.exec(xml ?? '');
  return m ? Number(m[1]) : null;
}

/** Veridian's results page → `{ total, decades: { 1930: 47, … } }`. Pure. */
export function parseNlvFacet(html) {
  const text = (s) =>
    s
      .replace(/<[^>]+>/g, ' ')
      .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
      .replace(/&amp;/g, '&')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ');
  const total = /trả về\s+(\d+)\s+kết quả/.exec(text(html));
  const i = html.indexOf("'facet-de'");
  const j = html.indexOf("'facet-wo'");
  const decades = {};
  if (i > 0 && j > i)
    for (const [, d, n] of text(html.slice(i, j)).matchAll(/(\d{4})-\d{4}\D{0,120}?\((\d+)\)/g))
      decades[Number(d)] = Number(n);
  return { total: total ? Number(total[1]) : 0, decades };
}

const RETRIES = 3;

async function get(url, headers = {}) {
  let last;
  for (let attempt = 0; attempt < RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': UA, ...headers },
        signal: AbortSignal.timeout(30_000),
      });
      if (!res.ok) throw new Error(`http ${res.status}`);
      return await res.text();
    } catch (err) {
      last = err;
      // Both archives drop a connection now and then; back off rather than
      // hammer, and let the caller decide whether losing one row is fatal.
      await sleep(4000 * (attempt + 1));
    }
  }
  throw last;
}

async function nlvCurve(name) {
  const p = new URLSearchParams({
    a: 'q', r: '1', results: '1', txq: `"${name}"`, txf: 'txIN', ssnip: 'img', o: '50',
    e: '-------vi-20--1--img-txIN------',
  });
  return parseNlvFacet(await get(`${NLV}?${p}`));
}

async function sruCount(cql) {
  const p = new URLSearchParams({ operation: 'searchRetrieve', version: '1.2', query: cql, maximumRecords: '1' });
  return parseSruCount(await get(`${SRU}?${p}`)) ?? 0;
}

async function gallicaCurve(name) {
  const decades = {};
  let total = 0;
  for (const d of DECADES) {
    const n = await sruCount(buildScopedQuery(name, d, d + 9));
    if (n) decades[d] = n;
    total += n;
    await sleep(PAUSE_MS);
  }
  // How much of this name's Gallica footprint is Saigon's at all. One extra
  // request, and it is a measurement rather than a lexical guess about which
  // legend words are proper names: "Binh Tay" is 0.77, "Européen" is 0.26.
  const wide = await sruCount(buildGallicaQuery(name, DECADES[0], DECADES.at(-1) + 9));
  await sleep(PAUSE_MS);
  const specificity = wide ? total / wide : null;
  return { total, decades, specificity, generic: specificity !== null && specificity < 0.4 };
}

/**
 * The corpus's own shape, so a count can be read as history rather than as
 * coverage. **The two archives get different denominators**, so a normalised
 * BnF number and a normalised NLV number are each comparable down their own
 * column and across decades, but not with each other: every Gallica query is
 * already scoped to Saigon, so its universe is "documents naming Saigon", while
 * the NLV queries are unscoped, so its universe is "pages of Vietnamese press". Both archives thin out after 1940 for reasons that have nothing to
 * do with Saigon's markets, so every curve is also reported per thousand
 * mentions of the city itself — the nearest thing either archive has to a
 * denominator. It is not a perfect control (the French press left, and what
 * stayed wrote about different things) but it is the difference between
 * "Chợ Quán stopped being news" and "the archive stops here": measured, Gallica
 * falls 2.5x from the 1930s to the 1950s while Chợ Quán falls 45x.
 */
async function baseline() {
  const gallica = { total: 0, decades: {} };
  for (const d of DECADES) {
    const p = new URLSearchParams({
      operation: 'searchRetrieve',
      version: '1.2',
      query: `((gallica adj "Saigon") or (gallica adj "Saïgon")) and (dc.date >= "${d}" and dc.date <= "${d + 9}")`,
      maximumRecords: '1',
    });
    const n = parseSruCount(await get(`${SRU}?${p}`)) ?? 0;
    if (n) gallica.decades[d] = n;
    gallica.total += n;
    await sleep(PAUSE_MS);
  }
  // NOT "Sài Gòn": as an exact phrase that is 21 hits in the whole 1930s,
  // because the period press wrote Sàigòn and Sài-gòn. `và` is the commonest
  // Vietnamese word, so its decade facet is simply how much text the archive
  // holds for each decade — 80,288 pages for the 1930s against 3,676 for the
  // 1960s, which is the shape every raw curve was otherwise showing.
  const nlv = await nlvCurve('và');
  return { gallica, nlv, measured: new Date().toISOString().slice(0, 10) };
}

/** Hits per thousand mentions of Saigon in the same archive and decade. Pure. */
export function perMille(curve, base, decade) {
  const n = curve?.decades?.[decade] ?? 0;
  const b = base?.decades?.[decade] ?? 0;
  return b ? (n / b) * 1000 : null;
}

/** The Vietnamese and French proper names a thread offers, if it has each. */
export function namesFor(thread) {
  const at = (y) => thread.years[y]?.[0]?.name?.trim() || null;
  return { vi: at(1959), fr: at(1942) ?? at(1923) ?? at(1878) };
}

/**
 * One row of the curve. Three ways to read the same numbers:
 *
 *   default  corpus-corrected, then indexed 0-99 against this row's own peak —
 *            the shape of when a place was in the news, which is what survives
 *            both the archives having different universes and the Vietnamese
 *            corpus being 80,288 pages in the 1930s against 3,676 in the 1960s.
 *   --rate   the per-mille itself. Honest, and unreadable on the NLV side,
 *            where every place is a vanishing fraction of all Vietnamese print.
 *   --raw    the counts as the archives gave them. Mostly corpus shape.
 */
function curveLine(c, decades, base, mode) {
  const cell = (t) => String(t).padStart(5);
  if (mode === 'raw' || !base)
    return decades.map((d) => cell(c?.decades?.[d] ? c.decades[d] : '·')).join('');

  const rates = Object.fromEntries(decades.map((d) => [d, perMille(c, base, d)]));
  if (mode === 'rate')
    return decades
      .map((d) => {
        const r = rates[d];
        if (r === null) return cell('?');
        if (!r) return cell('·');
        return cell(r >= 100 ? Math.round(r) : r >= 10 ? r.toFixed(0) : r.toFixed(1));
      })
      .join('');

  const peak = Math.max(0, ...Object.values(rates).filter((r) => r !== null));
  return decades
    .map((d) => {
      const r = rates[d];
      if (r === null) return cell('?');
      if (!r) return cell('·');
      return cell(Math.max(1, Math.round((r / peak) * 99)));
    })
    .join('');
}

function report(rows) {
  const decades = [1870, 1880, 1890, 1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980];
  const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : null;
  const mode = flag('--raw') ? 'raw' : flag('--rate') ? 'rate' : base ? 'index' : 'raw';
  const head = decades.map((d) => `${String(d).slice(2)}s`.padStart(5)).join('');
  console.log(
    {
      index: 'corpus-corrected, indexed 0-99 against each row\'s own peak (--rate for per-mille, --raw for counts)',
      rate: 'per 1,000 of each archive\'s own universe (--raw for counts)',
      raw: 'raw counts as the archives gave them',
    }[mode]
  );
  if (base && mode !== 'raw')
    console.log(
      `baseline ${base.measured} — BnF: documents naming Saigon (${base.gallica.total}).` +
        ` NLV: pages of Vietnamese press (${base.nlv.total}).`
    );
  console.log(`${''.padEnd(30)}${head}   total`);
  for (const r of rows.filter((r) => (r.nlv?.total ?? 0) + (r.gallica?.total ?? 0) > 0)) {
    console.log(
      `\n${r.type} — ${r.fr ?? '—'} / ${r.vi ?? '—'}` +
        (r.gallica?.generic
          ? `   [generic: only ${Math.round(r.gallica.specificity * 100)}% of "${r.fr}" in Gallica is Saigon's — the word, not the place]`
          : '')
    );
    if (r.gallica)
      console.log(`  BnF ${(r.fr ?? '').slice(0, 20).padEnd(21)}${curveLine(r.gallica, decades, base?.gallica, mode)}  ${String(r.gallica.total).padStart(6)}`);
    if (r.nlv)
      console.log(`  NLV ${(r.vi ?? '').slice(0, 20).padEnd(21)}${curveLine(r.nlv, decades, base?.nlv, mode)}  ${String(r.nlv.total).padStart(6)}`);
  }
}

function selftest() {
  let bad = 0;
  const ok = (c, m) => {
    if (!c) {
      bad++;
      console.error(`  FAIL ${m}`);
    }
  };
  // Parity with src/lib/server/gallica.ts — the string tests/press.spec.ts pins.
  ok(
    buildGallicaQuery('Khánh Hội', 1913, 1933) ===
      '((gallica adj "Khanh Hoi") or (gallica adj "Khanh-Hoi") or (gallica adj "Khánh Hội")) ' +
        'and (dc.date >= "1913" and dc.date <= "1933")',
    `CQL parity with the TypeScript builder:\n    ${buildGallicaQuery('Khánh Hội', 1913, 1933)}`
  );
  ok(!buildGallicaQuery('Khanh" or (gallica all "war', 1920, 1929).includes('"war"'), 'quotes cannot escape the CQL');
  ok(
    buildScopedQuery('Binh Tay', 1920, 1929).endsWith('and (gallica adj "Saigon")'),
    'every gallica query is scoped to Saigon'
  );
  ok(parseSruCount('<srw:numberOfRecords>8341</srw:numberOfRecords>') === 8341, 'sru count');
  ok(parseSruCount('<numberOfRecords>0</numberOfRecords>') === 0, 'zero is a count, not absent');
  ok(parseSruCount('<oops/>') === null, 'absent count is null, not 0');
  const c = { decades: { 1930: 544 } };
  const b = { decades: { 1930: 3427, 1940: 1370 } };
  ok(Math.round(perMille(c, b, 1930)) === 159, `per-mille, got ${perMille(c, b, 1930)}`);
  ok(perMille(c, b, 1940) === 0, 'a decade with no hits but a baseline is zero, not null');
  ok(perMille(c, b, 1960) === null, 'a decade the baseline does not cover is null, not zero');

  const fixture = 'work/legend/fixture-facet.html';
  if (existsSync(fixture)) {
    const c = parseNlvFacet(readFileSync(fixture, 'utf8'));
    ok(c.total > 0, 'fixture states a total');
    ok(Object.keys(c.decades).length > 1, `decade facet parsed, got ${JSON.stringify(c.decades)}`);
    const summed = Object.values(c.decades).reduce((a, b) => a + b, 0);
    ok(summed <= c.total, `decades (${summed}) cannot exceed the total (${c.total})`);
  }
  console.log(bad ? `selftest FAILED (${bad})` : 'selftest ok');
  process.exitCode = bad ? 1 : 0;
}

if (flag('--selftest')) {
  selftest();
} else if (flag('--baseline')) {
  const b = await baseline();
  writeFileSync(BASELINE, JSON.stringify(b, null, 1));
  console.log(`baseline → ${BASELINE}`);
  console.log('  BnF', JSON.stringify(b.gallica.decades));
  console.log('  NLV', JSON.stringify(b.nlv.decades));
} else if (flag('--report')) {
  report(JSON.parse(readFileSync(OUT, 'utf8')));
} else {
  const threads = JSON.parse(readFileSync(TIMELINE, 'utf8'));
  const pick = opt('--threads', 'multi');
  const selected = threads.filter((t) => {
    const years = Object.keys(t.years).length;
    if (pick === 'cross') return years > 1 && t.years[1959];
    if (pick === 'all') return years >= 1;
    return years > 1;
  });
  console.log(`${selected.length} threads (--threads ${pick})`);
  const rows = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : [];
  const done = new Set(rows.map((r) => r.key));
  // A 20-minute run must not die on one upstream timeout. Rows are written as
  // they land and `done` is keyed off the file, so a failed thread is retried by
  // simply running the command again.
  const failed = [];
  for (const t of selected) {
    if (done.has(t.key)) continue;
    try {
      await one(t, rows);
    } catch (err) {
      failed.push(t.key);
      console.warn(`  SKIPPED ${t.key}: ${err.message}`);
    }
  }
  if (failed.length) console.warn(`\n${failed.length} threads failed and were not written; re-run to retry them`);
  console.log(`\n${rows.length} rows → ${OUT}`);
}

async function one(t, rows) {
  {
    const { vi, fr } = namesFor(t);
    const row = {
      key: t.key, type: t.type, vi, fr, nlv: null, gallica: null,
      // Both sides query the proper name, not the whole entry — the type word
      // is noise the period press does not repeat ("Chợ Bình Tây" is 4 hits,
      // "Bình Tây" is 60) — and the Gallica side is scoped to Saigon.
      query_form: 'proper name; gallica scoped to documents also naming Saigon',
    };
    if (vi) row.nlv = await nlvCurve(vi);
    await sleep(PAUSE_MS);
    if (fr) row.gallica = await gallicaCurve(fr);
    rows.push(row);
    writeFileSync(OUT, JSON.stringify(rows, null, 1));
    console.log(
      `  ${t.type.padEnd(11)} ${(fr ?? vi ?? '?').slice(0, 28).padEnd(29)} BnF ${String(row.gallica?.total ?? '-').padStart(5)}${row.gallica?.generic ? '!' : ' '} NLV ${String(row.nlv?.total ?? '-').padStart(4)}`
    );
  }
}
