#!/usr/bin/env node
/**
 * Index the USGS Store's Vietnam NGA sheets as USGS source items.
 * node --env-file=.env scripts/oneoff/import_usgs_holdings.mjs [--apply]
 * Reads work/usgs/vietnam-products.json (checked 2026-10-06). Only L7014 and L909, the two series
 * VMA indexes, become `cell_printings`; the rest (JOG 1501, L7015/L7016, odd sheets) are listed on
 * the institution page from that snapshot. Existing rows are never overwritten: the 18 L909 items
 * from ingest_l909_usgs.mjs carry XMP-read editions that the store listing does not have.
 */
import fs from 'node:fs';
import { serviceClient, upsertChunked, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const snapshot = JSON.parse(fs.readFileSync('work/usgs/vietnam-products.json', 'utf8'));
const L7014 = 'series-l7014-vietnam-1-50-000';
const L909 = 'ams-l909-viet-nam-city-maps-1-12-500';
// The two L909 store items not ingested by ingest_l909_usgs.mjs; the rest map to their own cells.
const L909_CELL = { L909XHONGAY__001: 'Hòn Gai', L909XTHANHPHOHO: 'Sài Gòn' };

const db = serviceClient();
const { data: series, error } = await db.from('series').select('id,key').in('key', [L7014, L909]);
if (error) throw error;
const seriesId = Object.fromEntries(series.map((s) => [s.key, s.id]));

const [cells, existing] = await Promise.all(
  [
    (from, to) => db.from('series_cells').select('series_key,sheet_number').range(from, to),
    (from, to) => db.from('cell_printings').select('institution,source_ref').range(from, to),
  ].map(async (query) => {
    const rows = [];
    for (let from = 0; ; from += 1000) {
      const { data, error: e } = await query(from, from + 999);
      if (e) throw e;
      rows.push(...data);
      if (data.length < 1000) return rows;
    }
  })
);
const cellKeys = new Set(cells.map((c) => `${c.series_key}|${c.sheet_number}`));
const known = new Set(existing.map((r) => `${r.institution}:${r.source_ref}`));

const items = [];
const skipped = [];
for (const p of snapshot.products) {
  let key, sheet;
  if (p.seriesCode === 'L7014') {
    const m = p.code.match(/^L7014(\d{4})(\d)/);
    [key, sheet] = [L7014, `${m[1]}-${m[2]}`];
  } else if (p.seriesCode === 'L909' && L909_CELL[p.code]) {
    [key, sheet] = [L909, L909_CELL[p.code]];
  } else continue;
  if (!cellKeys.has(`${key}|${sheet}`)) {
    skipped.push(`${p.code}: no cell ${sheet}`);
    continue;
  }
  const sourceRef = p.pdf ? p.pdf.split('/').pop() : `product-${p.product}`;
  if (known.has(`USGS:${sourceRef}`)) continue;
  items.push({
    series_id: seriesId[key],
    series_key: key,
    sheet_number: sheet,
    institution: 'USGS',
    source_ref: sourceRef,
    title: p.title,
    year: Number(p.versionDate.slice(-4)) || null,
    edition: null,
    part: null,
    url: p.pdf ?? p.productUrl,
    rights: null,
    note:
      `USGS Store catalogue, checked ${snapshot.checkedAt}: product ${p.product} (${p.productUrl}), ` +
      `version date ${p.versionDate}, scale ${p.scale}, ${p.georeferenced ? 'GeoPDF' : 'scanned PDF without georeference'}. ` +
      `Year is the store's version date, not a reviewed edition year; printing identity unreviewed.`,
  });
}
if (duplicateKeys(items, (i) => i.source_ref).length) throw new Error('duplicate source_ref');
const bySeries = items.reduce(
  (acc, i) => ({ ...acc, [i.series_key]: (acc[i.series_key] ?? 0) + 1 }),
  {}
);
console.log('new USGS source items:', items.length, bySeries);
if (skipped.length) console.log('skipped (no VMA cell):', skipped);
if (!willApply()) {
  dryNotice();
  process.exit(0);
}
await upsertChunked(db, 'cell_printings', items, { onConflict: 'institution,source_ref' });
const { count, error: countError } = await db
  .from('cell_printings')
  .select('id', { count: 'exact', head: true })
  .eq('institution', 'USGS');
if (countError) throw countError;
console.log('read-back: USGS cell_printings =', count);
