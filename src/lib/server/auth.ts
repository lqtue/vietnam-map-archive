/**
 * Role gate for `src/routes/api/**`.
 *
 * Replaces the 19 hand-rolled `getAdminClient` / `assertAdmin` copies. The
 * policy each route had before is preserved by its `roles` argument:
 * scout + search allow `admin | mod`, everything else is admin-only.
 */

import { error } from '@sveltejs/kit';
import type { User } from '@supabase/supabase-js';
import { adminClient } from './supabaseAdmin';

export type Role = 'admin' | 'mod' | 'user';

/**
 * Resolve the signed-in user and their profile role.
 * Returns null when there is no valid session.
 */
async function resolve(locals: App.Locals): Promise<{ user: User; role: Role } | null> {
  const { session, user } = await locals.safeGetSession();
  if (!session || !user) return null;

  const { data: profile } = await adminClient()
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single();

  const raw = profile?.role;
  const role: Role = raw === 'admin' || raw === 'mod' ? raw : 'user';
  return { user, role };
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
  return resolved;
}

/**
 * Non-throwing role lookup for routes that degrade instead of rejecting
 * (`/api/search` falls back to the public map set). Returns null when there is
 * no session, or when the lookup itself fails.
 */
export async function getRole(locals: App.Locals): Promise<Role | null> {
  try {
    const resolved = await resolve(locals);
    return resolved?.role ?? null;
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

/**
 * Cheap abuse brake for open contribution: how many rows this user has already
 * created in `table` within the window.
 *
 * ponytail: counts the target table directly rather than keeping a separate
 * rate-limit store — the data needed is already there, and a counter table
 * would need its own writer, its own cleanup and its own migration. Trades
 * exactness under bursts for having no moving parts; swap it for a real
 * limiter if a single count query ever shows up in the slow log.
 */
export async function assertUnderRateLimit(
  table: 'footprints' | 'stories',
  userId: string,
  maxPerHour: number
): Promise<void> {
  const since = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  const { count, error: err } = await adminClient()
    .from(table)
    .select('id', { count: 'exact', head: true })
    .eq('user_id', userId)
    .gt('created_at', since);

  // A failed count must not become a closed door: log and let the write through.
  if (err) {
    console.error('[auth] rate-limit count failed:', err.message);
    return;
  }
  if ((count ?? 0) >= maxPerHour) {
    throw error(429, `Rate limit: at most ${maxPerHour} ${table.replace(/_/g, ' ')} per hour`);
  }
}
