import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { safeReturnPath } from '$lib/server/safeReturnPath';
import { adminClient } from '$lib/server/supabaseAdmin';

export const GET: RequestHandler = async ({ url, locals }) => {
  const code = url.searchParams.get('code');
  const next = url.searchParams.get('next') || '/';

  if (code) {
    await locals.supabase.auth.exchangeCodeForSession(code);
  }

  const { session, user } = await locals.safeGetSession();
  if (session && user) {
    const { data: profile } = await adminClient()
      .from('profiles')
      .select('role')
      .eq('id', user.id)
      .single();
    if (profile?.role === 'admin' || profile?.role === 'mod') {
      const { data: assurance } = await locals.supabase.auth.mfa.getAuthenticatorAssuranceLevel(
        session.access_token
      );
      if (assurance?.currentLevel !== 'aal2') throw redirect(303, '/profile');
    }
  }

  // Only allow paths on this origin, to prevent open redirect attacks
  const safePath = safeReturnPath(next, url.origin);

  redirect(303, safePath);
};
