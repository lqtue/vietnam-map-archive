/**
 * Pure checks for the command palette's two pieces of real logic: which pages
 * a visitor is offered, and the gazetteer key a label resolves to. No browser,
 * no network — they ride the Playwright runner because it is already installed.
 *
 * The place-key checks matter most: the key is computed twice, once in
 * Postgres (`place_key`, migration 067) and once here, and a link built from a
 * key that disagrees with the view lands on a 404.
 */
import { test, expect } from '@playwright/test';
import {
  destinationsFor,
  matchDestinations,
  DESTINATIONS,
} from '../src/lib/features/shared/paletteDestinations';
import { placeKey, keyToSlug, placeHrefFor } from '../src/lib/core/utils/placeKey';
import { isPaletteShortcut, isTypingTarget } from '../src/lib/core/utils/commandPalette';

// ── who is offered what ─────────────────────────────────────────────────────

test('a signed-out visitor is offered only public pages', () => {
  const hrefs = destinationsFor(null, false).map((d) => d.href);
  expect(hrefs).toContain('/archive');
  expect(hrefs).toContain('/explore');
  expect(hrefs).toContain('/contribute');
  expect(hrefs).not.toContain('/profile');
  expect(hrefs).not.toContain('/scan?mode=review');
  expect(hrefs).not.toContain('/admin?tab=status');
});

test('each role adds the tier below it and nothing above', () => {
  const member = destinationsFor('user', true).map((d) => d.href);
  expect(member).toContain('/explore?mode=story');
  expect(member).toContain('/scan?mode=trace');
  expect(member).not.toContain('/scan?mode=review');

  const mod = destinationsFor('mod', true).map((d) => d.href);
  expect(mod).toContain('/scan?mode=review');
  expect(mod).toContain('/admin?tab=status');
  expect(mod).not.toContain('/admin?tab=bulk');

  const admin = destinationsFor('admin', true).map((d) => d.href);
  expect(admin).toHaveLength(DESTINATIONS.length);
});

test('a role claim without a session grants nothing', () => {
  // The store is set from the session; belt and braces if it ever lags behind.
  expect(destinationsFor('admin', true).length).toBeGreaterThan(
    destinationsFor(null, false).length
  );
});

// ── ranking ─────────────────────────────────────────────────────────────────

test('a label prefix beats a keyword match', () => {
  const all = destinationsFor('admin', true);
  const hits = matchDestinations(all, 'map');
  // "Map viewer" starts with it; "Bulk upload" only mentions maps in keywords.
  expect(hits[0].href).toBe('/explore');
});

test('the words people actually type reach the right tool', () => {
  const all = destinationsFor('admin', true);
  const first = (q: string) => matchDestinations(all, q)[0]?.href;
  expect(first('ocr')).toBe('/scan?mode=triage');
  expect(first('annotate')).toBe('/explore?mode=annotate');
  expect(first('story')).toBe('/explore?mode=story');
  expect(first('allmaps')).toBe('/contribute#georef');
  expect(first('tokens')).toBe('/screens');
});

test('an empty query lists pages rather than nothing', () => {
  expect(matchDestinations(destinationsFor(null, false), '').length).toBeGreaterThan(0);
});

test('a query that matches nothing returns nothing', () => {
  expect(matchDestinations(destinationsFor(null, false), 'zzzzz')).toEqual([]);
});

// ── the gazetteer key ───────────────────────────────────────────────────────

test('placeKey folds accents and collapses punctuation, like place_key() does', () => {
  expect(placeKey('Chợ Lớn')).toBe('cho lon');
  expect(placeKey('RIVIÈRE DE SAIGON')).toBe('riviere de saigon');
  expect(placeKey('Rue Catinat')).toBe('rue catinat');
  // Every run of non-alphanumerics becomes exactly one space.
  expect(placeKey('Boulevard  Charner,')).toBe('boulevard charner');
  expect(placeKey('Arroyo de l’Avalanche')).toBe('arroyo de l avalanche');
  expect(placeKey('Gia Định')).toBe('gia dinh');
});

