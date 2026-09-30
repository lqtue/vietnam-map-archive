/**
 * Role gate for `src/routes/api/**`.
 *
 * Replaces the 19 hand-rolled `getAdminClient` / `assertAdmin` copies. The
 * policy each route had before is preserved by its `roles` argument:
 * scout + search allow `admin | mod`, everything else is admin-only.
 */

import { error } from '@sveltejs/kit';
import type { Session, User } from '@supabase/supabase-js';
import { adminClient } from './supabaseAdmin';

export type Role = 'admin' | 'mod' | 'user';

/**
 * Resolve the signed-in user and their profile role.
 * Returns null when there is no valid session.
 */
async function resolve(
  locals: App.Locals
): Promise<{ user: User; role: Role; session: Session } | null> {
  const { session, user } = await locals.safeGetSession();
  if (!session || !user) return null;

  const { data: profile } = await adminClient()
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single();

  const raw = profile?.role;
  const role: Role = raw === 'admin' || raw === 'mod' ? raw : 'user';
  return { user, role, session };
}

async function hasStaffMfa(locals: App.Locals, session: Session): Promise<boolean> {
  const { data, error: mfaError } = await locals.supabase.auth.mfa.getAuthenticatorAssuranceLevel(
    session.access_token
  );
  return !mfaError && data.currentLevel === 'aal2';
}

/**
 * Gate a request on role. Throws 401 without a session, 403 when the role is
 * not in `roles`. Defaults to admin-only.
 */
export async function requireRole(
  locals: App.Locals,
  roles: Role[] = ['admin']
): Promise<{ user: User; role: Role }> {
  const resolved = await resolve(locals);
  if (!resolved) throw error(401, 'Unauthorized');
  if (!roles.includes(resolved.role)) throw error(403, 'Forbidden');
  if (
    (resolved.role === 'admin' || resolved.role === 'mod') &&
    !(await hasStaffMfa(locals, resolved.session))
  ) {
    throw error(403, 'Staff MFA required. Set it up on your profile.');
  }
  return { user: resolved.user, role: resolved.role };
}

/**
 * Non-throwing role lookup for routes that degrade instead of rejecting
 * (`/api/search` falls back to the public map set). Returns null when there is
 * no session, or when the lookup itself fails.
 */
export async function getRole(locals: App.Locals): Promise<Role | null> {
  try {
    const resolved = await resolve(locals);
    if (!resolved) return null;
    if (
      (resolved.role === 'admin' || resolved.role === 'mod') &&
      !(await hasStaffMfa(locals, resolved.session))
    )
      return 'user';
    return resolved.role;
  } catch {
    return null;
  }
}

/**
 * Any signed-in account. Open contribution means the gate is "is this a user",
 * not "is this staff" — the row's status is what keeps it out of public view
 * until someone reviews it.
 */
export async function requireUser(locals: App.Locals): Promise<{ user: User; role: Role }> {
  const resolved = await resolve(locals);
  if (!resolved) throw error(401, 'Sign in to contribute');
  return resolved;
}

/** Reserve an hourly slot atomically; a failed quota check must fail closed. */
export async function assertUnderRateLimit(
  table: 'footprints',
  userId: string,
  maxPerHour: number
): Promise<void> {
  const { data: allowed, error: err } = await adminClient().rpc('consume_contribution_quota', {
    p_user_id: userId,
    p_kind: table,
    p_limit: maxPerHour,
  });
  if (err) {
    console.error('[auth] rate-limit reservation failed:', err.message);
    throw error(503, 'Contribution quota unavailable');
  }
  if (!allowed) {
    throw error(429, `Rate limit: at most ${maxPerHour} ${table.replace(/_/g, ' ')} per hour`);
  }
}
