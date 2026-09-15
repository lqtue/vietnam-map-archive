/**
 * Where an OAuth round-trip is allowed to land.
 *
 * `?next=` arrives from the address bar, so it is attacker-controlled and the
 * only thing standing between it and `redirect(303, …)`. The old guard was
 * `next.startsWith('/') && !next.startsWith('//')`, which reads as "relative,
 * and not protocol-relative" and is neither: browsers normalise a backslash to
 * a forward slash in the authority position, so `/\evil.com` passes that test
 * and resolves to `https://evil.com`. The sign-in page then hands a visitor who
 * did nothing wrong to someone else's site, with the archive as the referrer.
 *
 * Resolving the candidate against our own origin and demanding the origin come
 * back unchanged is the check that actually answers the question asked. The
 * literal-shape test in front of it is not redundant: it rejects the spellings
 * that resolve to the right origin while still being something other than a
 * path on this site.
 */

/** The candidate if it is a path on `origin`, otherwise `/`. */
export function safeReturnPath(next: string, origin: string): string {
  // One leading slash, and no backslash anywhere: `//host`, `/\host` and a
  // bare `https://host` are all out before any parsing happens.
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) return '/';

  try {
    const resolved = new URL(next, origin);
    if (resolved.origin !== new URL(origin).origin) return '/';
    return resolved.pathname + resolved.search + resolved.hash;
  } catch {
    return '/';
  }
}
