/**
 * The review page's logic, as a store: the item, the stamps, the pick and the send.
 *
 * `createReviewSession(task)` is the same shape as `createReviewQueue` in `contribute/review/`:
 * components read it with `$session` and call its methods, and nothing here touches the DOM, so it
 * is tested without a page (tests/review-store.spec.ts).
 *
 * What it keeps honest (docs/plans/review-page-plan.md §2, §6):
 *  - `shown_at` starts when every view of the item has loaded, not when the item arrives, so a slow
 *    network adds no human time. There is no timer on screen and none here (`Date.now()` is read
 *    twice per item).
 *  - Time with the tab hidden is counted into `hidden_ms`, so idle time is known, not cut by guess.
 *  - Send is one key, no confirm step; a wrong verdict is fixed with undo, as offline.
 *  - A failed send stays on screen with Retry and carries the same `client_id`, so a retry whose
 *    first try landed stores nothing twice.
 */

import { writable, type Readable } from 'svelte/store';
import { ReviewApiError, reviewApi, type ReviewApi } from './reviewApi';
import type { Relation, ReviewItem, SearchHit, VerdictBody } from './types';

/** These relations name a place, so a place has to be picked first. */
export const NEEDS_PICK: readonly Relation[] = ['same_building', 'same_site_new_building', 'moved'];

export type Phase = 'loading' | 'ready' | 'saving' | 'failed' | 'done';

export type SessionState = {
  phase: Phase;
  /** Counts loads. The page keys its views on it: a stale 409 can bring back the same item with a
   * new bound, and the `<img>`s must load again so the clock can start. */
  loadId: number;
  /** The task's own title and question, from the task row. */
  title: string;
  question: string;
  item: ReviewItem | null;
  done: number;
  total: number;
  /** 1-based index into `item.proposal`, or null. */
  pick: number | null;
  /** A place chosen from the search, or null. A pick and a hit are never both set. */
  hit: SearchHit | null;
  note: string;
  /** A refusal or a stale notice, shown beside the item. */
  message: string;
  /** A failed load or send, shown with Retry. */
  failure: string;
  /** This sitting's median seconds per item, shown on the all-done screen only. */
  medianSeconds: number | null;
};

export type SessionDeps = {
  api: ReviewApi;
  now: () => number;
  uuid: () => string;
  client: () => VerdictBody['client'];
};

const defaultDeps: SessionDeps = {
  api: reviewApi,
  now: () => Date.now(),
  uuid: () => crypto.randomUUID(),
  client: () => ({
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    ua: navigator.userAgent.slice(0, 200),
  }),
};

const blank = (phase: Phase): SessionState => ({
  phase,
  loadId: 0,
  title: '',
  question: '',
  item: null,
  done: 0,
  total: 0,
  pick: null,
  hit: null,
  note: '',
  message: '',
  failure: '',
  medianSeconds: null,
});

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return Math.round((s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2) * 10) / 10;
}

