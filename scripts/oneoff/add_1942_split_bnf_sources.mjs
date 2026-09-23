// Add the missing "BnF Gallica" map_iiif_sources row for the two 1942 split
// sheets (Plan de Saigon / Plan de Cholon). ingest_1942_split_sheets.mjs
// wrote maps.iiif_manifest/iiif_image but never a map_iiif_sources row for
// the original scan the way every other multi-source sheet in the corpus
// has (IA + BnF + R2) -- so verifiedEditorSourceId() has no candidate that
// hashes to the map's allmaps_id (which is keyed to the Gallica /f1 image,
// confirmed by generateId()) and the admin georef-fix list shows "no
// source". See georef-tooling-district4 memory, 2026-09-23.
//
//   node --env-file=.env scripts/oneoff/add_1942_split_bnf_sources.mjs            # dry run
//   node --env-file=.env scripts/oneoff/add_1942_split_bnf_sources.mjs --apply

import { createClient } from '@supabase/supabase-js';

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const ROWS = [
  {
    map_id: '6989a04e-0f51-439e-9390-a6678aff374c', // Plan de Saïgon
    label: 'BnF Gallica',
    source_type: 'bnf',
    iiif_manifest: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53197000p/manifest.json',
    iiif_image: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53197000p/f1',
    is_primary: false,
    sort_order: 0,
  },
  {
    map_id: '8c605819-a8c3-4b2f-aa4a-6fad12893eab', // Plan de Cholon
    label: 'BnF Gallica',
    source_type: 'bnf',
    iiif_manifest: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53189369q/manifest.json',
    iiif_image: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53189369q/f1',
    is_primary: false,
    sort_order: 0,
  },
];

console.log(apply ? 'APPLY mode\n' : 'DRY RUN -- pass --apply to write\n');

for (const row of ROWS) {
  const { data: existing, error: fetchErr } = await db
    .from('map_iiif_sources')
    .select('id,source_type')
    .eq('map_id', row.map_id);
  if (fetchErr) throw fetchErr;
  if (existing.some((s) => s.source_type === 'bnf')) {
    console.log(`${row.map_id}: BnF row already exists, skipping`);
    continue;
  }

  console.log(`${row.map_id}:`, row);
  if (!apply) continue;

  const { error: insErr } = await db.from('map_iiif_sources').insert(row);
  if (insErr) throw insErr;
  console.log('   inserted.');
}

if (!apply) console.log('\ndry run -- nothing written. Re-run with --apply.');
