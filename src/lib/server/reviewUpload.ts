/**
 * Shape checks for what `work/review-kit/review_sync.py push` sends to
 * `POST /api/pipeline/review-items`.
 *
 * The worker token is trusted to write items, not to write anything it likes: a wrong shape
 * would reach the page as a broken item, and a bad `blind_frac` or `seed` changes who sees a
 * proposal. Every failure is a 400 (413 for size) naming the field, never a database error.
 * Unknown keys are refused so a typo cannot silently drop a field.
 */

import { error } from '@sveltejs/kit';
import type { Json } from '$lib/data/supabase/types';

export const MAX_ITEMS_PER_CALL = 200;
/** One item's payload + proposal + gold, as JSON. A place-link item with its 300 m pool is ~60 KB. */
export const MAX_ITEM_BYTES = 262_144;
/** The whole request body, as text. */
export const MAX_BODY_BYTES = 8_000_000;

export const TASK_KEY_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
const AUDIENCES = ['staff', 'signed_in'] as const;
const STATUSES = ['draft', 'open', 'closed'] as const;
const INT4 = 2_147_483_647;

export type ReviewTaskInput = {
  key: string;
  title: string;
  question: string;
  question_vi: string | null;
  method: string;
  seed: number;
  blind_frac: number;
  audience: (typeof AUDIENCES)[number];
  status: (typeof STATUSES)[number];
};

export type ReviewItemInput = {
  item_id: string;
  bound: string;
  payload: { [key: string]: Json | undefined };
  proposal: Json;
  gold: Json;
  active: boolean;
};

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);

function noExtraKeys(o: Obj, allowed: readonly string[], where: string) {
  for (const k of Object.keys(o))
    if (!allowed.includes(k)) throw error(400, `${where}: unknown field ${k}`);
}

function text(o: Obj, field: string, min: number, max: number, where: string): string {
  const v = o[field];
  if (typeof v !== 'string' || v.length < min || v.length > max)
    throw error(400, `${where}.${field} must be a string of ${min}-${max} characters`);
  // Postgres rejects \u0000 in text and jsonb; say so here rather than as a 500.
  if (v.includes('\u0000')) throw error(400, `${where}.${field} must not contain a null byte`);
  return v;
}

function jsonOrNull(o: Obj, field: string, where: string): Json {
  const v = o[field];
  if (v === undefined || v === null) return null;
  if (!isObj(v) && !Array.isArray(v))
    throw error(400, `${where}.${field} must be an object, an array or null`);
  return v as Json;
}

export function parseTask(raw: unknown): ReviewTaskInput {
  if (!isObj(raw)) throw error(400, 'task must be an object');
  noExtraKeys(
    raw,
    [
      'key',
      'title',
      'question',
      'question_vi',
      'method',
      'seed',
      'blind_frac',
      'audience',
      'status',
    ],
    'task'
  );
  const key = text(raw, 'key', 1, 64, 'task');
  if (!TASK_KEY_RE.test(key))
    throw error(400, 'task.key must be lower-case letters, digits and hyphens');
  const seed = raw.seed;
  if (typeof seed !== 'number' || !Number.isInteger(seed) || Math.abs(seed) > INT4)
    throw error(400, 'task.seed must be a 32-bit integer');
  const blind = raw.blind_frac ?? 0.2;
  if (typeof blind !== 'number' || !(blind >= 0 && blind <= 1))
    throw error(400, 'task.blind_frac must be a number from 0 to 1');
  const audience = raw.audience ?? 'staff';
  if (!AUDIENCES.includes(audience as never))
    throw error(400, 'task.audience must be staff or signed_in');
  const status = raw.status ?? 'draft';
  if (!STATUSES.includes(status as never))
    throw error(400, 'task.status must be draft, open or closed');
  return {
    key,
    title: text(raw, 'title', 1, 200, 'task'),
    question: text(raw, 'question', 1, 500, 'task'),
    question_vi: raw.question_vi == null ? null : text(raw, 'question_vi', 1, 500, 'task'),
    method: text(raw, 'method', 1, 200, 'task'),
    seed,
    blind_frac: blind,
    audience: audience as ReviewTaskInput['audience'],
    status: status as ReviewTaskInput['status'],
  };
}

export function parseItems(raw: unknown): ReviewItemInput[] {
  if (!Array.isArray(raw) || raw.length === 0) throw error(400, 'items must be a non-empty array');
  if (raw.length > MAX_ITEMS_PER_CALL)
    throw error(413, `At most ${MAX_ITEMS_PER_CALL} items per request`);
  const seen = new Set<string>();
  return raw.map((r, i) => {
    const where = `items[${i}]`;
    if (!isObj(r)) throw error(400, `${where} must be an object`);
    noExtraKeys(r, ['item_id', 'bound', 'payload', 'proposal', 'gold', 'active'], where);
    const item_id = text(r, 'item_id', 1, 200, where);
    if (seen.has(item_id)) throw error(400, `${where}.item_id ${item_id} appears twice`);
    seen.add(item_id);
    if (!isObj(r.payload)) throw error(400, `${where}.payload must be an object`);
    if (r.active !== undefined && typeof r.active !== 'boolean')
      throw error(400, `${where}.active must be true or false`);
    const item: ReviewItemInput = {
      item_id,
      bound: text(r, 'bound', 1, 128, where),
      payload: r.payload as ReviewItemInput['payload'],
      proposal: jsonOrNull(r, 'proposal', where),
      gold: jsonOrNull(r, 'gold', where),
      active: r.active ?? true,
    };
    const size = JSON.stringify([item.payload, item.proposal, item.gold]).length;
    if (size > MAX_ITEM_BYTES)
      throw error(413, `${where} is ${size} bytes; at most ${MAX_ITEM_BYTES} per item`);
    if (JSON.stringify(item).includes('\\u0000'))
      throw error(400, `${where} must not contain a null byte`);
    return item;
  });
}

/** Body of POST /api/pipeline/review-items: `{ task, items }`. */
export function parseUpload(body: unknown): { task: ReviewTaskInput; items: ReviewItemInput[] } {
  if (!isObj(body)) throw error(400, 'Body must be a JSON object');
  noExtraKeys(body, ['task', 'items'], 'body');
  return { task: parseTask(body.task), items: parseItems(body.items) };
}
