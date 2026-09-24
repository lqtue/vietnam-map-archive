#!/usr/bin/env node
// Clean up ocr_labels: normalise whitespace, drop empty labels, and collapse
// the duplicates left behind by OCR-ing the same sheet under several run_ids.
//
// Dry-run by default. `--apply` writes. Nothing is deleted: losers are moved to
// status 'rejected' through the set_extraction_status RPC, which the gazetteer
// view already filters out, and which reverts with the same RPC and 'pending'.
//
//   node scripts/dedupe_ocr.mjs                 # report, touch nothing
//   node scripts/dedupe_ocr.mjs --apply
//   node scripts/dedupe_ocr.mjs --map <uuid>    # one sheet only
//
// Needs PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_KEY (read from .env).

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const APPLY = process.argv.includes('--apply');
const MAP = process.argv.includes('--map') ? process.argv[process.argv.indexOf('--map') + 1] : null;
const IOU = 0.3; // ponytail: fixed threshold; the cut is flat from 0.1 to 0.5, so tuning buys nothing

for (const line of readFileSync('.env', 'utf8').split('\n')) {
  const m = line.match(/^([A-Z_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
}
const URL_ = process.env.PUBLIC_SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_KEY;
if (!URL_ || !KEY) throw new Error('PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY missing');
const H = { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' };

async function fetchAll() {
  const rows = [];
  for (let from = 0; ; from += 1000) {
    const q = `select=*&order=id${MAP ? `&map_id=eq.${MAP}` : ''}`;
    const res = await fetch(`${URL_}/rest/v1/ocr_labels?${q}`, {
      headers: { ...H, Range: `${from}-${from + 999}` },
    });
    if (!res.ok) throw new Error(`fetch ${res.status}: ${await res.text()}`);
    const page = await res.json();
    rows.push(...page);
    if (page.length < 1000) return rows;
  }
}

// Same folding as Postgres's place_key (migration 067): strip accents, lowercase,
// every run of non-alphanumerics becomes one space. "Rue de Khánh-Hội" and
// "Rue de Khanh Hoi" have to land on the same key or nothing gets deduped.
const label = (r) => r.text_corrected || r.text;
// đ has no canonical decomposition, so NFD leaves it and the a-z filter below
// would drop it outright: "ĐƯỜNG" folded to "ng" instead of "duong", which is
// why a bare "Đường" slipped past the generic-word rule. Same handling as
// src/lib/core/utils/unaccent.ts. (ư and ơ need no special case — their horn is
// a combining mark, so NFD does take it off.)
const placeKey = (s) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

// A map sets a river or a city name strung out along the feature it names —
// "R I V I È R E", "A r r o y o" — and OCR reads that back one letter at a time.
// Join a run of three or more single letters; a real word between two runs keeps
// them apart, so "S A I G O N GON" stays two tokens rather than becoming one.
// Letters only: "N ° 1" is not letter-spacing, and neither is "R. N. 1".
const LETTER = /^\p{L}$/u;
const despace = (line) => {
  const out = [];
  let run = [];
  const flush = () => {
    if (run.length >= 3) out.push(run.join(''));
    else out.push(...run);
    run = [];
  };
  for (const tok of line.split(' ')) {
    if (LETTER.test(tok)) run.push(tok);
    else {
      flush();
      if (tok) out.push(tok);
    }
  }
  flush();
  return out.filter(Boolean).join(' ');
};

// Trailing/leading whitespace only. Interior newlines are real: a multi-line
// legend entry is one label, and joining its lines would change the text.
const normalise = (s) =>
  s
    .normalize('NFC')
    .replace(/[ \t]+/g, ' ')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
    .trim()
    .split('\n')
    .map(despace)
    .join('\n');

const box = (r) =>
  r.global_x == null
    ? null
    : [r.global_x, r.global_y, r.global_x + r.global_w, r.global_y + r.global_h];
const area = (b) => (b[2] - b[0]) * (b[3] - b[1]);
function overlap(a, b) {
  if (!a || !b) return 0;
  const w = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const h = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  return w * h;
}
function iou(a, b) {
  if (!a || !b) return 0; // no pixel coords: no evidence these are the same spot
  const i = overlap(a, b);
  const u = area(a) + area(b) - i;
  return u > 0 ? i / u : 0;
}

// Every character outside ASCII, not just combining accents: "MANŒUVRES" beats
// "MANOEUVRES" and "N° 31" beats "No. 31" on the same evidence that "Khánh Hội"
// beats "Khanh Hoi" — the run that kept the character read the sheet, the one
// that dropped it guessed.
const exotic = (s) => [...s.normalize('NFD')].filter((c) => c.codePointAt(0) > 127).length;
const CTRL = new RegExp('[\\u0000-\\u0008\\u000b-\\u001f\\u007f-\\u009f\\ufffd]', 'g');
const broken = (s) => (s.match(CTRL) || []).length;
// Who survives a cluster: a human-validated row always; then a row with no
// mangled bytes; then the spelling that kept the most non-ASCII characters;
// then the longer text; then the newest run.
function better(a, b) {
  const rank = (r) => (r.review_status === 'validated' ? 2 : r.review_status === 'pending' ? 1 : 0);
  return (
    rank(a) - rank(b) ||
    broken(label(b)) - broken(label(a)) ||
    exotic(label(a)) - exotic(label(b)) ||
    label(a).length - label(b).length ||
    a.created_at.localeCompare(b.created_at)
  );
}

// Levenshtein, normalised by the longer string. Only ever called on two labels
// that already share a rectangle, so the strings are short.
function similar(a, b) {
  if (a === b) return 0;
  const m = a.length,
    n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++)
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[n] / Math.max(m, n);
}

// Cluster rows by union-find over a pairwise predicate.
function cluster(v, same) {
  const parent = v.map((_, i) => i);
  const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  for (let i = 0; i < v.length; i++)
    for (let j = i + 1; j < v.length; j++) if (same(v[i], v[j])) parent[find(i)] = find(j);
  const out = new Map();
  v.forEach((r, i) => {
    const c = find(i);
    if (!out.has(c)) out.set(c, []);
    out.get(c).push(r);
  });
  return [...out.values()];
}

async function setStatus(ids, status) {
  for (let i = 0; i < ids.length; i += 100) {
    const res = await fetch(`${URL_}/rest/v1/rpc/set_extraction_status`, {
      method: 'POST',
      headers: H,
      body: JSON.stringify({ p_status: status, p_user: null, p_ids: ids.slice(i, i + 100) }),
    });
    if (!res.ok) throw new Error(`set_extraction_status ${res.status}: ${await res.text()}`);
  }
}

const rows = await fetchAll();
const live = rows.filter((r) => r.review_status !== 'rejected');

// 1 — whitespace, plus the handful of rows where the write path stored a raw
// control byte in place of an accented letter. U+0001 is not one letter: it
// stands for É in CATHÉDRALE, È in POUDRIÈRE and ê in Évêché, so there is no
// mapping to apply — only these four known French words, spelled out. Anything
// else carrying a control byte is reported and left alone rather than guessed.
const REPAIRS = new Map([
  ["Rue de l'\u0001v\u0001ch\u0001", "Rue de l'Évêché"],
  ['PLACE DE LA CATH\u0001DRALE', 'PLACE DE LA CATHÉDRALE'],
  ['HOTEL DU G\u0001N\u0001RAL', 'HOTEL DU GÉNÉRAL'],
  ['POUDRI\u0001RE', 'POUDRIÈRE'],
  ['ANCIEN CAMP DES INDIG\u0001NES', 'ANCIEN CAMP DES INDIGÈNES'],
]);
const renames = live
  .map((r) => ({ r, from: r.text, text: normalise(REPAIRS.get(r.text) ?? r.text) }))
  .filter(({ r, text }) => text !== r.text && text !== '');
// Land the repair in memory before anything groups on the text. A repair changes
// the label's key — "ANCIEN CAMP DES INDIG<0x01>NES" becomes a plain duplicate of
// "ANCIEN CAMP DES INDIGÈNES" — so grouping on the raw text would need a second run.
for (const { r, text } of renames) r.text = text;

// 2 — empty labels. Only rows with no letter and no digit: a bare "1882" on a
// title block is content, and the gazetteer already ignores it by category.
const empty = live.filter((r) => !/[\p{L}\p{N}]/u.test(label(r)));

// 3 — duplicates: cluster per (map, place_key) by bbox overlap, keep one each
const groups = new Map();
for (const r of live) {
  if (empty.includes(r)) continue;
  const k = `${r.map_id}|${placeKey(normalise(label(r)))}`;
  if (!groups.has(k)) groups.set(k, []);
  groups.get(k).push(r);
}
const dups = [];
const gone = new Set();
function collapse(clusters, why) {
  for (const c of clusters) {
    if (c.length < 2) continue;
    const winner = c.reduce((a, b) => (better(a, b) >= 0 ? a : b));
    for (const r of c)
      if (r !== winner) {
        gone.add(r.id);
        dups.push({ loser: r, winner, why });
      }
  }
}
// Same name already matched, so a row with no pixel coords is redundant against
// one that has them. Pass 4 below must NOT do this: there, a coordinate-less row
// would bridge every similar-looking label on the sheet into one cluster.
// Overlapping tiles mean one word is read several times, and the model places it
// a few pixels differently each time. On a small box that jitter is enough to
// drop IoU to zero: "MINH" was read from three tiles at 8430,7541 / 8417,7496 /
// 8429,7538 — 45px apart, boxes ~46px wide, no overlap at all between two of
// them. So same-name rows also merge when their centres are close.
//
// Close relative to the label's own size, since a 40px word and a 1400px street
// name jitter by different amounts — and, separately, under an absolute cap. The
// cap is what stops a long street name printed twice along its own length from
// collapsing: "Boulevard Charner" appears twice 1279px apart, which is 0.9 of
// its own box, and those are two real placements of the name.
//
// ponytail: 1.5x and 300px are a judgement call, not a measurement — the
// distribution of same-name distances runs smoothly from 25px to 5000px with no
// gap to cut at. Both are set low, so obvious jitter merges and anything
// arguable is left for a reviewer.
const JITTER_SCALE = 1.5;
const JITTER_CAP = 300;
const centre = (b) => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
const longest = (b) => Math.max(b[2] - b[0], b[3] - b[1]);
function jittered(a, b) {
  const A = box(a),
    B = box(b);
  if (!A || !B) return false;
  const [ax, ay] = centre(A),
    [bx, by] = centre(B);
  const d = Math.hypot(ax - bx, ay - by);
  return d < JITTER_CAP && d < JITTER_SCALE * Math.max(longest(A), longest(B));
}

// Same name already matched, so a row with no pixel coords is redundant against
// one that has them. Pass 4 below must NOT do this: there, a coordinate-less row
// would bridge every similar-looking label on the sheet into one cluster.
for (const v of groups.values())
  collapse(
    cluster(v, (a, b) => !box(a) || !box(b) || iou(box(a), box(b)) > IOU || jittered(a, b)),
    'same name, same spot'
  );

// 4 — the same physical label read two ways. Text-key grouping cannot see these:
// "Vge de Xun Ha" and "Vge de Xuân Hòa" fold to different keys, so only the
// shared rectangle gives them away. Geometry alone is not enough either —
// two different streets whose long diagonal boxes overlap would be merged — so
// the strings have to be close as well.
//
// A cluster bigger than 10 is not a duplicate: on the 1968 sheet 243 legend
// entries were all written with the legend block's rectangle instead of their
// own line, and collapsing those would delete the legend.
// 5 — the residue left by letter-spaced street names. These sheets set a street
// name strung along the street itself — "Rue … du … Cap … St … Jacques" around a
// curve — so a tile-based read produces the whole name with a bbox covering the
// block, the separate words as their own rows, or both. Three rules:
//
//   a  same name, one box inside the other → keep the tighter box. 179 rows carry
//      a box exactly one tile across, which is the model returning the tile bounds
//      because it could not localise; a smaller box is never the worse read.
//   b  a strict subset of a fuller name's words, inside its box → keep the fuller
//      name, which is the whole label the fragment came from.
//   c  nothing but words for a *kind* of thing — "Rue", "ĐƯỜNG", "Quai", "Vge" —
//      names no place. The gazetteer listed "Rue" as an entry with 15 mentions.
const GENERIC = new Set(
  (
    'rue r ruelle boulevard bd blvd quai avenue av route rte chemin impasse passage ' +
    'place pl cite arroyo rach kinh song duong vge village de du des la le les l d ' +
    'et a au aux en no n st ste saint sainte ' +
    // The Vietnamese half of the same list, which was missing: bến (quay), kênh
    // (canal), hẻm (lane), xóm / ấp (hamlet). The gazetteer was listing 'Bến' as
    // a place for want of them. Only a label that is *nothing but* these is
    // dropped, so 'Bến Vân Đồn' is untouched.
    //
    // 'canal', 'lộ' and 'cầu' were in this list for one run and are deliberately
    // not: unlike 'rue' or 'đường', they also stand as the name itself. The rule
    // dropped 'Route du Canal' — a real street, every word of it generic — and
    // 'Lò', a kiln, which unaccents onto 'lộ'. Three bare 'Canal' rows are a
    // cheaper thing to leave for a reviewer than a street that vanishes quietly.
    'ben kenh hem xom ap'
  )
    .split(' ')
    .map((w) => placeKey(w))
);
const words = (r) =>
  placeKey(normalise(label(r)))
    .split(' ')
    .filter(Boolean);
const generic = (r) => {
  const w = words(r);
  return w.length > 0 && w.every((x) => GENERIC.has(x));
};
// Are a's words in b's, in order? A plain subset test is not enough: it reads
// "Chasseloup Catinat Rue" — two street names the model ran together — as a
// fuller form of "Rue Catinat" and throws the good row away. Order does not have
// to be contiguous, or "Rue Eudel" would not merge into "Rue Jean Eudel".
function subsequence(a, b) {
  let i = 0;
  for (const w of b) if (w === a[i]) i++;
  return i === a.length;
}
const areaOf = (r) => (box(r) ? area(box(r)) : Infinity);
// how much of a sits inside b
const inside = (a, b) => {
  const A = box(a);
  return A && box(b) && area(A) > 0 ? overlap(A, box(b)) / area(A) : 0;
};

const residue = [];
const survivors = live.filter((r) => !gone.has(r.id) && !empty.includes(r));
const bySheet5 = new Map();
for (const r of survivors) {
  if (!bySheet5.has(r.map_id)) bySheet5.set(r.map_id, []);
  bySheet5.get(r.map_id).push(r);
}
for (const v of bySheet5.values()) {
  for (const a of v) {
    if (gone.has(a.id)) continue;
    if (a.review_status === 'validated') continue; // a person signed off on this one
    if (generic(a)) {
      gone.add(a.id);
      residue.push({ loser: a, winner: null, why: 'names a kind of thing, not a place' });
      continue;
    }
    const wa = words(a);
    let keeper = null;
    for (const b of v) {
      if (a === b || gone.has(b.id)) continue;
      const wb = words(b);
      if (!subsequence(wa, wb)) continue;
      // The two rules point their containment test in opposite directions. A
      // fragment sits inside the fuller name's box, so a goes. The same name read
      // twice is the reverse: the looser box swallows the tighter one, and it is
      // the swallower that goes — a box one tile across is the model returning the
      // tile bounds rather than finding the words.
      const fuller = wb.length > wa.length && inside(a, b) >= 0.8;
      const looser = wb.length === wa.length && inside(b, a) >= 0.8 && areaOf(b) < areaOf(a);
      if (!fuller && !looser) continue;
      if (!keeper || areaOf(b) < areaOf(keeper)) keeper = b;
    }
    if (keeper) {
      gone.add(a.id);
      residue.push({
        loser: a,
        winner: keeper,
        why:
          words(keeper).length > wa.length ? 'fragment of a fuller name' : 'same name, looser box',
      });
    }
  }
}
dups.push(...residue);

const bySheet = new Map();
for (const r of live) {
  if (gone.has(r.id) || empty.includes(r)) continue;
  if (!bySheet.has(r.map_id)) bySheet.set(r.map_id, []);
  bySheet.get(r.map_id).push(r);
}
// A box that many rows share carries no location: the 1968 legend has 178
// entries all stamped with the legend block's rectangle instead of their own
// line. For those, IoU is 1 for every pair and the geometry half of the test
// below is meaningless — leaving only the text half, which read
// "109. Văn-Đồn Barracks" and "103. Lê-Văn-Duyệt Barracks" as one label.
const SHARED_BOX = 5;
const boxKey = (r) => {
  const b = box(r);
  return b ? `${r.map_id}|${b.map(Math.round).join(',')}` : null;
};
const boxUsers = new Map();
for (const v of bySheet.values())
  for (const r of v) {
    const k = boxKey(r);
    if (k) boxUsers.set(k, (boxUsers.get(k) ?? 0) + 1);
  }
const locatable = (r) => {
  const k = boxKey(r);
  return k !== null && (boxUsers.get(k) ?? 0) <= SHARED_BOX;
};

// Two labels on the same rectangle are one label read twice *only if the part
// that names something* is near-identical. Measured on the whole text this pass
// merged 'Đường Phan Tôn' into 'Đường Phan Ngữ' and 'Route Communale N° 10' into
// 'N° 13': the shared street-type word is half the string, so it carried the
// score on its own and two different streets scored as one. Two guards:
//
//   * compare the *core* — the name with its leading and trailing type words
//     ("Rue", "Đường", "de", "N°") dropped. This is also what lets the real
//     variants through, since "R. Vannier" and "Rue Vannier" have one core.
//   * a number is not a typo of another number. If both carry digits and the
//     digit runs differ, they are different labels whatever the letters say —
//     that alone was 23 of the 124 merges, all of them wrong.
const core = (r) => {
  const w = words(r);
  let i = 0;
  let j = w.length;
  while (i < j && GENERIC.has(w[i])) i++;
  while (j > i && GENERIC.has(w[j - 1])) j--;
  return w.slice(i, j).join(' ');
};
const numbers = (r) => (placeKey(normalise(label(r))).match(/[0-9]+/g) || []).join(' ');
// 0.25, not the 0.34 this pass used to run at. Between the two sit thirteen
// pairs, and they are not a wash: five are different streets ('Trần Doãn Khanh'
// against 'Trần Tấn Phát', 'Nguyễn Kim' against 'Nguyễn Tiểu La'), the rest are
// two readings of one. The costs are not symmetric either — a spare duplicate
// costs a reviewer one click, while a wrongly merged row takes a real street
// name out of the archive and says nothing. So the cut sits below them.
const SIMILAR_MAX = 0.25;
const sameLabelText = (a, b) =>
  numbers(a) === numbers(b) && similar(core(a), core(b)) <= SIMILAR_MAX;

const before = dups.length;
for (const v of bySheet.values())
  collapse(
    cluster(
      v,
      (a, b) => locatable(a) && locatable(b) && iou(box(a), box(b)) > 0.6 && sameLabelText(a, b)
    ).filter((c) => c.length <= 10),
    'same spot, near-identical text'
  );
const variants = dups.length - before;

console.log(`${rows.length} rows, ${live.length} not already rejected`);
console.log(`  text to repair          : ${renames.length}`);
for (const { from, text } of renames)
  console.log(`    ${JSON.stringify(from)} → ${JSON.stringify(text)}`);
console.log(`  empty labels to reject  : ${empty.length}`);
console.log(`  duplicates to reject    : ${dups.length - variants - residue.length}`);
console.log(`  text variants to reject : ${variants}`);
console.log(`  street-name residue     : ${residue.length}`);
console.log(`  labels that survive     : ${live.length - empty.length - dups.length}`);
for (const { loser, winner, why } of dups.slice(-15))
  console.log(
    `    "${label(loser)}" [${loser.run_id}] → ${winner ? `"${label(winner)}"` : '(dropped)'}  (${why})`
  );
if (dups.length > 15) console.log(`    … ${dups.length - 15} more`);

mkdirSync('work/ocr/outputs', { recursive: true });
const stamp = new Date().toISOString().slice(0, 19).replace(/[:T-]/g, '');
const report = `work/ocr/outputs/dedupe-${stamp}${APPLY ? '-applied' : '-dryrun'}.json`;
writeFileSync(
  report,
  JSON.stringify(
    {
      applied: APPLY,
      iou: IOU,
      renames: renames.map(({ r, from, text }) => ({ id: r.id, from, to: text })),
      empty: empty.map((r) => ({ id: r.id, map_id: r.map_id, run_id: r.run_id, text: r.text })),
      duplicates: dups.map(({ loser, winner, why }) => ({
        id: loser.id,
        map_id: loser.map_id,
        run_id: loser.run_id,
        text: label(loser),
        kept: winner?.id ?? null,
        kept_text: winner ? label(winner) : null,
        kept_run: winner?.run_id ?? null,
        why,
      })),
    },
    null,
    2
  )
);
console.log(`report → ${report}`);

const unfixed = live.filter(
  (r) => broken(r.text) && !REPAIRS.has(r.text) && !dups.some((d) => d.loser === r)
);
if (unfixed.length)
  console.log(
    `  ${unfixed.length} row(s) carry a control byte with no entry in REPAIRS — left untouched:\n` +
      unfixed.map((r) => `    ${r.id} ${JSON.stringify(r.text)}`).join('\n')
  );

if (!APPLY) {
  console.log('dry run — nothing written. Re-run with --apply.');
  process.exit(0);
}

for (const { r, text } of renames) {
  const res = await fetch(`${URL_}/rest/v1/ocr_labels?id=eq.${r.id}`, {
    method: 'PATCH',
    headers: H,
    body: JSON.stringify({ text }),
  });
  // 23505 is ocr_extractions_upsert_key (migration 077), which carries `text`:
  // the repair turned this row into a byte-for-byte copy of another read of the
  // same word in the same tile. That is the duplicate this script exists to
  // collapse, so report it and leave the row for the next pass rather than
  // aborting halfway through a corpus-wide write.
  if (!res.ok) {
    const body = await res.text();
    if (res.status === 409 && body.includes('23505')) {
      console.log(`  rename collided with an existing row, left alone: ${r.id} → ${text}`);
      continue;
    }
    throw new Error(`patch ${r.id}: ${body}`);
  }
}
await setStatus([...empty.map((r) => r.id), ...dups.map((d) => d.loser.id)], 'rejected');
console.log(`applied. Undo: set_extraction_status('pending', …) with the ids in ${report}`);
