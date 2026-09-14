/**
 * fix_l7014_editions.mjs — the edition field lost its leading zeros, and one
 * name is a merge that ran twice.
 *
 *   node --env-file=.env scripts/oneoff/fix_l7014_editions.mjs            # dry run
 *   node --env-file=.env scripts/oneoff/fix_l7014_editions.mjs --apply
 *   node --env-file=.env scripts/oneoff/fix_l7014_editions.mjs --apply-names
 *
 * Migration 086 made `edition` text on purpose: "003", "3-DMA" and "2-AMS" are
 * all real values off this one survey, and a number cannot hold the suffix that
 * says which office issued the printing. The column is text and the backfill
 * wrote integers into it anyway, so 433 of the 452 mosaic cells store `1` where
 * the GeoPDF's XMP says `001`. The nine hand-entered rows kept their `3-DMA`,
 * which is how the fault stayed invisible: the values that would have looked
 * obviously broken are the ones nothing touched.
 *
 * Source of truth is `work/l7014/build/<key>.geojson`, the mosaic manifest,
 * which `l7014_mosaic.py manifest` writes straight from each sheet's XMP.
 *
 * Names are a third thing and are NOT applied here — see `--apply-names` and
 * the CSV it reads. A sheet's name belongs to an edition rather than to the
 * cell (6150-3 is KIM BÔI to Vietnam and "Thuy Hien" to PCL), so which name a
 * row should carry is a judgement about what the column means, not a repair.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const KEY = 'series-l7014-vietnam-1-50-000';
const MANIFEST = 'work/l7014/build/l7014-20260913.geojson';
const CSV = 'work/l7014/name-conflicts.csv';
const apply = process.argv.includes('--apply');
const applyNames = process.argv.includes('--apply-names');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

/** Levenshtein, so the conflict list can be sorted by how different the two
 *  names actually are. `Atiun`/`Atuin` is a transposition; `Pa Kha`/`Bac Ha` is
 *  a different name for the same ground. Only the second kind needs a human. */
function distance(a, b) {
  const m = a.length,
    n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[n];
}
const fold = (s) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '');

const manifest = new Map(
  JSON.parse(readFileSync(MANIFEST, 'utf8')).features.map((f) => [f.properties.sheet, f.properties])
);
const { data: rows, error } = await db
  .from('series_sheets')
  .select('sheet_number,name,edition')
  .eq('series_key', KEY)
  .limit(2000);
if (error) throw new Error(error.message);

// ── 1. editions the backfill turned into numbers ───────────────────────────
const editionFixes = [];
for (const r of rows) {
  const src = manifest.get(r.sheet_number)?.edition;
  if (src == null || r.edition == null) continue;
  const want = String(src);
  if (want === String(r.edition)) continue;
  // Only restore a value that differs by its leading zeros. Anything else is a
  // disagreement about which printing this is, and must not be papered over.
  if (!/^\d+$/.test(want) || String(Number(want)) !== String(r.edition)) {
    console.log(`SKIP ${r.sheet_number}: "${r.edition}" vs manifest "${want}" — not just zeros`);
    continue;
  }
  editionFixes.push({ sheet_number: r.sheet_number, edition: want });
}

// ── 2. a name that carries the same alternate twice ────────────────────────
const nameFixes = [];
for (const r of rows) {
  if (!r.name) continue;
  const parts = r.name.split(' / ').map((s) => s.trim());
  const uniq = [...new Set(parts)];
  if (uniq.length !== parts.length)
    nameFixes.push({ sheet_number: r.sheet_number, name: uniq.join(' / ') });
}

// ── 3. the conflict list, for a human, sorted by how different they are ────
const conflicts = [];
for (const r of rows) {
  const src = manifest.get(r.sheet_number)?.name;
  if (!src || !r.name || r.name.includes(src)) continue;
  const alts = r.name.split(' / ').map((s) => s.trim());
  const best = Math.min(...alts.map((a) => distance(fold(a), fold(src))));
  conflicts.push({ sheet: r.sheet_number, manifest: src, db: r.name, d: best });
}
conflicts.sort((a, b) => b.d - a.d);

console.log(`\neditions to restore: ${editionFixes.length}`);
for (const f of editionFixes.slice(0, 5)) console.log(`  ${f.sheet_number} -> ${f.edition}`);
if (editionFixes.length > 5) console.log(`  … ${editionFixes.length - 5} more`);
console.log(`duplicated names to collapse: ${nameFixes.length}`);
for (const f of nameFixes) console.log(`  ${f.sheet_number} -> ${f.name}`);
console.log(`name conflicts for review: ${conflicts.length}`);

if (applyNames) {
  if (!existsSync(CSV)) throw new Error(`${CSV} not found — run without --apply-names first`);
  const lines = readFileSync(CSV, 'utf8').trim().split('\n').slice(1);
  let n = 0;
  for (const line of lines) {
    const [sheet, , , keep] = line.split(',').map((s) => s.replace(/^"|"$/g, '').trim());
    if (!keep) continue;
    const { error } = await db
      .from('series_sheets')
      .update({ name: keep })
      .eq('series_key', KEY)
      .eq('sheet_number', sheet);
    if (error) throw new Error(`${sheet}: ${error.message}`);
    n++;
  }
  console.log(`\n${n} names written from ${CSV}`);
} else {
  // `keep` starts empty: a blank row changes nothing, so an unreviewed file is
  // a no-op rather than a bulk overwrite.
  const csv = ['sheet,manifest_name,db_name,keep']
    .concat(conflicts.map((c) => `${c.sheet},"${c.manifest}","${c.db}",`))
    .join('\n');
  writeFileSync(CSV, csv + '\n');
  console.log(
    `  written to ${CSV}, most-different first (edit distance ${conflicts[0]?.d} … ${conflicts.at(-1)?.d})`
  );
}

if (!apply) {
  console.log('\nDry run. Re-run with --apply to write editions and the duplicated name.');
} else {
  for (const f of editionFixes) {
    const { error } = await db
      .from('series_sheets')
      .update({ edition: f.edition })
      .eq('series_key', KEY)
      .eq('sheet_number', f.sheet_number);
    if (error) throw new Error(`${f.sheet_number}: ${error.message}`);
  }
  for (const f of nameFixes) {
    const { error } = await db
      .from('series_sheets')
      .update({ name: f.name })
      .eq('series_key', KEY)
      .eq('sheet_number', f.sheet_number);
    if (error) throw new Error(`${f.sheet_number}: ${error.message}`);
  }
  console.log(`\napplied: ${editionFixes.length} editions, ${nameFixes.length} names`);
}
