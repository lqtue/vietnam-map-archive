#!/usr/bin/env node
// Re-sync the District 4 series' annotation mirror from live Allmaps state.
//
//   node --env-file=.env scripts/oneoff/sync_district4_annotations.mjs [--dry] [--map <id>]
//
// `maps.annotation_url` is a one-time snapshot in Supabase Storage
// (src/lib/server/annotationMirror.ts). Nothing re-pulls it when a person edits
// the georeference directly in the Allmaps Editor, and a same-day audit
// (2026-09-22) found four of the six District 4 sheets had drifted — 1923 worst,
// 13 months stale at 3 GCPs against a live 10. This is the same fix
// `POST /api/admin/maps/[id]/sync-allmaps` performs, run here directly with the
// service key because that route requires an authenticated admin session.
//
// Same guard as the production path: refuses to write, per sheet, if the live
// annotation's declared source size disagrees with what the target IIIF base
// actually serves (a rescan under a different id) — that would silently move
// every control point. Default is --dry; --apply is required to write.

import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const dry = !args.includes('--apply');
const mapIdx = args.indexOf('--map');
const onlyMap = mapIdx > -1 ? args[mapIdx + 1] : null;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const R2_BASE = 'https://iiif.maparchive.vn/iiif';
const ANNOTATIONS_BUCKET = 'annotations';
const ALLMAPS_ANNOTATIONS = 'https://annotations.allmaps.org/images';

const DISTRICT4 = [
  '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b', // 1882 Plan Cadastral
  '1bce28f0-aa82-48eb-8e33-8f0b07182c2f', // 1923 Saigon - Cholon
  'f08aa539-e46e-48f4-8689-dee80bd66ec9', // 1895 Plan des environs
  'eca788e5-6780-4dca-bf23-7651a1c48aba', // 1942 Plan de Saigon - Cho Lon
];

function extractSourceUrl(annotation) {
  const items = annotation.type === 'Annotation' ? [annotation] : (annotation.items ?? annotation.maps ?? []);
  for (const item of items) {
    const target = item.target;
    if (!target) continue;
    const source = typeof target === 'string' ? target : (target.source ?? target);
    const id = typeof source === 'string' ? source : source?.id;
    if (id && typeof id === 'string' && id.startsWith('http')) return id;
  }
  return null;
}

function rewriteSourceUrl(annotation, oldUrl, newUrl) {
  const raw = JSON.stringify(annotation);
  const oldBase = oldUrl.replace(/\/+$/, '');
  const newBase = newUrl.replace(/\/+$/, '');
  const updated = raw.replaceAll(oldBase + '/', newBase + '/').replaceAll(oldBase, newBase);
  return JSON.parse(updated);
}

function declaredSourceSize(annotation) {
  const items = annotation?.type === 'Annotation' ? [annotation] : (annotation?.items ?? annotation?.maps ?? []);
  for (const item of items) {
    const source = item?.target?.source;
    if (typeof source?.width === 'number' && typeof source?.height === 'number') {
      return { width: source.width, height: source.height };
    }
  }
  return null;
}

