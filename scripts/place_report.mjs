#!/usr/bin/env node
// Build a cited, dated evidence report for one place from the two period
// archives — Gallica (BnF) for the French press and books, the National Library
// of Vietnam for the Vietnamese press.
//
// The two archives answer in different media, and that shapes the whole script:
//
//   Gallica  has OCR'd full text, so `services/ContentSearch` returns the actual
//            sentence the place is named in. Free, and quotable as it stands.
//   NLV      returns no text at all — only the page scan and a `crop` box. So
//            each clipping is READ by a vision model before it can be cited,
//            and the transcription is marked as such.
//
// **The crop is not always the match.** For an advertisement or a page-level hit
// Veridian crops the matched line, but for an article-level hit it crops the
// article's HEADING — so the phrase sits somewhere in the body, off-image. Read
// naively that produces evidence that looks solid and is not: the 1918 Lục Tỉnh
// Tân Văn hit crops to the section header "TẠP TRỞ (Variétés)", which says
// nothing about the place. So the crop is widened for context and the model is
// asked whether the name is actually visible; entries where it is not say so
// rather than quoting a headline as though it were the source.
//
// **All three endpoints match loose words unless told otherwise**, and each one
// spells it differently. This has now bitten three times:
//   NLV `txq`              → quote it:  "Khánh Hội"
//   Gallica SRU            → `gallica adj "Khanh Hoi"`, not `all`
//   Gallica ContentSearch  → quote it:  "Khanh Hoi"
// Unquoted, ContentSearch for `Khanh Hoi` returns 18 hits on *quan*, *Quant* and
// *quand*, and one on the place. Quoted it returns the one. Getting this wrong
// does not error — it returns a page of confident, irrelevant evidence.
//
// The synthesis at the top is written by the model from the gathered evidence
// and NOTHING else, with [n] citations into the table below it. The table is the
// point: every line carries its date, its archive and its URL, so a reader can
// check the claim rather than trust it.
//
// Usage:
//   node scripts/place_report.mjs --selftest
//   node scripts/place_report.mjs "Khánh Hội"
//   node scripts/place_report.mjs "Khánh Hội" --variants "Khanh Hoi,Khánh-Hội" --max 16

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { parseDecades, parseResults, parseTotal } from './scout_nlv_press.mjs';

const NLV = 'http://baochi.nlv.gov.vn/baochi/cgi-bin/baochi';
const NLV_IMAGE = 'https://baochi-tvqg.vercel.app/api/image';
const SRU = 'https://gallica.bnf.fr/SRU';
const CONTENT_SEARCH = 'https://gallica.bnf.fr/services/ContentSearch';
const GEMINI = 'https://generativelanguage.googleapis.com/v1beta/models';
const MODEL = 'gemini-3.8-flash';
const OUT_DIR = 'work/reports';
const UA = 'VietnamMapArchive/1.0 (+https://maparchive.vn; period source report)';
const PAUSE_MS = 1000;

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => (argv.indexOf(n) > -1 ? argv[argv.indexOf(n) + 1] : d);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const unaccent = (s) =>
  s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D');
