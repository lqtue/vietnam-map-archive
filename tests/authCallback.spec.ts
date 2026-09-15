/**
 * Where /auth/callback is allowed to send someone. No browser, no network.
 *
 * The failure this exists to catch is silent from the inside: every one of
 * these inputs made the old guard return the attacker's string, and the
 * redirect that followed looked exactly like a successful sign-in. `/\evil.com`
 * is the case that matters — it starts with a single `/`, so the "relative
 * path" test it replaced passed it, and the browser then read the backslash as
 * a slash and resolved it to https://evil.com.
 */
import { test, expect } from '@playwright/test';
import { safeReturnPath } from '../src/lib/server/safeReturnPath';

const ORIGIN = 'https://maparchive.vn';

test('a path on this site is returned unchanged', () => {
  expect(safeReturnPath('/explore', ORIGIN)).toBe('/explore');
});

test('a query string survives the round trip', () => {
  expect(safeReturnPath('/catalog/x?y=1', ORIGIN)).toBe('/catalog/x?y=1');
});

test('every off-site spelling falls back to the root', () => {
  for (const hostile of ['//evil.com', '/\\evil.com', 'https://evil.com', '']) {
    expect(safeReturnPath(hostile, ORIGIN)).toBe('/');
  }
});
