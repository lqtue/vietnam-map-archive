#!/usr/bin/env node
/**
 * Index the 1971 South Vietnam provincial maps: one series cell per held sheet.
 * node --env-file=.env scripts/oneoff/import_1971_series_cells.mjs [--apply]
 * Until this ran, /catalog/series/south-vietnam-provincial-maps-1971 was a 404
 * ("That series has no index"): the page lists series_cells, and the 44 maps had none.
 * Cells only. No bbox (a georeference is not a survey cell), no source (the atlas is a
 * private copy, no catalogue lists it), no printing identity. Whether the atlas had
 * sheets beyond 01-44 is not established, so the index is partial
 * (`src/lib/core/seriesIndexScope.ts`). Read-back: every cell publicly held.
 */
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const key = 'south-vietnam-provincial-maps-1971';
const db = serviceClient();
const { data: series, error: seriesError } = await db
  .from('series')
  .select('id,key')
  .eq('key', key)
  .single();
if (seriesError) throw seriesError;
const { data: maps, error: mapError } = await db
  .from('maps')
  .select('id,name,sheet_number,status')
  .eq('series_id', series.id)
  .neq('status', 'archived');
if (mapError) throw mapError;
const want = Array.from({ length: 44 }, (_, i) => String(i + 1).padStart(2, '0'));
const have = maps.map((m) => m.sheet_number).sort();
if (have.join() !== want.join()) {
  throw new Error(`Held sheets are not exactly 01-44: ${have.join(' ')}`);
}
const cells = maps.map((m) => ({
  series_id: series.id,
  series_key: key,
  sheet_number: m.sheet_number,
  name: m.name,
  note: 'Index of the sheets scanned from one private copy; sheets are numbered 01-44 with no gap. Whether the atlas had other sheets is not established.',
}));
const { data: existing, error: existingError } = await db
  .from('series_cells')
  .select('sheet_number')
  .eq('series_id', series.id);
if (existingError) throw existingError;
const known = new Set(existing.map((c) => c.sheet_number));
const add = cells.filter((c) => !known.has(c.sheet_number));
console.log(
  JSON.stringify({ series: key, held: maps.length, existing: known.size, add: add.length })
);
if (!willApply()) {
  dryNotice('Adds only missing cells.');
  process.exit(0);
}
if (add.length) {
  const { error } = await db
    .from('series_cells')
    .upsert(add, { onConflict: 'series_id,sheet_number', ignoreDuplicates: true });
  if (error) throw error;
}
const { data: coverage, error } = await db
  .from('series_cell_coverage_detail')
  .select('sheet_number,publicly_held')
  .eq('key', key);
if (error) throw error;
if (coverage.length !== 44 || coverage.some((c) => !c.publicly_held)) {
  throw new Error(
    `Read-back: ${coverage.length} cells, ${coverage.filter((c) => c.publicly_held).length} publicly held; expected 44 / 44`
  );
}
console.log('Verified: 44 indexed cells, all publicly held. No full-series denominator claimed.');
