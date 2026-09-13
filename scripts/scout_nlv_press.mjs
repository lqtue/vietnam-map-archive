#!/usr/bin/env node
// Harvest the National Library of Vietnam's newspaper archive (baochi.nlv.gov.vn)
// for map/survey vocabulary, straight from the library's own search.
//
// Why direct and not the proxy https://hanoimaps.github.io/news runs on: that
// site (github.com/hanoimaps/hanoimaps.github.io) holds no NLV code at all — it
// is a form over a closed Vercel function, which is 10x slower, states no result
// total, caps out around a thousand rows, and drops the date, publication and
// facet filters the library exposes. `bản đồ` is 15,154 results here and ~960
// through the proxy.
//
// The archive is Veridian. Its search is a plain GET:
//   baochi/cgi-bin/baochi?a=q&r=<1-based>&results=1&txq=<phrase>&txf=txIN&ssnip=img
//   &puq=<publication id>&dafyq=<from year>&datyq=<to year>
// `r` is the 1-based index of the first result; `o` is the page size, max 50.
//
// **txq ANDs words — it does not match phrases.** `bản đồ` and `đồ bản` both
// return 15,154, because that is every page carrying *bản* and *đồ* anywhere on
// it. Quoting is what asks for the phrase: `"bản đồ"` is 838. So every line in
// scripts/nlv-queries.txt is quoted, and an unquoted query is a different, much
// noisier question. (The hanoimaps proxy behaves like the quoted form, which is
// why its "bản đồ Hà Nội" came back empty.)
//
// ponytail: HTML regexes, not a DOM parser. Veridian's output is machine-
// generated and has not moved in years; the ceiling is that a template change
// breaks parsing loudly (zero results on a query whose total is non-zero, which
// --selftest pins), not quietly. Reach for a parser when that actually happens.
//
// Politeness: sequential, one request at a time, PAUSE_MS between, one retry.
// This is a national library's public search, not an API. Do not parallelise.
//
// Output: work/press/nlv.jsonl, one row per `oid` (the archive's own article
// key), appended and deduped. --images pulls each hit's full page scan.
//
// Usage:
//   node scripts/scout_nlv_press.mjs --selftest
//   node scripts/scout_nlv_press.mjs --pubs                    # the 82 titles
//   node scripts/scout_nlv_press.mjs --queries scripts/nlv-queries.txt
//   node scripts/scout_nlv_press.mjs "bản đồ" --pub RbD,WHfY   # southern only
//   node scripts/scout_nlv_press.mjs "bản đồ" --from 1920 --to 1945
//   node scripts/scout_nlv_press.mjs --report
//
// --max is a per-query page budget for ONE run, not the size of the archive:
// each (query, filter) pair's next `r` is remembered in work/press/offsets.json,
// so running the same list again continues where it stopped. --restart ignores it.

import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const HOST = 'http://baochi.nlv.gov.vn';
const SEARCH = `${HOST}/baochi/cgi-bin/baochi`;
const IMAGES = `${HOST}/baochi/cgi-bin/imageserver/imageserver.pl`;
const OUT_DIR = 'work/press';
const OUT = `${OUT_DIR}/nlv.jsonl`;
const IMG_DIR = `${OUT_DIR}/img`;
const OFFSETS = `${OUT_DIR}/offsets.json`;
const PAGE = 50; // the `o` select's largest page; 2.5x fewer requests than the default 20
const PAUSE_MS = 1200;
const UA = 'Mozilla/5.0 (compatible; vietnam-map-archive/1.0; +https://maparchive.vn)';

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => (argv.indexOf(n) > -1 ? argv[argv.indexOf(n) + 1] : d);