test('a key round-trips through the slug the route parses', () => {
  // /archive/place/[name] turns the slug back into the key by the same rules.
  const key = placeKey('Chợ Lớn');
  expect(keyToSlug(key)).toBe('cho-lon');
  expect(placeKey(keyToSlug(key).replace(/-/g, ' '))).toBe(key);
});

test('only the five gazetteer categories get a place link', () => {
  expect(placeHrefFor('Rue Catinat', 'street')).toBe('/archive/place/rue-catinat');
  expect(placeHrefFor('Chợ Lớn', 'place')).toBe('/archive/place/cho-lon');
  expect(placeHrefFor('Arroyo Chinois', 'hydrology')).toBe('/archive/place/arroyo-chinois');
  // The loader 404s on a key under two characters, so don't offer the link.
  expect(placeHrefFor('A', 'place')).toBeNull();
  expect(placeHrefFor('...', 'place')).toBeNull();
  // Categories the view does not group.
  expect(placeHrefFor('Échelle 1:5000', 'legend')).toBeNull();
  expect(placeHrefFor('Plan de Saigon', 'title')).toBeNull();
});

test('a folded key carries nothing PostgREST reads as syntax', () => {
  // /api/search matches the gazetteer with `ilike('name_key', '%' + placeKey(q) + '%')`.
  // It used to pass the raw query into `.or()`, which splits on commas: typing
  // "rue catinat, saigon" became three malformed conditions and 500'd the whole
  // search — maps and labels with it. Folding is now the escaping, so nothing
  // that ends up in the pattern may be PostgREST punctuation or an ilike wildcard.
  for (const q of [
    'rue catinat, saigon',
    'Chợ Lớn (Cholon)',
    'boulevard "charner"',
    "quai de l'arroyo",
    '100% de la ville',
    'a_b\\c',
    'rue.catinat',
  ]) {
    expect(placeKey(q)).toMatch(/^[a-z0-9 ]*$/);
  }
});

test('places and labels agree on one spelling of a name', () => {
  // search_labels unaccents its query in Postgres; the place lookup folds here.
  // Every way a reader might type the street has to land on the same key, or a
  // label hit shows with no place page behind it.
  const want = 'khanh hoi';
  for (const typed of ['Khánh Hội', 'khanh-hoi', 'KHANH  HOI', 'Khánh-Hội']) {
    expect(placeKey(typed)).toBe(want);
  }
});

// ── the shortcut ────────────────────────────────────────────────────────────

const key = (init: Partial<KeyboardEvent>) => init as KeyboardEvent;

test('⌘K and Ctrl+K open it; plain K does not', () => {
  expect(isPaletteShortcut(key({ key: 'k', metaKey: true }))).toBe(true);
  expect(isPaletteShortcut(key({ key: 'K', ctrlKey: true }))).toBe(true);
  expect(isPaletteShortcut(key({ key: 'k' }))).toBe(false);
  // ⌥⌘K is a different binding in several browsers; leave it alone.
  expect(isPaletteShortcut(key({ key: 'k', metaKey: true, altKey: true }))).toBe(false);
});

test('"/" is left alone while someone is typing', () => {
  expect(isTypingTarget({ tagName: 'INPUT' } as unknown as EventTarget)).toBe(true);
  expect(isTypingTarget({ tagName: 'TEXTAREA' } as unknown as EventTarget)).toBe(true);
  expect(isTypingTarget({ tagName: 'SELECT' } as unknown as EventTarget)).toBe(true);
  expect(
    isTypingTarget({ tagName: 'DIV', isContentEditable: true } as unknown as EventTarget)
  ).toBe(true);
  expect(isTypingTarget({ tagName: 'DIV' } as unknown as EventTarget)).toBe(false);
  expect(isTypingTarget(null)).toBe(false);
});
