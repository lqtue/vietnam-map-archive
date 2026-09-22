import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data } = await db
  .from('maps')
  .select('slug,source_type,holding_institution,source_url')
  .eq('source_type', 'ia');
console.log(JSON.stringify(data, null, 2));
