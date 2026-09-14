/**
 * Supabase Storage upserts, via the REST API.
 *
 * The JS client is unreliable for text/JSON payloads in server runtimes, so
 * both the annotation-GCP editor and the R2 mirror POST directly with
 * `x-upsert: true`. This is the single copy of that request.
 */

import { error } from '@sveltejs/kit';
import { PUBLIC_SUPABASE_URL } from '$env/static/public';
import { SUPABASE_SERVICE_KEY } from '$env/static/private';

/**
 * Write `obj` as pretty-printed JSON to `bucket/path`, creating or overwriting.
 * Returns the public URL of the stored object. Throws 500 on failure.
 */
export async function uploadJson(bucket: string, path: string, obj: unknown): Promise<string> {
  const url = `${PUBLIC_SUPABASE_URL}/storage/v1/object/${bucket}/${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      // Both headers, and the `apikey` one is not optional. Since the project
      // moved to the new key format (`sb_secret_…`, not a JWT), Storage given
      // only a Bearer tries to parse it as one and answers 400 "Invalid
      // Compact JWS" — which surfaced as "Storage upload failed (400)" on
      // every mirror and every GCP save. supabase-js sends `apikey` itself,
      // which is why database writes never noticed. Harmless for a legacy JWT.
      apikey: SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
      'Content-Type': 'application/json',
      'x-upsert': 'true',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify(obj, null, 2),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => String(res.status));
    console.error('[storage] upload failed:', res.status, errText);
    throw error(500, `Storage upload failed (${res.status})`);
  }

  return `${PUBLIC_SUPABASE_URL}/storage/v1/object/public/${bucket}/${path}`;
}
