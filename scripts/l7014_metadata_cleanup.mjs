/** Apply an explicit, reviewed L7014 plan. Bare invocation only reads/checks.
 *
 * node --env-file=.env scripts/l7014_metadata_cleanup.mjs --plan PLAN.json [--apply]
 * Plans carry per-field before/after values and identity invariants. Concurrent
 * edits stop the pass. Every successful correction is written to a local receipt.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';
import { serviceClient } from './lib/db.mjs';
import { opt, willApply } from './lib/cli.mjs';

const path = opt('--plan');
if (!path) throw new Error('--plan is required');
const apply = willApply();
const plan = JSON.parse(readFileSync(path, 'utf8'));
const key = 'series-l7014-vietnam-1-50-000';
if (plan.series_key !== key || !Array.isArray(plan.changes)) throw new Error('Invalid L7014 plan');
const db = serviceClient();
const seen = new Set();
const receipt = {
  plan: path,
  started_at: new Date().toISOString(),
  apply,
  changed: [],
  already_applied: [],
};

// Validate the entire proposal before sending any write.
for (const change of plan.changes) {
  const allowed =
    change.table === 'maps'
      ? ['name', 'year', 'extra_metadata']
      : change.table === 'series_cells'
        ? ['name', 'year']
        : [];
  if (
    !allowed.length ||
    !change.id ||
    change.invariants?.series_key !== key ||
    Object.keys(change.after).some((field) => !allowed.includes(field))
  )
    throw new Error('Unsafe plan fields');
  const identity = `${change.table}:${change.id}`;
  if (seen.has(identity)) throw new Error(`Duplicate proposal ${identity}`);
  seen.add(identity);
  if ('name' in change.after && (!change.after.name || typeof change.after.name !== 'string'))
    throw new Error('Invalid name');
  if (
    'year' in change.after &&
    change.after.year !== null &&
    (!Number.isInteger(change.after.year) || change.after.year < 1850 || change.after.year > 2026)
  )
    throw new Error('Invalid year');
  if (
    change.table === 'maps' &&
    'year' in change.after &&
    change.after.year !== null &&
    !change.evidence.some(
      (e) =>
        e.review_status === 'reviewed' && e.year === change.after.year && e.quote && e.source_sha256
    )
  )
    throw new Error('Year lacks reviewed scan evidence');
}

async function currentRow(change) {
  const { data, error } = await db.from(change.table).select('*').eq('id', change.id).single();
  if (error) throw new Error(`${change.table}/${change.id}: ${error.message}`);
  for (const [field, value] of Object.entries(change.invariants)) {
    if (!isDeepStrictEqual(data[field] ?? null, value ?? null))
      throw new Error(`Identity changed: ${change.id}/${field}`);
  }
  const pending = {};
  for (const [field, value] of Object.entries(change.after)) {
    if (isDeepStrictEqual(data[field], value)) continue;
    if (!isDeepStrictEqual(data[field], change.before[field]))
      throw new Error(`Concurrent metadata edit: ${change.id}/${field}`);
    pending[field] = value;
  }
  return { row: data, pending };
}

// Preflight all records first. Re-read immediately before each guarded update.
for (const change of plan.changes) await currentRow(change);
console.log(JSON.stringify({ ...plan.summary, records: plan.changes.length, apply }));
if (!apply) process.exit(0);
const receiptPath = `${path}.receipt.json`;
for (const change of plan.changes) {
  const { row, pending } = await currentRow(change);
  if (!Object.keys(pending).length) {
    receipt.already_applied.push({ table: change.table, id: change.id });
    continue;
  }
  let query = db.from(change.table).update(pending).eq('id', change.id).eq('series_key', key);
  if (change.table === 'maps') query = query.eq('updated_at', row.updated_at);
  else {
    for (const field of Object.keys(pending)) {
      query = row[field] == null ? query.is(field, null) : query.eq(field, row[field]);
    }
  }
  const { data, error } = await query.select('*').single();
  if (error) throw new Error(`Update stopped at ${change.id}: ${error.message}`);
  for (const [field, value] of Object.entries(change.invariants)) {
    if (!isDeepStrictEqual(data[field] ?? null, value ?? null))
      throw new Error(`Post-update identity changed: ${change.id}/${field}`);
  }
  for (const [field, value] of Object.entries(pending)) {
    if (!isDeepStrictEqual(data[field], value))
      throw new Error(`Write mismatch: ${change.id}/${field}`);
  }
  receipt.changed.push({
    table: change.table,
    id: change.id,
    sheet_number: change.sheet_number,
    fields: Object.keys(pending),
    before: change.before,
    after: change.after,
  });
  writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
}
receipt.finished_at = new Date().toISOString();
writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
console.log(
  JSON.stringify({
    changed: receipt.changed.length,
    already_applied: receipt.already_applied.length,
    receipt: receiptPath,
  })
);
