import { expect, test } from '@playwright/test';
import { dispatchKey, keys, matches, parseBinding } from '../src/lib/core/utils/keys';

/** Pure checks for `use:keys`. No browser, no network: events are plain objects. */

type Ev = { key: string; [field: string]: unknown };

/** A keydown stand-in that records `preventDefault`. */
function ev(init: Ev) {
  const e = {
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    defaultPrevented: false,
    target: { tagName: 'DIV' },
    ...init,
    preventDefault() {
      e.defaultPrevented = true;
    },
  };
  return e as unknown as KeyboardEvent;
}

const run = (map: Parameters<typeof dispatchKey>[0], init: Ev) => {
  const e = ev(init);
  return { hit: dispatchKey(map, e), prevented: e.defaultPrevented };
};

test('a bound key runs its handler and takes the default', () => {
  let n = 0;
  expect(run({ j: () => void n++ }, { key: 'j' })).toEqual({ hit: true, prevented: true });
  expect(n).toBe(1);
});

test('keys are exact: r is not R, and an unbound key does nothing', () => {
  let n = 0;
  const map = { r: () => void n++ };
  expect(run(map, { key: 'R' }).hit).toBe(false);
  expect(run(map, { key: 'q' }).hit).toBe(false);
  expect(n).toBe(0);
});

test('a handler that returns false leaves the browser default alone', () => {
  expect(run({ ArrowDown: () => false }, { key: 'ArrowDown' })).toEqual({
    hit: true,
    prevented: false,
  });
});

test('typing in a field is left alone, in every kind of field', () => {
  for (const target of [
    { tagName: 'INPUT' },
    { tagName: 'TEXTAREA' },
    { tagName: 'SELECT' },
    { tagName: 'DIV', isContentEditable: true },
  ]) {
    expect(run({ j: () => {} }, { key: 'j', target }).hit).toBe(false);
  }
});

test('Ctrl, Meta and Alt pass a plain binding by', () => {
  const map = { z: () => {}, r: () => {} };
  expect(run(map, { key: 'z', metaKey: true }).hit).toBe(false);
  expect(run(map, { key: 'z', ctrlKey: true }).hit).toBe(false);
  expect(run(map, { key: 'r', altKey: true }).hit).toBe(false);
});

test('a binding that asks for a modifier needs exactly it', () => {
  const map = { 'mod+z': () => {} };
  expect(run(map, { key: 'z', metaKey: true }).hit).toBe(true);
  expect(run(map, { key: 'z', ctrlKey: true }).hit).toBe(true);
  expect(run(map, { key: 'z' }).hit).toBe(false);
  expect(run(map, { key: 'z', metaKey: true, altKey: true }).hit).toBe(false);
  expect(run({ 'alt+x': () => {} }, { key: 'x', altKey: true }).hit).toBe(true);
  expect(run({ 'ctrl+x': () => {} }, { key: 'x', metaKey: true }).hit).toBe(false);
});

test('Shift is not a modifier: ? and Escape work as written', () => {
  expect(run({ '?': () => {} }, { key: '?', shiftKey: true }).hit).toBe(true);
  expect(run({ Escape: () => {} }, { key: 'Escape' }).hit).toBe(true);
});

test('a key someone else already took is not taken twice', () => {
  expect(run({ j: () => {} }, { key: 'j', defaultPrevented: true }).hit).toBe(false);
});

test('Enter and Space belong to a focused button or link', () => {
  const onButton = { closest: (s: string) => (s.includes('button') ? {} : null) };
  const map = { Enter: () => {}, ' ': () => {}, v: () => {} };
  expect(run(map, { key: 'Enter', target: onButton }).hit).toBe(false);
  expect(run(map, { key: ' ', target: onButton }).hit).toBe(false);
  expect(run(map, { key: 'v', target: onButton }).hit).toBe(true); // letters are not stolen
  expect(run(map, { key: 'Enter' }).hit).toBe(true);
});

test('parseBinding reads prefixes and leaves the key whole', () => {
  expect(parseBinding('j')).toMatchObject({ key: 'j', mod: false });
  expect(parseBinding('mod+z')).toMatchObject({ key: 'z', mod: true });
  expect(parseBinding('ctrl+alt+x')).toMatchObject({ key: 'x', ctrl: true, alt: true });
  expect(parseBinding('+')).toMatchObject({ key: '+' });
  expect(
    matches(parseBinding('+'), { key: '+', ctrlKey: false, metaKey: false, altKey: false })
  ).toBe(true);
});

test('the action listens on window, swaps its map on update, and lets go on destroy', () => {
  const listeners = new Set<(e: KeyboardEvent) => void>();
  const g = globalThis as unknown as { window?: unknown };
  const before = g.window;
  g.window = {
    addEventListener: (_t: string, fn: (e: KeyboardEvent) => void) => listeners.add(fn),
    removeEventListener: (_t: string, fn: (e: KeyboardEvent) => void) => listeners.delete(fn),
  };
  try {
    const calls: string[] = [];
    const action = keys({} as HTMLElement, { j: () => void calls.push('a') });
    expect(listeners.size).toBe(1);
    const fire = (key: string) => [...listeners].forEach((fn) => fn(ev({ key })));

    fire('j');
    action.update({ j: () => void calls.push('b') });
    fire('j');
    expect(calls).toEqual(['a', 'b']);
    expect(listeners.size).toBe(1); // update adds no second listener

    action.destroy();
    expect(listeners.size).toBe(0);
    fire('j');
    expect(calls).toEqual(['a', 'b']);
  } finally {
    g.window = before;
  }
});
