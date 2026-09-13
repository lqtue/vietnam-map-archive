#!/usr/bin/env node
// Publish the eight verified L7014 city sheets.
//
//   node --env-file=.env scripts/oneoff/publish_l7014_city_sheets.mjs [--dry]
//
// `Series L7014 (Vietnam 1:50,000)` is the hand-georeferenced half of the AMS
// 1:50,000 series — the 24 sheets PCL publishes as plain JPGs with no embedded
// georeference, which is why they are `maps` rows warped live by Allmaps
// instead of cells in the pre-tiled mosaic. They are also the sheets over
// Saigon, so they are exactly the hole in `overlay/l7014-*.pmtiles`.
//
// Ten of the sixteen rows are georeferenced but only one was published, and
// `map_series` (mig 082) counts sheets *this reader can see* — so with one
// published sheet the `having count(*) > 1` gate dropped the series entirely
// and no reader was offered it at all. This publishes the eight that are ready.
//
// Two rows are deliberately left out:
//   - 830551ec — Hue 6541 IV. Same PCL scan as cdef2d04, georeferenced from a
//     1660x2147 copy with THREE control points (an affine has six parameters,
//     so three points fit it exactly and its zero residual measures nothing)
//     and a mask covering the whole image, collar and title block included.
//     It lands ~7 km north of the cell at 48% of its size. cdef2d04 is the
//     same sheet done properly and is already public.
//   - the six TTU rows that are not georeferenced yet.
//
// Each of the eight was checked before this script was written: all five
// Allmaps tile scale factors served from R2 (`cache-control: immutable`), and
// annotation and thumbnail both 200. That check is the point — the previous
// publish in this series verified the database gate, not the pixels, and 56
// sheets went live drawing nothing.

import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
const COLLECTION = 'Series L7014 (Vietnam 1:50,000)';
const BAD_HUE = '830551ec-0eed-439d-8206-1a64c8b10d4f';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data, error } = await db
  .from('maps')
  .select('id,name,status,georef_done,iiif_image,annotation_url,thumbnail,extra_metadata')
  .eq('collection', COLLECTION);
if (error) throw error;

const todo = data.filter((m) => m.georef_done && m.status !== 'public' && m.id !== BAD_HUE);
if (!todo.length) {
  console.log('nothing to publish — every georeferenced sheet is already public');
  process.exit(0);
}

// Re-verify rather than trust the note above: a sheet whose tiles do not serve
// must not be published, whatever the database says about it.
let blocked = 0;
for (const m of todo) {
  const info = await fetch(`${m.iiif_image}/info.json`);
  const j = await info.json();
  const t = j.tiles?.[0];
  let hits = 0;
  for (const sf of t.scaleFactors) {
    const w = t.width * sf;
    const r = await fetch(`${m.iiif_image}/0,0,${w},${w}/${t.width},/0/default.jpg`);
    if (r.ok && (r.headers.get('cache-control') || '').includes('immutable')) hits++;
  }
  const ann = await fetch(m.annotation_url);
  const ok = hits === t.scaleFactors.length && ann.ok;
  if (!ok) blocked++;
  console.log(
    `  ${(m.extra_metadata?.sheet_number || '?').padEnd(8)} tiles ${hits}/${t.scaleFactors.length}` +
      ` ann ${ann.status}  ${ok ? 'OK' : 'BLOCKED'}  ${m.name}`
  );
  m._ok = ok;
}

const ready = todo.filter((m) => m._ok);
if (blocked) console.log(`\n${blocked} sheet(s) will not be published — their tiles do not serve.`);
if (!ready.length) process.exit(1);

if (dry) {
  console.log(`\n--dry: would publish ${ready.length}`);
  process.exit(0);
}

const { error: upErr } = await db
  .from('maps')
  .update({ status: 'public' })
  .in(
    'id',
    ready.map((m) => m.id)
  );
if (upErr) throw upErr;
console.log(`\npublished ${ready.length}`);

const { data: series } = await db.from('map_series').select('*');
console.log('\nmap_series as an anonymous reader sees it:');
for (const r of series)
  console.log(`   ${r.key} | ${r.sheets} sheets | ${r.first_year}-${r.last_year}`);