const QUERY_FILE = opt('--queries', null);
const QUERIES = QUERY_FILE
  ? readFileSync(QUERY_FILE, 'utf8')
      .split('\n')
      .map((l) => l.replace(/#.*$/, '').trim())
      .filter(Boolean)
  : argv.filter((a, i) => !a.startsWith('--') && !argv[i - 1]?.startsWith('--'));
const PUBS = (opt('--pub', '') || '').split(',').filter(Boolean);
const FROM = opt('--from', null);
const TO = opt('--to', null);
const MAX_PAGES = Number(opt('--max', 50));
const RESTART = flag('--restart');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const unent = (s) =>
  s
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();

function searchUrl(q, r, pub) {
  const p = new URLSearchParams({
    a: 'q',
    r: String(r),
    results: '1',
    txq: q,
    txf: 'txIN', // full text; the only other option is txTI, titles alone
    ssnip: 'img',
    o: String(PAGE),
  });
  if (pub) p.set('puq', pub);
  if (FROM) p.set('dafyq', FROM);
  if (TO) p.set('datyq', TO);
  // Veridian carries display state in `e`; the defaults are what the site's own
  // form submits. It must be present or the CGI renders the blank search page.
  p.set('e', '-------vi-20--1--img-txIN------');
  return `${SEARCH}?${p}`;
}

/** `"HtCq19320421.1.31"` → publication id + packed date. Pure. */
export function splitOid(oid) {
  const m = /^([A-Za-z]+)(\d{8})\b/.exec(oid ?? '');
  return m ? { publication_id: m[1], date_id: m[2] } : { publication_id: '', date_id: '' };
}

/** `"19320421"` → 1932; null when it is not a plausible packed date. Pure. */
export function oidYear(dateId) {
  const y = Number((dateId ?? '').slice(0, 4));
  return Number.isInteger(y) && y > 1400 && y < 2200 ? y : null;
}

/** `"trả về 15154 kết quả"` → 15154. Null when the page states no total. Pure. */
export function parseTotal(html) {
  const m = /trả về\s+([\d.,]+)\s+kết quả/.exec(unent(html));
  return m ? Number(m[1].replace(/[.,]/g, '')) : null;
}

/**
 * One results page → its rows. Pure, so --selftest can pin it against a saved
 * page: a Veridian template change shows up as zero rows on a non-zero total.
 *
 * Each result is one `<table cellpadding="3" ...>`; the title anchor carries the
 * oid, the `<div>` under it the publication and printed date, and the snippet
 * `<img>` a `crop=x,y,w,h` — the box of the matched phrase on the scan, which is
 * the one thing the proxy throws away.
 */
export function parseResults(html, query) {
  const rows = [];
  for (const block of html.split(/<table cellpadding="3"/).slice(1)) {
    const a = /<a href="[^"]*a=d&amp;d=([^&"]+)&amp;srpos=(\d+)[^"]*"\s*>([^<]*)<\/a>/.exec(block);
    if (!a) continue;
    const [, oid, srpos, rawTitle] = a;
    const line = /<\/a>\s*<div>([^<]*)<\/div>/.exec(block);
    const crop = /crop=(\d+),(\d+),(\d+),(\d+)/.exec(block);
    const title = unent(rawTitle);
    // Veridian appends the document type in brackets: "Bản đồ Công-gô [Bài báo]".
    const typed = /^(.*?)\s*\[([^\]]+)\]\s*$/.exec(title);
    const { publication_id, date_id } = splitOid(oid);
    rows.push({
      oid,
      srpos: Number(srpos),
      query,
      title: typed ? typed[1] : title,
      doc_type: typed ? typed[2] : '',
      publication_id,
      publication_name: line ? unent(line[1]).replace(/\s*\d{1,2} Tháng .*$/, '').trim() : '',
      printed_date: line ? unent(line[1]) : '',
      date_id,
      year: oidYear(date_id),
      article_url: `${SEARCH}?a=d&d=${oid}`,
      crop: crop ? crop.slice(1, 5).map(Number) : null,
      snippet_url: crop
        ? `${IMAGES}?oid=${oid}&area=1&crop=${crop.slice(1, 5).join(',')}&width=${crop[3]}&color=all&ext=jpg`
        : '',
      image_full_url: `${IMAGES}?oid=${oid}&area=1&width=2000&color=all&ext=png`,
    });
  }
  return rows;
}

async function get(url) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA } });
      if (!res.ok) throw new Error(`http ${res.status}`);
      return await res.text();
    } catch (err) {
      if (attempt) throw err;
      console.warn(`  retry after ${err.message}`);
      await sleep(5000);
    }
  }
  return '';
}

function seenOids() {
  if (!existsSync(OUT)) return new Set();
  return new Set(
    readFileSync(OUT, 'utf8')
      .split('\n')
      .filter(Boolean)
      .map((l) => JSON.parse(l).oid)
      .filter(Boolean)
  );
}

