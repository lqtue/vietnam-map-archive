// One-off, 2026-10-05: link the two published halves of the 1942 Saigon-Cho Lon plan so each one's
// Info tab offers the other (SheetEditions reads `extra_metadata.part_of` when a map has no series).
//
//   node --env-file=.env scripts/oneoff/link_saigon_cholon_2026_10.mjs          # dry run
//   node --env-file=.env scripts/oneoff/link_saigon_cholon_2026_10.mjs --apply
//
// Merges one key into `extra_metadata`; every other key is kept. A re-run is a no-op.
import { createClient } from '@supabase/supabase-js';

const KEY = 'plan-saigon-cholon-1942';
const SLUGS = ['plan-de-cholon', 'plan-de-saigon'];

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

let changed = 0;
for (const slug of SLUGS) {
  const { data, error } = await db
    .from('maps')
    .select('id,extra_metadata')
    .eq('slug', slug)
    .maybeSingle();
  if (error) throw new Error(`${slug}: ${error.message}`);
  if (!data) {
    console.log(`MISSING  ${slug}`);
    continue;
  }
  const meta = data.extra_metadata ?? {};
  if (meta.part_of === KEY) {
    console.log(`SKIP     ${slug} already part_of ${KEY}`);
    continue;
  }
  if (meta.part_of !== undefined) {
    console.log(`SKIP     ${slug} has part_of ${JSON.stringify(meta.part_of)}, expected none`);
    continue;
  }
  console.log(`${apply ? 'UPDATE  ' : 'WOULD   '} ${slug}.extra_metadata.part_of = ${KEY}`);
  if (!apply) continue;
  const { error: e2 } = await db
    .from('maps')
    .update({ extra_metadata: { ...meta, part_of: KEY } })
    .eq('id', data.id);
  if (e2) throw new Error(`${slug}: ${e2.message}`);
  changed++;
}
console.log(apply ? `\n${changed} rows updated.` : '\nDry run. Re-run with --apply.');
