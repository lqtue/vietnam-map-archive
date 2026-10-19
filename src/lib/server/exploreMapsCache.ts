import type { exploreMapsParameters } from './exploreMaps';

type Args = ReturnType<typeof exploreMapsParameters>;
type Cache = <T>(
  platform: unknown,
  key: string,
  load: () => Promise<T>,
  options: { ttl: number }
) => Promise<T>;

/** Cache anonymous first-page summaries only; role-sensitive and spatial requests bypass. */
export function cachedExploreMaps<T>(
  platform: unknown,
  anonymous: boolean,
  args: Args,
  load: () => Promise<T>,
  cache: Cache
): Promise<T> {
  if (
    !anonymous ||
    args.p_staff ||
    args.p_ids !== null ||
    args.p_point !== null ||
    args.p_cursor !== null
  )
    return load();
  const filters = Object.fromEntries(
    Object.keys(args.p_filters)
      .sort()
      .filter((key) => args.p_filters[key].length)
      .map((key) => [
        key,
        key === 'year' || key === 'kind'
          ? args.p_filters[key]
          : [...new Set(args.p_filters[key])].sort(),
      ])
  );
  // cached() adds the deployment version. Geography definitions belong to that version.
  const key = `explore-maps-v1/${encodeURIComponent(
    JSON.stringify({
      query: args.p_query,
      filters,
      limit: args.p_limit,
      sources: args.p_sources,
    })
  )}`;
  if (key.length > 4096) return load();
  return cache(platform, key, load, { ttl: 300 });
}
