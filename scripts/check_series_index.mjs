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
 * Read-only. Exits 1 on drift, on a dangling `map_id`, or on a collection
 * whose key the database cannot produce — so it can gate a deploy.
 *
 * It reported clean over the whole Indochine survey until 2026-09-14, because
 * it spelled `series_key()` itself and skipped the `f_unaccent`. It no longer
 * spells it: `resolveKeys` asks the database. See `findDrift`.
 *
 * ponytail: joins in JS over one paged read of each table, rather than a SQL
 * view we would then have to keep. Fine to ~10k sheets; if a survey lands that
 * makes this slow, that is the moment to write the view and delete this.
 */
import { createClient } from '@supabase/supabase-js';

/**
 * The whole check, over plain arrays so it can be exercised without a database.
 * A cell is adrift when the index calls it unheld and a `maps` row claims it;
 * a `map_id` is dangling when the row it points at is gone.
 *
 * `keyOf` maps a `maps.collection` onto the `series_key` the index files it
 * under. It is passed in rather than computed here because this file spelled
 * that function itself until 2026-09-14 and got it wrong: it lowercased and
 * replaced `[^a-z0-9]+`, while migration 082's `series_key()` runs
 * `f_unaccent` first. So `'Indochine 1:25,000 — Tonkin & Thanh Hóa'` folded to
 * `...thanh-h-a` here and `...thanh-hoa` in the database, no cell of that
 * survey ever matched, and the detector reported clean over 79 sheets it could
 * not see — while that survey was the one being ingested. A wrong key does not
 * error, it finds nothing, which is the same shape as no drift.
 *
 * `unresolved` is the guard against that failing quietly a second time: a
 * collection carrying sheet numbers that `keyOf` cannot place is reported, not
 * skipped. `orphanKeys` is the same fault seen from the index's side — a
 * `series_key` no collection produces, which is what a hand-typed key in an
 * importer looks like.
 */
export function findDrift(sheets, maps, keyOf) {
  const byCell = new Map();
  const unresolved = new Set();
  for (const m of maps) {
    const n = m.extra_metadata?.sheet_number;
    if (!n || !m.collection) continue;
    const key = keyOf(m.collection);
    if (!key) {
      unresolved.add(m.collection);
      continue;
    }
    byCell.set(`${key}|${String(n)}`, m);
  }
  const ids = new Set(maps.map((m) => m.id));
  const drift = [];
  const dangling = [];
  for (const s of sheets) {
    const m = byCell.get(`${s.series_key}|${s.sheet_number}`);
    if (!s.held_by && m) drift.push({ ...s, map: m.name, status: m.status });
    if (s.map_id && !ids.has(s.map_id)) dangling.push(s);
  }
  const known = new Set(
    maps.map((m) => m.collection && keyOf(m.collection)).filter((k) => typeof k === 'string')
  );
  const orphanKeys = [...new Set(sheets.map((s) => s.series_key))].filter((k) => !known.has(k));
  return { drift, dangling, unresolved: [...unresolved], orphanKeys };
}

/**
 * The offline exercise. Two of these cases are the parity check: `keyOf` is
 * the database's answer in production, and the pair below pins that this file
 * works off that answer rather than re-deriving one — the accented collection
 * must match, and a key nothing produces must be shouted about.
 *
 *     node scripts/check_series_index.mjs --self-check
 */
