import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, { auth: { persistSession: false } });

const DRAFT = '830551ec-0eed-439d-8206-1a64c8b10d4f';
const PUBLIC = 'cdef2d04-4749-48a8-99f9-1a8b8f1c14ad';

for (const [label, id] of [['DRAFT', DRAFT], ['PUBLIC', PUBLIC]]) {
  const { data, error } = await db.from('maps').select('*').eq('id', id).single();
  if (error) throw error;
  console.log(`\n=== ${label} maps row ===`);
  console.log(JSON.stringify(data, null, 2));
}

for (const table of ['pipeline_jobs', 'map_iiif_sources', 'map_slug_aliases']) {
  const { data, error } = await db.from(table).select('*').in('map_id', [DRAFT, PUBLIC]);
  if (error) { console.log(`\n=== ${table}: ERROR ${error.message} ===`); continue; }
  console.log(`\n=== ${table} rows referencing either id (${data.length}) ===`);
  console.log(JSON.stringify(data, null, 2));
}

// series_sheets may reference by a different column name; probe schema safely
const { data: ss, error: ssErr } = await db.from('series_sheets').select('*').limit(1);
if (ssErr) {
  console.log(`\n=== series_sheets: ERROR ${ssErr.message} ===`);
} else {
  console.log('\n=== series_sheets sample row (to find the right column) ===');
  console.log(JSON.stringify(ss, null, 2));
}
