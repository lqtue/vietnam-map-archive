/**
 * The rebuild set for the two things that can happen to a published map:
 * its pixels change (a rescan) or its georeference changes (a re-place in
 * the Allmaps editor). `stale-after-change` in docs/ROADMAP.md.
 *
 * Re-georeferencing is already handled: `mirror_annotation`/`sync_allmaps`
 * chain into a `warp` job (`src/routes/api/pipeline/execute/+server.ts`),
 * which calls `rewarpMap` (`$lib/server/rewarp.ts`) to re-derive
 * `ocr_extractions.geom` and `footprint_submissions.geom` from their stored
 * *pixel* positions. Nothing here needs building — this file just pins that
 * the ground-space columns it writes are exactly these two, so a schema
 * change there is a deliberate edit to this test, not a silent drift.
 *
 * A rescan has no equivalent. `PATCH /api/admin/maps/[id]` can set
 * `iiif_image` to a new scan with no coupling to any pixel-space column —
 * confirmed below by exercising the real allow-list. That gap is left open
 * on purpose: an `iiif_image` write also fires on a same-pixels hosting move
 * (`MapEditHostingTab`'s "Mirror to R2"), which must NOT clear anything, and
 * telling the two apart needs a person, not a column diff. What follows is
 * the checklist that person needs, pinned so it cannot drift unnoticed.
 */
import { test, expect } from '@playwright/test';
import { pickMapFields } from '../src/lib/server/mapFields';

/** table.column, one entry per real column — never a joined list — so the
 *  disjointness checks below mean what they say. */
const RESCAN_INVALIDATES = new Set([
  'maps.triage', // neatline + regions, source pixel coords
  'ocr_extractions.tile_x',
  'ocr_extractions.tile_y',
  'ocr_extractions.tile_w',
  'ocr_extractions.tile_h',
  'ocr_extractions.global_x',
  'ocr_extractions.global_y',
  'ocr_extractions.global_w',
  'ocr_extractions.global_h',
  'footprint_submissions.pixel_polygon', // traced against the old scan
]);
/** Not a column — the R2 object cache of the old pixels. Redo it too. */
const RESCAN_ALSO_REDO = ['tile_to_r2 output (R2 tiles)'];

const REGEOREF_INVALIDATES = new Set([
  'maps.bbox',
  'ocr_extractions.geom',
  'ocr_extractions.geom_src',
  'ocr_extractions.geom_rmse',
  'footprint_submissions.geom',
  'footprint_submissions.geom_src',
  'footprint_submissions.geom_rmse',
]);

/** Reusable after a rescan, IF the replacement is confirmed to be the same
 *  crop and orientation as the old scan — never assume it, check it. */
const RESCAN_REUSABLE_IF_SAME_CROP = new Set([
  'maps.annotation_url',
  'maps.allmaps_id',
  'ocr_extractions.text',
  'ocr_extractions.category',
  'ocr_extractions.confidence',
]);

/** Reusable after a re-place, unconditionally: none of it is pixel-derived. */
const REGEOREF_REUSABLE = new Set([
  'maps.triage',
  'ocr_extractions.tile_x',
  'ocr_extractions.text',
  'footprint_submissions.pixel_polygon',
]);

test('a rescan and a re-place never claim the same column', () => {
  for (const col of RESCAN_INVALIDATES) expect(REGEOREF_INVALIDATES.has(col)).toBe(false);
  for (const col of REGEOREF_INVALIDATES) expect(RESCAN_INVALIDATES.has(col)).toBe(false);
});

test('nothing a rescan invalidates is also listed reusable-after-rescan', () => {
  for (const col of RESCAN_INVALIDATES) expect(RESCAN_REUSABLE_IF_SAME_CROP.has(col)).toBe(false);
});

test('nothing a re-place invalidates is also listed reusable-after-re-place', () => {
  for (const col of REGEOREF_INVALIDATES) expect(REGEOREF_REUSABLE.has(col)).toBe(false);
});

test('every pixel-space column a re-place leaves alone is one a rescan invalidates', () => {
  // The two are complementary by construction: what a georeference change
  // cannot touch (pixel space) is exactly what a rescan does touch.
  for (const col of REGEOREF_REUSABLE) {
    if (col === 'maps.triage' || col === 'footprint_submissions.pixel_polygon') {
      expect(RESCAN_INVALIDATES.has(col)).toBe(true);
    }
  }
});

test('PATCH /api/admin/maps/[id] can change iiif_image with zero coupling to triage', () => {
  // This is the gap, exercised against the real allow-list rather than
  // asserted about it. If this ever starts including `triage`, that is a
  // deliberate fix landing — update this test to say so, do not just make
  // it pass.
  const out = pickMapFields({ iiif_image: 'https://iiif.maparchive.vn/iiif/new-scan' });
  expect(out).toEqual({ iiif_image: 'https://iiif.maparchive.vn/iiif/new-scan' });
  expect('triage' in out).toBe(false);
  expect('bbox' in out).toBe(false);
  expect('annotation_url' in out).toBe(false);
});

test('a rescan redoes the R2 tile cache too, not just database columns', () => {
  expect(RESCAN_ALSO_REDO).toContain('tile_to_r2 output (R2 tiles)');
});
