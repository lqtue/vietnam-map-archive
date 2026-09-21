import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, { auth: { persistSession: false } });

const { data: indo } = await db.from('maps')
  .select('slug,source_url,holding_institution,year,original_title')
  .eq('collection', 'Indochine 1:25,000 — Tonkin & Thanh Hóa')
  .eq('holding_institution', 'IGN (Institut national de l\'information géographique et forestière)')
  .order('slug');
console.log(JSON.stringify(indo, null, 2));
