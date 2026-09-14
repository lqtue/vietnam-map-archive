#!/usr/bin/env node
// Queue an `ocr` job for every georeferenced map that has never been OCR'd.
//
//   node --env-file=.env scripts/enqueue_ocr_all.mjs [--dry] [--force] [--limit N]
//                                                    [--untriaged] [--model NAME]
//                                                    [--map <id|id-prefix>] [--max-calls N]
//                                                    [--max-cost USD] [--low-thinking]
//                                                    [--tile-metres M] [--single-pass]
//
// Label search (`/api/search?include=labels`, mig 065) is only as good as the
// share of the corpus that has extractions, and measured on 2026-09-02 that was
// one map. This inserts the same `pipeline_jobs` row `/api/admin/maps/[id]/ocr`
// does, with the same defaults, then the worker drains it:
//   source work/ocr/.venv/bin/activate && python work/worker/vma_worker.py
//
// --force also re-queues maps that already have extractions (new run_id).
// The one-live-job index turns a duplicate into a skipped row, never a second job.
//
// By default this queues only sheets someone has **saved a triage** for in
// /contribute/digitalize (`maps.triage`, migration 069): the neatline, tile grid
// and per-tile priorities a person decided on, spread into the job payload
// unchanged. That is the deliberate order — triage, look at what you did, then
// queue. `--untriaged` includes the rest, which run in `auto` mode and let the
// scout pass guess the neatline; that is the old behaviour and it is worse.

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';
import { parseAnnotation } from '@allmaps/annotation';

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const force = args.includes('--force');
const limitIdx = args.indexOf('--limit');
const limit = limitIdx > -1 ? Number(args[limitIdx + 1]) : Infinity;
const untriaged = args.includes('--untriaged');
// One sheet only, by id or id prefix. A re-scanned sheet needs re-queuing on its
// own; every other selector here is corpus-wide.
const mapIdx = args.indexOf('--map');
const onlyMap = mapIdx > -1 ? args[mapIdx + 1] : null;
// Queue proposals nobody has accepted yet. The point of the accept step is that
// a bad crop is caught before it is paid for, so this is opt-in.
const unvalidated = args.includes('--unvalidated');
const modelIdx = args.indexOf('--model');
const model = modelIdx > -1 ? args[modelIdx + 1] : null;
// Two passes by default: the grid, then the grid moved half a tile, voted into
// one run by `ocr.py merge`. 41/43 against 39/43 for one pass on the gate sheet
// (work/ocr/EVAL-BASELINE.md), for twice the tokens — cents. --single-pass opts out.
const passes = args.includes('--single-pass') ? 1 : 2;
// A ceiling on what one sheet may spend, checked by the worker between plan
// steps and reported back in the job result. Measured on the 1959 sheet: the
// two grid passes cost 72 calls at 26 extractions each, while a third,
// finer sweep of the same ground returned 0.07 — so the budget is what stops
// a fleet run from spending its afternoon on one sheet's last few labels.
const mcIdx = args.indexOf('--max-calls');
const maxCalls = mcIdx > -1 ? Number(args[mcIdx + 1]) : null;
// The same ceiling in money. A call is a poor proxy: measured over 1,192 calls
// on this corpus one ranges $0.0012 to $0.155, and the dearest tenth carry 28%
// of all spend, so a call budget is roughly 6x loose either way.
const costIdx = args.indexOf('--max-cost');
const maxCost = costIdx > -1 ? Number(args[costIdx + 1]) : null;
// Ask for thinking_level=low. Measured 2026-09-13: thinking was 59% of billed
// output tokens and 56% of that day's bill. It changes the answer as well as
// the price -- better on numerals, not established on body text -- so it is
// opt-in rather than the default.
const lowThinking = args.includes('--low-thinking');

