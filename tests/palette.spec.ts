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
  DESTINATION_GROUPS,
  matchDestinations,
  DESTINATIONS,
} from '../src/lib/features/shared/paletteDestinations';
import {
  placeKey,
  placeCoreKey,
  keyToSlug,
  placeHrefFor,
  GAZETTEER_CATEGORIES,
  GENERIC_WORDS,
  CORE_KEY_MIN,
} from '../src/lib/core/utils/placeKey';
import { readFileSync } from 'node:fs';
import { letteringRole, letteringClass } from '../src/lib/core/utils/mapLettering';
import { isPaletteShortcut, isTypingTarget } from '../src/lib/core/utils/commandPalette';

// ── who is offered what ─────────────────────────────────────────────────────

test('a signed-out visitor is offered only public pages', () => {
  const hrefs = destinationsFor(null, false).map((d) => d.href);
  expect(hrefs).toContain('/catalog');
  expect(hrefs).toContain('/explore');
  expect(hrefs).toContain('/contribute');
  expect(hrefs).not.toContain('/profile');
  expect(hrefs).not.toContain('/scan?mode=shapes&tab=validate');
  expect(hrefs).not.toContain('/admin?tab=status');
});

test('each role adds the tier below it and nothing above', () => {
  const member = destinationsFor('user', true).map((d) => d.href);
  expect(member).toContain('/explore?mode=story');
  expect(member).toContain('/scan?mode=shapes');
  expect(member).not.toContain('/scan?mode=shapes&tab=validate');

  const mod = destinationsFor('mod', true).map((d) => d.href);
  expect(mod).toContain('/scan?mode=shapes&tab=validate');
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

test('/directory shows every page the palette would offer', () => {
  // The page renders group by group, so a destination whose group is not in
  // DESTINATION_GROUPS would vanish from the directory without any error.
  for (const d of DESTINATIONS) {
    expect(DESTINATION_GROUPS, d.href).toContain(d.group);
  }
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
  expect(first('ocr')).toBe('/scan?mode=text');
  expect(first('annotate')).toBe('/explore?mode=studio');
  expect(first('story')).toBe('/explore?mode=story');
  expect(first('allmaps')).toBe('/contribute/georef');
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
  // /place/[name] turns the slug back into the key by the same rules.
  const key = placeKey('Chợ Lớn');
  expect(keyToSlug(key)).toBe('cho-lon');
  expect(placeKey(keyToSlug(key).replace(/-/g, ' '))).toBe(key);
});

test('only the five gazetteer categories get a place link', () => {
  expect(placeHrefFor('Rue Catinat', 'street')).toBe('/catalog/place/rue-catinat');
  expect(placeHrefFor('Chợ Lớn', 'place')).toBe('/catalog/place/cho-lon');
  expect(placeHrefFor('Arroyo Chinois', 'hydrology')).toBe('/catalog/place/arroyo-chinois');
  // The loader 404s on a key under two characters, so don't offer the link.
  expect(placeHrefFor('A', 'place')).toBeNull();
  expect(placeHrefFor('...', 'place')).toBeNull();
  // Categories the view does not group.
  expect(placeHrefFor('Échelle 1:5000', 'legend')).toBeNull();
  expect(placeHrefFor('Plan de Saigon', 'title')).toBeNull();
});

// ── the gazetteer's identity key ────────────────────────────────────────────
//
// `placeCoreKey` decides what counts as one place, so a change here merges or
// splits pages and, with them, the per-name lookups `press.ts` bills to Gallica
// and the NLV. Measured on the corpus when it went in: 2554 entries to 1796.

test('the generic word in front of a name is not part of the name', () => {
  // The screenshot case: three spellings, one village.
  const khanhHoi = ['Khánh Hội', 'Village de Khanh-Hoi', 'Vge de Khánh Hồi'].map(placeCoreKey);
  expect(new Set(khanhHoi).size).toBe(1);
  expect(khanhHoi[0]).toBe('khanh hoi');

  // A street written six ways across forty years is one street. This is what
  // `Boul.d` / `Bould.` / `Bd` / `R.` cost before: six gazetteer pages, and six
  // SRU calls to ask the French press about one boulevard.
  const charner = ['Boulevard Charner', 'Bd Charner', 'Bould. Charner', 'Charner'].map(
    placeCoreKey
  );
  expect(new Set(charner).size).toBe(1);

  // Vietnamese generics too, since the same feature is written both ways.
  expect(placeCoreKey('Đường Bình Tây')).toBe(placeCoreKey('Rue de Binh Tay'));
  expect(placeCoreKey('Rạch Bến Nghé')).toBe(placeCoreKey('Arroyo de Ben Nghe'));

  // A trailing article is not a name either.
  expect(placeCoreKey('Rue de la Grandière')).toBe(placeCoreKey('Rue Grandière'));
});

test('a core too short to be a name keeps its generic word', () => {
  // Vietnamese names are short syllables, so the generic word is a much bigger
  // fraction of them. Without the floor "Chợ Lớn" strips to "lon" and collects
  // every other name ending in Lớn — the merge that would be hardest to notice,
  // because a gazetteer page that is wrong still renders.
  expect(placeCoreKey('Chợ Lớn')).toBe('cho lon');
  expect(placeCoreKey('Rạch Bà')).toBe('rach ba');
  expect(placeCoreKey('Rue Cây')).toBe('rue cay');
  // Exactly at the floor it strips.
  expect('cong'.length).toBe(CORE_KEY_MIN);
  expect(placeCoreKey('Rạch Công')).toBe('cong');
});

test('a place cannot be stripped down to nothing', () => {
  // Every token is generic. The regex must not consume the whole key and leave
  // a row whose identity is the empty string, which would swallow the others.
  for (const all of ['Rue', 'Quai de la', 'Đường', 'de la']) {
    expect(placeCoreKey(all).length).toBeGreaterThan(0);
  }
});

test('the generic word list is the same one Postgres strips', () => {
  // The list exists twice — here and in `place_generic_words()` (migration 081).
  // A JS-only assertion would pass happily while the SQL drifted, and the
  // symptom is not an error: it is a place page that quietly stops merging, or
  // starts merging two streets that are not one. So read the migration.
  const sql = readFileSync('supabase/migrations/081_place_core_key.sql', 'utf8');
  const fnBody = sql.slice(
    sql.indexOf('place_generic_words()'),
    sql.indexOf('create or replace function public.place_core_key')
  );
  // Postgres concatenates adjacent string literals across newlines; JS uses `+`.
  const words = (s: string) => (s.match(/'([a-z|]+)'/g) ?? []).map((m) => m.slice(1, -1)).join('');
  expect(words(fnBody)).toBe(GENERIC_WORDS);
  // And the floor, which is the other half of the rule.
  expect(sql).toContain(`length(core) >= ${CORE_KEY_MIN}`);
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

test('a label is lettered the way its sheet letters it', () => {
  // The two marked cases, and the unmarked one that must stay unmarked.
  expect(letteringRole('hydrology')).toBe('hydronym');
  expect(letteringRole('place')).toBe('area');
  for (const c of ['street', 'building', 'institution', 'legend', 'title', 'other'])
    expect(letteringRole(c)).toBe('roman');
  expect(letteringRole(null)).toBe('roman');
  expect(letteringRole(undefined)).toBe('roman');

  // Roman emits no class at all — an empty rule is an invitation to fill it.
  expect(letteringClass('hydrology')).toBe('lettering-hydronym');
  expect(letteringClass('place')).toBe('lettering-area');
  expect(letteringClass('street')).toBe('');
  expect(letteringClass(null)).toBe('');

  // Every gazetteer category resolves to a role, so no label falls through
  // with an undefined class in the markup.
  for (const c of GAZETTEER_CATEGORIES) expect(typeof letteringClass(c)).toBe('string');
});
