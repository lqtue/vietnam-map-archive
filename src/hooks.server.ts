import { createServerClient } from '@supabase/ssr';
import { PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY } from '$env/static/public';
import { redirect, type Handle } from '@sveltejs/kit';
import type { Database } from '$lib/data/supabase/types';

/**
 * Retired route paths → their replacements (301, query string preserved).
 *
 * The Sept 2026 route merge collapsed fifteen surfaces onto six, so most of
 * this table dates from then. Every share link, bookmark and printed reference
 * to an old path still has to land somewhere real.
 */
const LEGACY_REDIRECTS: Record<string, string> = {
  '/view': '/explore',
  '/annotate': '/explore?mode=annotate',
  '/studio': '/explore?mode=annotate',
  '/create': '/explore?mode=story',
  '/catalog': '/archive',
  '/image': '/scan',
  '/contribute/label': '/scan?mode=triage',
  '/contribute/digitalize': '/scan?mode=triage',
  '/contribute/trace': '/scan?mode=trace',
  '/contribute/review': '/scan?mode=review',
  '/contribute/georef': '/contribute',
  '/admin/bulk': '/admin?tab=bulk',
  '/admin/scout': '/admin?tab=scout',
  '/admin/status': '/admin?tab=status',
};

/** The two that carry an id in the path rather than a fixed name. */
const LEGACY_PREFIXES: [string, string][] = [
  ['/map/', '/archive/'],
  ['/place/', '/archive/place/'],
];

/**
 * Half these targets already carry a `?mode=`, so the incoming query string
 * has to join with `&`, not a second `?`.
 */
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

export const handle: Handle = async ({ event, resolve }) => {
  const target = legacyTarget(event.url.pathname);
  if (target) throw redirect(301, withSearch(target, event.url.search));

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
  });

  // Mark response as resolved to prevent late cookie setting
  responseResolved = true;

  return response;
};