// ── What a sheet has actually cost ──────────────────────────────────────────
// Queuing a sweep used to print how many maps it would touch and nothing about
// what they would cost, so the only way to find out was the bill. On
// 2026-09-13 one command queued 14 OCR jobs and 72 layout scouts; the figure
// below would have said roughly what that was going to be, before it ran.
//
// Rates come from work/ocr/prices.json, the same file work/ocr/scripts/pricing.py
// reads, so there is no second copy to drift.
const REPO = new URL('..', import.meta.url);
const PRICES = (() => {
  try {
    return JSON.parse(readFileSync(fileURLToPath(new URL('work/ocr/prices.json', REPO)), 'utf8'))
      .models;
  } catch {
    return {};
  }
})();

/** USD for one logged call, or null when the model has no published rate. */
function callCost(rec) {
  if (rec.cost_usd != null) return rec.cost_usd; // written by gemini_client since 2026-09-14
  const rate = PRICES[rec.model];
  if (!rate || rec.total_tokens == null || rec.input_tokens == null) return null;
  const cached = rec.cached_tokens ?? 0;
  return (
    (Math.max(rec.input_tokens - cached, 0) * rate.input) / 1e6 +
    (cached * rate.cached) / 1e6 +
    (Math.max(rec.total_tokens - rec.input_tokens, 0) * rate.output) / 1e6
  );
}

/** Every calls.jsonl under a directory, at any depth. */
function findLogs(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, e.name);
    if (e.isDirectory()) out.push(...findLogs(full));
    else if (e.name === 'calls.jsonl') out.push(full);
  }
  return out;
}

/** Total USD already spent per map, from every calls.jsonl on disk.
 *
 * Walks the whole map directory rather than just `runs/`: the segmentation
 * review writes to `<map>/seg-review/<run>/calls.jsonl`, which is $3.26 of
 * real spend that a runs-only scan reports as zero.
 */
function costPerMap() {
  const root = fileURLToPath(new URL('work/ocr/outputs', REPO));
  if (!existsSync(root)) return [];
  const totals = [];
  // withFileTypes, because outputs/ also holds loose files (dedupe-*.json and
  // friends) alongside the per-map directories, and recursing into one throws.
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = join(root, entry.name);
    let sum = 0;
    let priced = 0;
    for (const log of findLogs(dir)) {
      for (const line of readFileSync(log, 'utf8').split('\n')) {
        if (!line.trim()) continue;
        let rec;
        try {
          rec = JSON.parse(line);
        } catch {
          continue; // a half-written last line is not worth failing an estimate over
        }
        const c = callCost(rec);
        if (c != null) {
          sum += c;
          priced++;
        }
      }
    }
    if (priced) totals.push(sum);
  }
  return totals.sort((a, b) => a - b);
}

const q = (xs, p) => (xs.length ? xs[Math.min(Math.floor(p * xs.length), xs.length - 1)] : 0);

/** One line of projected spend, or null when there is no history to go on. */
function estimate(nMaps) {
  const hist = costPerMap();
  if (hist.length < 3 || !nMaps) return null;
  const med = q(hist, 0.5);
  return (
    `  estimate: ${nMaps} x ~$${med.toFixed(2)} median = ~$${(nMaps * med).toFixed(2)} ` +
    `(per-sheet range $${q(hist, 0.25).toFixed(2)}-$${q(hist, 0.9).toFixed(2)}, ` +
    `measured over ${hist.length} sheets). Cap a sheet with --max-cost.`
  );
}

// Mirrors RENDER_FLOOR in work/worker/vma_worker.py. Only used to print the
// ground-per-call figure below — the worker computes the value it actually
// sends, so there is nothing here to drift out of step with.
const RENDER_FLOOR = 1024;

