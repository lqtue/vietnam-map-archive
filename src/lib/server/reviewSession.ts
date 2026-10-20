/**
 * The review page's server side: which item is next, a verdict, an undo, a search.
 *
 * Every read of `review_tasks` and `review_items` goes through here with the service role, because
 * `proposal` must never reach a client on the blind arm (migration 122; plan §2.3). A reviewer sees
 * only their own events: arm and order come from `reviewArms.ts`, "done" is this reviewer's last
 * live event per item, and nobody sees what others decided (it would make the checks echo).
 *
 * Handlers in `src/routes/api/review/**` are thin: gate the role, call one of these, return json.
 */

import { error } from '@sveltejs/kit';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database, Json } from '$lib/data/supabase/types';
import { dbError } from './http';
import { armFor, orderItems } from './reviewArms';
import {
  buildVerdict,
  checkClock,
  searchPool,
  type Place,
  type VerdictBody,
} from './reviewVerdict';

type Client = SupabaseClient<Database>;
type Task = Database['public']['Tables']['review_tasks']['Row'];

/** ponytail: one read of a reviewer's events, no paging. A task is tens to hundreds of items; page
 * by id (as the export does) if a task ever has more than this many events per reviewer. */
const MAX_EVENTS = 5000;

const asPlaces = (v: Json | null | undefined): Place[] => (Array.isArray(v) ? (v as Place[]) : []);

/** The task a reviewer may answer: it must exist, be open, and be for staff (v1). */
export async function openTask(sb: Client, key: string): Promise<Task> {
  const { data, error: err } = await sb
    .from('review_tasks')
    .select('*')
    .eq('key', key)
    .maybeSingle();
  if (err) dbError(err, 'Could not read the task');
  if (!data || data.status !== 'open') throw error(404, 'No such open task');
  // ponytail: staff only until the contributor work (plan §2 v2: rate limit, first-run guide).
  if (data.audience !== 'staff') throw error(403, 'This task is not open to you yet');
  return data;
}

type LiveEvent = {
  id: number;
  item_id: string;
  bound: string;
  order_idx: number;
  proposal_shown: boolean;
  undone: boolean;
};

/** This reviewer's events for a task, oldest first, reduced to the last event per item. */
async function reviewerState(sb: Client, task: string, reviewer: string) {
  const { data, error: err } = await sb
    .from('review_events')
    .select('id, item_id, bound, order_idx, proposal_shown, verdicts')
    .eq('task', task)
    .eq('reviewer', reviewer)
    .order('id', { ascending: true })
    .limit(MAX_EVENTS);
  if (err) dbError(err, 'Could not read your verdicts');
  const last = new Map<string, LiveEvent>();
  for (const e of data ?? []) {
    const v = e.verdicts as { undone?: boolean };
    last.set(e.item_id, {
      id: e.id,
      item_id: e.item_id,
      bound: e.bound,
      order_idx: e.order_idx,
      proposal_shown: e.proposal_shown,
      undone: v?.undone === true,
    });
  }
  const live = new Map([...last].filter(([, e]) => !e.undone));
  return { live };
}

/** Active item ids, and which of them carry a proposal (the others can never be blind). */
async function itemIndex(sb: Client, task: string) {
  const all = await sb.from('review_items').select('item_id').eq('task', task).eq('active', true);
  if (all.error) dbError(all.error, 'Could not read the items');
  // The upload stores no candidates as SQL NULL (`it["cands"] or None`), so not-null is "has some".
  const withProposal = await sb
    .from('review_items')
    .select('item_id')
    .eq('task', task)
    .eq('active', true)
    .not('proposal', 'is', null);
  if (withProposal.error) dbError(withProposal.error, 'Could not read the items');
  const hasProposal = new Set((withProposal.data ?? []).map((r) => r.item_id));
  return { ids: (all.data ?? []).map((r) => r.item_id), hasProposal };
}

/**
 * The next item for this reviewer: the first in their order with no live verdict. The proposal is
 * sent only on their shown arm, and `pool` (what search reads) never. The reviewer is not told
 * which arm they are on: blind and no-candidate look the same.
 */
export async function nextItem(sb: Client, task: Task, reviewer: string) {
  const [{ ids, hasProposal }, { live }] = await Promise.all([
    itemIndex(sb, task.key),
    reviewerState(sb, task.key, reviewer),
  ]);
  const doneCount = ids.filter((id) => live.has(id)).length;
  const next = orderItems(task.seed, reviewer, ids).find((id) => !live.has(id));
  if (!next) return { done: doneCount, total: ids.length, item: null };

  const { data, error: err } = await sb
    .from('review_items')
    .select('item_id, bound, payload, proposal')
    .eq('task', task.key)
    .eq('item_id', next)
    .single();
  if (err) dbError(err, 'Could not read the item');
  const arm = armFor(task.seed, reviewer, next, task.blind_frac, hasProposal.has(next));
  const { pool: _pool, ...payload } = data.payload as { pool?: unknown };
  return {
    done: doneCount,
    total: ids.length,
    item: {
      item_id: data.item_id,
      bound: data.bound,
      payload,
      proposal: arm === 'shown' ? asPlaces(data.proposal) : [],
    },
  };
}

