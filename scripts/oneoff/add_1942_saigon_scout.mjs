// Add BnF's "Plan de Saïgon" 1942 (GE C-17229) to scout_candidates.
//
// It's the companion to "Plan de Cholon" 1942 (GE C-17230, ark btv1b53189369q),
// which is already linked as an unused secondary source on our composite 1942
// map (eca788e5-6780-4dca-bf23-7651a1c48aba). Found while investigating the
// sheet-to-sheet alignment drift on that composite (work/analysis/saigon6/) —
// see georef-tooling-district4 memory, 2026-09-23. Sequential shelfmarks
// (C-17229/C-17230), same publisher/date/format, height within 0.1% of the
// Cholon plate — same pair BnF catalogued and issued separately, same
// signature `sheet_panels.py` measured on our own composite scan.
//
//   node --env-file=.env scripts/oneoff/add_1942_saigon_scout.mjs            # dry run
//   node --env-file=.env scripts/oneoff/add_1942_saigon_scout.mjs --apply

import { createClient } from '@supabase/supabase-js';

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

const row = {
  source: 'gallica',
  external_id: 'ark:/12148/btv1b53197000p',
  source_url: 'https://gallica.bnf.fr/ark:/12148/btv1b53197000p',
  manifest_url: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b53197000p/manifest.json',
  title: 'Plan de Saïgon',
  creator: 'Indochine française. Service géographique. Auteur du texte',
  publisher: "Service géographique de l'Indochine",
  date: '1942',
  year: 1942,
  rights: 'domaine public',
  language: 'fre',
  holding_institution: 'Bibliothèque nationale de France',
  collection: null,
  thumbnail: 'https://gallica.bnf.fr/ark:/12148/btv1b53197000p/f1.thumbnail',
  score: 75,
  category: 'urban_plan',
  reasons: '+place +colonial:1942 +map_kw +iiif +pairs-with-held-cholon-plate',
  found_via: 'manual: companion lookup for eca788e5 (1942 Plan de Saigon-Cho Lon) sheet-to-sheet fix',
  status: 'pending',
  review_note:
    'Companion sheet to GE C-17230 "Plan de Cholon" 1942, already a secondary (unused, ' +
    'is_primary:false) source on map eca788e5-6780-4dca-bf23-7651a1c48aba. Our current R2 ' +
    'primary for that map is a composite of both panels under one rigid transform; hand-picked ' +
    'cross-sheet landmark comparison (work/analysis/saigon6/points.json, 2026-09-23) found the ' +
    'composite drifts 45-70m south of the other five D4-series sheets on every point north of ' +
    'the river, tapering to ~0 near it — consistent with one transform stretched across two ' +
    'panels rather than a mosaic defect (already ruled out: georef_error.md found the panel ' +
    "seam geometrically sound to a few pixels). Plan: import this sheet, split the map into " +
    'two independently-georeferenced rows (Saigon + Cholon), each fit with its own local GCPs.',
  raw: {
    subject: ['Saïgon'],
    coverage: ['Viêt Nam'],
    provenance: 'Gallica',
    companion_map_id: 'eca788e5-6780-4dca-bf23-7651a1c48aba',
    companion_gallica_ark: 'ark:/12148/btv1b53189369q',
    canvas: { width: 8172, height: 10860 },
  },
};

console.log(row);

if (!apply) {
  console.log('\ndry run — nothing written. Re-run with --apply.');
  process.exit(0);
}

const { error } = await db.from('scout_candidates').upsert([row], { onConflict: 'source,external_id' });
if (error) throw error;
console.log('\nupserted 1 row into scout_candidates (source=gallica, ark btv1b53197000p)');
