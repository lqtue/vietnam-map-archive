import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// find the two truncated slugs
const { data: s1 } = await db
  .from('maps')
  .select('slug,source_url,holding_institution')
  .ilike('slug', '%plan-cadastral-de-la-ville-de-saigon%');
console.log('---- saigon cadastral candidates ----', JSON.stringify(s1, null, 2));
const { data: s2 } = await db
  .from('maps')
  .select('slug,source_url,holding_institution')
  .ilike('slug', '%batiments-civils%');
console.log('---- batiments civils candidates ----', JSON.stringify(s2, null, 2));

// canonical Gallica holding_institution string(s) already in use
const { data: gal } = await db
  .from('maps')
  .select('slug,holding_institution')
  .ilike('source_url', '%gallica%')
  .not('holding_institution', 'is', null);
const spellings = [...new Set(gal.map((r) => r.holding_institution))];
console.log(
  '---- canonical Gallica holding_institution spellings in use ----',
  JSON.stringify(spellings, null, 2)
);
console.log('count of gallica rows with holding_institution set:', gal.length);

// how many gallica-sourced rows are missing holding_institution
const { data: galMissing } = await db
  .from('maps')
  .select('slug,source_url')
  .ilike('source_url', '%gallica%')
  .is('holding_institution', null);
console.log(
  '---- gallica rows MISSING holding_institution ----',
  JSON.stringify(galMissing, null, 2)
);

// sibling Indochine 1:25,000 sheets: source_url pattern
const { data: indo } = await db
  .from('maps')
  .select('slug,source_url,holding_institution')
  .eq('collection', 'Indochine 1:25,000 — Tonkin & Thanh Hóa')
  .limit(8);
console.log('---- Indochine 1:25,000 siblings ----', JSON.stringify(indo, null, 2));