const slug = (s) =>
  unaccent(s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

/** The spellings a Vietnamese name takes in a French OCR corpus. Pure. */
export function spellings(name, extra = []) {
  const clean = (name ?? '')
    .replace(/["()[\]{}\\-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!clean) return [];
  const plain = unaccent(clean);
  const out = [plain];
  if (plain.includes(' ')) out.push(plain.replace(/ /g, '-'));
  if (clean !== plain) out.push(clean);
  for (const e of extra) {
    const c = e
      .replace(/["()[\]{}\\-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (c) out.push(unaccent(c), c);
  }
  return [...new Set(out.filter(Boolean))].slice(0, 8);
}

/** Gallica SRU CQL. `adj` is its phrase operator; `all` would match either word. Pure. */
export function sruQuery(name, extra = []) {
  const forms = spellings(name, extra);
  if (!forms.length) throw new Error('sruQuery: empty name');
  return `(${forms.map((v) => `(gallica adj "${v}")`).join(' or ')})`;
}

/** Decode the doubly-escaped highlight markup ContentSearch returns. Pure. */
export function snippetText(raw) {
  const once = (s) =>
    s
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
      .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
      .replace(/&amp;apos;/g, "'")
      .replace(/&apos;/g, "'")
      .replace(/&amp;quot;/g, '"')
      .replace(/&amp;/g, '&');
  return once(once(raw ?? ''))
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

async function get(url, opts = {}) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': UA, ...(opts.headers ?? {}) },
        signal: AbortSignal.timeout(opts.timeout ?? 30_000),
      });
      if (!res.ok) throw new Error(`http ${res.status}`);
      return opts.binary ? Buffer.from(await res.arrayBuffer()) : await res.text();
    } catch (err) {
      if (attempt === 2) throw err;
      await sleep(3000 * (attempt + 1));
    }
  }
}

/* ------------------------------------------------------------------- gather */

async function gatherNlv(name, max) {
  const p = new URLSearchParams({
    a: 'q',
    r: '1',
    results: '1',
    txq: `"${name.replace(/"/g, '')}"`, // quoted, or txq ANDs the words
    txf: 'txIN',
    ssnip: 'img',
    o: '50',
    e: '-------vi-20--1--img-txIN------',
  });
  const html = await get(`${NLV}?${p}`, { timeout: 45_000 });
  const rows = parseResults(html, name);
  const total = parseTotal(html) ?? 0;
  if (!rows.length && total > 0) throw new Error('nlv parse failed: results stated, none parsed');
  // Spread the sample across the run rather than taking the top of one decade —
  // the point of the report is change over time.
  const byYear = rows.filter((r) => r.year).sort((a, b) => a.year - b.year);
  const step = Math.max(1, Math.floor(byYear.length / max));
  const picked = byYear.filter((_, i) => i % step === 0).slice(0, max);
  return { total, decades: parseDecades(html), rows: picked };
}

async function gatherGallica(name, extra, max) {
  const p = new URLSearchParams({
    operation: 'searchRetrieve',
    version: '1.2',
    query: sruQuery(name, extra),
    maximumRecords: String(max * 2),
  });
  const xml = await get(`${SRU}?${p}`, { timeout: 30_000 });
  const recs = [];
  for (const block of xml.split('<srw:record>').slice(1)) {
    const ark = /ark:\/[0-9]+\/([A-Za-z0-9._-]+)/.exec(block)?.[1];
    const title = /<dc:title>([\s\S]*?)<\/dc:title>/.exec(block)?.[1];
    const date = /<dc:date>([\s\S]*?)<\/dc:date>/.exec(block)?.[1];
    if (ark) recs.push({ ark, title: snippetText(title ?? ''), date: snippetText(date ?? '') });
  }
  const out = [];
  for (const r of recs) {
    if (out.length >= max) break;
    // Quoted here too: unquoted, "Khanh Hoi" matches quan / Quant / quand.
    const cs = new URLSearchParams({ ark: r.ark, query: `"${unaccent(name)}"` });
    let snippets = [];
    try {
      const body = await get(`${CONTENT_SEARCH}?${cs}`, { timeout: 25_000 });
      snippets = [...body.matchAll(/<content>([\s\S]*?)<\/content>/g)]
        .map((m) => snippetText(m[1]))
        .filter((t) => t.length > 20)
        .slice(0, 2);
    } catch {
      // A record with no readable text is still a citation; it just carries none.
    }
    await sleep(PAUSE_MS);
    // Only keep records the phrase was actually found inside. A catalogue hit
    // with no locatable sentence is a lead, not evidence.
    if (snippets.length)
      out.push({ ...r, snippets, url: `https://gallica.bnf.fr/ark:/12148/${r.ark}` });
  }
  return out;
}

/* -------------------------------------------------------------------- model */

function apiKey() {
  const env = Object.fromEntries(
    readFileSync('.env', 'utf8')
      .split('\n')
      .filter((l) => l && !l.startsWith('#'))
      .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()])
  );
  const k = env.GEMINI_API_KEY;
  if (!k) throw new Error('GEMINI_API_KEY missing from .env');
  return k;
}

