import { createServerClient } from '@supabase/ssr';
import { PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY } from '$env/static/public';
import { redirect, type Handle } from '@sveltejs/kit';
import type { Database } from '$lib/data/supabase/types';
import { LOCALE_COOKIE, isLocale, localeFromPath, stripLocale } from '$lib/core/i18n';
import { resolveScanMode } from '$lib/core/scanModes';
import { CANONICAL_HOST } from '$lib/core/site';

/** Retired route paths → their replacements (301, query string preserved). */
const LEGACY_REDIRECTS: Record<string, string> = {
  '/view': '/explore',
  '/annotate': '/explore?mode=studio',
  '/studio': '/explore?mode=studio',
  '/create': '/explore?mode=story',
  '/image': '/catalog',
  '/contribute/label': '/scan?mode=prepare',
  '/contribute/digitalize': '/scan?mode=prepare',
  '/contribute/trace': '/scan?mode=shapes',
  '/contribute/review': '/scan?mode=shapes&tab=validate',
  '/admin/bulk': '/admin?tab=bulk',
  '/admin/scout': '/admin?tab=scout',
  '/admin/status': '/admin?tab=status',
};

/**
 * The two that carry an id in the path rather than a fixed name. Both moved
 * under `/catalog` so the archive is one subtree instead of three siblings;
 * every share link and printed reference to the old path still has to land
 * somewhere real.
 */
const LEGACY_PREFIXES: [string, string][] = [
  ['/map/', '/catalog/'],
  ['/place/', '/catalog/place/'],
];

/** Some targets already carry a query, so an incoming one joins with `&`. */
function withSearch(target: string, search: string): string {
  if (!search) return target;
  return target + (target.includes('?') ? '&' + search.slice(1) : search);
}

/**
 * `/scan` stopped being a public address (Sept 2026).
 *
 * The read-only viewer it offered is `/catalog/[id]` now — the same tiles with
 * the sheet's title, date, places and a URL worth pasting — so a request that
 * names no mode, or names one this shell does not serve, is a reader looking
 * for the archive. `?map=` is the sheet they asked for and keeps its identity
 * across the move; anything that is neither a uuid nor a slug is dropped rather
 * than pasted into a path.
 *
 * **302, not 301.** The path is still live for the staff modes, and a permanent
 * redirect on `/scan` risks a cache that is careless about the query string
 * taking `/scan?mode=prepare` with it.
 */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * `maps.slug` as migration 088 mints it: lowercase, digits, single hyphens.
 * Matched rather than trusted, because whatever this accepts is pasted straight
 * into a redirect path, and `?map=` is a stranger's query string rather than
 * one of our own links.
 */
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const isMapRef = (value: string): boolean =>
  UUID_RE.test(value) || (value.length <= 100 && SLUG_RE.test(value));

function retiredScanTarget(url: URL): string | null {
  // `/vi/scan` is the same route (`src/hooks.ts` reroutes it), so it is the same
  // retirement — and the reader stays in the language they arrived in.
  const prefix = localeFromPath(url.pathname) ? '/vi' : '';
  if (stripLocale(url.pathname) !== '/scan') return null;
  if (resolveScanMode(url.searchParams.get('mode'))) return null;
  const mapId = url.searchParams.get('map');
  return mapId && isMapRef(mapId) ? `${prefix}/catalog/${mapId}` : `${prefix}/catalog`;
}

/**
 * Link-preview bots fetch a URL once, with no JS — so `/explore?map=`
 * (`ssr = false`, no per-sheet meta) unfurls as the bare site title and no
 * image. `/catalog/[id]` already builds the real og:title/description/image
 * for the same sheet, so a bot that asked for `/explore?map=<ref>` is sent
 * there instead. A human on the same URL is untouched — this only matches
 * known crawler user agents, and only `mode=browse` (or no mode), so Studio
 * and story deep links are left alone.
 */
const PREVIEW_BOT_RE =
  /facebookexternalhit|Facebot|Twitterbot|Slackbot|TelegramBot|WhatsApp|LinkedInBot|Discordbot|SkypeUriPreview|redditbot|Pinterest|vkShare|Viber/i;

function explorePreviewTarget(url: URL, userAgent: string | null): string | null {
  if (!userAgent || !PREVIEW_BOT_RE.test(userAgent)) return null;
  if (stripLocale(url.pathname) !== '/explore') return null;
  const mode = url.searchParams.get('mode');
  if (mode && mode !== 'browse') return null;
  const mapId = url.searchParams.get('map');
  if (!mapId || !isMapRef(mapId)) return null;
  const prefix = localeFromPath(url.pathname) ? '/vi' : '';
  return `${prefix}/catalog/${mapId}`;
}

function legacyTarget(pathname: string): string | null {
  const exact = LEGACY_REDIRECTS[pathname];
  if (exact) return exact;
  for (const [from, to] of LEGACY_PREFIXES) {
    if (pathname.startsWith(from)) return to + pathname.slice(from.length);
  }
  return null;
}

