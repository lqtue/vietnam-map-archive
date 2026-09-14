/**
 * db.mjs — the service-role client and the two write idioms, once.
 *
 * Twenty-five call sites built this client by hand and eight of them parsed
 * `.env` themselves, splitting on `=` in a way that mangles a value containing
 * one. `node --env-file=.env` has done that job properly since Node 20; this
 * module only reads what it put in `process.env`, and says so when it is empty
 * rather than handing Supabase `undefined` and failing later with a 401.
 */
import { createClient } from '@supabase/supabase-js';

/**
 * @returns {import('@supabase/supabase-js').SupabaseClient}
 */
export function serviceClient() {
  const url = process.env.PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    throw new Error(
      'PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY must be set — run with `node --env-file=.env`'
    );
  }
  return createClient(url, key, { auth: { persistSession: false } });
}

/**
 * Upsert in chunks, reporting progress, stopping on the first error.
 *
 * PostgREST takes the whole array in one statement, so a thousand-row upsert is
 * one timeout away from telling you nothing about which rows landed. Chunked,
 * the log says where it stopped.
 *
 * @param {import('@supabase/supabase-js').SupabaseClient} db
 * @param {string} table
 * @param {Record<string, unknown>[]} rows
 * @param {{ onConflict: string, size?: number, quiet?: boolean }} opts
 *   `onConflict` is the table's item key. Naming it is not optional: without
 *   one, a re-run duplicates instead of correcting.
 */
export async function upsertChunked(db, table, rows, { onConflict, size = 200, quiet = false }) {
  for (let i = 0; i < rows.length; i += size) {
    const { error } = await db.from(table).upsert(rows.slice(i, i + size), { onConflict });
    if (error) throw new Error(`${table} upsert at row ${i}: ${error.message}`);
    if (!quiet) console.log(`  upserted ${Math.min(i + size, rows.length)}/${rows.length}`);
  }
}

/**
 * The item keys that appear more than once.
 *
 * Worth checking before every upsert: a duplicate key makes PostgreSQL reject
 * the whole statement with `ON CONFLICT DO UPDATE command cannot affect row a
 * second time`, and worse, a duplicate that differs only in a field you are not
 * upserting makes the write quietly keep whichever arrived last. Either way the
 * totals still look right.
 *
 * @template T
 * @param {T[]} rows
 * @param {(row: T) => string} keyOf
 * @returns {string[]} the duplicated keys, in first-seen order
 */
export function duplicateKeys(rows, keyOf) {
  const seen = new Set();
  const dups = [];
  for (const r of rows) {
    const k = keyOf(r);
    if (seen.has(k)) dups.push(k);
    else seen.add(k);
  }
  return dups;
}
