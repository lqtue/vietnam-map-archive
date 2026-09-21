import { createClient } from '@supabase/supabase-js';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false }
});

const BNF = 'Bibliothèque nationale de France';
const CARTOMUNDI_243 = 'https://www.cartomundi.fr/searchMap?type=serie&id=243';

const holdingInstitutionFixes = [
  { slug: 'hanoi-economique', holding_institution: BNF },
  { slug: 'hue-et-ses-environs', holding_institution: BNF },
  { slug: 'plan-de-la-ville-de-saigon-1878', holding_institution: BNF },
  { slug: 'plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise', holding_institution: BNF },
  { slug: 'saigon-plan', holding_institution: BNF },
  { slug: 'hanoi-plan-dessine-par-pham-dinh-bach', holding_institution: BNF },
  { slug: 'saigon-port-plan', holding_institution: BNF },
  { slug: 'saigon-cholon', holding_institution: BNF },
  { slug: 'plan-de-la-ville-de-hanoi-1942', holding_institution: BNF },
  { slug: 'carte-du-sud-vietnam', holding_institution: 'Michigan State University, Vietnam Group Archive' }
];

const sourceUrlFixes = [
  { slug: 'nha-nam', source_url: CARTOMUNDI_243 },
  { slug: 'an-thi', source_url: CARTOMUNDI_243 }
];

for (const { slug, ...patch } of [...holdingInstitutionFixes, ...sourceUrlFixes]) {
  const { data, error } = await db.from('maps').update(patch).eq('slug', slug).select('slug,holding_institution,source_url');
  if (error) throw new Error(`${slug}: ${error.message}`);
  if (!data.length) throw new Error(`${slug}: no row matched`);
  console.log(JSON.stringify(data[0]));
}
