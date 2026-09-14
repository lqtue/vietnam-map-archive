/**
 * sitemap.xml — the crawl entry the server-rendered half of the site never had.
 *
 * `/catalog/[id]` and `/catalog/place/[name]` are both rendered without JavaScript so a
 * crawler can read them, but until Sept 2026 they linked only to *each other*:
 * the catalog listed maps as click handlers, not anchors, so there was no path
 * in from `/`. The catalog rows are anchors now; this is the other half, and it
 * covers the place pages, which nothing lists.
 *
 * Public route: it enumerates `public`/`featured` maps only, and `place_names`
 * has been published-only since migration 068.
 */
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { keyToSlug } from '$lib/core/utils/placeKey';
import { LOCALIZED_PATHS, withLocale } from '$lib/core/i18n';
import { SITE_ORIGIN } from '$lib/core/site';
import { posts } from '../(editorial)/blog/posts';

/**
 * Editorial pages worth indexing — `LOCALIZED_PATHS`, which is the same list
 * for the same reason: a page is worth indexing when it is a page rather than
 * a record, and those are exactly the ones translated into Vietnamese. The app
 * tools are behind `ssr = false` and appear in neither.
 *
 * Each is emitted twice, once per locale. Every other URL below is a single
 * document in its own language — a map's title, a place's spellings, a post's
 * prose — so a `/vi` twin of one would be the same page a second time.
 */
const STATIC_PATHS = LOCALIZED_PATHS;

/** Long enough to be worth generating, short enough to follow a publish. */
const CACHE_SECONDS = 3600;

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const GET: RequestHandler = async ({ setHeaders }) => {
  const supabase = adminClient();

  const [{ data: maps }, { data: places }, { data: series }] = await Promise.all([
    supabase
      .from('maps')
      .select('slug, updated_at')
      .in('status', ['public', 'featured'])
      .limit(5000),
    // The gazetteer is a view over an aggregate, so cap it rather than let a
    // crawler's request grow with the corpus.
    supabase
      .from('place_names')
      .select('name_key')
      .order('mentions', { ascending: false })
      .limit(5000),
    /* `map_series` runs its own visibility gate in SQL (mig 082), which is why
       reading it on the service client still returns only surveys a signed-out
       reader may see. The per-sheet pages underneath are NOT listed: the series
       page links to all 706 of them, and the ~200 for sheets nobody holds carry
       `noindex` — a sitemap entry for those would be asking for a page we have
       told the crawler to skip. */
    /* `survey_sheets` is null for a survey whose index was never imported (mig
       084's left join), and that page 404s deliberately — AMS L909 has three
       sheets and nobody has decided what the survey contains. A sitemap entry
       for it would be a crawl invitation to a 404. */
    supabase
      .from('map_series')
      .select('key')
      .gt('published_sheets', 0)
      .not('survey_sheets', 'is', null),
  ]);

  /* The pinned origin, not the request's: a preview deploy would otherwise
     publish a sitemap of its own `<hash>.vmabeta.pages.dev` URLs, which is the
     same competing-duplicate problem the canonical tags exist to close. */
  const entry = (path: string, lastmod?: string | null) =>
    `  <url><loc>${esc(new URL(path, SITE_ORIGIN).href)}</loc>${
      lastmod ? `<lastmod>${esc(lastmod.slice(0, 10))}</lastmod>` : ''
    }</url>`;

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...STATIC_PATHS.map((p) => entry(p)),
    ...STATIC_PATHS.map((p) => entry(withLocale(p))),
    ...posts.map((p) => entry(`/blog/${p.slug}`, p.date)),
    ...(maps ?? []).map((m) => entry(`/catalog/${m.slug}`, m.updated_at as string | null)),
    /* Listed here rather than in `LOCALIZED_PATHS`: the index is a page, but
       its prose is not translated, and a `/vi` twin with an hreflang pair
       would be the same document claiming to be two. */
    entry('/catalog/series'),
    ...(series ?? []).map((s) => entry(`/catalog/series/${s.key}`)),
    ...(places ?? [])
      .filter((p) => p.name_key)
      .map((p) => entry(`/catalog/place/${keyToSlug(p.name_key as string)}`)),
    '</urlset>',
  ].join('\n');

  setHeaders({
    'content-type': 'application/xml',
    'cache-control': `public, max-age=${CACHE_SECONDS}`,
  });
  return new Response(body);
};
