import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, { auth: { persistSession: false } });
const { data } = await db.from('maps').select('slug,source_url').in('slug', ['nha-nam', 'an-thi', 'bac-ninh']);
for (const r of data) {
  console.log(r.slug, '->', JSON.stringify(r.source_url), 'raw bytes around &:', [...r.source_url].filter(c => c === '&' || c === ';').join(''));
}
