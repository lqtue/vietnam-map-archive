/**
 * Diacritic folding, shared by every place that has to match a Vietnamese or
 * French name typed without its accents.
 *
 * Lived in `$lib/server/gallica.ts` until 2026-09-04, which meant no component
 * could use it — `$lib/server` is import-guarded — and the contribute map
 * picker matched raw substrings instead, so "sai gon" found nothing and "hue"
 * missed "Huế". Postgres folds the same way for label search (`label_key`,
 * migration 065); this is the client's copy of that rule.
 */

/**
 * Letters that are one character but two sounds. NFD does not decompose them —
 * they are not a base letter plus a mark — so they survive the strip below and
 * then die in the caller's `[^a-z0-9]` pass, which is how `Rue Schrœder` became
 * the key `rue schr der` and its place page a 404. Postgres's `unaccent`
 * expands all of these, and it is the side that decides what a row's key is.
 */
const LIGATURES: [RegExp, string][] = [
  [/œ/g, 'oe'],
  [/Œ/g, 'OE'],
  [/æ/g, 'ae'],
  [/Æ/g, 'AE'],
  [/ß/g, 'ss'],
];

/**
 * Strip diacritics the way a 1920s French typesetter would have: NFD-decompose
 * and drop the combining marks, then handle `đ` and the ligatures, which have no
 * decomposition.
 */
export function unaccent(s: string): string {
  let out = s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D');
  for (const [re, to] of LIGATURES) out = out.replace(re, to);
  return out;
}

/** `unaccent`, lowercased — the form a case-insensitive substring match wants. */
export function foldForSearch(s: string): string {
  return unaccent(s).toLowerCase();
}

/**
 * True when every whitespace-separated term in `query` appears in `haystack`,
 * both folded. All-terms rather than the whole string, so "saigon 1882"
 * narrows a list instead of matching nothing.
 */
export function matchesAllTerms(haystack: string, query: string): boolean {
  const q = foldForSearch(query).trim();
  if (!q) return true;
  const folded = foldForSearch(haystack);
  return q.split(/\s+/).every((term) => folded.includes(term));
}
