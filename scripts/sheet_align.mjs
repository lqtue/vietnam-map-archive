// Sheet-to-sheet alignment check, as opposed to sheet-to-ground (georef_error.py).
//
// Each sheet already has its own georeference, fit independently to its own
// GCPs. This asks a different question: do two independently-georeferenced
// sheets AGREE with each other? Take a place name printed on both sheets,
// warp its pixel location through EACH sheet's own transform to lon/lat, and
// measure the distance between the two results. Small disagreement = the two
// sheets are consistent; large disagreement = at least one georeference is
// off, and this tool tells you where to go nudge it.
//
// Why place names and not block centroids or GCP convergence: a census
// (`sheet_to_sheet_census.mjs`) over the District 4 six + 1898 found every
// pair overlaps and every sheet has OCR, but only one sheet (1882) has any
// approved block geometry — so names are the only correspondence source that
// actually exists across this set today. Method matches
// docs/journals/260921-sheet-overlap.md's third check (names, both ends
// warped to ground: 33 of 46 shared names within 150 m, median 25 m). This
// script gets 31/46, median 20 m on the same pair by default — ballpark
// agreement with that independent measurement, NOT a byte-for-byte
// reproduction: the journal pinned 1882 to run `post0910` and 1898 to
// `2026-09-13T1036-*`; this script pools every non-rejected run per sheet
// unless told otherwise. Pin runs with --run-id <mapId>=<runId>[,...] to get
// an exact match.
//
// Usage:
//   node --env-file=.env scripts/sheet_align.mjs                       # all pairs, default 7 sheets
//   node --env-file=.env scripts/sheet_align.mjs --maps <id1,id2,...>
//   node --env-file=.env scripts/sheet_align.mjs --anchors             # ranked multi-sheet anchor points, editor-ready
//   node --env-file=.env scripts/sheet_align.mjs --run-id <id>=<run>,... # pin one run per sheet
//   node --env-file=.env scripts/sheet_align.mjs --points <file.json>  # hand-picked points instead of OCR names
//   node --env-file=.env scripts/sheet_align.mjs --self-check          # no network
//
// --points file format: { "<label>": { "<mapId-or-year>": [px, py], ... }, ... }
// One entry per real-world feature you can identify on 2+ sheets. Key each
// sheet's pixel coords by its map id (unambiguous) or year (fine as long as
// the set has one sheet per year, e.g. work/analysis/saigon6). Sheets you
// haven't picked a point on yet are just omitted from that label's object —
// the pairwise/anchor report below only compares labels two sheets share.
// This replaces the OCR-derived names entirely (no OCR fetch when set), so
// disagreement measures YOUR points: map drawing/survey error, scan/stitch
// distortion, and residual georef error, not OCR-matching noise.

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';
import { readFileSync } from 'node:fs';
import { editorLinkFor } from './lib/allmaps_editor_link.mjs';

const SKIP_CAT = new Set(['title', 'legend', 'other']);
const MIN_KEY = 5; // "OUEST" and shorter match by accident, per sheet_register.py
const THRESHOLD_M = 150; // journal's own cutoff for "the same real feature"

function nameKey(text) {
  const stripped = text
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
  return stripped;
}

