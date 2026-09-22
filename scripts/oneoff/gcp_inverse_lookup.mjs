// For each sheet in a map-id list, inverse-transform a set of known-good
// ground points (lon, lat) through that sheet's OWN current annotation to get
// an approximate pixel location — so fixing georeference in Allmaps Editor is
// "zoom to this pixel and nudge to the real feature" instead of hunting a
// 14,000 px scan by eye from scratch.
//
// Ground points are the cross-sheet convergence points found by comparing
// every District 4 sheet's existing GCPs pairwise (see chat / ROADMAP §E6):
// coordinates where two or more independently-georeferenced sheets already
// agree to within ~25 m. Not fabricated — read off the live annotations.
//
// Usage:
//   node --env-file=.env scripts/oneoff/gcp_inverse_lookup.mjs
//   node --env-file=.env scripts/oneoff/gcp_inverse_lookup.mjs --maps <id1,id2,...>
//
// Output per sheet: `pixelX pixelY lon lat` lines, ready to paste into the
// Allmaps Editor's GCP box, plus a flag if the guess falls outside the scan.

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';
import { readFileSync } from 'node:fs';

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
};

const mapIds = (
  arg('--maps') ??
  readFileSync(new URL('../../work/analysis/district4/maps.txt', import.meta.url), 'utf8')
)
  .trim()
  .split(',')
  .filter(Boolean);

// [lon, lat, label] — the 10 cross-sheet convergence points.
const CANDIDATES = [
  [106.7064, 10.7753, 'seed: 1882+1923+1942 (3-sheet, 3.2-15.9 m spread)'],
  [106.7021, 10.7755, '1882+1942 (1.1 m)'],
  [106.6894, 10.7736, '1882+1895 (2.2 m)'],
  [106.7084, 10.7626, '1882+1895 (2.3 m)'],
  [106.6592, 10.7508, '1959+1968 (2.6 m)'],
  [106.6974, 10.7791, '1882+1895 (2.8 m)'],
  [106.7064, 10.7917, '1882+1942 (3.4 m)'],
  [106.6367, 10.8018, '1895+1968 (4.4 m)'],
  [106.6959, 10.7826, '1882+1959 (6.7 m)'],
  [106.71, 10.7955, '1895+1968 (23.5 m, weak)']
];

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false }
});

function annotationUrlFor(row) {
  return row.annotation_url || (row.allmaps_id ? `https://annotations.allmaps.org/images/${row.allmaps_id}` : null);
}

const asJson = process.argv.includes('--json');
const report = [];

const EDITOR_BASE = 'https://editor.allmaps.org/#/collection?url=';
const withInfoJson = (u) => (/\.json($|\?)/.test(u) ? u : `${u.replace(/\/$/, '')}/info.json`);

// Baseline mirrors $lib/core/iiif/annotationUrl.ts:allmapsEditorSourceUrl — the
// editor keys a map off its IIIF resource, not off an annotation, and refuses
// a self-hosted (R2/Supabase-mirrored) annotation outright ("Only
// Georeference Annotations loaded from Allmaps are supported"). That helper
// also skips R2 sources on the assumption R2 is always a redundant mirror of
// the original — true in general, but 1942 broke it: its GCPs were re-fit to
// a higher-res R2 rescan after the original scan turned out too coarse, so R2
// there is the ONLY correct source and the archive.org original is stale.
// Fixed properly below by matching the annotation's own target.source.id
// against map_iiif_sources instead of guessing by source_type.
function editorUrlFallback(row) {
  if (row.iiif_manifest) return EDITOR_BASE + encodeURIComponent(withInfoJson(row.iiif_manifest));
  const original = row.map_iiif_sources?.find((s) => s.source_type !== 'r2' && s.iiif_image)?.iiif_image;
  if (original) return EDITOR_BASE + encodeURIComponent(withInfoJson(original));
  if (!row.annotation_url && row.allmaps_id)
    return EDITOR_BASE + encodeURIComponent(`https://annotations.allmaps.org/images/${row.allmaps_id}`);
  return null;
}

/** Whichever source's iiif_image the annotation is ACTUALLY fit to, verified by URL match. */
function editorUrlFromAnnotation(row, sourceId) {
  if (!sourceId) return null;
  const stripInfoJson = (u) => u.replace(/\/info\.json$/, '');
  const match = row.map_iiif_sources?.find(
    (s) => s.iiif_image && stripInfoJson(sourceId) === stripInfoJson(s.iiif_image)
  );
  return match ? EDITOR_BASE + encodeURIComponent(withInfoJson(match.iiif_image)) : null;
}

for (const id of mapIds) {
  const { data: rows, error } = await db
    .from('maps')
    .select('id,year,name,slug,allmaps_id,annotation_url,iiif_manifest,map_iiif_sources(iiif_image,source_type)')
    .eq('id', id);
  if (error || !rows?.length) {
    console.log(`\n## ${id} — could not read maps row (${error?.message ?? 'no row'})`);
    continue;
  }
  const row = rows[0];
  const url = annotationUrlFor(row);
  const sheet = {
    id,
    year: row.year,
    name: row.name ?? row.slug ?? id,
    editorUrl: editorUrlFallback(row),
    editorUrlVerified: false,
    points: []
  };
  report.push(sheet);
  console.log(`\n## ${row.year ?? '?'} ${row.name ?? row.slug ?? id} (${id.slice(0, 8)})`);
  if (!url) {
    console.log('  no allmaps_id/annotation_url — skipped');
    continue;
  }

  let annotation;
  try {
    annotation = await (await fetch(url)).json();
  } catch (e) {
    console.log(`  could not fetch annotation: ${e.message}`);
    continue;
  }

  const source = annotation.items?.[0]?.target?.source;
  const width = source?.width ?? null;
  const height = source?.height ?? null;

  // Trust the annotation's own target over the source_type heuristic: if it
  // names a source we know about, that IS the sheet the GCPs were fit to.
  const verified = editorUrlFromAnnotation(row, source?.id);
  if (verified) {
    if (sheet.editorUrl && sheet.editorUrl !== verified) {
      console.log(`  editor link corrected — annotation is fit to a different source than the heuristic picked (target: ${source.id})`);
    }
    sheet.editorUrl = verified;
    sheet.editorUrlVerified = true;
  } else if (source?.id) {
    console.log(`  WARNING: annotation targets ${source.id}, which is not in map_iiif_sources — editor link may open the wrong scan`);
  }

  const maps = parseAnnotation(annotation);
  if (!maps.length) {
    console.log('  annotation had no georeferenced map');
    continue;
  }
  const transformer = GcpTransformer.fromGeoreferencedMap(maps[0]);

  for (const [lon, lat, label] of CANDIDATES) {
    let px;
    try {
      px = transformer.transformToResource([lon, lat]);
    } catch {
      console.log(`  ${label}: transform refused this point`);
      continue;
    }
    const [x, y] = px;
    const outOfBounds = width && height && (x < 0 || y < 0 || x > width || y > height);
    console.log(
      `  ${Math.round(x)} ${Math.round(y)} ${lon} ${lat}` +
        `${outOfBounds ? '   OFF SCAN — not on this sheet' : ''}   # ${label}`
    );
    if (!outOfBounds) {
      sheet.points.push({ x: Math.round(x), y: Math.round(y), lon, lat, label });
    }
  }
}

if (asJson) {
  console.log('\n---JSON---');
  console.log(JSON.stringify(report, null, 2));
}
