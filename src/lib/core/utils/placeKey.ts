/**
 * placeKey.ts — the gazetteer key, computed the same way on both sides.
 *
 * Postgres builds it in `place_key()` (migration 067): unaccent, lowercase,
 * then every run of non-alphanumerics collapsed to one space. `/archive/place/[name]`
 * inverts the slug with the same rules. This is the client-side twin, so a
 * label on screen can link straight to its place page without a round trip.
 *
 * The folding itself is `foldForSearch`, the same rule the map picker and
 * Postgres's `label_key` use — this module only adds the collapse-and-trim on
 * top of it.
 */
import { foldForSearch } from './unaccent';

/** Categories the gazetteer is built from (migration 067). Others have no page. */
export const GAZETTEER_CATEGORIES = ['street', 'hydrology', 'place', 'building', 'institution'];

/** Label text → gazetteer `name_key`. Empty when nothing usable is left. */
export function placeKey(text: string): string {
  return foldForSearch(text)
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/** Gazetteer `name_key` → the slug `/archive/place/[name]` expects. */
export const keyToSlug = (key: string) => key.replace(/\s+/g, '-');

/**
 * `/archive/place/<slug>` for a gazetteer key. The one-liner had four copies — here,
 * `paletteDestinations`, the share page and the place loader — which is three
 * places for the URL shape to drift away from the route that parses it.
 */
export const placeHref = (key: string) => `/archive/place/${keyToSlug(key)}`;

/**
 * `/archive/place/<slug>` for a label, or null when it cannot have a page — the
 * category is not one the gazetteer groups, or the key is too short for the
 * loader, which 404s under two characters.
 */
export function placeHrefFor(text: string, category: string): string | null {
  if (!GAZETTEER_CATEGORIES.includes(category)) return null;
  const key = placeKey(text);
  return key.length >= 2 ? placeHref(key) : null;
}
