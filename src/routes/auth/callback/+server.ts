import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { safeReturnPath } from '$lib/server/safeReturnPath';

export const GET: RequestHandler = async ({ url, locals }) => {
  const code = url.searchParams.get('code');
  const next = url.searchParams.get('next') || '/';

  if (code) {
    await locals.supabase.auth.exchangeCodeForSession(code);
  }

  // Only allow paths on this origin, to prevent open redirect attacks
  const safePath = safeReturnPath(next, url.origin);

  redirect(303, safePath);
};
