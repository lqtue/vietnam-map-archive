import { expect, test } from '@playwright/test';
import { armFor, fnv1a, orderItems } from '../src/lib/server/reviewArms';
import {
  CLOCK_SLACK_MS,
  buildVerdict,
  checkClock,
  parseVerdictBody,
  searchPool,
  type Place,
} from '../src/lib/server/reviewVerdict';

/**
 * Pure checks for the review page's server rules (no database). They pin what the paper's numbers
 * rest on: a blind reviewer never gets a pick they could not see, the arm is the server's, and the
 * verdict has the fields `confirm.py` writes. The routes and the table are in tests/write.spec.ts.
 */

const place = (id: string, name: string, dist_m: number, extra: Partial<Place> = {}): Place => ({
  id,
  name,
  source: 'osm',
  lon: 106.7,
  lat: 10.77,
  dist_m,
  osm: id.replace('osm:', ''),
  ...extra,
});

const proposal = [
  place('osm:way/1', 'Chợ Bến Thành', 140),
  place('osm:way/2', 'Saigon Square', 90),
];
const pool = [
  ...proposal,
  place('osm:way/3', 'Đồng Khởi', 60, { names: ['Đồng Khởi', 'Rue Catinat'] }),
];

const body = (over: Record<string, unknown> = {}) => ({
  item_id: 'a',
  bound: 'b1',
  relation: 'moved',
  pick: 1,
  shown_at: 1_000_000,
  decided_at: 1_009_500,
  client_id: '5b4f1a52-7a0c-4d49-9d3c-0d7c9d7a0001',
  ...over,
});

test('fnv1a is FNV-1a 32 (published test vectors)', () => {
  expect(fnv1a('')).toBe(0x811c9dc5);
  expect(fnv1a('a')).toBe(0xe40c292c);
  expect(fnv1a('foobar')).toBe(0xbf9cf968);
});

test('the arm is a function of seed, reviewer and item, and an item with no proposal is nocand', () => {
  expect(armFor(7, 'u1', 'x', 0.2, true)).toBe(armFor(7, 'u1', 'x', 0.2, true));
  expect(armFor(7, 'u1', 'x', 0.2, false)).toBe('nocand');
  expect(armFor(7, 'u1', 'x', 0, true)).toBe('shown');
  expect(armFor(7, 'u1', 'x', 1, true)).toBe('blind');
});

test('about blind_frac of the items are blind, and each reviewer gets their own set', () => {
  const ids = Array.from({ length: 4000 }, (_, i) => `item-${i}`);
  const blind = (u: string) => ids.filter((id) => armFor(11, u, id, 0.2, true) === 'blind');
  const a = blind('reviewer-a');
  const b = blind('reviewer-b');
  expect(a.length / ids.length).toBeGreaterThan(0.18);
  expect(a.length / ids.length).toBeLessThan(0.22);
  expect(a).not.toEqual(b);
});

test('adding items does not move the relative order of the old ones (the arm never reads the set)', () => {
  const old = Array.from({ length: 50 }, (_, i) => `i${i}`);
  const more = [...old, 'new-1', 'new-2'];
  const o1 = orderItems(3, 'u', old);
  const o2 = orderItems(3, 'u', more).filter((id) => old.includes(id));
  expect(o2).toEqual(o1);
  expect(orderItems(3, 'u', old)).not.toEqual(orderItems(3, 'other', old));
  expect([...orderItems(3, 'u', old)].sort()).toEqual([...old].sort());
});

test('a verdict request is shape-checked, field by field', () => {
  expect(parseVerdictBody(body()).relation).toBe('moved');
  for (const bad of [
    null,
    body({ relation: 'm' }),
    body({ pick: 0 }),
    body({ pick: 1.5 }),
    body({ shown_at: 'now' }),
    body({ client_id: 'not-a-uuid' }),
    body({ note: 'x'.repeat(2001) }),
    body({ hidden_ms: -1 }),
    body({ item_id: '' }),
  ])
    expect(() => parseVerdictBody(bad)).toThrow();
  expect(parseVerdictBody({ ...body(), note: '  hi  ' }).note).toBe('hi');
});

test('the clock check allows a little slack, refuses a wrong order, a far future and a day-long item', () => {
  const now = 2_000_000_000_000;
  expect(() => checkClock(now - 9000, now - 100, now)).not.toThrow();
  expect(() => checkClock(now - 5000, now + CLOCK_SLACK_MS - 1, now)).not.toThrow();
  expect(() => checkClock(now - 5000, now + CLOCK_SLACK_MS + 1, now)).toThrow();
  expect(() => checkClock(now - 100, now - 5000, now)).toThrow();
  expect(() => checkClock(now - 90_000_000, now, now)).toThrow();
});

test('shown arm: a pick becomes the candidate as target, in the offline file shape', () => {
  const { verdicts, proposalShown } = buildVerdict(
    { relation: 'same_site_new_building', pick: 2, search_id: null },
    'shown',
    proposal,
    pool
  );
  expect(proposalShown).toBe(true);
  expect(verdicts).toMatchObject({
    arm: 'shown',
    pick: 2,
    pick_via: 'candidate',
    relation: 'same_site_new_building',
    target: { id: 'way/2', name: 'Saigon Square', source: 'osm', osm_alts: [], tasco_ids: [] },
  });
});

test('blind and no-candidate arms cannot pick a candidate they never saw', () => {
  for (const arm of ['blind', 'nocand'] as const)
    expect(() =>
      buildVerdict({ relation: 'moved', pick: 1, search_id: null }, arm, proposal, pool)
    ).toThrow(/No candidates were shown/);
});

test('search works on every arm, only from the pool, and records how the place was found', () => {
  const { verdicts, proposalShown } = buildVerdict(
    { relation: 'same_building', pick: null, search_id: 'osm:way/3' },
    'blind',
    proposal,
    pool
  );
  expect(proposalShown).toBe(false);
  expect(verdicts).toMatchObject({ arm: 'blind', pick: null, pick_via: 'search' });
  expect(() =>
    buildVerdict({ relation: 'moved', pick: null, search_id: 'osm:nope' }, 'blind', proposal, pool)
  ).toThrow(/pool/);
});

test('relations that name a place need one; gone and unsure do not; none clears a pick', () => {
  expect(() =>
    buildVerdict({ relation: 'moved', pick: null, search_id: null }, 'shown', proposal, pool)
  ).toThrow(/Pick a place/);
  for (const relation of ['gone', 'unsure'] as const)
    expect(
      buildVerdict({ relation, pick: null, search_id: null }, 'nocand', [], pool).verdicts
    ).toMatchObject({ relation, target: null, pick: null, pick_via: null });
  expect(
    buildVerdict({ relation: 'none', pick: 1, search_id: null }, 'shown', proposal, pool).verdicts
  ).toMatchObject({ relation: 'none', target: null, pick: null, pick_via: null });
});

test('pool search: accent-free, any name, nearest first, never ranks the machine candidates', () => {
  expect(searchPool(pool, 'dong khoi').map((h) => h.id)).toEqual(['osm:way/3']);
  expect(searchPool(pool, 'catinat').map((h) => h.id)).toEqual(['osm:way/3']);
  expect(searchPool(pool, '').map((h) => h.id)).toEqual(['osm:way/3', 'osm:way/2', 'osm:way/1']);
  expect(searchPool(pool, 'zzz')).toEqual([]);
  const many = Array.from({ length: 20 }, (_, i) => place(`osm:way/${i}`, `Place ${i}`, i));
  expect(searchPool(many, '')).toHaveLength(8);
});
