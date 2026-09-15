#!/usr/bin/env node
// Backfill `maps.bbox` from each map's Allmaps annotation.
//
//   node --env-file=.env scripts/oneoff/backfill_map_bbox.mjs [--dry] [--force] [--concurrency N]
//
// Measured on 2026-09-04: 0 of 101 maps had a bbox, so every "where is this
// map?" question — /explore's zoom-to-overlay, `?map=` deep links, and any
// selection by area — fell through `resolveBounds()` to a live annotation
// fetch per map. The column exists and the ladder already prefers it; nothing
// had ever written it.
//
// The value is the **warped extent of the sheet's resource mask**: the mask
// pushed through the map's own transform, which is the ground the overlay
// actually covers.
//
// It used to be the hull of the GCPs, and that was wrong in a way nothing
// reported. GCPs sit wherever the georeferencer clicked — usually the neatline,
// never the paper edge — so the hull under-states the sheet, and on `Đô thành
// Sài Gòn` (10 GCPs spanning x 2712-12522 of a 14000 px sheet) it under-stated
// it by half the area. A bbox that small makes zoom-to-overlay clip the sheet's
// margins with nothing looking broken. Worse, `--force` would silently replace
// a correct mask extent with the smaller hull, so re-running this script after
// an unrelated re-georeference quietly degraded maps it was not called for.
// Measured 2026-09-15; the two values on that sheet were:
//
//   mask extent  [106.605939, 10.710292, 106.734181, 10.807962]
//   GCP hull     [106.630810, 10.725215, 106.720521, 10.799605]
//
// Computing the extent the same way the renderer does makes `--force`
// idempotent: a correctly-set row recomputes to itself, so there is no longer a
// value this script can destroy.
//
// Skips maps that already have one unless --force. 404 (never georeferenced)
// and no-GCP annotations are left null, not zeroed.

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const force = args.includes('--force');
const cIdx = args.indexOf('--concurrency');
const concurrency = cIdx > -1 ? Number(args[cIdx + 1]) : 10;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

/** Bare hex id → the Allmaps annotation endpoint; a full URL passes through.
 *  Mirrors `annotationUrlForSource()` in $lib/core/iiif/annotationUrl.ts. */
function annotationUrl(source) {
  const trimmed = source.trim();
  try {
    const u = new URL(trimmed);
    if (u.protocol === 'http:' || u.protocol === 'https:') return trimmed;
  } catch {
    // not a URL — treat as an Allmaps image id
  }
  return `https://annotations.allmaps.org/images/${trimmed}`;
}

/** Extent of a list of [lng, lat] pairs, or null when there is nothing to bound. */
function extentOf(points) {
  if (!points.length) return null;
  const lng = points.map((p) => p[0]);
  const lat = points.map((p) => p[1]);
  return [Math.min(...lng), Math.min(...lat), Math.max(...lng), Math.max(...lat)];
}

/**
 * Subdivide each edge of a resource ring into `perEdge` segments.
 *
 * A mask is four corners, and under a Helmert or first-order polynomial a
 * straight resource edge stays straight, so the corners alone bound it. Under a
 * higher-order polynomial or a thin-plate spline the edge bows, and a bow that
 * leaves the corner box is invisible to a four-point extent. Densifying costs
 * one transform call per point and removes the question.
 */
function densify(ring, perEdge = 24) {
  const out = [];
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    for (let s = 0; s < perEdge; s++) {
      const t = s / perEdge;
      out.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]);
    }
  }
  return out;
}

/**
 * The ground a sheet covers: its resource mask warped through its own
 * transform. Falls back to the GCP hull when the annotation carries no usable
 * mask or the transform refuses it — an under-estimate, but better than null.
 * Returns `{ bbox, how, n }`.
 */
function sheetExtent(annotation) {
  let maps = [];
  try {
    maps = parseAnnotation(annotation);
  } catch {
    return null;
  }
  if (!maps.length) return null;
  const map = maps[0];
  const gcps = map.gcps ?? [];
  if (gcps.length < 2) return null;

  const hull = extentOf(gcps.map((g) => g.geo));

  const mask = map.resourceMask;
  if (Array.isArray(mask) && mask.length >= 3) {
    try {
      const transformer = GcpTransformer.fromGeoreferencedMap(map);
      const warped = densify(mask).map((p) => transformer.transformToGeo(p));
      const usable = warped.filter(
        (p) => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])
      );
      const bbox = extentOf(usable);
      if (bbox) return { bbox, how: 'mask', n: gcps.length };
    } catch {
      // fall through to the hull
    }
  }
  return hull ? { bbox: hull, how: 'hull', n: gcps.length } : null;
}

const { data: maps, error } = await db
  .from('maps')
  .select('id, name, year, bbox, allmaps_id, annotation_url')
  .order('year', { nullsFirst: false });
if (error) throw error;

const todo = maps.filter(
  (m) =>
    (m.annotation_url || m.allmaps_id) && (force || !Array.isArray(m.bbox) || m.bbox.length !== 4)
);
console.log(
  `${maps.length} maps · ${maps.filter((m) => m.bbox?.length === 4).length} already have a bbox → ${todo.length} to fetch${dry ? ' (dry run)' : ''}`
);

const results = [];
let cursor = 0;
async function worker() {
  while (cursor < todo.length) {
    const m = todo[cursor++];
    const source = m.annotation_url ?? m.allmaps_id;
    try {
      const res = await fetch(annotationUrl(source));
      if (!res.ok) {
        results.push({ m, bbox: null, why: `HTTP ${res.status}` });
        continue;
      }
      const got = sheetExtent(await res.json());
      if (!got) {
        results.push({ m, bbox: null, why: 'no GCPs' });
        continue;
      }
      results.push({ m, bbox: got.bbox, how: got.how, n: got.n });
    } catch (e) {
      results.push({ m, bbox: null, why: String(e?.message ?? e) });
    }
  }
}
await Promise.all(Array.from({ length: Math.min(concurrency, todo.length) }, worker));

// A hull of one point is a degenerate box; the app's `looksValidBbox` would
// reject it downstream, so don't write it in the first place.
const writable = results.filter((r) => r.bbox && r.bbox[0] < r.bbox[2] && r.bbox[1] < r.bbox[3]);
const skipped = results.filter((r) => !writable.includes(r));

let changed = 0;
for (const r of writable) {
  const b = r.bbox.map((n) => +n.toFixed(6));
  const cur = r.m.bbox;
  const same =
    Array.isArray(cur) && cur.length === 4 && cur.every((v, i) => Math.abs(v - b[i]) < 1e-6);
  if (same) continue;
  changed++;
  console.log(
    `  ${String(r.m.year ?? '????')}  ${r.n}gcp ${r.how.padEnd(4)}  [${b}]  ${r.m.name.slice(0, 48)}`
  );
  if (dry) continue;
  const { error: upErr } = await db.from('maps').update({ bbox: b }).eq('id', r.m.id);
  if (upErr) throw upErr;
}

const byHow = {};
for (const r of writable) byHow[r.how] = (byHow[r.how] ?? 0) + 1;
console.log(
  `\n${writable.length} with a real extent (${Object.entries(byHow)
    .map(([k, n]) => `${n} ${k}`)
    .join(', ')}), ${skipped.length} left null · ${changed} differ from what is stored`
);
const why = {};
for (const r of skipped) why[r.why] = (why[r.why] ?? 0) + 1;
for (const [k, n] of Object.entries(why)) console.log(`  ${String(n).padStart(3)}  ${k}`);
if (!dry) console.log(`\nwrote ${changed} bboxes`);
