#!/usr/bin/env node
// Audit the rights stated by Nakala for CartoMundi scans already identified by VMA.
// This reads public metadata only. Run with --check to fetch missing DOIs or
// --refresh to recheck every DOI. A failed new request stays unknown.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const root = new URL('../', import.meta.url);
const out = new URL('../work/research/cartomundi-rights/', import.meta.url);
mkdirSync(out, { recursive: true });
const read = (path) => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const doiFrom = (value) => String(value || '').match(/10\.34847\/nkl\.[a-z0-9]+/i)?.[0] || null;
const records = new Map();

function add(row) {
  const old = records.get(row.doi);
  if (!old) records.set(row.doi, row);
  else old.catalogue_records.push(...row.catalogue_records);
}

for (const path of [
  'work/tonkin/sources/nakala.json',
  'work/tonkin/sources/nakala-originals.json',
  'work/tonkin/sources/nakala-an-thi.json',
]) {
  const source = read(path);
  for (const [cell, sheets] of Object.entries(source.cells)) {
    for (const sheet of sheets) {
      const doi = doiFrom(sheet.nakala || sheet.iiif);
      if (!doi) continue;
      add({
        doi,
        series: String(sheet.serie || 243),
        sheet: cell,
        title: sheet.title || '',
        year: sheet.year || '',
        catalogue_records: [`${path}#${sheet.fkey || cell}`],
      });
    }
  }
}

for (const series of [325, 561]) {
  const path = `work/indochine-100k/sources/serie-${series}.json`;
  const source = read(path);
  for (const [cell, sheets] of Object.entries(source.cells)) {
    for (const sheet of sheets) {
      for (const asset of sheet.assets || []) {
        const doi = doiFrom(asset.nakala_value);
        if (!doi) continue;
        add({
          doi,
          series: String(series),
          sheet: `${cell}${sheet.part ? ` ${sheet.part}` : ''}`,
          title: sheet.title || '',
          year: sheet.year || '',
          catalogue_records: [`${path}#${sheet.fkey || cell}/${asset.dpKey || ''}`],
        });
      }
    }
  }
}

const cachePath = new URL('nakala-metadata.json', out);
const cache = existsSync(cachePath) ? JSON.parse(readFileSync(cachePath, 'utf8')) : {};
const refresh = process.argv.includes('--refresh');
const check = refresh || process.argv.includes('--check');
const missing = [...records.keys()].filter((doi) => refresh || !cache[doi]);

async function fetchOne(doi) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await fetch(`https://api.nakala.fr/datas/${doi}`, {
        signal: AbortSignal.timeout(20000),
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const item = await response.json();
      const values = (key) =>
        (item.metas || [])
          .filter((meta) => meta.propertyUri === `http://nakala.fr/terms#${key}`)
          .map((meta) => meta.value)
          .filter(Boolean);
      return {
        license: values('license').join('; '),
        title: values('title').join('; '),
        status: item.status || '',
        file_count: item.files?.length || 0,
        depositor: item.depositor?.name || '',
        checked_at: new Date().toISOString(),
      };
    } catch (error) {
      if (attempt === 1) return { error: String(error), checked_at: new Date().toISOString() };
    }
  }
}

if (check) {
  // Keep modest concurrency; Nakala is a shared public service.
  let next = 0;
  let done = 0;
  await Promise.all(
    Array.from({ length: 4 }, async () => {
      while (next < missing.length) {
        const doi = missing[next++];
        const result = await fetchOne(doi);
        if (!result.error) cache[doi] = result;
        done++;
        if (done % 25 === 0 || done === missing.length) {
          writeFileSync(cachePath, JSON.stringify(cache, null, 2) + '\n');
          process.stderr.write(`Checked ${done}/${missing.length} remaining DOIs\n`);
        }
      }
    })
  );
}

const csv = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
const columns = [
  'series',
  'sheet',
  'title',
  'year',
  'doi',
  'posted_license',
  'nakala_status',
  'file_count',
  'depositor',
  'checked_at',
  'source_records',
];
const rows = [...records.values()].sort(
  (a, b) =>
    Number(a.series) - Number(b.series) ||
    a.sheet.localeCompare(b.sheet) ||
    a.doi.localeCompare(b.doi)
);
const lines = [columns.map(csv).join(',')];
for (const row of rows) {
  const rights = cache[row.doi] || {};
  lines.push(
    [
      row.series,
      row.sheet,
      row.title,
      row.year,
      row.doi,
      rights.license || '',
      rights.status || '',
      rights.file_count ?? '',
      rights.depositor || '',
      rights.checked_at || '',
      row.catalogue_records.join('; '),
    ]
      .map(csv)
      .join(',')
  );
}
writeFileSync(new URL('sheets.csv', out), lines.join('\n') + '\n');
const byLicense = {};
for (const row of rows) {
  const license = cache[row.doi]?.license || 'unchecked';
  byLicense[license] = (byLicense[license] || 0) + 1;
}
writeFileSync(
  new URL('summary.json', out),
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      scope: 'Nakala-linked CartoMundi scans in VMA local Tonkin and Indochine source files',
      total_unique_dois: rows.length,
      series_counts: Object.fromEntries(
        [175, 243, 325, 561].map((series) => [
          series,
          rows.filter((row) => row.series === String(series)).length,
        ])
      ),
      posted_licenses: byLicense,
      note: 'A posted license is not proof that the depositor controlled every right in a scan or underlying map.',
    },
    null,
    2
  ) + '\n'
);
console.log(`${rows.length} unique Nakala DOIs; ${JSON.stringify(byLicense)}`);

