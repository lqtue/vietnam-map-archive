#!/usr/bin/env node
/**
 * Convert staff-placed legend positions from ground (`point=lng,lat`) to image
 * pixels (`px=x,y`) in `ocr_labels.notes`, through each map's own annotation.
 *
 * Pixels are the design: a position is a fact about the sheet, and a ground
 * coordinate frozen at save time stops matching the scan the moment the map is
 * re-georeferenced. Points placed before 2026-10-05 (1959 and 1923) were saved
 * as lng/lat; this takes them back.
 *
 * Dry run by default — prints per map how far px→geo lands from the stored
 * lng/lat (the round trip through the backward fit). --apply writes.
 *
 *   node --env-file=.env scripts/oneoff/legend_points_to_pixels.mjs [--apply]
 */
import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

const { data: rows, error } = await db
  .from('ocr_labels')
  .select('id,map_id,notes')
  .eq('category', 'legend_entry')
  .like('notes', '%point=%');
if (error) throw error;

const byMap = Map.groupBy(rows, (r) => r.map_id);
for (const [mapId, list] of byMap) {
  const { data: map, error: mapError } = await db
    .from('maps')
    .select('name,year,allmaps_id,annotation_url')
    .eq('id', mapId)
    .single();
  if (mapError) throw mapError;
  const url = map.annotation_url || `https://annotations.allmaps.org/images/${map.allmaps_id}`;
  const res = await fetch(url);
  if (!res.ok) {
    console.log(`${map.year} ${map.name}: annotation ${res.status}, skipped ${list.length}`);
    continue;
  }
  const t = GcpTransformer.fromGeoreferencedMap(parseAnnotation(await res.json())[0]);

  const drift = [];
  const updates = [];
  for (const row of list) {
    const parts = row.notes.split(';').map((p) => p.trim());
    const raw = parts.find((p) => p.startsWith('point='));
    const [lng, lat] = raw.slice(6).split(',').map(Number);
    const px = t.transformToResource([lng, lat]).map(Math.round);
    const [lng2, lat2] = t.transformToGeo(px);
    drift.push(
      Math.hypot((lng2 - lng) * 111320 * Math.cos((lat * Math.PI) / 180), (lat2 - lat) * 110574)
    );
    const notes = parts
      .filter((p) => p && !/^(point|px)=/.test(p))
      .concat(`px=${px.join(',')}`)
      .join('; ');
    updates.push({ id: row.id, notes });
  }
  drift.sort((a, b) => a - b);
  const q = (f) => drift[Math.min(drift.length - 1, Math.floor(f * drift.length))].toFixed(2);
  console.log(
    `${map.year} ${map.name}: ${list.length} rows, round-trip drift m median ${q(0.5)} max ${q(1)}`
  );
  if (!apply) continue;
  for (const u of updates) {
    const { error: e } = await db.from('ocr_labels').update({ notes: u.notes }).eq('id', u.id);
    if (e) throw e;
  }
  console.log(`  wrote ${updates.length}`);
}
if (!apply) console.log('dry run — pass --apply to write');
