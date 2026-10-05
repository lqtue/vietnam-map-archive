/**
 * localSearch.ts — search the catalog's maps in the browser.
 *
 * Every field the server's `search_vector` indexes is already in the list row, and the whole
 * public archive is one response, so a keystroke does not need a round trip. It also fixes what
 * the server's `simple` text-search config cannot: accents. `hue` finds `Huế`, `da nang` finds
 * `Đà Nẵng`.
 *
 * Rule: fold both sides (`foldForSearch`), split into words, and every query token must be the
 * start of some word — `192` finds 1920–1929, `hano` finds Hanoi, `1920s` folds to `192`. A query
 * shaped like a sheet number (`5929-3`) matches that column exactly, because its parts are also
 * years and house numbers.
 */
import { foldForSearch } from '$lib/core/utils/unaccent';
import type { Row } from './catalogFilters';

/** The row fields searched — what `search_vector` covers, under this response's own names. */
const FIELDS = [
  'name',
  'original_title',
  'creator',
  'dc_publisher',
  'holding_institution',
  'collection',
  'location',
  'shelfmark',
  'year_label',
  'year',
  'sheet_number',
] as const;

const words = (s: string) =>
  foldForSearch(s)
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);

/** The query as tokens; a decade written `1920s` is its prefix. */
export function queryTokens(q: string): string[] {
  return words(q).map((t) => (/^\d{3}0s$/.test(t) ? t.slice(0, 3) : t));
}

const index = new WeakMap<Row, string[]>();
function wordsOf(r: Row): string[] {
  let w = index.get(r);
  if (!w) {
    w = FIELDS.flatMap((f) => (r[f] == null ? [] : words(String(r[f]))));
    index.set(r, w);
  }
  return w;
}

/** True when the row answers the query; an empty query answers every row. */
export function matchesQuery(r: Row, q: string): boolean {
  const trimmed = q.trim();
  if (!trimmed) return true;
  if (/^\d{4}-\d$/.test(trimmed)) return r.sheet_number === trimmed;
  const tokens = queryTokens(trimmed);
  if (!tokens.length) return true;
  const w = wordsOf(r);
  return tokens.every((t) => w.some((x) => x.startsWith(t)));
}