export function createReviewSession(task: string, deps: Partial<SessionDeps> = {}) {
  const { api, now, uuid, client } = { ...defaultDeps, ...deps };
  const store = writable<SessionState>(blank('loading'));
  let state = blank('loading');
  const set = (patch: Partial<SessionState>) => store.set((state = { ...state, ...patch }));

  // Per-item stamps. Plain variables: nothing on screen reads them.
  let viewsLoaded = 0;
  let shownAt = 0;
  let hiddenMs = 0;
  let hiddenSince = 0;
  let tabHidden = false;
  let pending: VerdictBody | null = null;
  let loads = 0;
  const seconds: number[] = [];

  async function load() {
    set({ phase: 'loading', failure: '' });
    try {
      const next = await api.next(task);
      loads += 1;
      viewsLoaded = 0;
      shownAt = 0;
      hiddenMs = 0;
      hiddenSince = 0;
      pending = null;
      if (!next.item) {
        set({
          ...blank('done'),
          loadId: loads,
          title: next.task.title,
          question: next.task.question,
          done: next.done,
          total: next.total,
          medianSeconds: median(seconds),
        });
        return;
      }
      set({
        ...blank('ready'),
        loadId: loads,
        title: next.task.title,
        question: next.task.question,
        item: next.item,
        done: next.done,
        total: next.total,
        medianSeconds: median(seconds),
      });
    } catch (e) {
      set({ phase: 'failed', failure: e instanceof Error ? e.message : 'Could not load the item' });
    }
  }

  /** Called once per view `<img>` load. The clock starts when the last one has. */
  function viewLoaded(of: number) {
    viewsLoaded += 1;
    if (viewsLoaded === of && shownAt === 0) {
      shownAt = now();
      if (tabHidden) hiddenSince = shownAt;
    }
  }

  function viewFailed() {
    set({ phase: 'failed', failure: 'The sheet crop did not load.' });
  }

  function setHidden(hidden: boolean) {
    tabHidden = hidden;
    if (!shownAt) return;
    if (hidden && !hiddenSince) hiddenSince = now();
    if (!hidden && hiddenSince) {
      hiddenMs += now() - hiddenSince;
      hiddenSince = 0;
    }
  }

  function pickCandidate(k: number) {
    if (state.phase !== 'ready' || !state.item?.proposal[k - 1]) return;
    set({ pick: state.pick === k ? null : k, hit: null, message: '' });
  }

  function chooseHit(hit: SearchHit | null) {
    if (state.phase !== 'ready') return;
    set({ hit, pick: null, message: '' });
  }

  const setNote = (note: string) => set({ note });

  async function submit() {
    if (!pending) return;
    set({ phase: 'saving', failure: '', message: '' });
    try {
      await api.verdict(task, pending);
      seconds.push((pending.decided_at - pending.shown_at) / 1000);
      await load();
    } catch (e) {
      const err = e instanceof ReviewApiError ? e : null;
      if (err && err.status === 409) {
        // The item changed after it was loaded: nothing was saved. Say so and move on.
        pending = null;
        await load();
        set({ message: err.message });
      } else if (err && err.status >= 400 && err.status < 500) {
        pending = null;
        set({ phase: 'ready', message: err.message });
      } else {
        // No connection, or a server error. Keep the verdict; Retry sends the same client_id.
        set({ phase: 'failed', failure: err?.message ?? 'Could not save your verdict' });
      }
    }
  }

  async function send(relation: Relation) {
    const item = state.item;
    if (state.phase !== 'ready' || !item) return;
    if (!shownAt) {
      set({ message: 'The views are still loading.' });
      return;
    }
    if (NEEDS_PICK.includes(relation) && !state.pick && !state.hit) {
      set({ message: 'Pick a place first: 1 2 3, or / to search.' });
      return;
    }
    const decidedAt = now();
    pending = {
      item_id: item.item_id,
      bound: item.bound,
      relation,
      pick: state.pick,
      search_id: state.hit?.id ?? null,
      note: state.note.trim(),
      shown_at: shownAt,
      decided_at: decidedAt,
      hidden_ms: hiddenMs + (hiddenSince ? decidedAt - hiddenSince : 0),
      client_id: uuid(),
      client: client(),
    };
    await submit();
  }

  /** Retry a failed send with the same body, or a failed load. */
  const retry = () => (pending ? submit() : load());

  async function undo() {
    if (state.phase !== 'ready' && state.phase !== 'done') return;
    try {
      const { undone } = await api.undo(task);
      // The undone item comes back at its place in this reviewer's order.
      if (undone) seconds.pop();
      await load();
    } catch (e) {
      set({ message: e instanceof Error ? e.message : 'Could not undo' });
    }
  }

  return {
    subscribe: store.subscribe as Readable<SessionState>['subscribe'],
    load,
    viewLoaded,
    viewFailed,
    setHidden,
    pickCandidate,
    chooseHit,
    setNote,
    send,
    retry,
    undo,
  };
}

export type ReviewSession = ReturnType<typeof createReviewSession>;