function selfCheck() {
  // The real strings, and the real keys the database returns for them
  // (`select public.series_key(collection)` — verified against production
  // 2026-09-14). `Thanh Hóa` is the whole point: fold it without `unaccent`
  // and you get `thanh-h-a`, which matches no row in the index.
  const KEYS = {
    'Series L7014 (Vietnam 1:50,000)': 'series-l7014-vietnam-1-50-000',
    'Indochine 1:25,000 — Tonkin & Thanh Hóa': 'indochine-1-25-000-tonkin-thanh-hoa',
  };
  const keyOf = (c) => KEYS[c];

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
  const { drift } = findDrift(stale, maps, keyOf);
  if (drift.length !== 1)
    throw new Error(`a published sheet the index calls a gap must be drift, got ${drift.length}`);

  const fixed = [{ ...stale[0], held_by: 'map', map_id: 'm1' }];
  if (findDrift(fixed, maps, keyOf).drift.length !== 0)
    throw new Error('a held sheet must not be drift');

  // A cell of the mosaic has no `maps` row at all and is still held.
  const mosaic = [
    {
      series_key: 'series-l7014-vietnam-1-50-000',
      sheet_number: '6026-3',
      held_by: 'raster:l7014',
      map_id: null,
    },
  ];
  if (findDrift(mosaic, [], keyOf).drift.length !== 0)
    throw new Error('a mosaic cell must not be drift');

  // A genuine gap stays a gap.
  const gap = [
    {
      series_key: 'series-l7014-vietnam-1-50-000',
      sheet_number: '9999-9',
      held_by: null,
      map_id: null,
    },
  ];
  if (findDrift(gap, maps, keyOf).drift.length !== 0)
    throw new Error('an unheld sheet with no map must not be drift');

  // And a map_id pointing at nothing is dangling, which no `held_by` hides.
  const orphan = [{ series_key: 'k', sheet_number: '1', held_by: 'map', map_id: 'gone' }];
  if (findDrift(orphan, maps, keyOf).dangling.length !== 1)
    throw new Error('a map_id with no row must be dangling');

  // ── Parity with the database's own `series_key()` ────────────────────────
  // The bug: this file folded `Thanh Hóa` to `thanh-h-a` while the index was
  // written with `thanh-hoa`, so a published, unindexed sheet of that survey
  // read as no drift at all. It is caught here only because `keyOf` is the
  // database's answer — a local re-spelling would fail the same way twice.
  const accented = [
    {
      id: 'm2',
      name: 'Thanh Hoa',
      collection: 'Indochine 1:25,000 — Tonkin & Thanh Hóa',
      status: 'public',
      extra_metadata: { sheet_number: '71' },
    },
  ];
  const unindexed = [
    {
      series_key: 'indochine-1-25-000-tonkin-thanh-hoa',
      sheet_number: '71',
      held_by: null,
      map_id: null,
    },
  ];
  const accentDrift = findDrift(unindexed, accented, keyOf);
  if (accentDrift.drift.length !== 1)
    throw new Error('a published sheet of an accented collection must be drift, not silence');
  if (accentDrift.unresolved.length !== 0)
    throw new Error('an accented collection the database can key must resolve');

  // A collection `keyOf` cannot place is reported rather than skipped — the
  // silence that hid the fault above is now itself a failure.
  const unknown = [{ ...accented[0], collection: 'A Survey Nobody Imported' }];
  const miss = findDrift(unindexed, unknown, keyOf);
  if (miss.unresolved.length !== 1)
    throw new Error('a collection with sheet numbers and no key must be unresolved');
  if (miss.drift.length !== 0) throw new Error('an unresolvable collection must not claim drift');

  // The same fault from the index's side: a key no collection produces, which
  // is what a hand-typed `SERIES_KEY` in an importer looks like.
  if (findDrift(unindexed, maps, keyOf).orphanKeys.length !== 1)
    throw new Error('a series_key no collection produces must be an orphan key');

  console.log('self-check ok');
}

/**
 * `maps.collection` → `series_key`, answered by the database rather than
 * re-spelled here. `series_key()` (migration 082) is one `f_unaccent` and one
 * regexp; re-implementing two of those three lines in JS is what hid an entire
 * survey from this check for a day. One RPC per distinct collection — four
 * today — and the answer is the same one the index was written with.
 */
async function resolveKeys(db, maps) {
  const collections = [...new Set(maps.map((m) => m.collection).filter(Boolean))];
  const resolved = new Map();
  for (const c of collections) {
    const { data, error } = await db.rpc('series_key', { p_collection: c });
    if (error) throw new Error(`series_key(${c}): ${error.message}`);
    if (data) resolved.set(c, data);
  }
  return (c) => resolved.get(c);
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

  const keyOf = await resolveKeys(db, maps);

  for (const k of [...new Set(sheets.map((s) => s.series_key))]) {
    const rows = sheets.filter((s) => s.series_key === k);
    console.log(`${k}: ${rows.filter((r) => r.held_by).length} held / ${rows.length}`);
  }

  const { drift, dangling, unresolved, orphanKeys } = findDrift(sheets, maps, keyOf);
  for (const d of drift)
    console.log(`DRIFT   ${d.series_key} ${d.sheet_number} -> ${d.map} [${d.status}]`);
  for (const d of dangling)
    console.log(`DANGLING ${d.series_key} ${d.sheet_number} -> ${d.map_id}`);
  for (const c of unresolved) console.log(`UNRESOLVED collection with sheet numbers: ${c}`);
  for (const k of orphanKeys) console.log(`ORPHAN KEY  ${k} — no maps.collection produces it`);
  console.log(
    `\n${drift.length} adrift, ${dangling.length} dangling, over ${sheets.length} sheets.`
  );
  if (drift.length || dangling.length || unresolved.length) {
    console.log('Re-run the survey importer for that series, or mark the cell held by hand.');
    process.exit(1);
  }
}

if (process.argv.includes('--self-check')) selfCheck();
else await main();
