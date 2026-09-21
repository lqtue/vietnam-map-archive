import { createClient } from '@supabase/supabase-js';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false }
});

const ids = [
  '830551ec-0eed-439d-8206-1a64c8b10d4f',
  '0a8b92dc-4ad9-47b2-8072-ad570b73e327',
  '1979d85d-cb9a-4a25-932f-9fefd22a1663'
];
const canonical = 'Perry-Castañeda Library Map Collection, University of Texas at Austin';

const { data, error } = await db
  .from('maps')
  .update({ holding_institution: canonical })
  .in('id', ids)
  .select('slug,holding_institution');

if (error) throw error;
console.log(JSON.stringify(data, null, 2));
