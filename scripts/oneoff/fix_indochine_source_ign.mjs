/**
 * fix_indochine_source_ign.mjs — the catalogue searched is not the source.
 *
 *   node --env-file=.env scripts/oneoff/fix_indochine_source_ign.mjs
 *   node --env-file=.env scripts/oneoff/fix_indochine_source_ign.mjs --apply
 *
 * All 75 held Indochine cells recorded `source = 'CartoMundi'`. CartoMundi is a
 * union catalogue: it is where the scans were *found*. IGN holds the paper and
 * serves the images over Nakala, which the rows' own rights line has always
 * said ("CC BY 4.0 — scan by IGN, deposited in Nakala") and the About panel on
 * the series page says too. So the Source column named the index rather than
 * the library, on the one page whose job is provenance.
 *
 * `source_ref` moves with it. It holds a bare CartoMundi fkey — "16763" — which
 * is that catalogue's identifier and means nothing at IGN. Renaming `source`
 * and leaving the ref would reproduce the fault this survey already carries
 * once: 460 L7014 rows say PCL and link to Texas Tech. So the fkey goes into
 * `note`, where it is still findable and is labelled with the catalogue it
 * belongs to, and `source_ref` is emptied rather than left pointing at an
 * identifier its own column now misattributes.
 *
 * Per-printing IGN references are not lost — `sheet_sources` (mig 087) carries
 * IGN's 304 copy records for this survey with their Nakala DOIs, which is the
 * queryable home for them. `series_sheets.source` answers only "whose scan is
 * this", one institution per cell.
 *
 * The four unheld cells are untouched: they have no source at all, because no
 * digitised copy is known at IGN, CartoMundi or Gallica.
 */
import { createClient } from '@supabase/supabase-js';

const KEY = 'indochine-1-25-000-tonkin-thanh-hoa';
const apply = process.argv.includes('--apply');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: rows, error } = await db
  .from('series_sheets')
  .select('sheet_number,source,source_ref,note')
  .eq('series_key', KEY)
  .eq('source', 'CartoMundi')
  .limit(2000);
if (error) throw new Error(error.message);

const changes = rows.map((r) => ({
  sheet_number: r.sheet_number,
  source: 'IGN',
  source_ref: null,
  // Prepended, not appended: it is the identifier, and the existing note is a
  // sentence about the cell's records.
  note: [r.source_ref ? `CartoMundi fkey ${r.source_ref}` : null, r.note]
    .filter(Boolean)
    .join(' · '),
  was: `${r.source} ${r.source_ref ?? ''}`.trim(),
}));

console.log(`cells to re-attribute: ${changes.length}`);
for (const c of changes.slice(0, 5)) {
  console.log(`  ${c.sheet_number.padEnd(7)} ${c.was}  ->  IGN`);
  console.log(`  ${''.padEnd(7)} note: ${c.note.slice(0, 90)}`);
}
if (changes.length > 5) console.log(`  … ${changes.length - 5} more`);

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
  console.log(`\napplied: ${changes.length} cells now attributed to IGN`);
}
