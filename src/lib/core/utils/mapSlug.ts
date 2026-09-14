/**
 * mapSlug.ts — how a sheet is addressed in a URL.
 *
 * `/catalog/787439c7-8015-496d-a458-df61b89a4391` was the address of every
 * sheet until migration 088. It is the thing a reader is asked to paste into a
 * message, and it says nothing about what is on the other end. `maps.slug` is
 * the readable half of that address: `/catalog/plan-de-la-ville-de-saigon-1799`.
 *
 * Postgres mints the slug (`map_slug_base` / `map_slug_mint`, migration 088) and
 * is the only side that does. There is deliberately **no client-side slugifier
 * here** to be the twin of it — the gazetteer key needs one because a label on
 * screen has to find its place page without a round trip, but nothing needs to
 * guess a sheet's address: every row that could link to one already carries the
 * slug the database minted.
 *
 * Both forms resolve, for good. A UUID link is 301'd to the slug rather than
 * refused, because those URLs are in messages and bookmarks that predate the
 * slug and cannot be recalled.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** True for a canonical UUID. The old address shape, still honoured. */
export const isUuid = (value: string): boolean => UUID_RE.test(value);

/** The least a caller has to know about a map to address it. */
export interface MapRef {
  id: string;
  slug?: string | null;
}

/**
 * The sheet's reference in a URL — its slug, falling back to the uuid.
 *
 * The fallback is not dead code. Several rows reach the UI carrying only a
 * `map_id` (a label hit, a footprint submission), and a uuid there is a working
 * link that 301s to the readable one, which is strictly better than no link.
 */
export const mapRef = (map: MapRef): string => map.slug || map.id;

/** The sheet's record page. */
export const mapHref = (map: MapRef): string => `/catalog/${mapRef(map)}`;

/** The sheet, open in the viewer. */
export const exploreHref = (map: MapRef): string => `/explore?map=${mapRef(map)}`;