/** The 82 titles the archive holds, off the search form's own `puq` select. */
async function publications() {
  const html = await get(searchUrl('', 1, null));
  const sel = /<select[^>]*name="puq"[\s\S]*?<\/select>/.exec(html);
  if (!sel) throw new Error('no puq select — the form changed');
  return [...sel[0].matchAll(/<option[^>]*value="([^"]*)"[^>]*>([^<]*)<\/option>/g)]
    .map(([, id, name]) => ({ id, name: unent(name) }))
    .filter((p) => p.id);
}

async function harvest(q, pub, seen, offsets) {
  const key = [q, pub, FROM, TO].filter(Boolean).join('|');
  const start = RESTART ? 1 : (offsets[key]?.next ?? 1);
  let r = start;
  let added = 0;
  let total = null;
  console.log(`\n"${q}"${pub ? ` pub=${pub}` : ''}${start > 1 ? ` (resuming at r=${start})` : ''}`);
  const fresh = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const html = await get(searchUrl(q, r, pub));
    if (total === null) {
      total = parseTotal(html);
      console.log(`  ${total ?? '?'} results in the archive`);
    }
    const rows = parseResults(html, q);
    if (!rows.length) {
      // A non-zero total with no parsed rows means the template moved, not that
      // the archive is empty — say which, loudly, rather than logging "done".
      if (total) console.error(`  PARSE FAILED at r=${r}: ${total} results, 0 rows parsed`);
      break;
    }
    for (const row of rows) {
      if (seen.has(row.oid)) continue;
      seen.add(row.oid);
      appendFileSync(OUT, JSON.stringify(row) + '\n');
      fresh.push(row);
      added++;
    }
    r += rows.length;
    offsets[key] = { next: r, total };
    writeFileSync(OFFSETS, JSON.stringify(offsets, null, 2));
    if (page % 10 === 0 || rows.length < PAGE)
      console.log(`  r=${r - rows.length}: ${rows.length} rows, ${added} new, ${total ? Math.min(100, Math.round(((r - 1) / total) * 100)) : '?'}%`);
    if (rows.length < PAGE || (total && r > total)) break;
    await sleep(PAUSE_MS);
  }
  if (total && r <= total) console.log(`  hit --max; re-run to continue from r=${r} of ${total}`);
  return fresh;
}

async function pullImages(items) {
  mkdirSync(IMG_DIR, { recursive: true });
  for (const it of items) {
    const path = `${IMG_DIR}/${it.oid}.png`;
    if (existsSync(path)) continue;
    try {
      const res = await fetch(it.image_full_url, { headers: { 'User-Agent': UA } });
      if (!res.ok) throw new Error(`http ${res.status}`);
      writeFileSync(path, Buffer.from(await res.arrayBuffer()));
    } catch (err) {
      console.warn(`  img ${it.oid} failed: ${err.message}`);
    }
    await sleep(PAUSE_MS);
  }
}

