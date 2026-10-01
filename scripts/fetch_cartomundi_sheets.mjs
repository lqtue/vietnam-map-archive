#!/usr/bin/env node
// Make a resumable, reduced snapshot of every sheet record in the Vietnam-
// related CartoMundi series. The API repeats large parent objects per record,
// so keep only the fields needed by the public catalogue.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const index = JSON.parse(
  readFileSync(new URL('../src/lib/data/maps/cartomundiIndex.json', import.meta.url), 'utf8')
);
const output = new URL('../work/cartomundi-rights/feuilles/', import.meta.url);
mkdirSync(output, { recursive: true });
const onlyAt = process.argv.indexOf('--only');
const only = onlyAt < 0 ? null : process.argv[onlyAt + 1];
const pending = index.series.filter(
  (series) => (!only || series.id === only) && !existsSync(new URL(`${series.id}.json`, output))
);

async function fetchSeries(series) {
  const url = `https://www.cartomundi.fr/ctmd-services/serie/${series.id}/feuilles`;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const response = await fetch(url, {
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(600_000),
      });
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const records = await response.json();
      if (!Array.isArray(records)) throw Error('Response is not a sheet array');
      const sheets = records.map((record) => ({
        fkey: record.fkey ?? null,
        number: record.f100NumeroOuCode ?? null,
        title: record.f105Titre ?? null,
        year: record.f103DateAaaa ?? null,
        bbox: record.geometrieEmprise
          ? [
              record.geometrieEmprise.l123dLimiteOuestUnimarc,
              record.geometrieEmprise.l123gLimiteSudUnimarc,
              record.geometrieEmprise.l123eLimiteEstUnimarc,
              record.geometrieEmprise.l123fLimiteNordUnimarc,
            ]
          : null,
      }));
      writeFileSync(
        new URL(`${series.id}.json`, output),
        JSON.stringify(
          { source: url, fetchedAt: new Date().toISOString(), records: sheets },
          null,
          2
        ) + '\n'
      );
      process.stderr.write(`${series.id}: ${sheets.length} sheet records\n`);
      return;
    } catch (error) {
      process.stderr.write(`${series.id} attempt ${attempt}: ${error}\n`);
    }
  }
}

let next = 0;
await Promise.all(
  Array.from({ length: Math.min(3, pending.length) }, async () => {
    while (next < pending.length) await fetchSeries(pending[next++]);
  })
);
const missing = index.series
  .map((series) => series.id)
  .filter((id) => !existsSync(new URL(`${id}.json`, output)));
console.log(`${index.series.length - missing.length}/${index.series.length} series fetched`);
if (missing.length) {
  console.error(`Missing series: ${missing.join(', ')}`);
  process.exitCode = 1;
}
