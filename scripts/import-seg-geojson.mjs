#!/usr/bin/env node
// Import a pixel-space segmentation proposal into the Validate queue.
//
// The 1882 colour-20260919 run is already imported. For a new run, pass its
// raw, hole-free blocks.geojson and a fresh run id; use --dry first.
//
// The importer deliberately refuses an existing run_id. Re-importing a run
// would create duplicate candidates and erase the meaning of review counts.

import { readFile } from 'node:fs/promises';
import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);
const flag = (name) => {
  const index = args.indexOf(name);
  return index === -1 ? undefined : args[index + 1];
};

const mapId = flag('--map-id');
const runId = flag('--run-id');
const input = flag('--input');
const dry = args.includes('--dry');

if (!mapId || !runId || !input) {
  console.error(
    'usage: node --env-file=.env scripts/import-seg-geojson.mjs --map-id <uuid> --run-id <id> --input <blocks.geojson> [--dry]'
  );
  process.exit(1);
}

const document = JSON.parse(await readFile(input, 'utf8'));
if (document.type !== 'FeatureCollection' || !Array.isArray(document.features)) {
  throw new Error('--input must be a GeoJSON FeatureCollection');
}

// The colour pass names a cadastral wash, while footprints uses a
// cross-map geometry taxonomy. Keep both: `feature_type` is reviewable across
// sheets and `category` preserves the source classifier's evidence.
const COLOUR_CLASSES = {
  admin: { featureType: 'land_plot', category: 'local_svc' },
  blue: { featureType: 'land_plot', category: 'militaire' },
  cream: { featureType: 'land_plot', category: 'non_affect' },
  green: { featureType: 'land_plot', category: 'communal' },
  salmon: { featureType: 'land_plot', category: 'particulier' },
  building: { featureType: 'building', category: null },
};

// The colour pass emits one deterministic ring per polygon, so an exact repeat
// is the only duplicate it can produce. Keying on the class as well leaves a
// building inside its enclosing parcel alone — that overlap is the intended
// result, not a duplicate.
//
// ponytail: exact rings only; canonicalise rotation/winding if a producer ever
// emits the same polygon from a different start vertex.

const seen = new Set();
let duplicates = 0;
const rows = document.features.flatMap((feature, index) => {
  const ring = feature?.geometry?.type === 'Polygon' ? feature.geometry.coordinates?.[0] : null;
  if (feature?.geometry?.type === 'Polygon' && feature.geometry.coordinates?.length !== 1) {
    throw new Error(
      `feature ${index + 1} has interior rings; the Validate queue stores only an exterior ring`
    );
  }
  if (
    !Array.isArray(ring) ||
    ring.length < 3 ||
    !ring.every(
      (point) =>
        Array.isArray(point) && point.length >= 2 && point.slice(0, 2).every(Number.isFinite)
    )
  ) {
    throw new Error(`feature ${index + 1} is not a finite Polygon ring`);
  }
  const rawClass = String(feature.properties?.feature_type ?? 'other');
  const mapped = COLOUR_CLASSES[rawClass] ?? { featureType: 'other', category: rawClass };
  const key = `${rawClass}:${JSON.stringify(ring)}`;
  if (seen.has(key)) {
    duplicates += 1;
    return [];
  }
  seen.add(key);
  return [
    {
      map_id: mapId,
      pixel_polygon: ring.map(([x, y]) => [x, y]),
      feature_type: mapped.featureType,
      category: mapped.category,
      source: 'import',
      review_status: 'needs_review',
      run_id: runId,
    },
  ];
});

if (!rows.length) throw new Error('the FeatureCollection contains no polygons');

console.log(`${rows.length} proposals → Validate queue`);
if (duplicates)
  console.log(
    `  dropped ${duplicates} exact duplicate ${duplicates === 1 ? 'polygon' : 'polygons'}`
  );
console.log(`  map_id  ${mapId}`);
console.log(`  run_id  ${runId}`);
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});
const { data: map, error: mapError } = await db
  .from('maps')
  .select('id, name')
  .eq('id', mapId)
  .maybeSingle();
if (mapError) throw mapError;
if (!map) throw new Error(`map ${mapId} does not exist`);

const { count, error: existingError } = await db
  .from('footprints')
  .select('id', { count: 'exact', head: true })
  .eq('map_id', mapId)
  .eq('run_id', runId);
if (existingError) throw existingError;
if (count)
  throw new Error(
    `run ${runId} already has ${count} footprints; choose a new run id rather than duplicating it`
  );

// Below the two guards on purpose: a dry run that skipped them would report a
// file as importable that the real run then refuses.
if (dry) {
  console.log('--dry: file is valid and the run id is free; nothing imported');
  process.exit(0);
}

// PostgREST's default insert batch is generous, but chunks make this safe for
// the 1,443-polygon 1882 audit and for bigger sheets without relying on it.
for (let start = 0; start < rows.length; start += 250) {
  const { error } = await db.from('footprints').insert(rows.slice(start, start + 250));
  if (error) throw error;
}

console.log(`Imported ${rows.length} proposals for ${map.name}.`);
console.log(`Review at: /scan?mode=shapes&tab=validate&map=${mapId}`);