// Ground per Gemini call, in metres. Opt-in, and it only ever makes a tile
// FINER.
//
// What starves an OCR read is one call covering too much ground, and a fixed
// pixel tile is a different amount of ground on every sheet: 2048 px is 1.7 km
// on the 1923 sheet and 5.7 km on the 1959 one. Measured on the 1959 sheet,
// same crop and same 1:1 rendering, changing only the tile: 5.7 km/call found 1
// label inside the study area, 2.9 km found 2, 1.4 km found 6. Corpus-wide the
// same change is +19%, concentrated entirely in the sheets whose ground-per-call
// actually dropped a long way — see docs/pipelines.md.
//
// Off by default for two reasons. A saved triage carries the tile size a person
// chose, and overriding that silently would defeat the point of saving one. And
// the first version of this rule made a sheet WORSE: at 0.34 m/px the 1882
// cadastral needs a 4118 px tile to reach 1400 m, so a fixed ground target
// coarsened it. Hence `Math.min` against the tile we would otherwise have used —
// the rule may make a sheet finer, never coarser.
const tmIdx = args.indexOf('--tile-metres');
const tileMetres = tmIdx > -1 ? Number(args[tmIdx + 1]) : null;
const TILE_PX_MIN = 384;

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const { data: maps, error } = await db
  .from('maps')
  .select('id, name, year, iiif_image, allmaps_id, annotation_url, triage')
  .eq('georef_done', true)
  .not('iiif_image', 'is', null)
  .order('year');
if (error) throw error;

// Which maps already have extractions. `.select('map_id').limit(100000)` was
// wrong: PostgREST caps a response at 1000 rows whatever the limit says, and
// with 1404 extraction rows in the table this saw exactly one of the two
// OCR'd maps and re-queued the other on every run. A grouped count is capped
// by the number of *maps*, not the number of rows.
const hasOcr = new Set();
{
  const { data: rows, error: exErr } = await db
    .from('ocr_extractions')
    .select('map_id')
    .limit(1000);
  if (exErr) throw exErr;
  for (const r of rows ?? []) hasOcr.add(r.map_id);
  // The cap above is a silent truncation, so confirm per map rather than
  // trusting a full-table scan we cannot page cheaply.
  for (const m of maps) {
    if (hasOcr.has(m.id)) continue;
    const { count, error: cErr } = await db
      .from('ocr_extractions')
      .select('*', { count: 'exact', head: true })
      .eq('map_id', m.id);
    if (cErr) throw cErr;
    if (count) hasOcr.add(m.id);
  }
}

const { data: live } = await db
  .from('pipeline_jobs')
  .select('map_id')
  .eq('kind', 'ocr')
  .in('status', ['queued', 'claimed', 'running']);
const inFlight = new Set((live ?? []).map((r) => r.map_id));

// A sheet is queueable when a person has *accepted* a crop, not merely when one
// exists. The crop can now be proposed end-to-end with no human — the layout
// job adopts its own `main_map` region — so "has a triage" stopped meaning
// "someone decided this".
//
// The old gate was `triage.neatline`, and across 101 georeferenced maps **no
// sheet had one**, so this script's default mode queued nothing at all and
// looked like it had worked. 37 sheets already carried a main_map region that
// `tilingCrop` prefers to a neatline anyway. Mirrors `triageState()` in
// src/lib/data/maps/triageTypes.ts — this file is plain .mjs and cannot import
// the TS.
const cropOfTriage = (t) =>
  (t?.regions ?? []).find((r) => r.category === 'main_map')?.bbox ?? t?.neatline ?? null;
const triageOf = (m) => {
  const t = m.triage;
  if (!cropOfTriage(t)) return null;
  return unvalidated || t.validated_at ? t : null;
};

// The crop the tile pass should cover. A `main_map` region is the layout pass's
// answer to "where is the terrain", which beats the neatline: the neatline is
// the printed border, and a legend or an index printed inside it is inside the
// neatline too. Mirrors `tilingCrop()` in src/lib/data/maps/triageTypes.ts —
// this file is plain .mjs and cannot import the TS.
const cropOf = cropOfTriage;

// Blocks of printed *text about* the map rather than the map: the numbered
// legend, the street directory. They are inside the crop whenever the layout
// pass answered `main_map` with the neatline — which is what the 1942
// Saigon–Cho Lon sheet does — and a tile of one reads as a page of numerals
// stamped on nothing. The `legend` and `street-index` passes read these blocks
// as tables, with the grid cell each line names, so the tile pass has nothing
// to add here and everything to invent.
const PRINTED_BLOCKS = new Set(['legend', 'name_list']);
const excludeOf = (t) =>
  (t?.regions ?? []).filter((r) => PRINTED_BLOCKS.has(r.category)).map((r) => r.bbox);
