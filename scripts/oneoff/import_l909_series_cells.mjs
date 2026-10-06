#!/usr/bin/env node
/**
 * Index PCL's explicitly labelled L909 cities, plus the existing served Sài Gòn.
 * node --env-file=.env scripts/oneoff/import_l909_series_cells.mjs [--apply]
 * Adds catalogue cells/items only; no printing identities, rights, or geographic
 * extents are inferred. The source snapshot is a partial catalogue, not the
 * complete historical survey. Versos are source items of the same city cell.
 */
import fs from 'node:fs';
import { serviceClient, duplicateKeys } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const key = 'ams-l909-viet-nam-city-maps-1-12-500';
const snapshot = JSON.parse(fs.readFileSync('work/l909/pcl-city-maps.json', 'utf8'));
const cityNames = {
  'Bien Hoa': 'Biên Hòa',
  'Can Tho': 'Cần Thơ',
  'Chu Lai and Vicinity': 'Chu Lai',
  'Da Lat [Dalat]': 'Đà Lạt',
  'Da Nang [Tourane]': 'Đà Nẵng',
  'Dong Hoi': 'Đồng Hới',
  'Ha Noi [Hanoi]': 'Hà Nội',
  'Hai Phong': 'Hải Phòng',
  'Hon Gay': 'Hòn Gai',
  Hue: 'Huế',
  'Lac Giao [Ban Me Thuot]': 'Lạc Giao',
  'My Tho': 'Mỹ Tho',
  'Nha Trang': 'Nha Trang',
  'Phu Lang Thuong': 'Phủ Lạng Thương',
  'Quang Ngai': 'Quảng Ngãi',
  'Qui Nhon': 'Quy Nhơn',
  'Tuy Hoa': 'Tuy Hòa',
  'Vinh and Ben Thuy': 'Vinh và Bến Thủy',
  'Vinh Long': 'Vĩnh Long',
};
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
if (maps.some((map) => !map.sheet_number)) throw new Error('A held city has no sheet identifier');
const cells = new Map();
const items = snapshot.items.map((item) => {
  if (!item.catalogueDescription.includes('Series L909')) throw new Error('Unexpected series');
  const city = cityNames[item.title.replace(/ \[verso\]$/, '')];
  if (!city) throw new Error(`Unmapped city: ${item.title}`);
  if (!cells.has(city))
    cells.set(city, {
      series_id: series.id,
      series_key: key,
      sheet_number: city,
      name: city,
      source: 'PCL',
      source_ref: item.url,
      note: `Partial catalogue-backed index. PCL Vietnam catalogue, checked ${snapshot.checkedAt}. Not a complete historical series inventory.`,
    });
  const year = item.catalogueDescription.match(/, ((?:19|20)\d{2}) \(/)?.[1];
  return {
    series_id: series.id,
    series_key: key,
    sheet_number: city,
    institution: 'PCL',
    source_ref: new URL(item.url).pathname.split('/').pop(),
    title: item.title,
    year: year ? Number(year) : null,
    edition: item.catalogueDescription.match(/Edition (.*?), Series L909/)?.[1] ?? null,
    part: null,
    url: item.url,
    rights: null,
    note: `PCL catalogue assertion, checked ${snapshot.checkedAt}: ${item.catalogueDescription} Printing identity and collar details remain unreviewed.`,
  };
});
for (const map of maps) {
  if (!cells.has(map.sheet_number))
    cells.set(map.sheet_number, {
      series_id: series.id,
      series_key: key,
      sheet_number: map.sheet_number,
      name: map.name,
      note: 'Partial catalogue-backed index. Existing served L909 city map; not a complete historical series inventory.',
    });
}
if (
  cells.size !== 20 ||
  items.length !== 21 ||
  duplicateKeys(items, (item) => item.source_ref).length
) {
  throw new Error('Source snapshot differs from the reviewed 20-city / 21-item plan');
}
const [existingCells, existingItems] = await Promise.all([
  db.from('series_cells').select('sheet_number').eq('series_id', series.id),
  db.from('cell_printings').select('institution,source_ref').eq('series_id', series.id),
]);
if (existingCells.error) throw existingCells.error;
if (existingItems.error) throw existingItems.error;
const knownCells = new Set(existingCells.data.map((item) => item.sheet_number));
const knownItems = new Set(
  existingItems.data.map((item) => `${item.institution}:${item.source_ref}`)
);
const newCells = [...cells.values()].filter((cell) => !knownCells.has(cell.sheet_number));
const newItems = items.filter((item) => !knownItems.has(`${item.institution}:${item.source_ref}`));
console.log(
  JSON.stringify(
    {
      series: key,
      indexedCities: cells.size,
      sourceItems: items.length,
      heldCities: maps.map((map) => map.sheet_number),
      addCells: newCells.length,
      addItems: newItems.length,
      scope: snapshot.scope,
    },
    null,
    2
  )
);
if (!willApply()) {
  dryNotice('Adds only missing cells and source items.');
  process.exit(0);
}
// Source items first: a interrupted run never advertises a cell without its source.
if (newItems.length) {
  const { error } = await db.from('cell_printings').upsert(newItems, {
    onConflict: 'institution,source_ref',
    ignoreDuplicates: true,
  });
  if (error) throw error;
}
if (newCells.length) {
  const { error } = await db.from('series_cells').upsert(newCells, {
    onConflict: 'series_id,sheet_number',
    ignoreDuplicates: true,
  });
  if (error) throw error;
}
const { data: coverage, error } = await db
  .from('series_cell_coverage_detail')
  .select('sheet_number,publicly_held,known_source')
  .eq('key', key);
if (error) throw error;
if (
  coverage.length !== 20 ||
  coverage.filter((cell) => cell.publicly_held).length !== 3 ||
  coverage.some((cell) => !cell.publicly_held && !cell.known_source)
) {
  throw new Error('Read-back did not match 20 known cities, 3 served and 17 externally obtainable');
}
console.log(
  'Verified: 20 indexed cities, 3 served, 17 externally obtainable. No full-series denominator claimed.'
);
