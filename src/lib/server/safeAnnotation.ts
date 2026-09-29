import { PUBLIC_SUPABASE_URL } from '$env/static/public';

const MAX_ANNOTATION_BYTES = 2 * 1024 * 1024;
const storageOrigin = new URL(PUBLIC_SUPABASE_URL).origin;

/** Only the two locations that publish annotations for this archive. */
export function isAllowedAnnotationUrl(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return false;
    if (url.hostname === 'annotations.allmaps.org') {
      return /^\/images\/[a-f0-9]+$/i.test(url.pathname);
    }
    return (
      url.origin === storageOrigin &&
      /^\/storage\/v1\/object\/public\/annotations\/[a-zA-Z0-9/_-]+\.json$/.test(url.pathname)
    );
  } catch {
    return false;
  }
}

/** No redirects, bounded time and bytes: stored map metadata is not a fetch authority. */
export async function fetchAnnotationJson(value: string): Promise<unknown> {
  if (!isAllowedAnnotationUrl(value)) throw new Error('Annotation URL is not allowed');
  const response = await fetch(value, {
    redirect: 'error',
    cache: 'no-store',
    signal: AbortSignal.timeout(10_000),
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error(`Annotation fetch failed (${response.status})`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error('Annotation response has no body');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value: chunk } = await reader.read();
      if (done) break;
      size += chunk.byteLength;
      if (size > MAX_ANNOTATION_BYTES) throw new Error('Annotation is too large');
      chunks.push(chunk);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}
