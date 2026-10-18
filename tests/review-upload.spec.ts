import { expect, test } from '@playwright/test';
import { MAX_ITEMS_PER_CALL, parseUpload } from '../src/lib/server/reviewUpload';

/**
 * The shape checks on what the offline pipeline pushes into review_items. A wrong value here does
 * not look like an error later: a blind_frac of 20 shows nobody a proposal, and an extra key a typo
 * dropped silently is an item that arrives without its candidates.
 */

const task = {
  key: 'place-link',
  title: 'Place links',
  question: 'What is this?',
  method: 'm@1',
  seed: 7,
};
const item = { item_id: 'a', bound: 'b1', payload: { text: 'MARCHÉ' } };
const status = (fn: () => unknown) => {
  try {
    fn();
  } catch (e) {
    return (e as { status?: number }).status;
  }
  return 200;
};

test('a minimal upload gets the defaults the table has', () => {
  const { task: t, items } = parseUpload({ task, items: [item] });
  expect(t).toMatchObject({
    blind_frac: 0.2,
    audience: 'staff',
    status: 'draft',
    question_vi: null,
  });
  expect(items[0]).toMatchObject({ active: true, proposal: null, gold: null });
});

test('bad shapes are 400, naming nothing the database would', () => {
  const bad = (t: object, i: object[] = [item]) =>
    status(() => parseUpload({ task: { ...task, ...t }, items: i }));
  expect(bad({ key: 'Place Link' })).toBe(400);
  expect(bad({ seed: 1.5 })).toBe(400);
  expect(bad({ seed: 2 ** 31 })).toBe(400);
  expect(bad({ blind_frac: 20 })).toBe(400);
  expect(bad({ audience: 'everyone' })).toBe(400);
  expect(bad({ status: 'live' })).toBe(400);
  expect(bad({ title: '' })).toBe(400);
  expect(bad({ blind: 0.2 })).toBe(400); // unknown key: a typo must not drop a field
  expect(bad({}, [])).toBe(400);
  expect(bad({}, [{ ...item, payload: [] }])).toBe(400);
  expect(bad({}, [{ ...item, proposal: 'x' }])).toBe(400);
  expect(bad({}, [{ ...item, active: 'yes' }])).toBe(400);
  expect(bad({}, [item, item])).toBe(400);
  expect(bad({}, [{ ...item, item_id: 'a\u0000b' }])).toBe(400);
  expect(status(() => parseUpload('x'))).toBe(400);
});

test('size limits are 413', () => {
  const many = Array.from({ length: MAX_ITEMS_PER_CALL + 1 }, (_, i) => ({
    ...item,
    item_id: String(i),
  }));
  expect(status(() => parseUpload({ task, items: many }))).toBe(413);
  const fat = { ...item, payload: { pool: 'x'.repeat(300_000) } };
  expect(status(() => parseUpload({ task, items: [fat] }))).toBe(413);
});