if (process.argv.includes('--series-from-db')) {
  const { serviceClient } = await import('./lib/db.mjs');
  const db = serviceClient();
  const { data, error } = await db
    .from('scout_candidates')
    .select('external_id,title,date,holding_institution,raw,source_url')
    .eq('source', 'cartomundi')
    .order('external_id');
  if (error) throw error;
  const seriesColumns = [
    'series',
    'title',
    'zone',
    'scope',
    'scale',
    'catalogued_sheets',
    'linked_dois_in_local_sources',
    'rights_evidence',
    'holding_institution',
    'date',
    'cartomundi_url',
  ];
  const seriesLines = [seriesColumns.map(csv).join(',')];
  for (const item of data || []) {
    const id = item.external_id.replace('serie/', '');
    const zone = item.raw?.zone || '';
    const label = `${zone} ${item.title}`;
    const scope = /^(Laos|Cambodge)/i.test(zone)
      ? 'outside Vietnam by series label'
      : /Tonkin|Annam|Cochinchine|Viet|Hanoi|Saigon/i.test(label)
        ? 'Vietnam named'
        : 'Indochina; Vietnam coverage needs checking';
    const linked = rows.filter((row) => row.series === id);
    const checked = linked.filter((row) => Boolean(cache[row.doi]?.license)).length;
    seriesLines.push(
      [
        id,
        item.title,
        zone,
        scope,
        item.raw?.scale || '',
        item.raw?.sheets || '',
        linked.length,
        linked.length
          ? `${checked}/${linked.length} linked items checked`
          : 'no linked items in local sources',
        item.holding_institution || '',
        item.date || '',
        item.source_url || '',
      ]
        .map(csv)
        .join(',')
    );
  }
  writeFileSync(new URL('series.csv', out), seriesLines.join('\n') + '\n');
  const webSeries = (data || [])
    .filter((item) => !/^(Laos|Cambodge)/i.test(item.raw?.zone || ''))
    .map((item) => {
      const id = item.external_id.replace('serie/', '');
      const zone = item.raw?.zone || '';
      return {
        id,
        title: item.title,
        zone,
        scope: /Tonkin|Annam|Cochinchine|Viet|Hanoi|Saigon/i.test(`${zone} ${item.title}`)
          ? 'Vietnam named'
          : 'Indochina; Vietnam coverage needs checking',
        scale: item.raw?.scale || null,
        cataloguedSheets: item.raw?.sheets || 0,
        checkedItems: rows.filter((row) => row.series === id && cache[row.doi]?.license).length,
        holdingInstitution: item.holding_institution || '',
        date: item.date || '',
        url: item.source_url || '',
      };
    })
    .sort((a, b) => Number(a.id) - Number(b.id));
  const webItems = rows.map((row) => ({
    seriesId: row.series,
    sheet: row.sheet,
    title: row.title,
    year: row.year,
    doi: row.doi,
    fkey: row.catalogue_records[0]?.match(/#(\d+)/)?.[1] || null,
    license: cache[row.doi]?.license || null,
    checkedAt: cache[row.doi]?.checked_at || null,
  }));
  const webSheets = webSeries.flatMap((series) => {
    const path = new URL(`${series.id}.json`, new URL('feuilles/', out));
    if (!existsSync(path)) return [];
    const source = JSON.parse(readFileSync(path, 'utf8'));
    return source.records.map((sheet) => ({ seriesId: series.id, ...sheet }));
  });
  const missingSheetIds = webSeries
    .filter((series) => !existsSync(new URL(`${series.id}.json`, new URL('feuilles/', out))))
    .map((series) => series.id);
  if (process.argv.includes('--require-sheets') && missingSheetIds.length) {
    throw Error(`CartoMundi sheet lists missing for series ${missingSheetIds.join(', ')}`);
  }
  for (const series of webSeries) {
    series.indexedRecords = webSheets.filter((sheet) => sheet.seriesId === series.id).length;
  }
  const webPath = new URL('../src/lib/data/maps/cartomundiIndex.json', import.meta.url);
  writeFileSync(
    webPath,
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        summary: {
          seriesCount: webSeries.length,
          sheetRecords: webSheets.length,
          checkedItems: webItems.filter((item) => item.license).length,
          license: Object.keys(byLicense).length === 1 ? Object.keys(byLicense)[0] : 'Mixed',
          checkedAt:
            webItems
              .map((item) => item.checkedAt)
              .filter(Boolean)
              .sort()
              .at(-1) || null,
        },
        series: webSeries,
        sheets: webSheets,
        items: webItems,
      },
      null,
      2
    ) + '\n'
  );
  console.log(`${data?.length || 0} CartoMundi scout series indexed`);
}
