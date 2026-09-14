/**
 * set_anu_source.mjs — name ANU as the source for the cells it documents best.
 *
 *   node --env-file=.env scripts/oneoff/set_anu_source.mjs          # dry run
 *   node --env-file=.env scripts/oneoff/set_anu_source.mjs --apply
 *
 * `series_sheets.source` holds ONE institution per cell, and for all 123 of
 * L7014's unheld cells it says TTU — because Texas Tech is the only place
 * anyone had looked. The ANU crawl (`scout_anu_l7014.mjs`) found 14 of those
 * cells in the Open Research Repository, every item marked Open Access and
 * "Copyright Expired". TTU states no rights position at all, so for a reader
 * deciding whether they may use a scan, ANU is the better answer.
 *
 * Both institutions hold these cells and one column cannot say so. That is what
 * `sheet_sources` (mig 087) exists to fix; until it is applied, the TTU URL is
 * preserved in `note` rather than dropped, so nothing is lost by pointing the
 * column at the source that documents its terms.
 *
 * Only cells the archive does NOT hold are touched: for a held cell `source`
 * records where our own copy came from, and rewriting that would be a lie about
 * provenance — the fault this survey has already been bitten by twice.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';

const KEY = 'series-l7014-vietnam-1-50-000';
const apply = process.argv.includes('--apply');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const anu = new Map(
  JSON.parse(readFileSync('work/l7014/anu-sources.json', 'utf8'))
    .items.filter((i) => i.cell)
    .map((i) => [i.cell, i])
);

const { data: rows, error } = await db
  .from('series_sheets')
  .select('sheet_number,held_by,source,source_ref,note')
  .eq('series_key', KEY)
  .limit(2000);
if (error) throw new Error(error.message);

const changes = [];
for (const r of rows) {
  if (r.held_by) continue;
  const item = anu.get(r.sheet_number);
  if (!item || r.source === 'ANU') continue;
  // Keep the Texas Tech URL. One column cannot name two institutions, and the
  // one it drops is still where a reader may have to go if ANU's copy is bad.
  const keep = r.source && r.source_ref ? `also at ${r.source}: ${r.source_ref}` : null;
  const note = [r.note, keep].filter(Boolean).join(' · ') || null;
  changes.push({
    sheet_number: r.sheet_number,
    source: 'ANU',
    source_ref: item.url,
    note,
    was: `${r.source} ${r.source_ref ?? ''}`.trim(),
  });
}

console.log(`cells ANU documents and the archive does not hold: ${changes.length}`);
for (const c of changes) {
  console.log(`  ${c.sheet_number.padEnd(8)} ${c.was}`);
  console.log(`  ${''.padEnd(8)} -> ANU ${c.source_ref}`);
}

if (!apply) {
  console.log('\nDry run. Re-run with --apply to write.');
} else {
  for (const c of changes) {
    const { error } = await db
      .from('series_sheets')
      .update({ source: c.source, source_ref: c.source_ref, note: c.note })
      .eq('series_key', KEY)
      .eq('sheet_number', c.sheet_number);
    if (error) throw new Error(`${c.sheet_number}: ${error.message}`);
  }
  console.log(`\napplied: ${changes.length} cells now name ANU`);
}