/** The pool search for one item, by name. Any arm; nearest first; never ranks the machine's picks. */
export async function searchItem(sb: Client, task: string, itemId: string, q: string) {
  const { data, error: err } = await sb
    .from('review_items')
    .select('payload')
    .eq('task', task)
    .eq('item_id', itemId)
    .eq('active', true)
    .maybeSingle();
  if (err) dbError(err, 'Could not read the item');
  if (!data) throw error(404, 'No such item');
  return searchPool(asPlaces((data.payload as { pool?: Json }).pool), q);
}

/** Store one verdict. 409 when the item changed since the page loaded it; a resend is a no-op. */
export async function saveVerdict(sb: Client, task: Task, reviewer: string, body: VerdictBody) {
  checkClock(body.shown_at, body.decided_at, Date.now());

  const { data: item, error: itemErr } = await sb
    .from('review_items')
    .select('item_id, bound, payload, proposal, active')
    .eq('task', task.key)
    .eq('item_id', body.item_id)
    .maybeSingle();
  if (itemErr) dbError(itemErr, 'Could not read the item');
  if (!item) throw error(404, 'No such item');
  if (!item.active || item.bound !== body.bound)
    throw error(409, 'This item changed since it was loaded; your verdict was not saved.');

  const proposal = asPlaces(item.proposal);
  // Same test as `itemIndex`: an item has a proposal when its column is not NULL.
  const arm = armFor(task.seed, reviewer, item.item_id, task.blind_frac, item.proposal !== null);
  const pool = asPlaces((item.payload as { pool?: Json }).pool);
  const { verdicts, proposalShown } = buildVerdict(body, arm, proposal, pool);

  const { live } = await reviewerState(sb, task.key, reviewer);
  const { error: insErr } = await sb.from('review_events').insert({
    task: task.key,
    item_id: item.item_id,
    bound: item.bound,
    reviewer,
    order_idx: live.size,
    shown_at: new Date(body.shown_at).toISOString(),
    decided_at: new Date(body.decided_at).toISOString(),
    proposal_shown: proposalShown,
    verdicts,
    readings: { hidden_ms: body.hidden_ms },
    note: body.note,
    client: body.client as Json,
    client_id: body.client_id,
  });
  if (insErr?.code === '23505') {
    // The same client_id again: a retry whose first try landed. Nothing is stored twice.
    const { data: prior } = await sb
      .from('review_events')
      .select('reviewer')
      .eq('client_id', body.client_id)
      .maybeSingle();
    if (prior?.reviewer === reviewer) return { ok: true, duplicate: true };
    throw error(409, 'That request id was already used');
  }
  if (insErr) dbError(insErr, 'Could not save your verdict');
  return { ok: true, duplicate: false };
}

/**
 * Append an undo for this reviewer's last live verdict (`{"undone": true}`, as offline). The item
 * comes back at its place in their order. Returns null when there is nothing to undo.
 */
export async function undoLast(sb: Client, task: Task, reviewer: string) {
  const { live } = await reviewerState(sb, task.key, reviewer);
  const last = [...live.values()].sort((a, b) => b.id - a.id)[0];
  if (!last) return { ok: true, undone: null };
  const now = new Date().toISOString();
  const { error: err } = await sb.from('review_events').insert({
    task: task.key,
    item_id: last.item_id,
    bound: last.bound,
    reviewer,
    order_idx: last.order_idx,
    shown_at: now,
    decided_at: now,
    proposal_shown: last.proposal_shown,
    verdicts: { undone: true },
    readings: {},
    note: '',
  });
  if (err) dbError(err, 'Could not undo');
  return { ok: true, undone: last.item_id };
}

/** For `/review`: every open staff task, with how many items this reviewer has left. */
export async function listTasks(sb: Client, reviewer: string) {
  const { data, error: err } = await sb
    .from('review_tasks')
    .select('key, title, question, question_vi')
    .eq('status', 'open')
    .eq('audience', 'staff')
    .order('created_at', { ascending: true });
  if (err) dbError(err, 'Could not read the tasks');
  return Promise.all(
    (data ?? []).map(async (t) => {
      const [{ ids }, { live }] = await Promise.all([
        itemIndex(sb, t.key),
        reviewerState(sb, t.key, reviewer),
      ]);
      const done = ids.filter((id) => live.has(id)).length;
      return { ...t, total: ids.length, done };
    })
  );
}
