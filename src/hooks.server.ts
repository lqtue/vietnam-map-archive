import { createServerClient } from '@supabase/ssr';
import { PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY } from '$env/static/public';
import { redirect, type Handle } from '@sveltejs/kit';
import type { Database } from '$lib/data/supabase/types';
import { LOCALE_COOKIE, isLocale, localeFromPath } from '$lib/core/i18n';
import { CANONICAL_HOST } from '$lib/core/site';

/** Retired route paths → their replacements (301, query string preserved). */
const LEGACY_REDIRECTS: Record<string, string> = {
  '/view': '/explore',
  '/annotate': '/explore?mode=studio',
  '/studio': '/explore?mode=studio',
  '/create': '/explore?mode=story',
  '/image': '/scan',
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
