#!/usr/bin/env node
/**
 * Index the online L909 holdings of institutions other than PCL and USGS.
 * node --env-file=.env scripts/oneoff/import_l909_other_institutions.mjs [--apply]
 * Source: work/l909/other-institutions.json (items with index: true). Adds
 * cell_printings only, onto existing series_cells; a city that has no cell
 * stops the run rather than creating one. Editions, years and rights are what
 * each catalogue asserts, null where it is silent. USGS is refused outright —
 * another import owns it. Re-running adds nothing.
 */
import fs from 'node:fs';
import { serviceClient, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const key = 'ams-l909-viet-nam-city-maps-1-12-500';
const snapshot = JSON.parse(fs.readFileSync('work/l909/other-institutions.json', 'utf8'));
const planned = snapshot.items.filter((item) => item.index);
if (planned.some((item) => ['PCL', 'USGS'].includes(item.institution)))
  throw new Error('PCL and USGS are not this import');

const db = serviceClient();
const { data: series, error: seriesError } = await db
  .from('series')
  .select('id,key')
  .eq('key', key)
  .single();
if (seriesError) throw seriesError;

const items = planned.map((item) => ({
  series_id: series.id,
  series_key: key,
  sheet_number: item.cell,
  institution: item.institution,
  source_ref: item.sourceRef,
  title: item.title,
  year: item.year ?? null,
  edition: item.edition ?? null,
  part: null,
  url: item.url,
  rights: item.rights ?? null,
  note: item.note,
}));
if (duplicateKeys(items, (item) => `${item.institution}:${item.source_ref}`).length)
  throw new Error('Duplicate institution/source_ref in the snapshot');

const [cells, existing] = await Promise.all([
  db.from('series_cells').select('sheet_number').eq('series_id', series.id),
  db.from('cell_printings').select('institution,source_ref').eq('series_id', series.id),
]);
if (cells.error) throw cells.error;
if (existing.error) throw existing.error;
const knownCells = new Set(cells.data.map((cell) => cell.sheet_number));
const missing = items.filter((item) => !knownCells.has(item.sheet_number));
if (missing.length)
  throw new Error(`No series_cells row for: ${missing.map((i) => i.sheet_number).join(', ')}`);
const known = new Set(existing.data.map((item) => `${item.institution}:${item.source_ref}`));
const add = items.filter((item) => !known.has(`${item.institution}:${item.source_ref}`));

console.log(
  JSON.stringify(
    {
      series: key,
      checkedAt: snapshot.checkedAt,
      sourceItems: items.length,
      addItems: add.length,
      plan: add.map(
        (i) =>
          `${i.institution} | ${i.sheet_number} | ${i.edition ?? '-'} | ${i.year ?? '-'} | ${i.source_ref}`
      ),
    },
    null,
    2
  )
);
if (!willApply()) {
  dryNotice('Adds only missing cell_printings rows; no cells, maps or images.');
  process.exit(0);
}
if (add.length) {
  const { error } = await db.from('cell_printings').upsert(add, {
    onConflict: 'institution,source_ref',
    ignoreDuplicates: true,
  });
  if (error) throw error;
}
const { data: back, error: backError } = await db
  .from('cell_printings')
  .select('institution,source_ref,sheet_number,edition,year,url,rights')
  .eq('series_id', series.id)
  .in('institution', [...new Set(items.map((i) => i.institution))]);
if (backError) throw backError;
for (const item of items) {
  const row = back.find(
    (r) => r.institution === item.institution && r.source_ref === item.source_ref
  );
  if (
    !row ||
    row.sheet_number !== item.sheet_number ||
    row.edition !== item.edition ||
    row.year !== item.year ||
    row.url !== item.url ||
    row.rights !== item.rights
  )
    throw new Error(`Read-back mismatch for ${item.institution} ${item.source_ref}`);
}
console.log(`Verified: ${items.length} source items present and matching the snapshot.`);