function report() {
  const rows = readFileSync(OUT, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const tally = (f) => {
    const m = new Map();
    for (const r of rows) m.set(f(r), (m.get(f(r)) ?? 0) + 1);
    return [...m].sort((a, b) => b[1] - a[1]);
  };
  console.log(`${rows.length} rows\n\nby publication`);
  for (const [k, n] of tally((r) => r.publication_name || r.publication_id || '?')) {
    const ys = rows.filter((r) => (r.publication_name || r.publication_id || '?') === k && r.year).map((r) => r.year);
    console.log(`  ${String(n).padStart(6)}  ${k}  ${ys.length ? `${Math.min(...ys)}-${Math.max(...ys)}` : ''}`);
  }
  console.log('\nby decade');
  for (const [k, n] of tally((r) => (r.year ? `${Math.floor(r.year / 10) * 10}s` : '?')).sort())
    console.log(`  ${String(n).padStart(6)}  ${k}`);
  console.log('\nby type');
  for (const [k, n] of tally((r) => r.doc_type || '?')) console.log(`  ${String(n).padStart(6)}  ${k}`);
  console.log('\nby query');
  for (const [k, n] of tally((r) => r.query)) console.log(`  ${String(n).padStart(6)}  ${k}`);
  const southFile = 'scripts/nlv-southern-pubs.txt';
  if (existsSync(southFile)) {
    const south = new Set(
      readFileSync(southFile, 'utf8')
        .split('\n')
        .map((l) => l.replace(/#.*$/, '').trim())
        .filter(Boolean)
    );
    const hit = rows.filter((r) => south.has(r.publication_id));
    const ys = hit.map((r) => r.year).filter(Boolean);
    console.log(
      `\nsouthern press (the HCMC corpus): ${hit.length} of ${rows.length} rows` +
        (ys.length ? `, ${Math.min(...ys)}-${Math.max(...ys)}` : '')
    );
  }
}

function selftest() {
  const fixture = 'work/press/fixture-results.html';
  // console.assert only prints; a selftest that cannot fail the process is a
  // selftest nobody notices failing.
  let bad = 0;
  const ok = (cond, msg) => {
    if (!cond) {
      bad++;
      console.error(`  FAIL ${msg}`);
    }
  };
  ok(splitOid('HtCq19320421.1.31').publication_id === 'HtCq', 'pub id off oid');
  ok(splitOid('HtCq19320421.1.31').date_id === '19320421', 'date off oid');
  ok(splitOid('nope').publication_id === '', 'unparseable oid is empty, not a guess');
  ok(oidYear('19320421') === 1932 && oidYear('') === null, 'year');
  ok(parseTotal('trả về 15154 kết quả') === 15154, 'total');
  ok(parseTotal('<p>nothing</p>') === null, 'absent total is null, not 0');
  if (!existsSync(fixture)) {
    console.log(bad ? `selftest FAILED (${bad})` : 'selftest ok (no fixture — run --fixture once to pin the parser)');
    process.exitCode = bad ? 1 : 0;
    return;
  }
  const html = readFileSync(fixture, 'utf8');
  const rows = parseResults(html, 'bản đồ');
  const total = parseTotal(html);
  // The one that matters: a Veridian template change must fail here, not read
  // as an archive with nothing in it.
  ok(rows.length === PAGE, `expected ${PAGE} rows from a full page, got ${rows.length}`);
  ok(total > 0, 'fixture states a total');
  const r = rows[0];
  ok(/^[A-Za-z]+\d{8}/.test(r.oid), 'oid shape');
  ok(r.year >= 1800 && r.year <= 2100, `year in range, got ${r.year}`);
  ok(r.publication_name.length > 1, 'publication name parsed');
  ok(Array.isArray(r.crop) && r.crop.length === 4, 'crop box parsed');
  ok(rows.every((x) => x.oid && x.article_url.includes(x.oid)), 'every row addressable');
  ok(new Set(rows.map((x) => x.srpos)).size === rows.length, 'one row per result, not per anchor');
  if (bad) {
    console.error(`selftest FAILED (${bad})`);
    process.exitCode = 1;
    return;
  }
  console.log(`selftest ok (${rows.length} rows parsed from the fixture, total ${total})`);
}

mkdirSync(OUT_DIR, { recursive: true });

if (flag('--selftest')) {
  selftest();
} else if (flag('--fixture')) {
  writeFileSync(`${OUT_DIR}/fixture-results.html`, await get(searchUrl('"bản đồ"', 1, null)));
  console.log(`saved ${OUT_DIR}/fixture-results.html`);
} else if (flag('--pubs')) {
  const pubs = await publications();
  writeFileSync(`${OUT_DIR}/publications.json`, JSON.stringify(pubs, null, 2));
  console.log(`${pubs.length} publications → ${OUT_DIR}/publications.json`);
  for (const p of pubs) console.log(`  ${p.id.padEnd(6)} ${p.name}`);
} else if (flag('--report')) {
  report();
} else if (!QUERIES.length) {
  console.error('usage: scout_nlv_press.mjs "<phrase>" [...] | --queries <file> [--pub ids] [--from Y --to Y] [--max pages] [--images] | --pubs | --report | --selftest');
  process.exit(1);
} else {
  const seen = seenOids();
  const offsets = existsSync(OFFSETS) ? JSON.parse(readFileSync(OFFSETS, 'utf8')) : {};
  console.log(`${seen.size} rows already in ${OUT}`);
  const fresh = [];
  for (const q of QUERIES)
    for (const pub of PUBS.length ? PUBS : [null]) fresh.push(...(await harvest(q, pub, seen, offsets)));
  console.log(`\n${fresh.length} new rows → ${OUT}`);
  if (flag('--images')) await pullImages(fresh);
}
