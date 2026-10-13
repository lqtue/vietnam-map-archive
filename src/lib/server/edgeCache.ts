/**
 * Cache one JSON-serialisable value in the Workers Cache API.
 *
 * For data that is identical for every visitor and changes rarely, whose source
 * is a database a continent away (Supabase in Sydney, the edge in Singapore).
 * Never put anything per-user through this: the key is the only thing that
 * tells two readers apart, and `cached` takes no cookie, role or session.
 *
 * The Cache API is per data centre, not global: each colo warms on its own first
 * request, then serves for `ttl` seconds. With no cache (dev, tests, a
 * non-Cloudflare run) it simply calls `load`.
 */

import { version } from '$app/environment';

/** The three Cache methods used here; the full type lives in an uninstalled package. */
interface EdgeCache {
  match(key: string): Promise<Response | undefined>;
  put(key: string, res: Response): Promise<void>;
}

interface EdgePlatform {
  caches?: { default?: EdgeCache };
  ctx?: { waitUntil(p: Promise<unknown>): void };
}

/**
 * Return the cached value for `key`, or run `load` and cache what it returns.
 *
 * - `load` throwing is never cached; the error reaches the caller.
 * - `ok` guards the quieter failure: the data layer here logs a failed query and
 *   returns 0 or `[]`. Pass a check that is false for such a result, or an
 *   outage would be served for the whole TTL.
 */
// ponytail: a fixed TTL, so a publish shows for up to 5 minutes (`ttl`) on a warm
// colo. Upgrade: purge the key (caches.default.delete) from the publish path.
export async function cached<T>(
  platform: unknown,
  key: string,
  load: () => Promise<T>,
  { ttl = 300, ok = () => true }: { ttl?: number; ok?: (value: T) => boolean } = {}
): Promise<T> {
  const p = platform as EdgePlatform | undefined;
  const cache = p?.caches?.default;
  if (!cache) return load();

  // The build version in the key: a deploy starts cold, so new code never reads
  // a value shaped by the old code.
  const url = `https://cache.internal/${version}/${key}`;
  try {
    const hit = await cache.match(url);
    if (hit) return (await hit.json()) as T;
  } catch (err) {
    console.error('edgeCache read:', err);
  }

  const value = await load();
  if (ok(value)) {
    const put = cache
      .put(
        url,
        new Response(JSON.stringify(value), {
          headers: { 'content-type': 'application/json', 'cache-control': `max-age=${ttl}` },
        })
      )
      .catch((err) => console.error('edgeCache write:', err));
    if (p?.ctx) p.ctx.waitUntil(put);
    else await put;
  }
  return value;
}