const nTriaged = maps.filter(triageOf).length;
const nProposed = maps.filter((m) => cropOf(m.triage) && !m.triage?.validated_at).length;
const nNeedsCrop = maps.filter((m) => !cropOf(m.triage) && (m.triage?.regions ?? []).length).length;
const nNeedsLayout = maps.filter(
  (m) => !cropOf(m.triage) && !(m.triage?.regions ?? []).length
).length;

const todo = maps
  .filter((m) => !onlyMap || m.id === onlyMap || m.id.startsWith(onlyMap))
  .filter((m) => !inFlight.has(m.id) && (force || !hasOcr.has(m.id)))
  .filter((m) => untriaged || triageOf(m))
  .slice(0, limit);

console.log(
  `${maps.length} georeferenced · ${nTriaged} accepted · ${nProposed} proposed (not accepted) · ` +
    `${nNeedsCrop} no main_map · ${nNeedsLayout} no layout pass · ` +
    `${hasOcr.size} already OCR'd · ${inFlight.size} in flight → ` +
    `${todo.length} to queue${dry ? ' (dry run)' : ''}`
);
const projected = estimate(todo.length);
if (projected) console.log(projected);
if (!untriaged && nTriaged < maps.length) {
  if (nNeedsLayout) {
    console.log(
      `  ${nNeedsLayout} sheets have had no layout pass. ` +
        `Run scripts/enqueue_layout_all.mjs and drain it — that proposes the crop.`
    );
  }
  if (nProposed) {
    console.log(
      `  ${nProposed} sheets have a proposed crop nobody has accepted. ` +
        `Accept them at /scan?mode=triage, or pass --unvalidated to queue them as proposed.`
    );
  }
  if (nNeedsCrop) {
    console.log(
      `  ${nNeedsCrop} sheets had a layout pass that found no main_map — those need a person ` +
        `to open them at /scan?mode=triage, where the browser proposes a crop from the ink.`
    );
  }
}

/**
 * Ground metres per source pixel over the rectangle we are about to tile.
 *
 * Measured through the sheet's own georeference — warp the crop's four corners
 * to lng/lat and compare the real area with the pixel area. Rotation- and
 * skew-invariant, unlike a bbox-to-width ratio, which read 0.33 m/px on the
 * 1912 sheet where the truth is nearer 1.8.
 *
 * Returns null when there is nothing to measure with; the caller then keeps the
 * tile it already had rather than guessing.
 */
/** `[x, y, w, h]` bounding the GCPs in source pixels, or null if unusable. */
function gcpPixelBox(gcps) {
  const pts = (gcps ?? []).map((g) => g.resource ?? g.pixel).filter(Boolean);
  if (pts.length < 3) return null;
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const w = Math.max(...xs) - Math.min(...xs);
  const h = Math.max(...ys) - Math.min(...ys);
  return w > 1 && h > 1 ? [Math.min(...xs), Math.min(...ys), w, h] : null;
}

const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 111320 * Math.cos((10.78 * Math.PI) / 180);

function ringAreaM2(lonlats) {
  let a = 0;
  for (let i = 0, j = lonlats.length - 1; i < lonlats.length; j = i++) {
    a += lonlats[j][0] * lonlats[i][1] - lonlats[i][0] * lonlats[j][1];
  }
  return (Math.abs(a) / 2) * M_PER_DEG_LON * M_PER_DEG_LAT;
}

