/**
 * placeKey.ts — the gazetteer key, computed the same way on both sides.
 *
 * Postgres builds it in `place_key()` (migration 067): unaccent, lowercase,
 * then every run of non-alphanumerics collapsed to one space. `/catalog/place/[name]`
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

/**
 * The generic words a place name is written in front of, already unaccented and
 * lowercased the way `placeKey` leaves them (`duong` is Đường, `rach` is Rạch).
 * Verbatim twin of Postgres's `place_generic_words()` (migration 081) — the two
 * are pinned against each other by `tests/palette.spec.ts`.
 */
export const GENERIC_WORDS =
  'rue|r|ruelle|boulevard|boul|bould|bd|blvd|avenue|av|ave|quai|quay|impasse|imp|' +
  'place|pl|chemin|ch|route|rte|passage|village|vge|vlge|hameau|marche|pont|canal|' +
  'arroyo|riviere|riv|fleuve|faubourg|duong|dg|pho|hem|rach|song|kenh|cho|ap|xom|' +
  'cau|ben|khu|phuong|quan|xa|thon|lang|de|du|des|d|le|la|les|l|au|aux';

/** The floor below which a stripped core is rejected. Twin of migration 081's `length(core) >= 4`. */
export const CORE_KEY_MIN = 4;

const LEADING_GENERIC = new RegExp(`^((${GENERIC_WORDS}) )+`);
const TRAILING_ARTICLE = / (de|du|des|d|le|la|les|l)$/;

/**
 * The gazetteer's identity key: `placeKey` with the generic word in front of the
 * name removed, so `Rue Catinat`, `R. Catinat` and `Catinat` are one place, and
 * `Khánh Hội`, `Village de Khanh-Hoi` and `Vge de Khánh Hồi` are one more.
 *
 * Client twin of `place_core_key()` (migration 081), including its four-character
 * floor: below that the full key is kept, or `Chợ Lớn` strips to `lon` and
 * collects every other name ending in Lớn.
 */
export function placeCoreKey(text: string): string {
  const key = placeKey(text);
  const core = key.replace(LEADING_GENERIC, '').replace(TRAILING_ARTICLE, '');
  return core.length >= CORE_KEY_MIN ? core : key;
}

/** Gazetteer `name_key` → the slug `/catalog/place/[name]` expects. */
export const keyToSlug = (key: string) => key.replace(/\s+/g, '-');

/**
 * `/catalog/place/<slug>` for a gazetteer key. The one-liner had four copies — here,
 * `paletteDestinations`, the share page and the place loader — which is three
 * places for the URL shape to drift away from the route that parses it.
 */
export const placeHref = (key: string) => `/catalog/place/${keyToSlug(key)}`;

/**
 * `/catalog/place/<slug>` for a label, or null when it cannot have a page — the
 * category is not one the gazetteer groups, or the key is too short for the
 * loader, which 404s under two characters.
 */
export function placeHrefFor(text: string, category: string): string | null {
  if (!GAZETTEER_CATEGORIES.includes(category)) return null;
  const key = placeKey(text);
  return key.length >= 2 ? placeHref(key) : null;
}
