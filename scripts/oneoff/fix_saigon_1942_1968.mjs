#!/usr/bin/env node
// Repair two Saigon sheets and re-warp the maps whose labels are stale (2026-10-01).
//
//   node --env-file=.env scripts/oneoff/fix_saigon_1942_1968.mjs           # dry run
//   node --env-file=.env scripts/oneoff/fix_saigon_1942_1968.mjs --apply
//
// 1942 (eca788e5): GCP [10504, 2356] -> (106.6950, 10.7795) misses by ~300 m
//   (leave-one-out 359 m; RMSE 112 m with it, 26 m without). drop_1942_gcp1.mjs
//   removed it on 2026-09-22, but it is still on Allmaps, and the 2026-10-01 sync
//   put it back. Dropped here again, matched by coordinates rather than index,
//   with a history copy first. It will come back on the next --fromAllmaps sync
//   unless it is also deleted in the Allmaps Editor; georef_contributions.mjs
//   will report the sheet as drifted until then, which is the intended signal.
// 1968 (3a446d85): allmaps_id 02c3e822b63e16b4 is keyed to the Internet Archive
//   scan, which has no map_images row, so no editor link can be built. Add it.
// Warp: queue a `warp` job for each map whose labels/footprints carry an old
//   geom_src; run `python work/worker/vma_worker.py --kinds warp` afterwards.

import { createClient } from '@supabase/supabase-js';
import { generateId } from '@allmaps/id';

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const MAP_1942 = 'eca788e5-6780-4dca-bf23-7651a1c48aba';
const BAD_GCP = { px: [10504, 2356], ll: [106.695, 10.7795] };
const MAP_1968 = '3a446d85-25a8-4e81-9cfc-8de357c3a5df';
const IA_1968 = 'https://iiif.archive.org/image/iiif/3/1968-sg%2F1968.jpg';
const IA_1968_MANIFEST = 'https://iiif.archive.org/iiif/1968-sg/manifest.json';
// Stale geom_src as of 2026-10-01: 1882 cadastral, 1895, 1898, 1923, 1942.
const STALE = [
  '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b',
  'f08aa539-e46e-48f4-8689-dee80bd66ec9',
  '20ec4f9a-16bd-4895-a593-40c6ed9c9555',
  '1bce28f0-aa82-48eb-8e33-8f0b07182c2f',
  MAP_1942,
];

async function uploadJson(path, obj) {
  const res = await fetch(
    `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/annotations/${path}`,
    {
      method: 'POST',
      headers: {
        apikey: process.env.SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'x-upsert': 'true',
      },
      body: JSON.stringify(obj),
    }
  );
  if (!res.ok) throw new Error(`upload ${path} failed (${res.status}): ${await res.text()}`);
}

// ── 1942: drop the bad GCP ───────────────────────────────────────────────
{
  const { data: blob, error } = await db.storage.from('annotations').download(`${MAP_1942}.json`);
  if (error) throw error;
  const annotation = JSON.parse(await blob.text());
  const item = annotation.type === 'Annotation' ? annotation : annotation.items[0];
  const features = item.body.features;
  const isBad = (f) =>
    Math.abs(f.properties.resourceCoords[0] - BAD_GCP.px[0]) < 2 &&
    Math.abs(f.properties.resourceCoords[1] - BAD_GCP.px[1]) < 2 &&
    Math.abs(f.geometry.coordinates[0] - BAD_GCP.ll[0]) < 1e-3 &&
    Math.abs(f.geometry.coordinates[1] - BAD_GCP.ll[1]) < 1e-3;
  const kept = features.filter((f) => !isBad(f));
  if (kept.length === features.length) {
    console.log(`1942: bad GCP not present (${features.length} GCPs) — nothing to do`);
  } else if (kept.length !== features.length - 1 || kept.length < 3) {
    throw new Error(`1942: matched ${features.length - kept.length} GCPs, expected exactly 1`);
  } else {
    console.log(`1942: ${features.length} -> ${kept.length} GCPs`);
    if (apply) {
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      await uploadJson(`${MAP_1942}/${stamp}.json`, annotation); // the version being replaced
      item.body.features = kept;
      await uploadJson(`${MAP_1942}.json`, annotation);
      console.log(`  written; previous version kept as ?version=${stamp}`);
    }
  }
}

// ── 1968: add the Internet Archive source ────────────────────────────────
{
  const { data: m, error } = await db
    .from('maps')
    .select('allmaps_id, map_images(iiif_image, sort_order)')
    .eq('id', MAP_1968)
    .single();
  if (error) throw error;
  if (m.map_images.some((i) => i.iiif_image === IA_1968)) {
    console.log('1968: IA source already present — nothing to do');
  } else {
    const hash = await generateId(IA_1968);
    if (hash !== m.allmaps_id)
      throw new Error(`1968: ${IA_1968} hashes to ${hash}, not ${m.allmaps_id}`);
    const manifestOk = (await fetch(IA_1968_MANIFEST, { method: 'HEAD' })).ok;
    const row = {
      map_id: MAP_1968,
      label: 'Internet Archive',
      source_type: 'ia',
      iiif_image: IA_1968,
      iiif_manifest: manifestOk ? IA_1968_MANIFEST : null,
      is_primary: false,
      sort_order: Math.max(0, ...m.map_images.map((i) => i.sort_order ?? 0)) + 1,
    };
    console.log('1968: insert', row);
    if (apply) {
      const { error: insErr } = await db.from('map_images').insert(row);
      if (insErr) throw insErr;
    }
  }
}

// ── Re-warp the stale maps ───────────────────────────────────────────────
console.log(`warp: queue ${STALE.length} jobs`);
if (apply) {
  for (const map_id of STALE) {
    const { error } = await db
      .from('pipeline_jobs')
      .insert({ kind: 'warp', map_id, payload: { reason: 'rewarp-stale' } });
    // 23505 = a live warp job already exists for this map (one-live-job index).
    if (error && error.code !== '23505') throw error;
  }
  console.log(
    '  queued; now run: python work/worker/vma_worker.py --kinds warp --worker $(hostname)'
  );
}

if (!apply) console.log('\ndry run — pass --apply to write');
