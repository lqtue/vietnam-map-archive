// For each sheet in a map-id list, inverse-transform a curated landmark list
// (lon, lat) through that sheet's OWN current annotation to get an
// approximate pixel location — so entering the SAME landmark as a GCP on
// every sheet that shows it is "zoom to this pixel, confirm the feature by
// eye, paste" instead of hunting a 14,000 px scan from scratch on each sheet
// independently. Once every sheet carries the same agreed lon/lat for a
// landmark, cross-sheet disagreement is attributable to the maps rather than
// to each sheet picking its own arbitrary points.
//
// Landmarks live in work/analysis/district4/landmarks.json (or --landmarks).
// Most start as `status: "candidate"` — GCP-convergence guesses, still
// circular — until a human confirms the same physical feature across sheets
// and records a `source` for the lon/lat. Only then do they carry any
// accuracy signal. `held_out: true` landmarks are for scoring a sheet's fit
// after editing, not for use in the fit itself.
//
// Usage:
//   node --env-file=.env scripts/oneoff/gcp_inverse_lookup.mjs
//   node --env-file=.env scripts/oneoff/gcp_inverse_lookup.mjs --maps <id1,id2,...>
//   node --env-file=.env scripts/oneoff/gcp_inverse_lookup.mjs --landmarks <path>
//
// Output per sheet: `pixelX pixelY lon lat` lines, ready to paste into the
// Allmaps Editor's GCP box, plus a flag if the guess falls outside the scan.

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';
import { readFileSync } from 'node:fs';
import { editorUrlFallback, editorUrlFromAnnotation } from '../lib/allmaps_editor_link.mjs';

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

// Landmarks: one agreed lon/lat per real-world feature, entered as a GCP on
// every sheet that shows it. `status: "candidate"` means it's still just a
// GCP-convergence guess — unverified until a human confirms it's the same
// physical feature in the editor and names a source for the lon/lat.
// `held_out: true` marks a landmark to exclude from a sheet's own fit so it
// can be used to score that sheet's accuracy without the circularity of
// scoring against points the fit already passes through.
const LANDMARKS = JSON.parse(
  readFileSync(
    arg('--landmarks', new URL('../../work/analysis/district4/landmarks.json', import.meta.url)),
    'utf8'
  )
);

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Live Allmaps first: maps.annotation_url is a one-time snapshot mirror that
// nothing re-syncs on edit (4 of 6 District 4 sheets were stale as of
// 2026-09-22, one by 13 months) — reading it here would silently hide GCP
// edits made in the Editor. Only fall back to it when there's no allmaps_id.
function annotationUrlFor(row) {
  return (
    (row.allmaps_id ? `https://annotations.allmaps.org/images/${row.allmaps_id}` : null) ||
    row.annotation_url
  );
}

const asJson = process.argv.includes('--json');
const report = [];

for (const id of mapIds) {
  const { data: rows, error } = await db
    .from('maps')
    .select(
      'id,year,name,slug,allmaps_id,annotation_url,iiif_manifest,map_iiif_sources(iiif_image,source_type)'
    )
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
    points: [],
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
      console.log(
        `  editor link corrected — annotation is fit to a different source than the heuristic picked (target: ${source.id})`
      );
    }
    sheet.editorUrl = verified;
    sheet.editorUrlVerified = true;
  } else if (source?.id) {
    console.log(
      `  WARNING: annotation targets ${source.id}, which is not in map_iiif_sources — editor link may open the wrong scan`
    );
  }

  const maps = parseAnnotation(annotation);
  if (!maps.length) {
    console.log('  annotation had no georeferenced map');
    continue;
  }
  const transformer = GcpTransformer.fromGeoreferencedMap(maps[0]);

  for (const lm of LANDMARKS) {
    const label = `${lm.id} [${lm.status}]${lm.held_out ? ' held-out' : ''}: ${lm.feature ?? lm.note}`;
    let px;
    try {
      px = transformer.transformToResource([lm.lon, lm.lat]);
    } catch {
      console.log(`  ${label}: transform refused this point`);
      continue;
    }
    const [x, y] = px;
    const outOfBounds = width && height && (x < 0 || y < 0 || x > width || y > height);
    console.log(
      `  ${Math.round(x)} ${Math.round(y)} ${lm.lon} ${lm.lat}` +
        `${outOfBounds ? '   OFF SCAN — not on this sheet' : ''}   # ${label}`
    );
    if (!outOfBounds) {
      sheet.points.push({
        x: Math.round(x),
        y: Math.round(y),
        lon: lm.lon,
        lat: lm.lat,
        id: lm.id,
        status: lm.status,
        heldOut: !!lm.held_out,
        label,
      });
    }
  }
}

if (asJson) {
  console.log('\n---JSON---');
  console.log(JSON.stringify(report, null, 2));
}
