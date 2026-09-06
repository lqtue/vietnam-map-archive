/**
 * sitemap.xml — the crawl entry the server-rendered half of the site never had.
 *
 * `/archive/[id]` and `/archive/place/[name]` are both rendered without JavaScript so a
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
import { posts } from '../(editorial)/blog/posts';

/** Editorial pages worth indexing. The app tools are behind `ssr = false`. */
// No fragment entries: a crawler ignores them, and /contribute already covers
// the georeference queue that now lives in a section of that page.
const STATIC_PATHS = ['/', '/archive', '/about', '/blog', '/contribute'];

/** Long enough to be worth generating, short enough to follow a publish. */
const CACHE_SECONDS = 3600;

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const GET: RequestHandler = async ({ url, setHeaders }) => {
  const supabase = adminClient();

  const [{ data: maps }, { data: places }] = await Promise.all([
    supabase.from('maps').select('id, updated_at').in('status', ['public', 'featured']).limit(5000),
    // The gazetteer is a view over an aggregate, so cap it rather than let a
    // crawler's request grow with the corpus.
    supabase
      .from('place_names')
      .select('name_key')
      .order('mentions', { ascending: false })
      .limit(5000),
  ]);

  const entry = (path: string, lastmod?: string | null) =>
    `  <url><loc>${esc(new URL(path, url.origin).href)}</loc>${
      lastmod ? `<lastmod>${esc(lastmod.slice(0, 10))}</lastmod>` : ''
    }</url>`;

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...STATIC_PATHS.map((p) => entry(p)),
    ...posts.map((p) => entry(`/blog/${p.slug}`, p.date)),
    ...(maps ?? []).map((m) => entry(`/archive/${m.id}`, m.updated_at as string | null)),
    ...(places ?? [])
      .filter((p) => p.name_key)
      .map((p) => entry(`/archive/place/${keyToSlug(p.name_key as string)}`)),
    '</urlset>',
  ].join('\n');

  setHeaders({
    'content-type': 'application/xml',
    'cache-control': `public, max-age=${CACHE_SECONDS}`,
  });
  return new Response(body);
};
