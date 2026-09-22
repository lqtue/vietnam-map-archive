import { createClient } from '@supabase/supabase-js';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Both confirmed against the source's own metadata (Gallica OAI record, Humazur item
// page) this session — year holds the survey date, year_label the later publication
// date. Documented here so catalog_audit's year/year_label WARN doesn't need
// re-investigating each time it fires.
const fixes = [
  {
    slug: 'hanoi-plan-dessine-par-pham-dinh-bach',
    dc_description:
      "Surveyed by Pham-Dinh-Bach in 1873; this edition was printed in 1937 by the Service géographique de l'Indochine. Gallica's own record splits the two: dc:subject 'Hanoï -- 1873', dc:date '1937'.",
  },
  {
    slug: 'plan-de-la-riviere-de-hue',
    dc_description:
      "Surveyed by Capitaine Louis Rey in 1819; this copy was produced for the 1931 Paris Colonial Exposition. Humazur's record lists both: couverture temporelle 1819, date (publication) 1931.",
  },
];

for (const { slug, ...patch } of fixes) {
  const { data, error } = await db
    .from('maps')
    .update(patch)
    .eq('slug', slug)
    .select('slug,dc_description');
  if (error) throw new Error(`${slug}: ${error.message}`);
  if (!data.length) throw new Error(`${slug}: no row matched`);
  console.log(JSON.stringify(data[0]));
}
