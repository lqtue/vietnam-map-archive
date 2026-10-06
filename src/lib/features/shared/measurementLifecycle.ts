import type { MeasurementActor } from '$lib/data/measurement';

/** Keep role lookup failures and auth transitions out of the audience reports. */
export function resolveMeasurementActor(
  authReady: boolean,
  signedIn: boolean,
  role: string | null
): MeasurementActor {
  if (!authReady) return 'unknown';
  if (!signedIn) return 'guest';
  if (role === 'admin' || role === 'mod') return 'staff';
  if (role === 'user') return 'reader';
  return 'unknown';
}
