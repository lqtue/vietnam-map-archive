#!/usr/bin/env node
// Fill dominant provinces (mig 109) and province lists (mig 111) from each map's bbox.
//
//   node --env-file=.env scripts/oneoff/backfill_map_region.mjs            # dry run: report only
//   node --env-file=.env scripts/oneoff/backfill_map_region.mjs --apply    # write (after mig 111)
//   ... --apply --force                                                    # also overwrite filled rows
//
// Dry by default. A dry run reads only `id,name,bbox,status`, so it works before the migration.
// `bbox` is [minLng, minLat, maxLng, maxLat] (checked 2026-10-05: all 1,036 fall inside Vietnam).
// The rules, and the 63 → 34 table, are in scripts/lib/regionOf.mjs.

import { createClient } from '@supabase/supabase-js';
import { BOUNDARY_URL, NEIGHBOUR_URLS, makeLocator, regionOf } from '../lib/regionOf.mjs';

const args = process.argv.slice(2);
const apply = args.includes('--apply');
const force = args.includes('--force');

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const res = await fetch(BOUNDARY_URL);
if (!res.ok) throw new Error(`boundary file: ${res.status}`);
const locate = makeLocator(await res.json());
const abroad = await Promise.all(
  NEIGHBOUR_URLS.map(async (u) => {
    const r = await fetch(u);
    if (!r.ok) throw new Error(`boundary file ${u}: ${r.status}`);
    return makeLocator(await r.json());
  })
);
const locateAbroad = (x, y) => abroad.some((f) => f(x, y));

const rows = [];
for (let from = 0; ; from += 1000) {
  const { data, error } = await db
    .from('maps')
    .select(apply ? 'id,name,bbox,status,region' : 'id,name,bbox,status')
    .order('id')
    .range(from, from + 999);
  if (error) throw error;
  rows.push(...data);
  if (data.length < 1000) break;
}

const out = { none: [], set: [] };
const byRegion = {};
for (const r of rows) {
  const hit = regionOf(r.bbox, locate, locateAbroad);
  if (!hit) out.none.push(r);
  else {
    out.set.push({ ...r, ...hit });
    byRegion[hit.region] = (byRegion[hit.region] ?? 0) + 1;
  }
}

console.log(`${rows.length} maps · ${out.set.length} get a region · ${out.none.length} left null`);
for (const [k, n] of Object.entries(byRegion).sort((a, b) => b[1] - a[1]))
  console.log(String(n).padStart(5), k);
const pub = (a) => a.filter((r) => r.status === 'public' || r.status === 'featured').length;
console.log(`public/featured: ${pub(out.set)} labelled, ${pub(out.none)} null`);
const nullBbox = out.none.filter((r) => !r.bbox);
console.log(
  `\nleft null: ${nullBbox.length} with no bbox, ${out.none.length - nullBbox.length} off Vietnamese land or mostly across a border:`
);
for (const r of out.none
  .filter((r) => r.bbox && r.status !== 'draft')
  .slice(0, Number(process.env.SHOW ?? 15)))
  console.log(' ', r.status, r.name, JSON.stringify(r.bbox.map((n) => +n.toFixed(2))));
const multi = out.set.filter((r) => r.regions.length > 1);
console.log(`\n${multi.length} maps span 2+ provinces (63-set); widest:`);
for (const r of [...multi].sort((a, b) => b.regions.length - a.regions.length).slice(0, 10))
  console.log(' ', r.regions.length, r.name.slice(0, 50), '→', r.regions.join(', '));
console.log('\nthinnest land share (check by eye):');
for (const r of [...out.set].sort((a, b) => a.land - b.land).slice(0, 12))
  console.log(' ', r.land.toFixed(2), r.name, '→', r.region);

if (!apply) {
  console.log('\ndry run — nothing written. Re-run with --apply once migration 111 is pushed.');
  process.exit(0);
}
let written = 0;
for (const r of out.set) {
  if (rows.find((x) => x.id === r.id)?.region && !force) continue;
  const { error } = await db
    .from('maps')
    .update({
      region: r.region,
      region_2025: r.region_2025,
      regions: r.regions,
      regions_2025: r.regions_2025,
    })
    .eq('id', r.id);
  if (error) throw error;
  written++;
}
console.log(`\nwrote ${written} rows`);
