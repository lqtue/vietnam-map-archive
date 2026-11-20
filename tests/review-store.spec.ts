import { expect, test } from '@playwright/test';
import { get } from 'svelte/store';
import { createReviewSession } from '../src/lib/features/review/reviewSession';
import { ReviewApiError, type ReviewApi } from '../src/lib/features/review/reviewApi';
import type { NextReply, ReviewItem, VerdictBody } from '../src/lib/features/review/types';

/**
 * The review page's logic without a page: when the clock starts, what a retry resends, what a
 * stale item does. The wire contract is in tests/write.spec.ts; the arm rules in review-session.spec.ts.
 */

const view = { url: 'x.png', x0: 0, y0: 0, side: 100, out: 100, bar_m: 50 };
const item = (id: string, withProposal = true): ReviewItem => ({
  item_id: id,
  bound: `b-${id}`,
  payload: {
    text: id,
    px: [50, 50],
    lon: 106.7,
    lat: 10.77,
    sheet: { map_id: 'm', m_per_px: 0.34, north_px: [1, 0] },
    views: { close: view, context: view },
  },
  proposal: withProposal
    ? [{ id: 'osm:way/1', name: 'One', source: 'osm', dist_m: 10, px: [10, 10] }]
    : [],
});

function harness(items: ReviewItem[]) {
  let clock = 1_000_000;
  const sent: VerdictBody[] = [];
  let todo = [...items];
  let failNext: ReviewApiError | null = null;
  let ids = 0;
  const api: ReviewApi = {
    next: async (): Promise<NextReply> => ({
      task: { key: 't', title: 'T', question: 'Q?' },
      done: items.length - todo.length,
      total: items.length,
      item: todo[0] ?? null,
    }),
    verdict: async (_task, body) => {
      if (failNext) {
        const e = failNext;
        failNext = null;
        throw e;
      }
      sent.push(body);
      todo = todo.filter((i) => i.item_id !== body.item_id);
      return { ok: true, duplicate: false };
    },
    undo: async () => ({ ok: true, undone: null }),
    search: async () => [],
  };
  const session = createReviewSession('t', {
    api,
    now: () => clock,
    uuid: () => `id-${++ids}`,
    client: () => ({ viewport: '1x1', ua: 'test' }),
  });
  return {
    session,
    sent,
    tick: (ms: number) => (clock += ms),
    failNext: (e: ReviewApiError) => (failNext = e),
    dropFromTodo: (id: string) => (todo = todo.filter((i) => i.item_id !== id)),
  };
}

test('the clock starts when the last view has loaded, not when the item arrives', async () => {
  const h = harness([item('a')]);
  await h.session.load();
  h.tick(4000); // a slow network
  h.session.viewLoaded(2);
  h.tick(1000);
  h.session.viewLoaded(2); // the second view: now it is shown
  h.tick(7000);
  await h.session.send('gone');
  expect(h.sent[0].decided_at - h.sent[0].shown_at).toBe(7000);
  expect(get(h.session).phase).toBe('done');
  expect(get(h.session).medianSeconds).toBe(7);
});

test('a verdict is refused on screen until the views have loaded, and a place is picked when needed', async () => {
  const h = harness([item('a')]);
  await h.session.load();
  await h.session.send('gone');
  expect(get(h.session).message).toMatch(/still loading/);
  h.session.viewLoaded(2);
  h.session.viewLoaded(2);
  await h.session.send('moved');
  expect(get(h.session).message).toMatch(/Pick a place first/);
  expect(h.sent).toHaveLength(0);
  h.session.pickCandidate(1);
  await h.session.send('moved');
  expect(h.sent[0]).toMatchObject({ relation: 'moved', pick: 1, search_id: null });
});

test('time with the tab hidden is counted, including a stretch still open at the send', async () => {
  const h = harness([item('a'), item('b')]);
  await h.session.load();
  h.session.viewLoaded(2);
  h.session.viewLoaded(2);
  h.tick(1000);
  h.session.setHidden(true);
  h.tick(2500);
  h.session.setHidden(false);
  h.tick(500);
  h.session.setHidden(true);
  h.tick(300); // still hidden when the key is pressed
  await h.session.send('gone');
  expect(h.sent[0].hidden_ms).toBe(2800);
});

test('a pick and a search result are never both set', async () => {
  const h = harness([item('a')]);
  await h.session.load();
  h.session.pickCandidate(1);
  h.session.chooseHit({ id: 'osm:way/9', name: 'Nine', source: 'osm', dist_m: 5, wikidata: null });
  expect(get(h.session)).toMatchObject({ pick: null, hit: { id: 'osm:way/9' } });
  h.session.pickCandidate(1);
  expect(get(h.session)).toMatchObject({ pick: 1, hit: null });
  h.session.pickCandidate(1);
  expect(get(h.session).pick).toBeNull();
  h.session.pickCandidate(2); // there is no candidate 2
  expect(get(h.session).pick).toBeNull();
});

test('a failed send keeps the verdict and a retry resends the same client id', async () => {
  const h = harness([item('a')]);
  await h.session.load();
  h.session.viewLoaded(2);
  h.session.viewLoaded(2);
  h.failNext(new ReviewApiError(0, 'No connection.'));
  await h.session.send('gone');
  expect(get(h.session)).toMatchObject({ phase: 'failed', failure: 'No connection.' });
  expect(get(h.session).item).not.toBeNull(); // the item stays; nothing is lost
  await h.session.retry();
  expect(h.sent).toHaveLength(1);
  expect(h.sent[0].client_id).toBe('id-1');
});

test('a stale item is said so and the next one loads; a refusal keeps the item', async () => {
  const h = harness([item('a'), item('b')]);
  await h.session.load();
  h.session.viewLoaded(2);
  h.session.viewLoaded(2);
  h.failNext(new ReviewApiError(409, 'This item changed since it was loaded; not saved.'));
  h.dropFromTodo('a'); // the server has moved on
  await h.session.send('gone');
  expect(get(h.session)).toMatchObject({
    phase: 'ready',
    message: expect.stringMatching(/changed/),
  });
  expect(get(h.session).item?.item_id).toBe('b');

  h.session.viewLoaded(2);
  h.session.viewLoaded(2);
  h.failNext(new ReviewApiError(400, 'No candidates were shown on this item'));
  await h.session.send('gone');
  expect(get(h.session)).toMatchObject({
    phase: 'ready',
    message: expect.stringMatching(/No candidates/),
  });
  expect(get(h.session).item?.item_id).toBe('b');
});

test('a view that fails to load stops the item with Retry, not a silent clock', async () => {
  const h = harness([item('a')]);
  await h.session.load();
  h.session.viewFailed();
  expect(get(h.session)).toMatchObject({
    phase: 'failed',
    failure: expect.stringMatching(/did not load/),
  });
  await h.session.retry();
  expect(get(h.session).phase).toBe('ready');
});
