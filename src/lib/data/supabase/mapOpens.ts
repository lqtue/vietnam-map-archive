/**
 * Tally one row per map open (migration 049).
 *
 * This is the only way to learn which maps get looked at: Cloudflare Web
 * Analytics reports requestPath and has no query-string dimension, so
 * /explore's `?map=` is invisible to it.
 *
 * The server checks publication and hourly caps before writing. Fire-and-forget
 * by design — a dropped tally must never interrupt opening a map.
 */
export function recordMapOpen(mapId: string): void {
  void fetch(`/api/maps/${encodeURIComponent(mapId)}/open`, { method: 'POST' }).then((response) => {
    if (!response.ok) console.warn('recordMapOpen:', response.status);
  }).catch(() => {});
}
