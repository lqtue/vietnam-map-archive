/**
 * fix_l7014_source_refs.mjs — 460 cells named one library and linked another.
 *
 *   node --env-file=.env scripts/oneoff/fix_l7014_source_refs.mjs
 *   node --env-file=.env scripts/oneoff/fix_l7014_source_refs.mjs --apply
 *
 * `source = 'PCL'` with `source_ref` pointing at `vietnam.ttu.edu`, on 460 of
 * the 461 held cells. `source` is right — the mosaic was built from Perry-
 * Castañeda's GeoPDFs — so it is the ref that is wrong, the mirror image of the
 * Indochine fault where the source named the catalogue and the ref was correct.
 *
 * Where the wrong ref came from is visible in the numbers: of the 460, Texas
 * Tech actually holds 25. The other 435 are a URL template stamped per sheet
 * number — `items.php?item=<sheet>` composed for every cell of the survey
 * before anyone checked which cells TTU has. They resolve to a page for a sheet
 * that may not exist there, which is worse than an empty column, and it is why
 * `source_ref` cannot be used as an item key for a join.
 *
 * The right value is already on disk: `work/l7014/sheets.json` carries PCL's
 * own URL for all 534 sheets it publishes, and every one of the 460 has one.
 * So this repairs rather than clears.
 *
 * The TTU URLs are dropped, not preserved in `note`. 435 of them were never
 * verified and keeping a guess costs more than it saves; the 25 real ones are
 * in `sheet_sources` (087) with the URLs the fetch on 2026-09-14 actually
 * resolved, which is where a per-institution reference now belongs.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';

const KEY = 'series-l7014-vietnam-1-50-000';
const apply = process.argv.includes('--apply');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const pcl = new Map(
  JSON.parse(readFileSync('work/l7014/sheets.json', 'utf8')).map((r) => [r.sheet, r])
);

const { data: rows, error } = await db
  .from('series_sheets')
  .select('sheet_number,source,source_ref')
  .eq('series_key', KEY)
  .eq('source', 'PCL')
  .limit(2000);
if (error) throw new Error(error.message);

const changes = [];
const noUrl = [];
for (const r of rows) {
  if (!/ttu\.edu/.test(r.source_ref ?? '')) continue;
  const url = pcl.get(r.sheet_number)?.url;
  if (!url) {
    noUrl.push(r.sheet_number);
    continue;
  }
  changes.push({ sheet_number: r.sheet_number, source_ref: url, was: r.source_ref });
}

console.log(`cells naming PCL and linking Texas Tech: ${changes.length + noUrl.length}`);
console.log(`  repairable from work/l7014/sheets.json: ${changes.length}`);
if (noUrl.length) console.log(`  no PCL url on disk, left alone: ${noUrl.join(' ')}`);
for (const c of changes.slice(0, 4))
  console.log(`  ${c.sheet_number.padEnd(8)} -> ${c.source_ref}`);
if (changes.length > 4) console.log(`  … ${changes.length - 4} more`);

if (!apply) {
  console.log('\nDry run. Re-run with --apply to write.');
} else {
  for (const c of changes) {
    const { error } = await db
      .from('series_sheets')
      .update({ source_ref: c.source_ref })
      .eq('series_key', KEY)
      .eq('sheet_number', c.sheet_number);
    if (error) throw new Error(`${c.sheet_number}: ${error.message}`);
  }
  console.log(`\napplied: ${changes.length} refs repointed at Perry-Castañeda`);
}
