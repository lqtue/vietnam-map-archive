import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';

/**
 * Guard, and the validated user for the page to render.
 *
 * This used to `return { session }` — the raw session straight out of
 * `getSession()`, whose `.user` read during serialisation is what logged
 * "could be insecure". Returning `user` instead is both safe and better typed:
 * the redirect above means it cannot be null here, so the page needs no
 * second null check for something the guard already settled.
 */
export const load: PageServerLoad = async ({ locals }) => {
  const { session, user } = await locals.safeGetSession();
  if (!session || !user) throw redirect(303, '/login');
  const { data: profile } = await adminClient()
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single();
  return {
    user,
    role: profile?.role === 'admin' || profile?.role === 'mod' ? profile.role : 'user',
  };
};
