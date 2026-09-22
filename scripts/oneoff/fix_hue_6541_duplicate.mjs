import { createClient } from '@supabase/supabase-js';

// Resolves the Hue sheet-6541 duplicate from the 2026-09-21 catalog_audit.mjs
// pass — one canonical + one archived, not a delete. `830551ec` (draft) and
// `cdef2d04` (public) are the same physical sheet ingested twice.
// georef_error.py --maps <both ids> measured the fit:
//   830551ec: helmert RMSE 14.8 m, worst 18.2 m, and holds the real Internet
//             Archive IIIF source (map_iiif_sources: source_type='ia').
//   cdef2d04: helmert RMSE 63.8 m, worst 69.0 m, no non-r2 IIIF source at all.
// 830551ec becomes the canonical public sheet at the well-known slug;
// cdef2d04 is demoted to draft (hidden from /catalog, not deleted) and takes
// a `-2` slug — the archive's own tie-break convention for two sheets that
// cannot be told apart by year (mig 088's header: "A bare -2 is the last
// resort... Quang Yen 1904 · 1904, the only true tie"). This is that case.
//
// Order matters: cdef2d04 must give up the 'hue-l7014-6541-4' slug before
// 830551ec can take it (unique constraint). The maps_assign_slug trigger
// handles aliasing automatically on each UPDATE — see its comment in
// supabase/migrations/088_map_slug.sql — so no manual alias insert is needed.

const WINNER = '830551ec-0eed-439d-8206-1a64c8b10d4f';
const ARCHIVED = 'cdef2d04-4749-48a8-99f9-1a8b8f1c14ad';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

console.log('--- 1. demote the worse-georeferenced duplicate: new slug, draft status ---');
{
  const { data, error } = await db
    .from('maps')
    .update({ slug: 'hue-l7014-6541-4-2', status: 'draft' })
    .eq('id', ARCHIVED)
    .select('id,slug,status');
  if (error) throw error;
  console.log(JSON.stringify(data, null, 2));
}

console.log('\n--- 2. promote the winner: slug, collection, description, status ---');
{
  const { data, error } = await db
    .from('maps')
    .update({
      slug: 'hue-l7014-6541-4',
      collection: 'Series L7014 (Vietnam 1:50,000)',
      dc_description:
        'Series L7014, 1:50,000. Transverse Mercator on the Everest spheroid, ' +
        '1,000-metre UTM grid zone 48, horizontal datum Indian 1960, elevations ' +
        'to mean sea level at Hà Tiên. Editions in this series were produced by ' +
        'several agencies — the U.S. Army Map Service, U.S. Army engineer ' +
        'battalions with the National Geographic Service of Vietnam, and later ' +
        'the Defense Mapping Agency — so the producing body is printed on each ' +
        'sheet rather than shared across the series.',
      status: 'public',
    })
    .eq('id', WINNER)
    .select('id,slug,collection,status');
  if (error) throw error;
  console.log(JSON.stringify(data, null, 2));
}

console.log('\n--- 3. repoint series_sheets at the surviving (canonical) row ---');
{
  const { data, error } = await db
    .from('series_sheets')
    .update({ map_id: WINNER })
    .eq('series_key', 'series-l7014-vietnam-1-50-000')
    .eq('sheet_number', '6541-4')
    .select('series_key,sheet_number,map_id');
  if (error) throw error;
  console.log(JSON.stringify(data, null, 2));
}

console.log('\n--- 4. verify the alias the rename trigger should have minted ---');
{
  const { data, error } = await db
    .from('map_slug_aliases')
    .select('slug,map_id')
    .eq('slug', 'hue-viet-nam-1-50-000-sheet-6541-iv');
  if (error) throw error;
  console.log(
    data.length
      ? JSON.stringify(data, null, 2)
      : 'WARNING: no alias found — the old draft slug will 404 instead of redirecting'
  );
}

console.log('\n--- 5. sanity check: no stray alias left pointing at the archived slug ---');
{
  const { data, error } = await db
    .from('map_slug_aliases')
    .select('slug,map_id')
    .eq('slug', 'hue-l7014-6541-4');
  if (error) throw error;
  console.log(
    data.length
      ? `WARNING: unexpected alias still holds 'hue-l7014-6541-4': ${JSON.stringify(data)}`
      : 'clean — the canonical slug is owned outright by the winner, not aliased'
  );
}