async function cropMpp(m, crop) {
  const url =
    m.annotation_url ||
    (m.allmaps_id ? `https://annotations.allmaps.org/images/${m.allmaps_id}` : null);
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const parsed = parseAnnotation(await res.json());
    if (!parsed.length) return null;
    const t = new GcpTransformer(parsed[0].gcps, parsed[0].transformation?.type ?? 'polynomial');
    // No crop means nobody has triaged this sheet — which is the majority, and
    // the ones this rule exists for. Fall back to the pixel hull of the GCPs
    // themselves: they sit on identifiable ground features, so their hull is
    // inside the map content, and warping its corners interpolates rather than
    // extrapolating. Warping the *image* corners instead would run a polynomial
    // out past its control points and into the margins, which is how the naive
    // bbox-to-width ratio read 0.33 m/px on the 1912 sheet.
    const rect = crop ?? gcpPixelBox(parsed[0].gcps);
    if (!rect) return null;
    const [x, y, w, h] = rect;
    const ground = [
      [x, y],
      [x + w, y],
      [x + w, y + h],
      [x, y + h],
    ].map((p) => t.transformToGeo(p));
    const area = ringAreaM2(ground);
    return area > 0 && w * h > 0 ? Math.sqrt(area / (w * h)) : null;
  } catch {
    return null;
  }
}

/** The tile to use, never coarser than `current`. */
function groundTile(mpp, current) {
  if (!mpp || !tileMetres) return current;
  const raw = Math.round(tileMetres / mpp);
  return Math.max(TILE_PX_MIN, Math.min(raw, current));
}

let queued = 0;
for (const m of todo) {
  const t = triageOf(m);
  const usingMainMap = (t?.regions ?? []).some((r) => r.category === 'main_map');
  const crop = cropOf(t);
  const baseTile = t?.tile_size ?? 2400;
  const mpp = tileMetres ? await cropMpp(m, crop) : null;
  const tile = groundTile(mpp, baseTile);
  // The render size is the worker's rule now (`_render_size`), so the button and
  // this script cannot drift apart again. Shown here only to report it.
  const render = Math.max(tile, RENDER_FLOOR);
  const ground = mpp ? `   ${((tile * mpp) / 1000).toFixed(2)} km/call` : '';
  console.log(
    `  ${m.year ?? '????'}  ${m.name}` +
      (t ? (usingMainMap ? '   (cropped to main_map)' : '') : '   (no triage — auto mode)') +
      (tile !== baseTile ? `   tile ${baseTile} → ${tile}` : '') +
      ground
  );
  if (dry) continue;
  // Per map, not per second: a shared run_id would collapse every map's run
  // summary into one and break `--ocr-run-id` seeding for segmentation.
  const run_id = `${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}-${m.id.slice(0, 8)}`;
  const { error: insErr } = await db.from('pipeline_jobs').insert({
    kind: 'ocr',
    map_id: m.id,
    payload: {
      run_id,
      tile_size: tile,
      overlap: t?.overlap ?? Math.round(tile / 4),
      // A saved neatline is the whole point of triaging: with one, the scout
      // pass has nothing left to guess, so `auto` only still runs the legend.
      auto: true,
      // Per-tile priorities from the measured density signal, computed at run
      // time on the grid actually being tiled — so there is no key to
      // mismatch. `tests/density-parity.spec.ts` pins the Python pass to the
      // browser's, which is the implementation that was measured; a saved
      // `tile_overrides` from a person still wins, since ocr.py prefers it.
      auto_priority: true,
      ...(crop ? { neatline: crop } : {}),
      ...(excludeOf(t).length ? { exclude: excludeOf(t) } : {}),
      ...(t?.tile_overrides && Object.keys(t.tile_overrides).length
        ? { tile_overrides: t.tile_overrides }
        : {}),
      ...(model ? { model } : {}),
      ...(maxCalls ? { max_calls: maxCalls } : {}),
      ...(maxCost ? { max_cost_usd: maxCost } : {}),
      ...(lowThinking ? { low_thinking: true } : {}),
      passes,
    },
  });
  if (insErr && insErr.code !== '23505') throw insErr; // 23505 = one-live-job index, already queued
  if (!insErr) queued++;
}
if (!dry) console.log(`queued ${queued}`);