async function gemini(key, parts, { json = false } = {}) {
  const res = await fetch(`${GEMINI}/${MODEL}:generateContent?key=${key}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts }],
      generationConfig: {
        temperature: 0.2, // transcription and citation, not invention
        ...(json ? { responseMimeType: 'application/json' } : {}),
      },
    }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) throw new Error(`gemini http ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const body = await res.json();
  return body.candidates?.[0]?.content?.parts?.map((p) => p.text).join('') ?? '';
}

const TRANSCRIBE = (
  name
) => `This is a crop from a Vietnamese newspaper page, scanned from microfilm.
Transcribe the Vietnamese text exactly as printed, keeping the period orthography and diacritics.
Then give a literal English rendering.
Also answer whether the place name "${name}" is actually VISIBLE in this image —
the archive matched it somewhere on the page, but this crop may show only a heading.
Do not infer it from context; say false unless you can read it.
If the crop is too dark or broken to read, say so instead of guessing.
Return JSON: {"vi": "...", "en": "...", "legible": true|false, "found": true|false}`;

/**
 * Widen Veridian's crop for context. Pure.
 *
 * Its box is one line, often the heading rather than the match, and a single
 * line out of a newspaper page reads as a non-sequitur. This keeps the box
 * centred and grows it — enough to carry the paragraph around it without
 * pulling in the whole page.
 */
export function widenCrop([x, y, w, h], grow = 2.2, tall = 5) {
  const nw = Math.round(w * grow);
  const nh = Math.round(h * tall);
  return [
    Math.max(0, Math.round(x - (nw - w) / 2)),
    Math.max(0, Math.round(y - (nh - h) / 2)),
    nw,
    nh,
  ];
}

async function transcribe(key, row, name) {
  const box = row.crop ? widenCrop(row.crop) : null;
  const url = box
    ? `${NLV_IMAGE}?oid=${row.oid}&area=1&crop=${box.join(',')}&w=${Math.min(1600, Math.max(900, box[2]))}&color=all&ext=jpg`
    : `${NLV_IMAGE}?oid=${row.oid}&area=1&w=1200&color=all&ext=jpg`;
  const img = await get(url, { binary: true, timeout: 60_000 });
  const out = await gemini(
    key,
    [
      { text: TRANSCRIBE(name) },
      { inline_data: { mime_type: 'image/jpeg', data: img.toString('base64') } },
    ],
    { json: true }
  );
  try {
    const parsed = JSON.parse(out);
    return { ...parsed, image: url };
  } catch {
    return { vi: '', en: '', legible: false, found: false, image: url };
  }
}

const SYNTH = (
  name
) => `You are writing the opening section of an archival source report on the place "${name}" in Saigon.

Below is EVERY piece of evidence gathered, numbered. Write 4-6 short paragraphs that:
- say what these sources actually show about the place, in date order;
- cite with [n] after each claim, using only the numbers given;
- state plainly where the record is thin or silent, and do not fill those gaps;
- note when the French and Vietnamese records disagree or cover different decades;
- never introduce a fact, date, name or event that is not in the evidence.

Do not write a conclusion that the evidence does not support. If the evidence is
mostly incidental mentions rather than reporting about the place, say exactly that.
Plain prose. No headings, no bullet list, no preamble.`;

/* ------------------------------------------------------------------- report */

function markdown(name, nlv, gallica, transcripts, synthesis) {
  const L = [];
  const now = new Date().toISOString().slice(0, 10);
  L.push(`# ${name} — period sources`, '');
  L.push(`Generated ${now} by \`scripts/place_report.mjs\`. Every claim below is numbered to the`);
  L.push('evidence table; nothing is asserted that is not in it.', '');

  const decades = Object.entries(nlv.decades)
    .map(([d, n]) => [Number(d), n])
    .sort((a, b) => a[0] - b[0]);
  L.push('| archive | what was searched | hits |', '|---|---|---|');
  L.push(`| National Library of Vietnam | \`"${name}"\` full text, quoted | ${nlv.total} |`);
  L.push(
    `| Gallica (BnF) | \`gallica adj\` over ${spellings(name).length} spellings | ${gallica.length} with a locatable sentence |`
  );
  L.push('');
  if (decades.length) {
    L.push('Vietnamese press by decade:', '');
    L.push('```');
    const peak = Math.max(...decades.map((d) => d[1]));
    for (const [d, n] of decades)
      L.push(
        `${d}s ${String(n).padStart(4)} ${'█'.repeat(Math.max(1, Math.round((n / peak) * 40)))}`
      );
    L.push('```', '');
  }

  L.push('## What the sources show', '');
  L.push('> Written by Gemini from the evidence table below and nothing else.', '');
  L.push(synthesis.trim(), '');

  L.push('## Evidence', '');
  let n = 0;
  if (transcripts.length) {
    L.push('### Vietnamese press — National Library of Vietnam', '');
    L.push('The archive returns no text, only the page scan. Each entry below was read');
    L.push(
      'from the clipping image by a vision model; the scan is linked so it can be checked.',
      ''
    );
    for (const t of transcripts) {
      n += 1;
      L.push(
        `**[${n}]** ${t.row.date_id ? t.row.date_id.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3') : '—'} · ${t.row.publication_name || '—'}${t.row.doc_type ? ` · ${t.row.doc_type}` : ''}`
      );
      if (t.legible === false) L.push(`> *illegible at this crop* — [scan](${t.image})`);
      else {
        if (t.found === false)
          L.push(
            '> **The name is not visible in this crop.** The archive matched it elsewhere on the',
            '> page; what follows is only what the crop shows, and is not evidence about the place.',
            '> '
          );
        if (t.vi) L.push(`> ${t.vi.replace(/\n/g, ' ')}`);
        if (t.en) L.push(`> `, `> *${t.en.replace(/\n/g, ' ')}*`);
        L.push(`> `, `> [clipping](${t.image}) · [page in the archive](${NLV}?a=d&d=${t.row.oid})`);
      }
      L.push('');
    }
  }
  if (gallica.length) {
    L.push('### French press and books — Gallica, BnF', '');
    L.push('Full text, OCR of period print, so these are quoted as the archive holds them.', '');
    for (const g of gallica) {
      n += 1;
      L.push(`**[${n}]** ${g.date || '—'} · ${g.title}`);
      for (const s of g.snippets) L.push(`> …${s}…`);
      L.push(`> `, `> [${g.url}](${g.url})`);
      L.push('');
    }
  }

  L.push('## Method, and what this cannot tell you', '');
  L.push('- **Both archives match loose words unless quoted**, and each spells that differently:');
  L.push(
    '  NLV `txq` takes `"…"`, Gallica SRU takes `gallica adj "…"`, Gallica ContentSearch takes `"…"`.'
  );
  L.push('  Unquoted, ContentSearch for `Khanh Hoi` returns hits on *quan*, *Quant* and *quand*.');
  L.push('  A wrong query here does not error — it returns confident, irrelevant evidence.');
  L.push('- **The Vietnamese entries are machine transcriptions of scans**, not archive text.');
  L.push('  Every one links its clipping; treat a quotation as a reading, not a record.');
  L.push('- **The archive crops to a heading, not always to the match.** For an article-level hit');
  L.push('  Veridian crops the article title, so the phrase itself may be elsewhere on the page.');
  L.push('  Entries where the name could not be read in the image say so, and are not evidence');
  L.push('  about the place — only proof the archive matched that page.');
  L.push('- **Absence is not evidence.** The Vietnamese press barely exists before 1900 and thins');
  L.push('  after 1960 in this archive, so a decade with no hits may be a gap in the corpus.');
  L.push('- **Gallica records with no locatable sentence were dropped**, so the count above is');
  L.push('  smaller than the catalogue would report. They are leads, not evidence.');
  L.push('');
  return L.join('\n');
}

/* --------------------------------------------------------------------- main */

function selftest() {
  let bad = 0;
  const ok = (c, m) => {
    if (!c) {
      bad++;
      console.error(`  FAIL ${m}`);
    }
  };
  ok(spellings('Khánh Hội')[0] === 'Khanh Hoi', 'unaccented form first');
  ok(spellings('Khánh Hội').includes('Khanh-Hoi'), 'hyphenated house style present');
  ok(spellings('Khánh Hội').includes('Khánh Hội'), 'accented form kept');
  ok(
    sruQuery('Khánh Hội') ===
      '((gallica adj "Khanh Hoi") or (gallica adj "Khanh-Hoi") or (gallica adj "Khánh Hội"))',
    `SRU uses adj, not all: ${sruQuery('Khánh Hội')}`
  );
  ok(
    !sruQuery('Khanh" or (gallica all "war').includes('"war"'),
    'quotes cannot break out of the CQL'
  );
  // ContentSearch double-escapes: &amp;#233; is é, and the highlight span goes.
  ok(
    snippetText(
      "rue Boresse &amp;#233;tait C&amp;#226;u-&lt;span class='highlight'&gt;quan&lt;/span&gt;"
    ) === 'rue Boresse était Câu-quan',
    `snippet decode: ${snippetText("rue Boresse &amp;#233;tait C&amp;#226;u-&lt;span class='highlight'&gt;quan&lt;/span&gt;")}`
  );
  ok(snippetText('') === '', 'empty snippet is empty, not "undefined"');
  ok(slug('Khánh Hội') === 'khanh-hoi', `slug: ${slug('Khánh Hội')}`);
  // The widened box stays centred on the original and never runs negative.
  const [x, y, w, h] = widenCrop([1313, 1779, 391, 37]);
  ok(w > 391 && h > 37, 'the crop grows');
  ok(Math.abs(x + w / 2 - (1313 + 391 / 2)) <= 1, 'and stays centred horizontally');
  ok(Math.abs(y + h / 2 - (1779 + 37 / 2)) <= 1, 'and vertically');
  ok(
    widenCrop([5, 5, 10, 10])[0] === 0,
    'a box near the edge clamps at zero rather than going negative'
  );
  console.log(bad ? `selftest FAILED (${bad})` : 'selftest ok');
  process.exitCode = bad ? 1 : 0;
}

if (flag('--selftest')) {
  selftest();
} else {
  const name = argv.find((a, i) => !a.startsWith('--') && !argv[i - 1]?.startsWith('--'));
  if (!name) {
    console.error(
      'usage: node scripts/place_report.mjs "<place name>" [--variants a,b] [--max 16]'
    );
    process.exit(1);
  }
  const extra = (opt('--variants', '') || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
  const max = Number(opt('--max', 16));
  const key = apiKey();
  mkdirSync(OUT_DIR, { recursive: true });

  console.log(`National Library of Vietnam — "${name}"`);
  const nlv = await gatherNlv(name, max);
  console.log(
    `  ${nlv.total} hits, sampling ${nlv.rows.length} across ${Object.keys(nlv.decades).length} decades`
  );

  console.log('Gallica — SRU + ContentSearch');
  const gallica = await gatherGallica(name, extra, Math.ceil(max / 2));
  console.log(`  ${gallica.length} records with a locatable sentence`);

  console.log('Reading the Vietnamese clippings');
  const transcripts = [];
  for (const row of nlv.rows) {
    try {
      const t = await transcribe(key, row, name);
      transcripts.push({ ...t, row });
      console.log(
        `  ${row.date_id} ${t.found === false ? '[name not in crop] ' : ''}${t.legible === false ? '(illegible)' : (t.vi ?? '').replace(/\n/g, ' ').slice(0, 60)}`
      );
    } catch (err) {
      console.warn(`  ${row.oid} failed: ${err.message}`);
    }
    await sleep(PAUSE_MS);
  }

  const evidence = [
    ...transcripts.map(
      (t, i) =>
        `[${i + 1}] ${t.row.date_id} ${t.row.publication_name} (Vietnamese press)` +
        (t.found === false
          ? ': THE PLACE NAME IS NOT VISIBLE IN THIS CROP — do not cite it as evidence about the place; ' +
            `the crop shows only: ${(t.vi ?? '').replace(/\n/g, ' ')}`
          : `: ${t.legible === false ? '(illegible)' : `${(t.vi ?? '').replace(/\n/g, ' ')} / ${(t.en ?? '').replace(/\n/g, ' ')}`}`)
    ),
    ...gallica.map(
      (g, i) =>
        `[${transcripts.length + i + 1}] ${g.date} ${g.title} (Gallica): ${g.snippets.join(' … ')}`
    ),
  ].join('\n');

  console.log('Writing the synthesis');
  const synthesis = await gemini(key, [{ text: `${SYNTH(name)}\n\nEVIDENCE\n${evidence}` }]);

  const base = `${OUT_DIR}/${slug(name)}`;
  writeFileSync(`${base}.md`, markdown(name, nlv, gallica, transcripts, synthesis));
  // The same report as data, so a page can show the clipping beside its reading
  // rather than linking away to it. Numbering matches the markdown's [n].
  writeFileSync(
    `${base}.json`,
    JSON.stringify(
      {
        name,
        generated: new Date().toISOString().slice(0, 10),
        nlv: { total: nlv.total, decades: nlv.decades },
        gallicaSpellings: spellings(name, extra),
        synthesis,
        evidence: [
          ...transcripts.map((t, i) => ({
            n: i + 1,
            archive: 'nlv',
            date: t.row.date_id ? t.row.date_id.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3') : '',
            publication: t.row.publication_name,
            docType: t.row.doc_type,
            vi: t.vi ?? '',
            en: t.en ?? '',
            legible: t.legible !== false,
            found: t.found !== false,
            image: t.image,
            url: `${NLV}?a=d&d=${t.row.oid}`,
          })),
          ...gallica.map((g, i) => ({
            n: transcripts.length + i + 1,
            archive: 'gallica',
            date: g.date,
            title: g.title,
            snippets: g.snippets,
            url: g.url,
          })),
        ],
      },
      null,
      1
    )
  );
  console.log(`\n→ ${base}.md and ${base}.json`);
}
