import { createClient } from '@supabase/supabase-js';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const ids = ['830551ec-0eed-439d-8206-1a64c8b10d4f', 'cdef2d04-4749-48a8-99f9-1a8b8f1c14ad'];
const { data: ss } = await db.from('series_sheets').select('*').in('map_id', ids);
console.log('series_sheets rows:', JSON.stringify(ss, null, 2));
const { data: aliases } = await db.from('map_slug_aliases').select('*').in('map_id', ids);
console.log('map_slug_aliases rows:', JSON.stringify(aliases, null, 2));
const { data: sources } = await db.from('map_iiif_sources').select('*').in('map_id', ids);
console.log('map_iiif_sources rows:', JSON.stringify(sources, null, 2));
