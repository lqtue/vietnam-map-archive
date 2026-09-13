/**
 * check_series_index.mjs — does the survey index still agree with `maps`?
 *
 * `series_sheets` (mig 083) is one row per sheet a survey CONTAINS, held or
 * not, and `held_by` / `map_id` say how the archive reaches each one. Nothing
 * maintains those two columns: there is no trigger and no function, and the
 * only writers in the tree are the one-off importers. So the day anyone
 * publishes a draft or georeferences one of the obtainable sheets, the index
 * still says *gap*, the coverage page still draws it as missing, and the
 * percentage on it is wrong by a plausible amount. There is no other symptom.
 *
 * This is the detector, not the fix. The fix is to derive `held_by` in a view
 * or a trigger (docs/ROADMAP.md, "Open from the survey layer"); until that
 * exists, run this after any publish, georeference or re-import:
 *
 *     node --env-file=.env scripts/check_series_index.mjs
 *     node --env-file=.env scripts/check_series_index.mjs --self-check
 *
 * Read-only. Exits 1 on drift, so it can gate a deploy.
 *
 * ponytail: joins in JS over one paged read of each table, rather than a SQL
 * view we would then have to keep. Fine to ~10k sheets; if a survey lands that
 * makes this slow, that is the moment to write the view and delete this.
 */
import { createClient } from '@supabase/supabase-js';

/** `maps.collection` → `series_sheets.series_key`, as the importers spell it. */
const slug = (s) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

/**
 * The whole check, over plain arrays so it can be exercised without a database.
 * A cell is adrift when the index calls it unheld and a `maps` row claims it;
 * a `map_id` is dangling when the row it points at is gone.
 */
export function findDrift(sheets, maps) {
  const byCell = new Map();
  for (const m of maps) {
    const n = m.extra_metadata?.sheet_number;
    if (n && m.collection) byCell.set(`${slug(m.collection)}|${String(n)}`, m);
  }
  const ids = new Set(maps.map((m) => m.id));
  const drift = [];
  const dangling = [];
  for (const s of sheets) {
    const m = byCell.get(`${s.series_key}|${s.sheet_number}`);
    if (!s.held_by && m) drift.push({ ...s, map: m.name, status: m.status });
    if (s.map_id && !ids.has(s.map_id)) dangling.push(s);
  }
  return { drift, dangling };
}

function selfCheck() {
  const maps = [
    {
      id: 'm1',
      name: 'Sai Gon',
      collection: 'Series L7014 (Vietnam 1:50,000)',
      status: 'public',
      extra_metadata: { sheet_number: '6330-4' },
    },
  ];
  // The failure this exists to catch: someone published 6330-4 and the index
  // never heard about it.
  const stale = [
    {
      series_key: 'series-l7014-vietnam-1-50-000',
      sheet_number: '6330-4',
      held_by: null,
      map_id: null,
    },
  ];
  const { drift } = findDrift(stale, maps);
  if (drift.length !== 1)
    throw new Error(`a published sheet the index calls a gap must be drift, got ${drift.length}`);

  const fixed = [{ ...stale[0], held_by: 'map', map_id: 'm1' }];
  if (findDrift(fixed, maps).drift.length !== 0) throw new Error('a held sheet must not be drift');

  // A cell of the mosaic has no `maps` row at all and is still held.
  const mosaic = [
    {
      series_key: 'series-l7014-vietnam-1-50-000',
      sheet_number: '6026-3',
      held_by: 'raster:l7014',
      map_id: null,
    },
  ];
  if (findDrift(mosaic, []).drift.length !== 0) throw new Error('a mosaic cell must not be drift');

  // A genuine gap stays a gap.
  const gap = [
    {
      series_key: 'series-l7014-vietnam-1-50-000',
      sheet_number: '9999-9',
      held_by: null,
      map_id: null,
    },
  ];
  if (findDrift(gap, maps).drift.length !== 0)
    throw new Error('an unheld sheet with no map must not be drift');

  // And a map_id pointing at nothing is dangling, which no `held_by` hides.
  const orphan = [{ series_key: 'k', sheet_number: '1', held_by: 'map', map_id: 'gone' }];
  if (findDrift(orphan, maps).dangling.length !== 1)
    throw new Error('a map_id with no row must be dangling');

  console.log('self-check ok');
}

async function readAll(db, table, cols) {
  const out = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await db
      .from(table)
      .select(cols)
      .range(from, from + 999);
    if (error) throw new Error(`${table}: ${error.message}`);
    out.push(...data);
    if (data.length < 1000) break;
  }
  return out;
}

async function main() {
  const { PUBLIC_SUPABASE_URL: url, SUPABASE_SERVICE_KEY: key } = process.env;
  if (!url || !key) {
    console.error(
      'Need PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY — run with `node --env-file=.env`.'
    );
    process.exit(2);
  }
  const db = createClient(url, key, { auth: { persistSession: false } });
  const sheets = await readAll(db, 'series_sheets', 'series_key,sheet_number,held_by,map_id');
  const maps = await readAll(db, 'maps', 'id,name,collection,status,extra_metadata');

  for (const k of [...new Set(sheets.map((s) => s.series_key))]) {
    const rows = sheets.filter((s) => s.series_key === k);
    console.log(`${k}: ${rows.filter((r) => r.held_by).length} held / ${rows.length}`);
  }

  const { drift, dangling } = findDrift(sheets, maps);
  for (const d of drift)
    console.log(`DRIFT   ${d.series_key} ${d.sheet_number} -> ${d.map} [${d.status}]`);
  for (const d of dangling)
    console.log(`DANGLING ${d.series_key} ${d.sheet_number} -> ${d.map_id}`);
  console.log(
    `\n${drift.length} adrift, ${dangling.length} dangling, over ${sheets.length} sheets.`
  );
  if (drift.length || dangling.length) {
    console.log('Re-run the survey importer for that series, or mark the cell held by hand.');
    process.exit(1);
  }
}

if (process.argv.includes('--self-check')) selfCheck();
else await main();
