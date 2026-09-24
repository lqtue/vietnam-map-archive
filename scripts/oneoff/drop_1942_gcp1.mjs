#!/usr/bin/env node
// Drop the bad control point modern_prior.py --sweep flagged on the 1942 sheet
// after the 2026-09-22 re-sync: "gcp 1 misses 357 px -> drop it for 30.8 px".
//
// resourceCoords [10504, 2356] / lon 106.6950 lat 10.7795 sits ~260 m from the
// "1882+1895 (2.8 m)" cross-sheet anchor (106.6974, 10.7791) the Saigon Anchor
// Points artifact proposed for this sheet -- almost certainly that anchor,
// mis-clicked. This edits only our stored mirror
// (annotations/{mapId}.json); the live Allmaps annotation still carries the
// bad point and will reintroduce it on the next --fromAllmaps sync unless it
// is also deleted in the Editor.
//
//   node --env-file=.env scripts/oneoff/drop_1942_gcp1.mjs [--dry]

import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
const MAP_ID = 'eca788e5-6780-4dca-bf23-7651a1c48aba';
const BAD_INDEX = 1;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

async function uploadJson(bucket, path, obj) {
  const url = `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/${bucket}/${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      apikey: process.env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}`,
      'Content-Type': 'application/json',
      'x-upsert': 'true',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify(obj, null, 2),
  });
  if (!res.ok) throw new Error(`Storage upload failed (${res.status}): ${await res.text()}`);
  return `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/public/${bucket}/${path}`;
}

const { data: m, error: mErr } = await db
  .from('maps')
  .select('id, name, annotation_url')
  .eq('id', MAP_ID)
  .single();
if (mErr) throw mErr;

const res = await fetch(m.annotation_url + '?_t=' + Date.now());
if (!res.ok) throw new Error(`fetch mirror failed: ${res.status}`);
const annotation = await res.json();
const item = annotation.type === 'Annotation' ? annotation : annotation.items[0];
const features = item.body.features;

console.log(`${m.name}: ${features.length} GCPs in the stored mirror`);
const bad = features[BAD_INDEX];
console.log(
  `dropping index ${BAD_INDEX}:`,
  bad.properties?.resourceCoords,
  bad.geometry?.coordinates
);

item.body.features = features.filter((_, i) => i !== BAD_INDEX);
console.log(`${item.body.features.length} GCPs after drop`);

if (dry) {
  console.log('(dry run, nothing written)');
  process.exit(0);
}

const stamp = new Date().toISOString().replace(/[:.]/g, '-');
await uploadJson('annotations', `${MAP_ID}/${stamp}.json`, annotation);
await uploadJson('annotations', `${MAP_ID}.json`, annotation);
console.log('✓ mirror updated (history kept)');
console.log('⚠ the live Allmaps annotation still has this point — delete it in the Editor too,');
console.log('  or the next --fromAllmaps sync will bring it back.');