async function sourceSizeMismatch(annotation, iiifBase) {
  const declared = declaredSourceSize(annotation);
  if (!declared) return null;
  let served;
  try {
    const res = await fetch(`${iiifBase}/info.json`, { headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    served = await res.json();
  } catch {
    return null;
  }
  if (typeof served?.width !== 'number' || typeof served?.height !== 'number') return null;
  if (served.width === declared.width && served.height === declared.height) return null;
  return (
    `Annotation is georeferenced against a ${declared.width}x${declared.height} image, ` +
    `but ${iiifBase} serves ${served.width}x${served.height}. Writing it would move every ` +
    `control point and the mask. Re-georeference this sheet against the scan R2 holds.`
  );
}

function r2MirrorBase(currentIiifImage, fallback) {
  return currentIiifImage?.includes('maparchive.vn') ? currentIiifImage : fallback;
}

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
  if (!res.ok) {
    const errText = await res.text().catch(() => String(res.status));
    throw new Error(`Storage upload failed (${res.status}): ${errText}`);
  }
  return `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/public/${bucket}/${path}`;
}

async function upsertR2Source(mapId, newIiifBase) {
  const { data: existingSources } = await db
    .from('map_iiif_sources')
    .select('id, iiif_image, sort_order')
    .eq('map_id', mapId);

  const r2Source = (existingSources ?? []).find((s) => s.iiif_image?.includes('maparchive.vn'));

  await db.from('map_iiif_sources').update({ is_primary: false }).eq('map_id', mapId).eq('is_primary', true);

  if (r2Source) {
    const { error } = await db
      .from('map_iiif_sources')
      .update({ iiif_image: newIiifBase, is_primary: true })
      .eq('id', r2Source.id);
    if (error) throw error;
    return;
  }

  const maxOrder = (existingSources ?? []).reduce((max, s) => Math.max(max, s.sort_order ?? 0), 0);
  const { error } = await db.from('map_iiif_sources').insert({
    map_id: mapId,
    label: 'Cloudflare R2',
    source_type: 'r2',
    iiif_image: newIiifBase,
    is_primary: true,
    sort_order: maxOrder + 1,
  });
  if (error) throw error;
}

async function syncOne(mapId) {
  const { data: map, error: mErr } = await db
    .from('maps')
    .select('id, name, allmaps_id, annotation_url, iiif_image')
    .eq('id', mapId)
    .single();
  if (mErr) throw mErr;
  if (!map.allmaps_id) {
    console.log(`  ${map.name}: no allmaps_id — nothing upstream to re-fetch. SKIP`);
    return;
  }

  const sourceUrl = `${ALLMAPS_ANNOTATIONS}/${map.allmaps_id}`;
  const annotationRes = await fetch(sourceUrl + '?_t=' + Date.now(), { headers: { Accept: 'application/json' } });
  if (!annotationRes.ok) {
    console.log(`  ${map.name}: failed to fetch live annotation (${annotationRes.status}). SKIP`);
    return;
  }
  const annotation = await annotationRes.json();

  const oldSourceUrl = extractSourceUrl(annotation);
  const newIiifBase = r2MirrorBase(map.iiif_image, `${R2_BASE}/${mapId}`);
  const updated = oldSourceUrl ? rewriteSourceUrl(annotation, oldSourceUrl, newIiifBase) : annotation;

  console.log(`  ${map.name}`);
  console.log(`    live source:  ${oldSourceUrl}`);
  console.log(`    rewrite to:   ${newIiifBase}`);

  const mismatch = await sourceSizeMismatch(updated, newIiifBase);
  if (mismatch) {
    console.log(`    ⚠ REFUSED: ${mismatch}`);
    return;
  }

  if (dry) {
    console.log('    would write annotation mirror + map_iiif_sources (dry run)');
    return;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  await uploadJson(ANNOTATIONS_BUCKET, `${mapId}/${stamp}.json`, updated);
  const publicAnnotationUrl = await uploadJson(ANNOTATIONS_BUCKET, `${mapId}.json`, updated);

  const { error: upErr } = await db
    .from('maps')
    .update({
      iiif_image: newIiifBase,
      annotation_url: publicAnnotationUrl,
      thumbnail: `${newIiifBase}/full/800,/0/default.jpg`,
    })
    .eq('id', mapId);
  if (upErr) throw upErr;

  await upsertR2Source(mapId, newIiifBase);
  console.log('    ✓ synced');
}

const targets = onlyMap ? [onlyMap] : DISTRICT4;
console.log(`${targets.length} sheet(s) to sync${dry ? ' (dry run — pass --apply to write)' : ''}\n`);
for (const id of targets) {
  await syncOne(id);
  console.log();
}
