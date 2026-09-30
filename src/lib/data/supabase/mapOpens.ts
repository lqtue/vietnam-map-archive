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
  // A JSON body, not none: on Cloudflare a body-less POST still arrives with a
  // non-null `request.body`, so hooks.server.ts's empty-body exemption never
  // matches and the tally was refused with 415.
  void fetch(`/api/maps/${encodeURIComponent(mapId)}/open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  }).then((response) => {
    if (!response.ok) console.warn('recordMapOpen:', response.status);
  }).catch(() => {});
}
