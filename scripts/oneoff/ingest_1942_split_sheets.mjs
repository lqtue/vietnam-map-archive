// Ingest the two new 1942 District 4 sheets (Plan de Saïgon GE C-17229, Plan de
// Cholon GE C-17230) as their own `maps` rows, replacing the stitched composite
// (eca788e5-...) as the maintained georeference for that survey. See
// georef-tooling-district4 memory, 2026-09-23, and add_1942_saigon_scout.mjs /
// guess_1942_split_xy.mjs for how this arc got here.
//
// Mirrors POST /api/admin/scout's ingest logic exactly (src/routes/api/admin/
// scout/+server.ts) since that route needs an authenticated admin/mod session
// this script doesn't have -- same insertPayload shape, same scout_candidates
// bookkeeping. Adds one step that route doesn't do: sets `allmaps_id` to the
// annotation the user already placed by hand in the Allmaps Editor (11 GCPs
// Saigon, 4 GCPs Cholon, both helmert, both self-fit RMSE in the healthy
// 12-16m range -- see chat).
//
// Deliberately stops short of `mirrorAnnotation` (R2 rewrite + publish): these
// images aren't tiled to R2 yet, and mirrorAnnotation's sourceSizeMismatch
// check would fail against a mirror that doesn't exist. That's the next step,
// not this one.
//
//   node --env-file=.env scripts/oneoff/ingest_1942_split_sheets.mjs            # dry run
//   node --env-file=.env scripts/oneoff/ingest_1942_split_sheets.mjs --apply

import { createClient } from '@supabase/supabase-js';

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const CHOLON_CANDIDATE = {
  source: 'gallica',
  external_id: 'ark:/12148/btv1b53189369q',
  source_url: 'https://gallica.bnf.fr/ark:/12148/btv1b53189369q',
  manifest_url: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53189369q/manifest.json',
  title: 'Plan de Cholon',
  creator: 'Indochine française. Service géographique. Auteur du texte',
  publisher: "Service géographique de l'Indochine",
  date: '1942',
  year: 1942,
  rights: 'domaine public',
  language: 'fre',
  holding_institution: 'Bibliothèque nationale de France',
  collection: null,
  thumbnail: 'https://gallica.bnf.fr/ark:/12148/btv1b53189369q/f1.thumbnail',
  score: 75,
  category: 'urban_plan',
  reasons: '+place +colonial:1942 +map_kw +iiif +pairs-with-held-saigon-plate',
  found_via:
    'manual: companion lookup for eca788e5 (1942 Plan de Saigon-Cho Lon) sheet-to-sheet fix',
  status: 'pending',
  review_note:
    'Companion sheet to GE C-17229 "Plan de Saïgon" 1942 (scout_candidates row added same day). ' +
    'Already an unused (is_primary:false) secondary source on map eca788e5-6780-4dca-bf23-7651a1c48aba; ' +
    "this record gives it its own maps row instead. See that row's review_note for the full " +
    'rationale (sheet-to-sheet drift on the stitched composite).',
  raw: {
    subject: ['Chợ Lớn'],
    coverage: ['Viêt Nam'],
    provenance: 'Gallica',
    companion_map_id: 'eca788e5-6780-4dca-bf23-7651a1c48aba',
    companion_gallica_ark: 'ark:/12148/btv1b53197000p',
    canvas: { width: 7840, height: 10846 },
  },
};

const ALLMAPS_ID = {
  'ark:/12148/btv1b53189369q': '05790daa7f6c8e50', // Cholon
  'ark:/12148/btv1b53197000p': 'fb8fb7d08d2338bd', // Saigon
};

console.log(apply ? 'APPLY mode\n' : 'DRY RUN -- pass --apply to write\n');

// 1. Ensure the Cholon candidate exists (Saigon's was added earlier this session).
const { error: upsertErr } = await db
  .from('scout_candidates')
  .upsert([CHOLON_CANDIDATE], { onConflict: 'source,external_id' });
if (upsertErr) throw upsertErr;
console.log('scout_candidates: Cholon row upserted (pending).');

// 2. Approve both.
const externalIds = ['ark:/12148/btv1b53189369q', 'ark:/12148/btv1b53197000p'];
if (apply) {
  const { error: approveErr } = await db
    .from('scout_candidates')
    .update({ status: 'approved' })
    .eq('source', 'gallica')
    .in('external_id', externalIds);
  if (approveErr) throw approveErr;
}
console.log(`scout_candidates: ${externalIds.length} rows set to approved.`);

// 3. Ingest -- same shape as POST /api/admin/scout.
const { data: cands, error: fetchErr } = await db
  .from('scout_candidates')
  .select('*')
  .eq('source', 'gallica')
  .in('external_id', externalIds);
if (fetchErr) throw fetchErr;

for (const c of cands ?? []) {
  const holdingInst = c.holding_institution ?? '';
  const insertPayload = {
    name: (c.title || '(untitled)').slice(0, 240),
    year: c.year ?? null,
    year_label: c.date ?? null,
    status: 'draft',
    source_type: holdingInst.includes('David Rumsey')
      ? 'rumsey'
      : holdingInst.includes('Bibliothèque nationale')
        ? 'bnf'
        : 'other',
    holding_institution: c.holding_institution ?? null,
    collection: c.collection ?? null,
    original_title: c.title ?? null,
    creator: c.creator ?? null,
    dc_publisher: c.publisher ?? null,
    language: c.language ?? null,
    rights: c.rights ?? null,
    iiif_manifest: c.manifest_url ?? null,
    iiif_image: null,
    source_url: c.source_url ?? null,
    thumbnail: c.thumbnail ?? null,
    allmaps_id: ALLMAPS_ID[c.external_id] ?? null,
    extra_metadata: {
      scout_source: c.source,
      scout_external_id: c.external_id,
      scout_category: c.category,
      scout_found_via: c.found_via,
      scout_candidate_id: c.id,
    },
  };

  console.log(`\n-> ${c.title} (${c.external_id})`);
  console.log(insertPayload);

  if (!apply) continue;

  const { data: newMap, error: insErr } = await db
    .from('maps')
    .insert(insertPayload)
    .select('id')
    .single();
  if (insErr) throw insErr;

  await db
    .from('scout_candidates')
    .update({ status: 'ingested', map_id: newMap.id })
    .eq('id', c.id);

  console.log(`   maps row created: ${newMap.id}`);
}

if (!apply) console.log('\ndry run -- nothing written. Re-run with --apply.');