/**
 * The archive answers on one name. Cloudflare Pages also publishes the project
 * at `vmabeta.pages.dev`, which is a second address for the same site — two
 * URLs a crawler can index, and one of them says `beta` in front of a public
 * archive. Production hits there are sent to the real host, path and query
 * kept.
 *
 * Only the bare production host. A preview deploy is
 * `<hash>.vmabeta.pages.dev`, and those have to stay reachable to be any use,
 * so the match is exact rather than a suffix.
 */
const PAGES_DEV_HOST = 'vmabeta.pages.dev';

/**
 * Security headers for everything this Worker renders.
 *
 * The `_headers` file at the project root carries the same list, and is not
 * redundant: Cloudflare applies it only to files Pages serves directly — the
 * fonts and `/_app/*` — while `_routes.json` sends every HTML page through
 * this Worker instead. So `_headers` alone left exactly the pages that matter
 * for clickjacking bare, which is how the first deploy of it shipped looking
 * correct (the fonts carried the headers) while `/` carried nothing. Keep the
 * two lists in step; between them they cover the whole site.
 *
 * The CSP is Report-Only on purpose. /explore reaches several origins for
 * tiles and annotations, and an enforcing policy written before reading the
 * reports would break the map. Tighten `connect-src`/`img-src` to the hosts
 * that actually appear, then drop the `-Report-Only` suffix here and there.
 *
 * **Two directives must survive that tightening or /explore stops working
 * entirely**, and neither is about hosts, which is why reading the reports for
 * origins alone would miss them. `@allmaps/render` compiles its WebGL
 * transformer at runtime, so `script-src` needs `'unsafe-eval'`; it warps in a
 * worker built from a blob, so `worker-src blob:` (and `child-src blob:` for
 * older engines) has to be there too. Both show in the console as report-only
 * violations today — nothing is blocked, so the map works and the warnings
 * look like noise. They are the enforcement bill, itemised in advance.
 *
 * `X-Frame-Options: DENY` is safe: nothing in src/ renders an iframe, and the
 * Allmaps Editor is opened in a new tab rather than embedded.
 */
const SECURITY_HEADERS: Record<string, string> = {
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'Permissions-Policy': 'geolocation=(self), camera=(), microphone=(), payment=()',
  'Content-Security-Policy-Report-Only':
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data: blob: https:; connect-src 'self' https:; font-src 'self'; " +
    "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
};

export const handle: Handle = async ({ event, resolve }) => {
  if (event.url.hostname === PAGES_DEV_HOST) {
    const canonical = new URL(event.url);
    canonical.hostname = CANONICAL_HOST;
    throw redirect(301, canonical.toString());
  }

  const target = legacyTarget(event.url.pathname);
  if (target) throw redirect(301, withSearch(target, event.url.search));

  const scanTarget = retiredScanTarget(event.url);
  if (scanTarget) throw redirect(302, scanTarget);

  const previewTarget = explorePreviewTarget(event.url, event.request.headers.get('user-agent'));
  if (previewTarget) throw redirect(302, previewTarget);

  // Read before anything renders, so a server-rendered page is already in the
  // reader's language rather than flipping after hydration.
  //
  // The path wins over the cookie: `/vi/about` is an address, and an address
  // has to mean the same thing to every reader — including a crawler, which
  // sends no cookie and so saw nothing but English until the prefix existed.
  const cookieLocale = event.cookies.get(LOCALE_COOKIE);
  event.locals.locale =
    localeFromPath(event.url.pathname) ?? (isLocale(cookieLocale) ? cookieLocale : 'en');

  /**
   * Track whether the response has been resolved to prevent
   * Supabase from setting cookies after the response is sent.
   */
  let responseResolved = false;

  event.locals.supabase = createServerClient<Database>(
    PUBLIC_SUPABASE_URL,
    PUBLIC_SUPABASE_ANON_KEY,
    {
      cookies: {
        getAll: () => event.cookies.getAll(),
        setAll: (cookiesToSet) => {
          // Only set cookies if the response hasn't been resolved yet
          if (responseResolved) {
            return;
          }
          cookiesToSet.forEach(({ name, value, options }) => {
            event.cookies.set(name, value, { ...options, path: '/' });
          });
        },
      },
    }
  );

  /**
   * Safe session retrieval that validates with the Supabase Auth server.
   *
   * getSession() only checks if session cookies exist (unverified).
   * getUser() validates the session with Supabase's server (verified).
   *
   * We use both: getSession() for quick existence check, getUser() for security.
   */
  event.locals.safeGetSession = async () => {
    // Quick check: does a session cookie exist?
    const {
      data: { session },
    } = await event.locals.supabase.auth.getSession();
    if (!session) {
      return { session: null, user: null };
    }

    // Security check: validate the session with Supabase Auth server
    const {
      data: { user },
      error,
    } = await event.locals.supabase.auth.getUser();
    if (error) {
      // Session was invalid/tampered - reject it
      return { session: null, user: null };
    }

    return { session, user };
  };

  const response = await resolve(event, {
    filterSerializedResponseHeaders(name) {
      return name === 'content-range' || name === 'x-supabase-api-version';
    },
    // `<html lang>` in app.html is a placeholder the server fills in.
    transformPageChunk: ({ html }) => html.replace('%vma.lang%', event.locals.locale),
  });

  // Mark response as resolved to prevent late cookie setting
  responseResolved = true;

  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(name, value);
  }

  return response;
};
