import { createClient } from '@supabase/supabase-js';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const yearMismatchSlugs = [
  'plan-de-la-riviere-de-hue',
  'hanoi-plan-dessine-par-pham-dinh-bach',
  'cochinchine-francaise',
  'plan-annamite-d-hanoi',
  'plan-du-port-de-saigon',
];

const provenanceGapSlugs = [
  'map-of-imperial-city-of-hue',
  'plan-cadastral-de-la-ville-de-saigon-cochinchine',
  'saigon-cholon',
  'saigon-plan',
  'saigon-port-plan',
  'sai-gon-viet-nam-city-maps-1-12-500',
  'hanoi-plan-dessine-par-pham-dinh-bach',
  'plan-de-la-ville-de-hanoi-1942',
  'hue-et-ses-environs',
  'nha-nam',
  'an-thi',
  'hanoi-economique',
  'plan-de-la-ville-de-saigon-1878',
  'carte-du-sud-vietnam',
  'batiments-civils-le-plan-du-colonel-du-genie',
];

const cols =
  'id,slug,name,original_title,year,year_label,creator,dc_publisher,dc_description,dc_subject,dc_coverage,source_type,source_url,holding_institution,collection,iiif_image,status';

const allSlugs = [...new Set([...yearMismatchSlugs, ...provenanceGapSlugs])];
const { data, error } = await db.from('maps').select(cols).in('slug', allSlugs);
if (error) throw error;

for (const slug of allSlugs) {
  const m = data.find((r) => r.slug === slug);
  console.log('----', slug, m ? '' : '(NOT FOUND — slug may be truncated in audit output)');
  if (m) console.log(JSON.stringify(m, null, 2));
}

// Hue sheet-6541 duplicate + L7014 iiif cluster sample
const { data: hue } = await db.from('maps').select(cols).ilike('slug', '%6541%');
console.log('---- hue 6541 family ----');
console.log(JSON.stringify(hue, null, 2));

const { data: l7014sample } = await db
  .from('maps')
  .select('slug,source_type,iiif_image')
  .eq('slug', 'phat-diem-w')
  .single();
console.log('---- phat-diem-w (sample iiif-warning row) ----');
console.log(JSON.stringify(l7014sample, null, 2));
const { data: srcs } = await db
  .from('map_iiif_sources')
  .select('*')
  .eq('map_id', (await db.from('maps').select('id').eq('slug', 'phat-diem-w').single()).data.id);
console.log('---- its map_iiif_sources rows ----');
console.log(JSON.stringify(srcs, null, 2));
