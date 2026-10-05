// One-off, 2026-10-05: the fourteen findings of the hand audit of the public list that
// scripts/catalog_audit.mjs now reports (checks `title`, `sheet`, map_type).
//
//   node --env-file=.env scripts/oneoff/fix_catalog_names_2026_10.mjs          # dry run
//   node --env-file=.env scripts/oneoff/fix_catalog_names_2026_10.mjs --apply
//
// Each fix names the value it expects to replace. A row that has changed since the audit
// is skipped, not overwritten, so a re-run is safe. Slugs do not move on a rename (mig 088).
//
// Not here, on purpose: Ha Chau / Nha Nam sheet numbers (0, 0 bis) need the scans; the AMS L909
// city maps use the city name as `sheet_number` because it is that series' cell key.
import { createClient } from '@supabase/supabase-js';

const COFFYN = 'batiments-civils-le-plan-du-colonel-du-genie-paul-coffyn-pour-une-ville-de-500-0';

/** @type {{slug: string, col: string, from: string | null, to: string | null}[]} */
const FIXES = [
  // original_title that is a path, or only a year
  {
    slug: 'plan-de-la-riviere-de-hue',
    col: 'original_title',
    from: '/Users/airm1/Downloads/default (2).jpgPlan de la rivière de Huê ou de Kigne levé en 1819',
    to: 'Plan de la rivière de Huê ou de Kigne levé en 1819',
  },
  { slug: 'plan-du-port-de-saigon', col: 'original_title', from: '1863', to: null },
  {
    slug: 'plan-de-gia-dinh-et-des-environs-dresse-par-tran-van-hoc',
    col: 'original_title',
    from: '1815',
    to: null,
  },
  { slug: 'environs-de-saigon', col: 'original_title', from: '1900', to: null },
  // Virtual Saigon's record ID 1267 (the source fix_coffyn_provenance.mjs cites) gives the
  // printed title; the row's name stays the longer descriptive one.
  {
    slug: COFFYN,
    col: 'original_title',
    from: '03. 1862',
    to: 'Bâtiments civils. Projet de ville de 500 000 âmes à Saigon.',
  },
  // the half is already in the brackets
  { slug: 'cam-pha-est-e', col: 'name', from: 'Cam Pha est (E)', to: 'Cam Pha (E)' },
  { slug: 'cam-pha-ouest-w', col: 'name', from: 'Cam Pha ouest (W)', to: 'Cam Pha (W)' },
  {
    slug: 'xieng-khouang-est-e',
    col: 'name',
    from: 'Xieng Khouang est (E)',
    to: 'Xieng Khouang (E)',
  },
  { slug: 'plan-de-cholon', col: 'map_type', from: null, to: 'plan' },
  { slug: 'plan-de-saigon', col: 'map_type', from: null, to: 'plan' },
];

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

let changed = 0;
for (const { slug, col, from, to } of FIXES) {
  const { data, error } = await db.from('maps').select(col).eq('slug', slug).maybeSingle();
  if (error) throw new Error(`${slug}: ${error.message}`);
  if (!data) {
    console.log(`MISSING  ${slug}`);
    continue;
  }
  if (data[col] !== from) {
    console.log(
      `SKIP     ${slug}.${col} is now ${JSON.stringify(data[col])}, expected ${JSON.stringify(from)}`
    );
    continue;
  }
  console.log(
    `${apply ? 'UPDATE  ' : 'WOULD   '} ${slug}.${col}: ${JSON.stringify(from)} -> ${JSON.stringify(to)}`
  );
  if (!apply) continue;
  let q = db
    .from('maps')
    .update({ [col]: to })
    .eq('slug', slug);
  q = from === null ? q.is(col, null) : q.eq(col, from);
  const { data: rows, error: e2 } = await q.select('slug');
  if (e2) throw new Error(`${slug}: ${e2.message}`);
  if (!rows.length) throw new Error(`${slug}.${col}: changed under us, nothing written`);
  changed++;
}
console.log(apply ? `\n${changed} rows updated.` : '\nDry run. Re-run with --apply.');