// Haversine, metres. Good enough at city scale (georef_error.py's local
// tangent-plane projection is more precise but this needs no sheet-specific
// latitude and the two never disagree by more than ~0.1% over a few km).
function haversineM([lon1, lat1], [lon2, lat2]) {
  const R = 6371008.8;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function median(nums) {
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

// A manual point's per-sheet pixel is keyed by map id or by year (whichever
// the user wrote in the JSON); id wins if somehow both are present.
function resolveManualPx(bySheet, id, year) {
  return bySheet[id] ?? bySheet[String(year)] ?? null;
}

function selfCheck() {
  console.assert(nameKey('Rue de Kerlan') === nameKey('RUE DE KERLAN'), 'case/whitespace');
  console.assert(nameKey('Cầu Ông Lãnh') === 'cau ong lanh', `got ${nameKey('Cầu Ông Lãnh')}`);
  // ~111.2 km per degree of latitude at the equator, a well-known constant.
  const d = haversineM([0, 0], [0, 1]);
  console.assert(Math.abs(d - 111195) < 50, `haversine off: ${d}`);
  console.assert(median([1, 2, 3]) === 2 && median([1, 2, 3, 4]) === 2.5, 'median');
  console.assert(
    resolveManualPx({ 'map-a': [1, 2] }, 'map-a', 1900)?.join() === '1,2',
    'resolveManualPx by id'
  );
  console.assert(
    resolveManualPx({ 1900: [3, 4] }, 'map-b', 1900)?.join() === '3,4',
    'resolveManualPx by year'
  );
  console.assert(resolveManualPx({}, 'map-c', 1900) === null, 'resolveManualPx missing');
  console.log('self-check ok — name normalization, haversine, median, manual point lookup');
}

if (process.argv.includes('--self-check')) {
  selfCheck();
  process.exit(0);
}

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
};

const D4_IDS = readFileSync(new URL('../work/analysis/district4/maps.txt', import.meta.url), 'utf8')
  .trim()
  .split(',')
  .filter(Boolean);
const DEFAULT_IDS = [...D4_IDS, '20ec4f9a-16bd-4895-a593-40c6ed9c9555']; // + 1898 Saigon Plan

const mapIds = (arg('--maps') ?? DEFAULT_IDS.join(',')).split(',').filter(Boolean);
const showAnchors = process.argv.includes('--anchors');
const asJson = process.argv.includes('--json');

const pointsPath = arg('--points', null);
const manualPoints = pointsPath ? JSON.parse(readFileSync(pointsPath, 'utf8')) : null;

// --run-id 0e02b9d9...=post0910,20ec4f9a...=2026-09-13T1036-20ec4f9a
const runIdOverride = new Map(
  (arg('--run-id', '') || '')
    .split(',')
    .filter(Boolean)
    .map((pair) => pair.split('='))
);

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Live first, mirror only as fallback — the mirror is a one-time snapshot
// (`src/lib/server/annotationMirror.ts`) that goes stale the moment someone
// edits GCPs directly in the Allmaps Editor, which is the whole point of
// this tool. Memory on this project found 4 of 6 D4 mirrors stale by up to
// 13 months. `/images/{allmaps_id}` is the per-map-image endpoint —
// `/maps/{id}` is a per-annotation id and not what `allmaps_id` is.
async function liveAnnotation(row) {
  if (row.allmaps_id) {
    try {
      const res = await fetch(`https://annotations.allmaps.org/images/${row.allmaps_id}`);
      if (res.ok) return { ann: await res.json(), source: 'live' };
    } catch {
      /* fall through */
    }
  }
  if (row.annotation_url) {
    try {
      const res = await fetch(row.annotation_url);
      if (res.ok) return { ann: await res.json(), source: 'mirror (stale risk)' };
    } catch {
      /* no source at all */
    }
  }
  return { ann: null, source: 'unreachable' };
}

async function loadSheet(id) {
  const { data: rows, error } = await db
    .from('maps')
    .select(
      'id,year,name,slug,allmaps_id,annotation_url,map_images(iiif_image,iiif_manifest,source_type)'
    )
    .eq('id', id);
  if (error || !rows?.length) return { id, error: error?.message ?? 'no row' };
  const row = rows[0];

  const { ann, source } = await liveAnnotation(row);
  if (!ann) return { id, row, error: `annotation ${source}` };

  const sourceId = ann.items?.[0]?.target?.source?.id;
  const link = editorLinkFor(row, sourceId);

  const maps = parseAnnotation(ann);
  if (!maps.length) return { id, row, error: 'annotation had no georeferenced map' };
  const transformer = GcpTransformer.fromGeoreferencedMap(maps[0]);

  if (manualPoints) {
    const names = new Map();
    for (const [label, bySheet] of Object.entries(manualPoints)) {
      const px = resolveManualPx(bySheet, id, row.year);
      if (!px) continue;
      let lonlat;
      try {
        lonlat = transformer.transformToGeo(px);
      } catch {
        continue;
      }
      names.set(nameKey(label), { px, text: label, lonlat, nRuns: 1 });
    }
    return { id, row, source, editorLink: link, names, nGcps: maps[0].gcps?.length ?? null };
  }

  let query = db
    .from('ocr_labels')
    .select('text,category,global_x,global_y,global_w,global_h,run_id')
    .eq('map_id', id)
    .neq('review_status', 'rejected');
  const pinnedRun = runIdOverride.get(id);
  if (pinnedRun) query = query.eq('run_id', pinnedRun);
  const { data: extractions, error: ocrError } = await query;
  if (ocrError) return { id, row, error: `ocr fetch: ${ocrError.message}` };

  // Group by name key. Several runs re-extracting the SAME printed label is
  // not the same fact as the label being printed several times on the
  // sheet — the former should collapse to one correspondence, the latter is
  // ambiguous and correctly dropped ("Rue Projetée" appears many times and
  // is a correspondence to nothing, sheet_register.py's rule). Distinguish
  // them by clustering on pixel position: occurrences within CLUSTER_PX of
  // their own centroid are one label re-read by different runs; anything
  // wider really is printed more than once.
  const CLUSTER_PX = 80;
  const seen = new Map();
  for (const e of extractions ?? []) {
    if (SKIP_CAT.has(e.category)) continue;
    const k = nameKey(e.text);
    if (k.length < MIN_KEY) continue;
    const px = [e.global_x + e.global_w / 2, e.global_y + e.global_h / 2];
    if (!seen.has(k)) seen.set(k, []);
    seen.get(k).push({ px, text: e.text });
  }

  const names = new Map();
  for (const [k, occurrences] of seen) {
    const cx = occurrences.reduce((s, o) => s + o.px[0], 0) / occurrences.length;
    const cy = occurrences.reduce((s, o) => s + o.px[1], 0) / occurrences.length;
    const maxDist = Math.max(...occurrences.map((o) => Math.hypot(o.px[0] - cx, o.px[1] - cy)));
    if (maxDist > CLUSTER_PX) continue; // genuinely printed more than once — ambiguous
    const px = [cx, cy];
    const text = occurrences[0].text;
    let lonlat;
    try {
      lonlat = transformer.transformToGeo(px);
    } catch {
      continue;
    }
    names.set(k, { px, text, lonlat, nRuns: occurrences.length });
  }

  return { id, row, source, editorLink: link, names, nGcps: maps[0].gcps?.length ?? null };
}

const sheets = await Promise.all(mapIds.map(loadSheet));

const ok = sheets.filter((s) => !s.error);
for (const s of sheets) {
  if (s.error) console.log(`${s.row?.year ?? s.id}: SKIPPED — ${s.error}`);
}
console.log(
  `\n${ok.length}/${sheets.length} sheets loaded. Unique-name counts: ` +
    ok.map((s) => `${s.row.year ?? s.id.slice(0, 8)}=${s.names.size}`).join(', ')
);

// ------------------------------------------------------------- pairwise check

console.log(
  '\n### Pairwise ground disagreement (shared unique names, each warped by its own sheet)\n'
);
// median_all/max_all are over EVERY shared name, unfiltered — the honest
// number. median_within/n_within describe only the sub-150m subset for
// comparison with the journal's method. Reporting median_within alone would
// be circular: a pair getting worse just drops points out of that
// denominator and the column can shrink, which is the same fault this
// session flagged in RMSE-on-fit-points. A blank median_within with a huge
// max_all means "catastrophic disagreement," not "no data."
console.log('| pair | shared | median all (m) | max all (m) | within 150m | median within (m) |');
console.log('|---|---:|---:|---:|---:|---:|');

const anchorTally = new Map(); // key -> [{sheet, lonlat, px, text}]
const pairwise = [];

for (let i = 0; i < ok.length; i++) {
  for (let j = i + 1; j < ok.length; j++) {
    const [a, b] = [ok[i], ok[j]];
    const shared = [...a.names.keys()].filter((k) => b.names.has(k));
    if (!shared.length) continue;

    const dists = shared.map((k) => ({
      key: k,
      text: a.names.get(k).text,
      d: haversineM(a.names.get(k).lonlat, b.names.get(k).lonlat),
    }));
    for (const { key, text, d } of dists) {
      if (!anchorTally.has(key)) anchorTally.set(key, { text, points: [] });
      const entry = anchorTally.get(key);
      for (const sheet of [a, b]) {
        if (!entry.points.some((p) => p.sheetId === sheet.id)) {
          entry.points.push({ sheetId: sheet.id, sheet, ...sheet.names.get(key) });
        }
      }
    }

    const within = dists.filter((x) => x.d <= THRESHOLD_M);
    console.log(
      `| ${a.row.year}<->${b.row.year} | ${shared.length} | ` +
        `${Math.round(median(dists.map((x) => x.d)))} | ${Math.round(Math.max(...dists.map((x) => x.d)))} | ` +
        `${within.length} | ${within.length ? Math.round(median(within.map((x) => x.d))) : '—'} |`
    );
    pairwise.push({
      a: a.row.year,
      b: b.row.year,
      aName: a.row.name,
      bName: b.row.name,
      shared: shared.length,
      medianAllM: Math.round(median(dists.map((x) => x.d))),
      maxAllM: Math.round(Math.max(...dists.map((x) => x.d))),
      nWithin: within.length,
      medianWithinM: within.length ? Math.round(median(within.map((x) => x.d))) : null,
    });
  }
}

// -------------------------------------------------------------- best anchors

const allAnchors = [...anchorTally.entries()]
  .filter(([, v]) => v.points.length >= 3) // seen independently on 3+ sheets
  .map(([key, v]) => {
    const centroid = [
      v.points.reduce((s, p) => s + p.lonlat[0], 0) / v.points.length,
      v.points.reduce((s, p) => s + p.lonlat[1], 0) / v.points.length,
    ];
    const spread = Math.max(...v.points.map((p) => haversineM(p.lonlat, centroid)));
    return {
      key,
      text: v.text,
      spread,
      points: v.points.map((p) => ({
        year: p.sheet.row.year,
        name: p.sheet.row.name,
        px: p.px.map(Math.round),
        lon: p.lonlat[0],
        lat: p.lonlat[1],
        editorUrl: p.sheet.editorLink?.url ?? null,
        verified: !!p.sheet.editorLink?.verified,
      })),
    };
  })
  .sort((a, b) => a.spread - b.spread);

if (asJson) {
  console.log('\n---JSON---');
  console.log(
    JSON.stringify(
      {
        sheets: ok.map((s) => ({
          id: s.id,
          year: s.row.year,
          name: s.row.name,
          source: s.source,
          nUniqueNames: s.names.size,
          nGcps: s.nGcps,
        })),
        pairwise,
        anchors: allAnchors,
      },
      null,
      2
    )
  );
}

if (!showAnchors) {
  if (!asJson) {
    console.log(
      '\n(run with --anchors for editor-ready per-sheet points, --json for structured output)'
    );
  }
  process.exit(0);
}

console.log('\n### Best multi-sheet anchors — editor-ready\n');
for (const anchor of allAnchors.slice(0, 10)) {
  console.log(
    `\n## "${anchor.text}" — ${anchor.points.length} sheets, spread ${anchor.spread.toFixed(1)} m`
  );
  for (const p of anchor.points) {
    const [px, py] = p.px;
    const verified = p.verified ? '' : '  [unverified link]';
    console.log(
      `  ${p.year} ${p.name}: ${px} ${py} ${p.lon.toFixed(6)} ${p.lat.toFixed(6)}${verified}\n    ${p.editorUrl ?? 'no editor link'}`
    );
  }
}
