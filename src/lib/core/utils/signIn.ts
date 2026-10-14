import type { SupabaseClient } from '@supabase/supabase-js';

/**
 * Google OAuth, returning to `next` (a path on this site) afterwards.
 *
 * `/auth/callback` reads `?next=` and runs it through `safeReturnPath`, so a bad
 * value lands on `/`; this only has to carry it there, URL-encoded.
 */
export async function signInWithGoogle(supabase: SupabaseClient, next?: string | null) {
  const callback = new URL('/auth/callback', window.location.origin);
  if (next && next.startsWith('/')) callback.searchParams.set('next', next);
  return supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: callback.toString() },
  });
}
