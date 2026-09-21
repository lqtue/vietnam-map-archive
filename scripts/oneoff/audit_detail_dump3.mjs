import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, { auth: { persistSession: false } });

const { data: indo } = await db.from('maps').select('slug,source_url,holding_institution').eq('collection', 'Indochine 1:25,000 — Tonkin & Thanh Hóa');
const byInst = {};
for (const r of indo) {
  const k = r.holding_institution ?? '(null)';
  byInst[k] ??= { count: 0, urlSamples: new Set() };
  byInst[k].count++;
  byInst[k].urlSamples.add(r.source_url);
}
for (const [k, v] of Object.entries(byInst)) {
  console.log(k, '—', v.count, 'rows —', v.urlSamples.size, 'distinct source_urls');
  if (v.urlSamples.size <= 3) console.log('  ', [...v.urlSamples]);
}
